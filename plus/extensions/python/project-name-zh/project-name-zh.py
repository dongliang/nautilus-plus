#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nautilus extension: show Chinese project names from .project.yaml.

For every folder whose `.project.yaml` has a top-level `name-zh` key, the
Chinese name is shown as a caption line right below the folder name in
icon view. The real folder name (and path) is never changed, and normal
renaming (F2) is unaffected — edit `.project.yaml` to change the Chinese
name.

The extension also drives the fork's grouped view: a folder whose
`.project.yaml` has `archived: true` (strictly the YAML boolean true) gets
the `group` extension attribute "已归档", which the fork's C sorters use to
partition the view — archived folders form a trailing "已归档" group with a
header, ungrouped items stay in front without one. Grouping is independent
of the switch below (it only controls the Chinese captions).

Folders can be archived and unarchived from the selection context menu
(multi-select supported): the action writes or removes `archived: true`
in each folder's `.project.yaml`, reusing the same comment-preserving
local update as the Chinese-name editor.

Archived folders can be hidden entirely (background context menu):
the fork's C layer filters out items carrying the archived group key,
so they vanish from icon view, list view (headers included) and search
results, as if they did not exist. The switch state lives in the fork's own
gsettings schema (org.gnome.NautilusPlus.preferences, default off = show),
which the C filter reads directly; it is deliberately not stored in
org.gnome.nautilus.preferences, whose file is owned by the distribution's
nautilus package and would be overwritten on upgrade. The hide menu item
only appears when running as the fork (nautilus-plus): the stock nautilus
has no filter hook, so the toggle would do nothing there.

A global on/off switch lives in the background context menu (right-click
empty space in a folder). Toggling takes effect immediately, and the menu
label flips to match within a moment. The switch state is stored in
~/.config/nautilus-project-zh/state (default: on).

Install:
    cp project-name-zh.py ~/.local/share/nautilus-python/extensions/
    nautilus -q        # restart nautilus
