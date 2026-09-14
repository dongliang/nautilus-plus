import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse


class _Settings:
    def __init__(self):
        self.values = {'captions': [], 'hide-archived': False}

    @classmethod
    def new(cls, schema):
        return cls()

    @classmethod
    def new_full(cls, schema, backend, path):
        return cls()

    def get_strv(self, key):
        return list(self.values.get(key, []))

    def set_strv(self, key, value):
        self.values[key] = list(value)

    def get_boolean(self, key):
        return bool(self.values.get(key, False))

    def set_boolean(self, key, value):
        self.values[key] = bool(value)


class _MenuItem:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def connect(self, *_args):
        pass


class _FileInfo:
    def __init__(self, uri, directory=True):
        self.uri = uri
        self.directory = directory

    def is_directory(self):
        return self.directory

    def get_uri(self):
        return self.uri


class _GObject:
    class GObject:
        def __init__(self):
            pass


class _Nautilus:
    class InfoProvider:
        pass

    class MenuProvider:
        pass

    MenuItem = _MenuItem
    FileInfo = _FileInfo


class _SettingsSchema:
    def __init__(self, keys):
        self._keys = set(keys)

    def has_key(self, key):
        return key in self._keys


class _SettingsSchemaSource:
    """Stand-in for Gio.SettingsSchemaSource.

    Tests empty `schemas` to simulate a system where the fork's schema was
    never installed (or was wiped by a nautilus package upgrade).
    """

    schemas = {'org.gnome.NautilusPlus.preferences': ['hide-archived']}

    def __init__(self, schemas):
        self._schemas = schemas

    @classmethod
    def get_default(cls):
        return cls(dict(cls.schemas))

    def lookup(self, schema_id, recursive):
        keys = self._schemas.get(schema_id)
        return _SettingsSchema(keys) if keys is not None else None


class _Gio:
    Settings = _Settings
    SettingsSchemaSource = _SettingsSchemaSource
    FileQueryInfoFlags = types.SimpleNamespace(NONE=0)

    class Application:
        @staticmethod
        def get_default():
            return None


class _GLib:
    class Error(Exception):
        pass

    @staticmethod
    def filename_from_uri(uri):
        parsed = urlparse(uri)
        return unquote(parsed.path), None


class _Gtk:
    Orientation = types.SimpleNamespace(VERTICAL=1, HORIZONTAL=2)
    Align = types.SimpleNamespace(END=1)


class _Gdk:
    KEY_Escape = 65307


