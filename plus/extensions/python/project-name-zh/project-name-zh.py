#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nautilus extension: show Chinese project names from .project.yaml.

For every folder whose `.project.yaml` has a top-level `name-zh` key, the
Chinese name is shown as a caption line right below the folder name in
icon view. The real folder name (and path) is never changed, and normal
renaming (F2) is unaffected — edit `.project.yaml` to change the Chinese
name.

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
import traceback

import yaml

from gi.repository import Gio, GLib, GObject, Nautilus

CONFIG_DIR = os.path.expanduser('~/.config/nautilus-project-zh')
STATE_FILE = os.path.join(CONFIG_DIR, 'state')
CAPTIONS_BACKUP = os.path.join(CONFIG_DIR, 'captions-backup.json')

ICON_VIEW_SCHEMA = 'org.gnome.nautilus.icon-view'
CAPTIONS_KEY = 'captions'
ATTR = 'name-zh'
YAML_NAME = '.project.yaml'
YAML_MAX_SIZE = 1024 * 1024

_settings = Gio.Settings.new(ICON_VIEW_SCHEMA)

# folder_path -> (mtime, name_zh | None)
_name_cache = {}
# folders we ever showed a Chinese name for; the source of truth for
# clearing stale captions (yaml deleted / key removed / switch off)
_shown = set()
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


def _atomic_write(path, text):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(text)
    os.replace(tmp, path)


# --- .project.yaml --------------------------------------------------------

def _name_zh(folder_path):
    """name-zh from the folder's .project.yaml, or None. Cached by mtime."""
    yaml_path = os.path.join(folder_path, YAML_NAME)
    try:
        mtime = os.path.getmtime(yaml_path)
    except OSError:
        _name_cache.pop(folder_path, None)
        return None
    hit = _name_cache.get(folder_path)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    name = None
    try:
        if os.path.getsize(yaml_path) <= YAML_MAX_SIZE:
            with open(yaml_path, encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict):
                value = data.get('name-zh')
                if isinstance(value, str) and value.strip():
                    name = value.strip()
    except (yaml.YAMLError, UnicodeDecodeError, OSError, ValueError):
        pass
    _name_cache[folder_path] = (mtime, name)
    if len(_name_cache) > 1024:
        _name_cache.pop(next(iter(_name_cache)))
    return name


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

def _apply(file):
    """Set/clear the name-zh extension attribute for one file."""
    if not file.is_directory():
        return
    uri = file.get_uri()
    if not uri.startswith('file:'):
        return
    try:
        folder = GLib.filename_from_uri(uri)[0]
    except GLib.Error:
        return
    name = _name_zh(folder) if _enabled() else None
    if name:
        file.add_string_attribute(ATTR, name)
        _shown.add(folder)
    elif folder in _shown:
        # Extension attributes have no removal: an empty value clears the
        # line. Needed when name-zh is removed or the switch is turned off.
        file.add_string_attribute(ATTR, '')


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

class ProjectNameZhInfoProvider(GObject.GObject, Nautilus.InfoProvider):
    """Shows the Chinese name via a caption extension attribute."""

    def __init__(self):
        super().__init__()

    def update_file_info(self, file):
        _apply(file)


class ProjectNameZhMenu(GObject.GObject, Nautilus.MenuProvider):
    """Global on/off switch in the background context menu."""

    def __init__(self):
        super().__init__()

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
