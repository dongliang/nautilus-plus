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
        self.values = {'captions': []}

    @classmethod
    def new(cls, _schema):
        return cls()

    def get_strv(self, key):
        return list(self.values.get(key, []))

    def set_strv(self, key, value):
        self.values[key] = list(value)


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


class _Gio:
    Settings = _Settings
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
        project_name_zh._remove_name_zh(self.folder.name)
        self.assertFalse(self.path.exists())

    def test_empty_value_keeps_other_fields(self):
        original = '# header\nname-zh: old  # keep\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._remove_name_zh(self.folder.name)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# header\narchived: true\n',
        )

    def test_remove_without_key_leaves_file_alone(self):
        original = 'archived: true\n'
        self.path.write_text(original, encoding='utf-8')
        project_name_zh._remove_name_zh(self.folder.name)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_remove_missing_file_is_noop(self):
        project_name_zh._remove_name_zh(self.folder.name)
        self.assertFalse(self.path.exists())

    def test_rejects_blank_and_multiline_values(self):
        with self.assertRaises(ValueError):
            project_name_zh._write_name_zh(self.folder.name, 'one\ntwo')
        self.assertFalse(self.path.exists())


class MenuFilterTests(unittest.TestCase):
    def test_only_single_local_folder_gets_menu(self):
        menu = project_name_zh.ProjectNameZhMenu()
        folder = _FileInfo('file:///tmp/project')
        regular_file = _FileInfo('file:///tmp/notes.txt', directory=False)
        remote_folder = _FileInfo('sftp://host/project')
        self.assertEqual(len(menu.get_file_items([folder])), 1)
        self.assertEqual(menu.get_file_items([folder, remote_folder]), [])
        self.assertEqual(menu.get_file_items([regular_file]), [])
        self.assertEqual(menu.get_file_items([remote_folder]), [])


if __name__ == '__main__':
    unittest.main()