def _load_extension():
    temp_home = tempfile.TemporaryDirectory()
    os.environ['HOME'] = temp_home.name
    repository = types.ModuleType('gi.repository')
    repository.Gdk = _Gdk
    repository.Gio = _Gio
    repository.GLib = _GLib
    repository.GObject = _GObject
    repository.Gtk = _Gtk
    repository.Nautilus = _Nautilus
    gi = types.ModuleType('gi')
    gi.repository = repository
    sys.modules['gi'] = gi
    sys.modules['gi.repository'] = repository

    path = Path(__file__).with_name('project-name-zh.py')
    spec = importlib.util.spec_from_file_location('project_name_zh', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._test_home = temp_home
    return module


project_name_zh = _load_extension()


class ProjectYamlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / project_name_zh.YAML_NAME

    def tearDown(self):
        self.folder.cleanup()

    def test_creates_yaml(self):
        project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), 'name-zh: 新项目\n')

    def test_replaces_value_and_preserves_comments_and_fields(self):
        original = '# header\nname-zh: old  # keep this\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# header\nname-zh: 新项目  # keep this\narchived: true\n',
        )

    def test_appends_missing_key_before_document_end(self):
        self.path.write_text('archived: true\n...\n', encoding='utf-8')
        project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'archived: true\nname-zh: 新项目\n...\n',
        )

    def test_replaces_block_scalar_with_single_line_value(self):
        original = 'name-zh: >\n  old\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'name-zh: 新项目\narchived: true\n',
        )

    def test_rejects_duplicate_name_keys_without_overwriting(self):
        original = 'name-zh: one\nname-zh: two\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_updates_flow_mapping(self):
        self.path.write_text('{archived: true}\n', encoding='utf-8')
        project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '{archived: true, name-zh: 新项目}\n',
        )

    def test_rejects_invalid_yaml_without_overwriting(self):
        original = 'archived: [\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_rejects_non_mapping_without_overwriting(self):
        original = '- one\n- two\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            project_name_zh._write_name_zh(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_empty_value_removes_key_and_file(self):
        self.path.write_text('name-zh: 旧名\n', encoding='utf-8')
        project_name_zh._remove_key_in_folder(self.folder.name,
                                              project_name_zh.ATTR)
        self.assertFalse(self.path.exists())

    def test_empty_value_keeps_other_fields(self):
        original = '# header\nname-zh: old  # keep\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._remove_key_in_folder(self.folder.name,
                                              project_name_zh.ATTR)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# header\narchived: true\n',
        )

    def test_remove_without_key_leaves_file_alone(self):
        original = 'archived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._remove_key_in_folder(self.folder.name,
                                              project_name_zh.ATTR)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_remove_missing_file_is_noop(self):
        project_name_zh._remove_key_in_folder(self.folder.name,
                                              project_name_zh.ATTR)
        self.assertFalse(self.path.exists())

    def test_rejects_blank_and_multiline_values(self):
        with self.assertRaises(ValueError):
            project_name_zh._write_name_zh(self.folder.name, 'one\ntwo')
        self.assertFalse(self.path.exists())


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / project_name_zh.YAML_NAME

    def tearDown(self):
        self.folder.cleanup()

    def test_archive_creates_yaml(self):
        project_name_zh._set_archived(self.folder.name, True)
        self.assertEqual(self.path.read_text(encoding='utf-8'),
                         'archived: true\n')

    def test_archive_appends_preserving_comments_and_fields(self):
        original = '# 项目\nname-zh: 阿尔法  # 保留\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._set_archived(self.folder.name, True)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# 项目\nname-zh: 阿尔法  # 保留\narchived: true\n',
        )

    def test_archive_replaces_existing_value(self):
        original = '# c\narchived: false  # note\nname-zh: x\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._set_archived(self.folder.name, True)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# c\narchived: true  # note\nname-zh: x\n',
        )

    def test_unarchive_removes_line_and_keeps_rest(self):
        original = 'name-zh: 阿尔法\narchived: true  # note\nother: y\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._set_archived(self.folder.name, False)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'name-zh: 阿尔法\nother: y\n',
        )

    def test_unarchive_deletes_file_when_empty(self):
        self.path.write_text('archived: true\n', encoding='utf-8')
        project_name_zh._set_archived(self.folder.name, False)
        self.assertFalse(self.path.exists())

    def test_unarchive_missing_file_is_noop(self):
        project_name_zh._set_archived(self.folder.name, False)
        self.assertFalse(self.path.exists())

    def test_archive_is_idempotent(self):
        original = '# keep\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        mtime_before = self.path.stat().st_mtime_ns
        project_name_zh._set_archived(self.folder.name, True)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime_before)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_unarchive_flow_mapping_keeps_braces(self):
        self.path.write_text('{archived: true, name-zh: a}\n',
                             encoding='utf-8')
        project_name_zh._set_archived(self.folder.name, False)
        result = self.path.read_text(encoding='utf-8')
        import yaml as _yaml
        data = _yaml.safe_load(result)
        self.assertEqual(data, {'name-zh': 'a'})

    def test_rejects_malformed_yaml_on_unarchive(self):
        original = 'archived: [\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            project_name_zh._set_archived(self.folder.name, False)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)


class HideArchivedStateTests(unittest.TestCase):
    """hide-archived lives in the fork's own gsettings schema."""

    def setUp(self):
        self.prefs = project_name_zh._plus_settings

    def test_defaults_to_show(self):
        self.assertFalse(project_name_zh._hide_archived())

    def test_round_trip(self):
        project_name_zh._set_hide_archived(True)
        self.assertTrue(project_name_zh._hide_archived())
        # Captions switch untouched.
        self.assertTrue(project_name_zh._enabled())
        project_name_zh._set_hide_archived(False)
        self.assertFalse(project_name_zh._hide_archived())

    def test_set_enabled_preserves_hide_archived(self):
        project_name_zh._set_hide_archived(True)
        project_name_zh._set_enabled(False)
        self.assertFalse(project_name_zh._enabled())
        self.assertTrue(self.prefs.values['hide-archived'])

    def test_state_file_only_holds_captions_switch(self):
        project_name_zh._set_enabled(False)
        project_name_zh._set_hide_archived(True)
        content = Path(project_name_zh.STATE_FILE).read_text(encoding='utf-8')
        self.assertNotIn('hide-archived', content)


