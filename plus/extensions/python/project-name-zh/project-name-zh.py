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
import tempfile
import traceback

import yaml

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Nautilus

CONFIG_DIR = os.path.expanduser('~/.config/nautilus-project-zh')
STATE_FILE = os.path.join(CONFIG_DIR, 'state')
CAPTIONS_BACKUP = os.path.join(CONFIG_DIR, 'captions-backup.json')

ICON_VIEW_SCHEMA = 'org.gnome.nautilus.icon-view'
CAPTIONS_KEY = 'captions'
ATTR = 'name-zh'
GROUP_ATTR = 'group'
ARCHIVED_LABEL = '已归档'
YAML_NAME = '.project.yaml'
YAML_MAX_SIZE = 1024 * 1024

_settings = Gio.Settings.new(ICON_VIEW_SCHEMA)

# folder_path -> (mtime, name_zh | None, archived: bool)
_yaml_cache = {}
# folders we ever showed a Chinese name for; the source of truth for
# clearing stale captions (yaml deleted / key removed / switch off)
_shown = set()
# folders we ever marked as grouped (archived); the source of truth for
# clearing the group attribute when it no longer applies
_grouped = set()
# (mtime, enabled)
_state_cache = (None, None)


# --- switch state ---------------------------------------------------------

def _enabled():
    """Whether the Chinese names are shown. Defaults to on."""
    global _state_cache
    try:
        mtime = os.path.getmtime(STATE_FILE)
    except OSError:
        return True
    if _state_cache[0] == mtime:
        return _state_cache[1]
    try:
        with open(STATE_FILE, encoding='utf-8') as f:
            enabled = f.read().strip() == 'on'
    except OSError:
        enabled = True
    _state_cache = (mtime, enabled)
    return enabled


def _set_enabled(on):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    _atomic_write(STATE_FILE, 'on' if on else 'off')


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


def _replace_yaml_name(text, scalar):
    try:
        data = yaml.safe_load(text)
        node = yaml.compose(text)
    except (yaml.YAMLError, UnicodeDecodeError, ValueError) as error:
        raise ValueError('现有 .project.yaml 格式无效') from error
    if not isinstance(data, dict) or not isinstance(node, yaml.MappingNode):
        raise ValueError('.project.yaml 顶层必须是对象')

    name_nodes = []
    for key_node, value_node in node.value:
        if (isinstance(key_node, yaml.ScalarNode)
                and key_node.tag == 'tag:yaml.org,2002:str'
                and key_node.value == ATTR):
            name_nodes.append(value_node)
    if len(name_nodes) > 1:
        raise ValueError('.project.yaml 中存在重复的 name-zh')

    newline = '\r\n' if '\r\n' in text else '\n'
    if name_nodes:
        value_node = name_nodes[0]
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
        entry = f'{separator}{ATTR}: {scalar}'
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
    entry = f'{ATTR}: {scalar}{newline}'
    return before + entry + text[insert_at:]


def _write_name_zh(folder_path, value):
    value = value.strip()
    if not value:
        raise ValueError('中文名不能为空')
    scalar = _yaml_scalar(value)
    yaml_path = os.path.join(folder_path, YAML_NAME)
    try:
        file_stat = os.stat(yaml_path)
    except FileNotFoundError:
        text = f'{ATTR}: {scalar}\n'
        mode = 0o644
    else:
        if file_stat.st_size > YAML_MAX_SIZE:
            raise ValueError('.project.yaml 文件过大')
        with open(yaml_path, encoding='utf-8', newline='') as f:
            original = f.read()
        text = _replace_yaml_name(original, scalar)
        mode = stat.S_IMODE(file_stat.st_mode)
    _atomic_write(yaml_path, text, mode)


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
        if len(files) != 1:
            return []
        file = files[0]
        if _local_folder_path(file) is None:
            return []
        item = Nautilus.MenuItem(
            name='ProjectNameZh::EditName',
            label='修改中文名',
            tip='编辑文件夹 .project.yaml 中的 name-zh',
            icon=None,
        )
        item.connect('activate', self._on_edit_name, file)
        return [item]

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

    def _show_error(self, window, message):
        alert = Gtk.AlertDialog()
        alert.set_message('无法修改中文名')
        alert.set_detail(message)
        alert.set_buttons(['确定'])
        self._alerts.add(alert)

        def on_alert_done(_alert, result, _user_data):
            try:
                alert.choose_finish(result)
            except GLib.Error:
                pass
            self._alerts.discard(alert)

        alert.choose(window, None, on_alert_done, None)

    def _on_save_name(self, _button, window, entry, file, folder):
        value = entry.get_text().strip()
        if not value:
            self._show_error(window, '中文名不能为空。')
            return
        try:
            _write_name_zh(folder, value)
            _yaml_cache.pop(folder, None)
            _apply(file)
            file.invalidate_extension_info()
        except Exception as error:
            traceback.print_exc()
            self._show_error(window, str(error) or '写入 .project.yaml 失败。')
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
        return [item]

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


# Keep the icon-view captions in sync from the start (switch defaults to on).
_sync_captions(_enabled())