"""

import json
import os
import re
import stat
import sys
import tempfile
import traceback

import yaml

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Nautilus

CONFIG_DIR = os.path.expanduser('~/.config/nautilus-project-zh')
STATE_FILE = os.path.join(CONFIG_DIR, 'state')
CAPTIONS_BACKUP = os.path.join(CONFIG_DIR, 'captions-backup.json')

ICON_VIEW_SCHEMA = 'org.gnome.nautilus.icon-view'
# Fork-only settings live in the fork's own schema, never in
# org.gnome.nautilus.preferences: that schema is owned by the distribution's
# nautilus package, so a system upgrade replaces the file and drops fork-only
# keys -- and reading a missing key aborts the process. See plus/docs/pitfalls.md.
PLUS_SCHEMA = 'org.gnome.NautilusPlus.preferences'
HIDE_ARCHIVED_KEY = 'hide-archived'
CAPTIONS_KEY = 'captions'
ATTR = 'name-zh'
GROUP_ATTR = 'group'
ARCHIVED_KEY = 'archived'
ARCHIVED_LABEL = '已归档'
YAML_NAME = '.project.yaml'
YAML_MAX_SIZE = 1024 * 1024

_settings = Gio.Settings.new(ICON_VIEW_SCHEMA)


def _open_plus_settings():
    """The fork's settings object, or None when its schema is not installed.

    Must never raise: this module is also loaded by the stock nautilus, where
    a failed import would take the whole extension down with it. Without the
    schema the hide-archived feature simply stays unavailable.
    """
    try:
        source = Gio.SettingsSchemaSource.get_default()
        schema = source.lookup(PLUS_SCHEMA, True) if source is not None else None
        if schema is None or not schema.has_key(HIDE_ARCHIVED_KEY):
            print(f'project-name-zh: schema {PLUS_SCHEMA!r} is missing; '
                  'hide-archived stays disabled until nautilus-plus is '
                  'installed again.', file=sys.stderr)
            return None
        # new_full() takes the already-validated schema: a plain
        # Settings.new() would abort the process (g_error, not a
        # catchable exception) if the lookup ever came up empty.
        return Gio.Settings.new_full(schema, None, None)
    except Exception:
        traceback.print_exc()
        return None


_plus_settings = _open_plus_settings()

# folder_path -> (mtime, name_zh | None, archived: bool)
_yaml_cache = {}
# folders we ever showed a Chinese name for; the source of truth for
# clearing stale captions (yaml deleted / key removed / switch off)
_shown = set()
# folders we ever marked as grouped (archived); the source of truth for
# clearing the group attribute when it no longer applies
_grouped = set()
# (mtime, unused, raw text) — the state file is now multi-line key=value
_state_cache = (None, None, '')


# --- switch state ---------------------------------------------------------

def _read_state():
    """State file text, or '' when missing. Cached by mtime."""
    global _state_cache
    try:
        mtime = os.path.getmtime(STATE_FILE)
    except OSError:
        return ''
    if _state_cache[0] == mtime:
        return _state_cache[2]
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            text = f.read()
    except OSError:
        return ''
    _state_cache = (mtime, None, text)
    return text


def _write_state(text):
    global _state_cache
    os.makedirs(CONFIG_DIR, exist_ok=True)
    _atomic_write(STATE_FILE, text)
    try:
        _state_cache = (os.path.getmtime(STATE_FILE), None, text)
    except OSError:
        _state_cache = (None, None, '')


def _enabled():
    """Whether the Chinese names are shown. Defaults to on."""
    first_line = _read_state().splitlines()[0].strip() \
        if _read_state().splitlines() else ''
    # Missing file / legacy formats without a leading on|off default to on.
    return first_line != 'off'


def _set_enabled(on):
    lines = _read_state().splitlines()
    value = 'on' if on else 'off'
    if lines and lines[0].strip() in ('on', 'off'):
        lines[0] = value
    else:
        lines.insert(0, value)
    _write_state('\n'.join(lines) + '\n')


def _hide_archived():
    """Whether archived folders are hidden. Defaults to off (= show).

    The state lives in the fork's gsettings schema: the C filter reads the
    same key, so every window follows instantly. Without the schema (fork not
    installed) this degrades to "show" instead of raising.
    """
    if _plus_settings is None:
        return False
    return _plus_settings.get_boolean(HIDE_ARCHIVED_KEY)


def _set_hide_archived(hide):
    if _plus_settings is None:
        return
    _plus_settings.set_boolean(HIDE_ARCHIVED_KEY, hide)


def _atomic_write(path, text, mode=None):
    parent = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(prefix='.' + os.path.basename(path) + '.',
                               dir=parent)
    try:
        if mode is not None:
            os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --- .project.yaml --------------------------------------------------------

def _yaml_info(folder_path):
    """(name-zh, archived) from the folder's .project.yaml. Cached by mtime."""
    yaml_path = os.path.join(folder_path, YAML_NAME)
    try:
        mtime = os.path.getmtime(yaml_path)
    except OSError:
        _yaml_cache.pop(folder_path, None)
        return (None, False)
    hit = _yaml_cache.get(folder_path)
    if hit is not None and hit[0] == mtime:
        return (hit[1], hit[2])
    name = None
    archived = False
    try:
        if os.path.getsize(yaml_path) <= YAML_MAX_SIZE:
            with open(yaml_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                value = data.get('name-zh')
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                # Strict: only the YAML boolean true marks a folder archived.
                # (PyYAML is YAML 1.1, so yes/on also parse as True — the
                # .project.yaml convention is to write true/false only.)
                archived = data.get('archived') is True
    except (yaml.YAMLError, UnicodeDecodeError, OSError, ValueError):
        pass
    _yaml_cache[folder_path] = (mtime, name, archived)
    if len(_yaml_cache) > 1024:
        _yaml_cache.pop(next(iter(_yaml_cache)))
    return (name, archived)


def _yaml_scalar(value):
    if '\n' in value or '\r' in value:
        raise ValueError('中文名不能包含换行')
    lines = yaml.safe_dump(value, allow_unicode=True,
                           default_flow_style=True,
                           sort_keys=False).splitlines()
    if len(lines) == 2 and lines[1] == '...':
        scalar = lines[0]
    elif len(lines) == 1:
        scalar = lines[0]
    else:
        raise ValueError('中文名无法写入 YAML')
    parsed = yaml.safe_load(f'{ATTR}: {scalar}\n')
    if not isinstance(parsed, dict) or parsed.get(ATTR) != value:
        raise ValueError('中文名无法写入 YAML')
    return scalar


def _replace_yaml_key(text, key, scalar):
    """Text with the top-level `key` value replaced by `scalar`.

    Missing keys are appended (before a trailing `...` in block style,
    inside the braces in flow style). Comments, other fields, key order
    and line endings are preserved.
    """
    try:
        data = yaml.safe_load(text)
        node = yaml.compose(text)
    except (yaml.YAMLError, UnicodeDecodeError, ValueError) as error:
        raise ValueError('现有 .project.yaml 格式无效') from error
    if not isinstance(data, dict) or not isinstance(node, yaml.MappingNode):
        raise ValueError('.project.yaml 顶层必须是对象')

    value_nodes = []
    for key_node, value_node in node.value:
        if (isinstance(key_node, yaml.ScalarNode)
                and key_node.tag == 'tag:yaml.org,2002:str'
                and key_node.value == key):
            value_nodes.append(value_node)
    if len(value_nodes) > 1:
        raise ValueError(f'.project.yaml 中存在重复的 {key}')

    newline = '\r\n' if '\r\n' in text else '\n'
    if value_nodes:
        value_node = value_nodes[0]
        start = value_node.start_mark.index
        end = value_node.end_mark.index
        replacement = scalar
        if '\n' in text[start:end] or '\r' in text[start:end]:
            replacement += newline
        return text[:start] + replacement + text[end:]

    if node.flow_style:
        close = text.rfind('}', node.start_mark.index, node.end_mark.index)
        if close < 0:
            raise ValueError('无法定位 .project.yaml 的顶层对象')
        # A trailing comma before '}' is valid YAML; don't double it.
        prefix = text[:close].rstrip()
        if prefix.endswith(','):
            separator = ' '
        elif node.value:
            separator = ', '
        else:
            separator = ''
        entry = f'{separator}{key}: {scalar}'
        return text[:close] + entry + text[close:]

    marker = re.search(
        r'(?m)^[ \t]*\.\.\.[ \t]*(?:#.*)?(?:\r?\n|$)',
        text[node.end_mark.index:],
    )
    insert_at = (node.end_mark.index + marker.start()
                 if marker is not None else len(text))
    before = text[:insert_at]
    if before and not before.endswith(('\n', '\r')):
        before += newline
    entry = f'{key}: {scalar}{newline}'
    return before + entry + text[insert_at:]


def _remove_yaml_key(text, key):
    """Text minus the top-level `key` entry.

    Returns '' when nothing remains (caller deletes the file); None when
    the key was absent.
    """
    try:
        data = yaml.safe_load(text)
        node = yaml.compose(text)
    except (yaml.YAMLError, UnicodeDecodeError, ValueError) as error:
        raise ValueError('现有 .project.yaml 格式无效') from error
    if not isinstance(data, dict) or not isinstance(node, yaml.MappingNode):
        raise ValueError('.project.yaml 顶层必须是对象')

    matches = [
        (key_node, value_node)
        for key_node, value_node in node.value
        if (isinstance(key_node, yaml.ScalarNode)
            and key_node.tag == 'tag:yaml.org,2002:str'
            and key_node.value == key)
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f'.project.yaml 中存在重复的 {key}')

    key_node, value_node = matches[0]
    if node.flow_style:
        # Flow style has no line structure: excise the entry plus one
        # adjacent comma (either the one after it, or the one before it
        # when removing the last entry).
        start = key_node.start_mark.index
        end = value_node.end_mark.index
        comma_after = text.find(',', end, node.end_mark.index)
        if comma_after >= 0:
            end = comma_after + 1
        else:
            comma_before = text.rfind(',', 0, start)
            if comma_before < 0:
                return ''  # Sole entry: nothing remains.
            start = comma_before
        result = text[:start] + text[end:]
        try:
            empty = not yaml.safe_load(result)
        except yaml.YAMLError as error:
            raise ValueError('无法安全移除条目') from error
        return '' if empty else result

    # Block style: excise the entry's whole physical line(s), trailing
    # comment included.
    line_start = text.rfind('\n', 0, key_node.start_mark.index) + 1
    newline_at = text.find('\n', value_node.end_mark.index)
    line_end = len(text) if newline_at < 0 else newline_at + 1
    result = text[:line_start] + text[line_end:]
    try:
        empty = not yaml.safe_load(result)
    except yaml.YAMLError as error:
        raise ValueError('无法安全移除条目') from error
    return '' if empty else result


def _update_yaml_file(folder_path, update):
    """Apply update(original_text) -> new text to .project.yaml atomically.

    An update returning '' deletes the file; None is a no-op. Missing file
    starts from '' (the updater produces the initial content).
    """
    yaml_path = os.path.join(folder_path, YAML_NAME)
    try:
        file_stat = os.stat(yaml_path)
    except FileNotFoundError:
        _atomic_write(yaml_path, update(''), 0o644)
        return
    if file_stat.st_size > YAML_MAX_SIZE:
        raise ValueError('.project.yaml 文件过大')
    with open(yaml_path, encoding='utf-8', newline='') as f:
        original = f.read()
    result = update(original)
    if result is None:
        return
    if result == '':
        os.unlink(yaml_path)
    else:
        _atomic_write(yaml_path, result, stat.S_IMODE(file_stat.st_mode))


def _write_name_zh(folder_path, value):
    value = value.strip()
    if not value:
        raise ValueError('中文名不能为空')
    scalar = _yaml_scalar(value)

    def update(text):
        return f'{ATTR}: {scalar}\n' if text == '' else _replace_yaml_key(
            text, ATTR, scalar)

    _update_yaml_file(folder_path, update)


def _remove_key_in_folder(folder_path, key):
    """Drop a top-level key; delete .project.yaml if nothing else remains."""
    yaml_path = os.path.join(folder_path, YAML_NAME)
    try:
        file_stat = os.stat(yaml_path)
    except FileNotFoundError:
        return  # Nothing to remove.
    if file_stat.st_size > YAML_MAX_SIZE:
        raise ValueError('.project.yaml 文件过大')
    with open(yaml_path, encoding='utf-8', newline='') as f:
        original = f.read()
    result = _remove_yaml_key(original, key)
    if result is None:
        return
    if result == '':
        os.unlink(yaml_path)
    else:
        _atomic_write(yaml_path, result, stat.S_IMODE(file_stat.st_mode))


def _set_archived(folder_path, archived):
    """Write or remove `archived: true` in the folder's .project.yaml.

    Removing it deletes the file when no other data remains. Idempotent:
    a folder already in the requested state is left untouched (missing
    file + unarchive is also a no-op).
    """
    if archived:
        if _yaml_info(folder_path)[1] is True:
            return

        def update(text):
            scalar = 'true'
            return (f'{ARCHIVED_KEY}: {scalar}\n' if text == ''
                    else _replace_yaml_key(text, ARCHIVED_KEY, scalar))

        _update_yaml_file(folder_path, update)
    elif os.path.exists(os.path.join(folder_path, YAML_NAME)):
        # Missing file + unarchive: nothing to do.
        _remove_key_in_folder(folder_path, ARCHIVED_KEY)



# --- icon-view captions ---------------------------------------------------
# The name label under the icon is always shown; captions are extra lines
# below it. Making 'name-zh' the first caption puts the Chinese name
# directly under the English one.

def _captions():
    return list(_settings.get_strv(CAPTIONS_KEY))


def _set_captions(captions):
    _settings.set_strv(CAPTIONS_KEY, captions)


def _save_captions_backup(captions):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    _atomic_write(CAPTIONS_BACKUP, json.dumps(captions))


def _load_captions_backup():
    try:
        with open(CAPTIONS_BACKUP, encoding='utf-8') as f:
            backup = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(backup, list) or not all(isinstance(c, str) for c in backup):
        return None
    return backup


def _clear_captions_backup():
    try:
        os.remove(CAPTIONS_BACKUP)
    except OSError:
        pass


def _sync_captions(enabled):
    """On: make 'name-zh' the first caption. Off: restore what the user had."""
    captions = _captions()
    if enabled:
        if ATTR not in captions:
            _save_captions_backup(captions)
            _set_captions([ATTR] + [c for c in captions if c not in ('none', ATTR)])
    else:
        if ATTR in captions:
            backup = _load_captions_backup()
            if backup is not None:
                _clear_captions_backup()
                _set_captions(backup)
            else:
                _set_captions([c for c in captions if c != ATTR])


# --- applying the name ----------------------------------------------------

def _local_folder_path(file):
    if not file.is_directory():
        return None
    uri = file.get_uri()
    if not uri.startswith('file:'):
        return None
    try:
        return GLib.filename_from_uri(uri)[0]
    except GLib.Error:
        return None


def _apply(file):
    """Set/clear the name-zh and group extension attributes for one file.

    The group attribute is independent of the on/off switch: the switch only
    controls the Chinese captions. Archived folders are always grouped.
    """
    folder = _local_folder_path(file)
    if folder is None:
        return
    name, archived = _yaml_info(folder)

    if _enabled() and name:
        file.add_string_attribute(ATTR, name)
        _shown.add(folder)
    elif folder in _shown:
        # Extension attributes have no removal: an empty value clears the
        # line. Needed when name-zh is removed or the switch is turned off.
        file.add_string_attribute(ATTR, '')

    if archived is True:
        file.add_string_attribute(GROUP_ATTR, ARCHIVED_LABEL)
        _grouped.add(folder)
    elif folder in _grouped:
        file.add_string_attribute(GROUP_ATTR, '')
        _grouped.discard(folder)


def _refresh_folder(folder):
    """Re-apply extension info for every child of folder, live."""
    gfile = folder.get_location()
    try:
        children = gfile.enumerate_children('standard::name',
                                            Gio.FileQueryInfoFlags.NONE,
                                            None)
    except GLib.Error:
        return
    try:
        for info in children:
            file_info = Nautilus.FileInfo.lookup_for_uri(
                gfile.get_child(info.get_name()).get_uri())
            if file_info is not None:
                _apply(file_info)
                file_info.invalidate_extension_info()
    finally:
        try:
            children.close(None)
        except GLib.Error:
            pass


# --- nautilus extension points -------------------------------------------

def _running_as_plus(candidates=None):
    """True when loaded by the nautilus-plus fork (has the C filter hook).

    The hide-archived toggle only makes sense in the fork: the stock
    nautilus has no filter, so the menu item is not offered there.
    nautilus-python embeds CPython in-process, so /proc/self/exe is the
    host binary; fall back to cmdline and argv[0] for odd setups.
    """
    if candidates is None:
        candidates = []
        try:
            candidates.append(os.path.realpath('/proc/self/exe'))
        except OSError:
            pass
        try:
            with open('/proc/self/cmdline', 'rb') as f:
                candidates.append(f.read().split(b'\0', 1)[0].decode(
                    'utf-8', 'replace'))
        except OSError:
            pass
        if sys.argv:
            candidates.append(sys.argv[0])
    return any(os.path.basename(c) == 'nautilus-plus' for c in candidates)


def _active_window():
    application = Gio.Application.get_default()
    if application is not None:
        try:
            window = application.get_active_window()
        except AttributeError:
            window = None
        if window is not None:
            return window
    for window in Gtk.Window.list_toplevels():
        if window.is_active():
            return window
    return None


class ProjectNameZhInfoProvider(GObject.GObject, Nautilus.InfoProvider):
    """Shows the Chinese name via a caption extension attribute."""

    def __init__(self):
        super().__init__()

    def update_file_info(self, file):
        _apply(file)


class ProjectNameZhMenu(GObject.GObject, Nautilus.MenuProvider):
    """Provides the project-name action and the global caption switch."""

    def __init__(self):
        super().__init__()
        self._dialogs = {}
        self._alerts = set()

    def get_file_items(self, files):
        # Multi-selection keeps the batch archive toggle only — "修改中文
        # 名" makes no sense when the user selected more than one item,
        # even if some of them are not local folders.
        folders = [(file, path) for file in files
                   if (path := _local_folder_path(file)) is not None]
        if len(files) != 1 or not folders:
            if not folders:
                return []
            single = False
        else:
            single = True
        items = []
        if single:
            file, _folder = folders[0]
            items.append(Nautilus.MenuItem(
                name='ProjectNameZh::EditName',
                label='修改中文名',
                tip='编辑文件夹 .project.yaml 中的 name-zh',
                icon=None,
            ))
            items[-1].connect('activate', self._on_edit_name, file)

        # Dynamic action label: offer unarchive only when every selected
        # folder is archived; mixed selections offer archiving (already
        # archived members are left alone).
        all_archived = all(_yaml_info(folder)[1] is True
                           for _file, folder in folders)
        items.append(Nautilus.MenuItem(
            name='ProjectNameZh::ToggleArchived',
            label='取消归档' if all_archived else '归档',
            tip='切换文件夹 .project.yaml 中的 archived: true',
            icon=None,
        ))
        items[-1].connect('activate', self._on_toggle_archived,
                          folders, not all_archived)
        return items

    def _on_toggle_archived(self, _item, folders, archived):
        failures = []
        for file, folder in folders:
            try:
                _set_archived(folder, archived)
            except Exception as error:
                traceback.print_exc()
                failures.append(f'{os.path.basename(folder)}: '
                                f'{error or "写入 .project.yaml 失败"}')
                continue
            _yaml_cache.pop(folder, None)
            _apply(file)
            file.invalidate_extension_info()
        if failures:
            self._show_error('归档状态修改失败', '\n'.join(failures))

    def _on_edit_name(self, _item, file):
        folder = _local_folder_path(file)
        if folder is None:
            return
        uri = file.get_uri()
        existing = self._dialogs.get(uri)
        if existing is not None:
            existing.present()
            return

        name, _archived = _yaml_info(folder)
        window = Gtk.Window(title='修改中文名')
        window.set_default_size(420, 120)
        window.set_modal(True)
        window.set_destroy_with_parent(True)
        parent = _active_window()
        if parent is not None and parent is not window:
            window.set_transient_for(parent)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        for margin in ('top', 'bottom', 'start', 'end'):
            getattr(box, f'set_margin_{margin}')(18)
        label = Gtk.Label(label='中文名')
        label.set_xalign(0)
        entry = Gtk.Entry()
        entry.set_hexpand(True)
        entry.set_activates_default(True)
        entry.set_text(name or '')
        entry.set_position(-1)

        buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        buttons.set_halign(Gtk.Align.END)
        cancel = Gtk.Button(label='取消')
        save = Gtk.Button(label='保存')
        buttons.append(cancel)
        buttons.append(save)
        box.append(label)
        box.append(entry)
        box.append(buttons)
        window.set_child(box)
        window.set_default_widget(save)

        cancel.connect('clicked', lambda _button: window.close())
        save.connect('clicked', self._on_save_name, window, entry, file, folder)
        window.connect('close-request', self._on_editor_close, uri)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect('key-pressed', self._on_editor_key, window)
        window.add_controller(key_controller)

        self._dialogs[uri] = window
        window.present()
        entry.grab_focus()

    def _on_editor_close(self, _window, uri):
        self._dialogs.pop(uri, None)
        return False

    def _on_editor_key(self, _controller, keyval, _keycode, _state, window):
        if keyval == Gdk.KEY_Escape:
            window.close()
            return True
        return False

    def _show_error(self, message, detail, parent=None):
        alert = Gtk.AlertDialog()
        alert.set_message(message)
        alert.set_detail(detail)
        alert.set_buttons(['确定'])
        self._alerts.add(alert)
        if parent is None:
            parent = _active_window()

        def on_alert_done(_alert, result, _user_data):
            try:
                alert.choose_finish(result)
            except GLib.Error:
                pass
            self._alerts.discard(alert)

        alert.choose(parent, None, on_alert_done, None)

    def _on_save_name(self, _button, window, entry, file, folder):
        value = entry.get_text().strip()
        try:
            if value:
                _write_name_zh(folder, value)
            else:
                # Empty input clears the Chinese name; the yaml file goes
                # with it when no other data remains.
                _remove_key_in_folder(folder, ATTR)
            _yaml_cache.pop(folder, None)
            _apply(file)
            file.invalidate_extension_info()
        except Exception as error:
            traceback.print_exc()
            self._show_error('无法修改中文名',
                             str(error) or '写入 .project.yaml 失败。',
                             parent=window)
            return
        window.close()

    def get_background_items(self, current_folder):
        item = Nautilus.MenuItem(
            name='ProjectNameZh::Toggle',
            label='隐藏中文项目名' if _enabled() else '显示中文项目名',
            tip='在文件夹名下方显示 .project.yaml 中的 name-zh',
            icon=None,
        )
        item.connect('activate', self._on_toggle, current_folder)
        items = [item]

        # Hide-archived needs the fork's C filter hook; in the stock
        # nautilus the toggle would do nothing, so don't offer it there.
        # Same when the fork's schema is missing: don't show a control that
        # cannot have any effect.
        if _running_as_plus() and _plus_settings is not None:
            hide_item = Nautilus.MenuItem(
                name='ProjectNameZh::ToggleHideArchived',
                label='隐藏归档' if not _hide_archived() else '显示归档',
                tip='切换已归档文件夹的可见性(由 nautilus-plus 过滤)',
                icon=None,
            )
            hide_item.connect('activate', self._on_toggle_hide_archived,
                              current_folder)
            items.append(hide_item)
        return items

    def _on_toggle(self, _item, current_folder):
        try:
            on = not _enabled()
            _set_enabled(on)
            _sync_captions(on)
            _refresh_folder(current_folder)
            # Nautilus builds the extension menus once per folder view and
            # has no "rebuild now" API for them, but it does rebuild when
            # the current folder's own file changes: re-adding the attribute
            # fires nautilus_file_changed on it, which schedules a menu
            # refresh, so the label flips to match the new state.
            current_folder.add_string_attribute(
                ATTR, current_folder.get_string_attribute(ATTR) or '')
        except Exception:
            traceback.print_exc()

    def _on_toggle_hide_archived(self, _item, current_folder):
        try:
            _set_hide_archived(not _hide_archived())
            _refresh_folder(current_folder)
            # Same menu-rebuild trick as the captions toggle: touching the
            # current folder's extension info schedules a menu refresh.
            current_folder.add_string_attribute(
                ATTR, current_folder.get_string_attribute(ATTR) or '')
        except Exception:
            traceback.print_exc()


# Keep the icon-view captions in sync from the start (switch defaults to on).
_sync_captions(_enabled())