class MissingPlusSchemaTests(unittest.TestCase):
    """A nautilus package upgrade must degrade, never crash the fork."""

    def setUp(self):
        self._saved = _SettingsSchemaSource.schemas
        _SettingsSchemaSource.schemas = {}

    def tearDown(self):
        _SettingsSchemaSource.schemas = self._saved

    def test_settings_object_is_none(self):
        self.assertIsNone(project_name_zh._open_plus_settings())

    def test_reads_and_writes_degrade_without_raising(self):
        original = project_name_zh._plus_settings
        project_name_zh._plus_settings = project_name_zh._open_plus_settings()
        self.addCleanup(setattr, project_name_zh, '_plus_settings', original)

        self.assertFalse(project_name_zh._hide_archived())
        project_name_zh._set_hide_archived(True)  # silent no-op
        self.assertFalse(project_name_zh._hide_archived())

    def test_toggle_is_not_offered(self):
        original_running = project_name_zh._running_as_plus
        original_settings = project_name_zh._plus_settings
        project_name_zh._running_as_plus = lambda *args, **kwargs: True
        project_name_zh._plus_settings = None
        self.addCleanup(setattr, project_name_zh, '_running_as_plus',
                        original_running)
        self.addCleanup(setattr, project_name_zh, '_plus_settings',
                        original_settings)

        menu = project_name_zh.ProjectNameZhMenu()
        items = menu.get_background_items(_FileInfo('file:///tmp/project'))
        names = [item.kwargs['name'] for item in items]
        self.assertNotIn('ProjectNameZh::ToggleHideArchived', names)

    def test_toggle_is_offered_when_schema_is_available(self):
        original_running = project_name_zh._running_as_plus
        project_name_zh._running_as_plus = lambda *args, **kwargs: True
        self.addCleanup(setattr, project_name_zh, '_running_as_plus',
                        original_running)

        menu = project_name_zh.ProjectNameZhMenu()
        items = menu.get_background_items(_FileInfo('file:///tmp/project'))
        names = [item.kwargs['name'] for item in items]
        self.assertIn('ProjectNameZh::ToggleHideArchived', names)


class RunningAsPlusTests(unittest.TestCase):
    def test_detection_matches_fork_name(self):
        self.assertTrue(project_name_zh._running_as_plus(
            ['/usr/bin/nautilus-plus']))
        self.assertTrue(project_name_zh._running_as_plus(
            ['/proc/exe', 'nautilus-plus', '/usr/bin/python3']))
        self.assertFalse(project_name_zh._running_as_plus(
            ['/usr/bin/nautilus', '--gapplication-service']))
        self.assertFalse(project_name_zh._running_as_plus([]))

    def test_stock_nautilus_gets_no_hide_menu(self):
        menu = project_name_zh.ProjectNameZhMenu()
        folder = _FileInfo('file:///tmp/project')
        items = menu.get_background_items(folder)
        names = [item.kwargs['name'] for item in items]
        self.assertNotIn('ProjectNameZh::ToggleHideArchived', names)


class MenuFilterTests(unittest.TestCase):
    def test_only_single_local_folder_gets_menu(self):
        menu = project_name_zh.ProjectNameZhMenu()
        folder = _FileInfo('file:///tmp/project')
        regular_file = _FileInfo('file:///tmp/notes.txt', directory=False)
        remote_folder = _FileInfo('sftp://host/project')
        items = menu.get_file_items([folder])
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['修改中文名', '归档'])
        # Remote members are dropped; the local one still gets the toggle.
        items = menu.get_file_items([folder, remote_folder])
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['归档'])
        self.assertEqual(menu.get_file_items([regular_file]), [])
        self.assertEqual(menu.get_file_items([remote_folder]), [])

    def test_multi_select_shows_only_archive_toggle(self):
        menu = project_name_zh.ProjectNameZhMenu()
        folders = [_FileInfo('file:///tmp/a'), _FileInfo('file:///tmp/b')]
        items = menu.get_file_items(folders)
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['归档'])

    def test_all_archived_selection_offers_unarchive(self):
        menu = project_name_zh.ProjectNameZhMenu()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / project_name_zh.YAML_NAME
            path.write_text('archived: true\n', encoding='utf-8')
            folder = _FileInfo('file://' + d)
            items = menu.get_file_items([folder])
            self.assertEqual(items[-1].kwargs['label'], '取消归档')

    def test_non_folder_selection_gets_nothing(self):
        menu = project_name_zh.ProjectNameZhMenu()
        regular_file = _FileInfo('file:///tmp/notes.txt', directory=False)
        self.assertEqual(menu.get_file_items([regular_file]), [])


if __name__ == '__main__':
    unittest.main()
