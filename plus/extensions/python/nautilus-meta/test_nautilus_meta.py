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
        self.attributes = {}

    def is_directory(self):
        return self.directory

    def get_uri(self):
        return self.uri

    def add_string_attribute(self, name, value):
        self.attributes[name] = value


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

    path = Path(__file__).with_name('nautilus-meta.py')
    spec = importlib.util.spec_from_file_location('nautilus_meta', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module._test_home = temp_home
    return module


nautilus_meta = _load_extension()


class FolderYamlTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / nautilus_meta.YAML_NAME

    def tearDown(self):
        self.folder.cleanup()

    def test_creates_yaml(self):
        nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), 'desc: 新项目\n')

    def test_replaces_value_and_preserves_comments_and_fields(self):
        original = '# header\ndesc: old  # keep this\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# header\ndesc: 新项目  # keep this\narchived: true\n',
        )

    def test_appends_missing_key_before_document_end(self):
        self.path.write_text('archived: true\n...\n', encoding='utf-8')
        nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'archived: true\ndesc: 新项目\n...\n',
        )

    def test_replaces_block_scalar_with_single_line_value(self):
        original = 'desc: >\n  old\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'desc: 新项目\narchived: true\n',
        )

    def test_rejects_duplicate_name_keys_without_overwriting(self):
        original = 'desc: one\ndesc: two\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_updates_flow_mapping(self):
        self.path.write_text('{archived: true}\n', encoding='utf-8')
        nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '{archived: true, desc: 新项目}\n',
        )

    def test_rejects_invalid_yaml_without_overwriting(self):
        original = 'archived: [\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_rejects_non_mapping_without_overwriting(self):
        original = '- one\n- two\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_desc(self.folder.name, '新项目')
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_empty_value_removes_key_and_file(self):
        self.path.write_text('desc: 旧名\n', encoding='utf-8')
        nautilus_meta._remove_key_in_folder(self.folder.name,
                                              nautilus_meta.ATTR)
        self.assertFalse(self.path.exists())

    def test_empty_value_keeps_other_fields(self):
        original = '# header\ndesc: old  # keep\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._remove_key_in_folder(self.folder.name,
                                              nautilus_meta.ATTR)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# header\narchived: true\n',
        )

    def test_remove_without_key_leaves_file_alone(self):
        original = 'archived: true\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._remove_key_in_folder(self.folder.name,
                                              nautilus_meta.ATTR)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_remove_missing_file_is_noop(self):
        nautilus_meta._remove_key_in_folder(self.folder.name,
                                              nautilus_meta.ATTR)
        self.assertFalse(self.path.exists())

    def test_rejects_blank_and_multiline_values(self):
        with self.assertRaises(ValueError):
            nautilus_meta._write_desc(self.folder.name, 'one\ntwo')
        self.assertFalse(self.path.exists())


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / nautilus_meta.YAML_NAME

    def tearDown(self):
        self.folder.cleanup()

    def test_archive_creates_yaml(self):
        nautilus_meta._set_archived(self.folder.name, True)
        self.assertEqual(self.path.read_text(encoding='utf-8'),
                         'archived: true\n')

    def test_archive_appends_preserving_comments_and_fields(self):
        original = '# 项目\ndesc: 阿尔法  # 保留\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._set_archived(self.folder.name, True)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# 项目\ndesc: 阿尔法  # 保留\narchived: true\n',
        )

    def test_archive_replaces_existing_value(self):
        original = '# c\narchived: false  # note\ndesc: x\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._set_archived(self.folder.name, True)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            '# c\narchived: true  # note\ndesc: x\n',
        )

    def test_unarchive_removes_line_and_keeps_rest(self):
        original = 'desc: 阿尔法\narchived: true  # note\nother: y\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._set_archived(self.folder.name, False)
        self.assertEqual(
            self.path.read_text(encoding='utf-8'),
            'desc: 阿尔法\nother: y\n',
        )

    def test_unarchive_deletes_file_when_empty(self):
        self.path.write_text('archived: true\n', encoding='utf-8')
        nautilus_meta._set_archived(self.folder.name, False)
        self.assertFalse(self.path.exists())

    def test_unarchive_missing_file_is_noop(self):
        nautilus_meta._set_archived(self.folder.name, False)
        self.assertFalse(self.path.exists())

    def test_archive_is_idempotent(self):
        original = '# keep\narchived: true\n'
        self.path.write_text(original, encoding='utf-8')
        mtime_before = self.path.stat().st_mtime_ns
        nautilus_meta._set_archived(self.folder.name, True)
        self.assertEqual(self.path.stat().st_mtime_ns, mtime_before)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)

    def test_unarchive_flow_mapping_keeps_braces(self):
        self.path.write_text('{archived: true, desc: a}\n',
                             encoding='utf-8')
        nautilus_meta._set_archived(self.folder.name, False)
        result = self.path.read_text(encoding='utf-8')
        import yaml as _yaml
        data = _yaml.safe_load(result)
        self.assertEqual(data, {'desc': 'a'})

    def test_rejects_malformed_yaml_on_unarchive(self):
        original = 'archived: [\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._set_archived(self.folder.name, False)
        self.assertEqual(self.path.read_text(encoding='utf-8'), original)


class HideArchivedStateTests(unittest.TestCase):
    """hide-archived lives in the fork's own gsettings schema."""

    def setUp(self):
        self.prefs = nautilus_meta._plus_settings

    def test_defaults_to_show(self):
        self.assertFalse(nautilus_meta._hide_archived())

    def test_round_trip(self):
        nautilus_meta._set_hide_archived(True)
        self.assertTrue(nautilus_meta._hide_archived())
        # Captions switch untouched.
        self.assertTrue(nautilus_meta._enabled())
        nautilus_meta._set_hide_archived(False)
        self.assertFalse(nautilus_meta._hide_archived())

    def test_set_enabled_preserves_hide_archived(self):
        nautilus_meta._set_hide_archived(True)
        nautilus_meta._set_enabled(False)
        self.assertFalse(nautilus_meta._enabled())
        self.assertTrue(self.prefs.values['hide-archived'])

    def test_state_file_only_holds_captions_switch(self):
        nautilus_meta._set_enabled(False)
        nautilus_meta._set_hide_archived(True)
        content = Path(nautilus_meta.STATE_FILE).read_text(encoding='utf-8')
        self.assertNotIn('hide-archived', content)


class MissingPlusSchemaTests(unittest.TestCase):
    """A nautilus package upgrade must degrade, never crash the fork."""

    def setUp(self):
        self._saved = _SettingsSchemaSource.schemas
        _SettingsSchemaSource.schemas = {}

    def tearDown(self):
        _SettingsSchemaSource.schemas = self._saved

    def test_settings_object_is_none(self):
        self.assertIsNone(nautilus_meta._open_plus_settings())

    def test_reads_and_writes_degrade_without_raising(self):
        original = nautilus_meta._plus_settings
        nautilus_meta._plus_settings = nautilus_meta._open_plus_settings()
        self.addCleanup(setattr, nautilus_meta, '_plus_settings', original)

        self.assertFalse(nautilus_meta._hide_archived())
        nautilus_meta._set_hide_archived(True)  # silent no-op
        self.assertFalse(nautilus_meta._hide_archived())

    def test_toggle_is_not_offered(self):
        original_running = nautilus_meta._running_as_plus
        original_settings = nautilus_meta._plus_settings
        nautilus_meta._running_as_plus = lambda *args, **kwargs: True
        nautilus_meta._plus_settings = None
        self.addCleanup(setattr, nautilus_meta, '_running_as_plus',
                        original_running)
        self.addCleanup(setattr, nautilus_meta, '_plus_settings',
                        original_settings)

        menu = nautilus_meta.FolderMetaMenu()
        items = menu.get_background_items(_FileInfo('file:///tmp/project'))
        names = [item.kwargs['name'] for item in items]
        self.assertNotIn('FolderMeta::ToggleHideArchived', names)

    def test_toggle_is_offered_when_schema_is_available(self):
        original_running = nautilus_meta._running_as_plus
        nautilus_meta._running_as_plus = lambda *args, **kwargs: True
        self.addCleanup(setattr, nautilus_meta, '_running_as_plus',
                        original_running)

        menu = nautilus_meta.FolderMetaMenu()
        items = menu.get_background_items(_FileInfo('file:///tmp/project'))
        names = [item.kwargs['name'] for item in items]
        self.assertIn('FolderMeta::ToggleHideArchived', names)


class CaptionsMigrationTests(unittest.TestCase):
    """Captions written before the name-zh -> desc rename are carried over.

    Missing this would leave an unresolvable caption line behind *and* make
    the code clobber the user's original caption backup.
    """

    def setUp(self):
        self._saved = nautilus_meta._captions()
        nautilus_meta._clear_captions_backup()

    def tearDown(self):
        nautilus_meta._set_captions(self._saved)
        nautilus_meta._clear_captions_backup()

    def test_legacy_caption_is_renamed_in_place(self):
        nautilus_meta._set_captions(['name-zh'])
        nautilus_meta._sync_captions(True)
        self.assertEqual(nautilus_meta._captions(), ['desc'])

    def test_rename_does_not_clobber_the_backup(self):
        nautilus_meta._save_captions_backup(['none', 'none', 'none'])
        nautilus_meta._set_captions(['name-zh'])
        nautilus_meta._sync_captions(True)
        self.assertEqual(nautilus_meta._load_captions_backup(),
                         ['none', 'none', 'none'])

    def test_backup_with_legacy_name_is_normalized(self):
        nautilus_meta._save_captions_backup(['name-zh', 'size'])
        self.assertEqual(nautilus_meta._load_captions_backup(),
                         ['desc', 'size'])

    def test_duplicates_collapse(self):
        nautilus_meta._set_captions(['name-zh', 'desc'])
        nautilus_meta._sync_captions(True)
        self.assertEqual(nautilus_meta._captions(), ['desc'])

    def test_disabling_drops_the_legacy_caption(self):
        nautilus_meta._set_captions(['name-zh', 'size'])
        nautilus_meta._sync_captions(False)
        self.assertEqual(nautilus_meta._captions(), ['size'])


class RunningAsPlusTests(unittest.TestCase):
    def test_detection_matches_fork_name(self):
        self.assertTrue(nautilus_meta._running_as_plus(
            ['/usr/bin/nautilus-plus']))
        self.assertTrue(nautilus_meta._running_as_plus(
            ['/proc/exe', 'nautilus-plus', '/usr/bin/python3']))
        self.assertFalse(nautilus_meta._running_as_plus(
            ['/usr/bin/nautilus', '--gapplication-service']))
        self.assertFalse(nautilus_meta._running_as_plus([]))

    def test_stock_nautilus_gets_no_hide_menu(self):
        menu = nautilus_meta.FolderMetaMenu()
        folder = _FileInfo('file:///tmp/project')
        items = menu.get_background_items(folder)
        names = [item.kwargs['name'] for item in items]
        self.assertNotIn('FolderMeta::ToggleHideArchived', names)


class MenuFilterTests(unittest.TestCase):
    def test_only_single_local_folder_gets_menu(self):
        menu = nautilus_meta.FolderMetaMenu()
        folder = _FileInfo('file:///tmp/project')
        regular_file = _FileInfo('file:///tmp/notes.txt', directory=False)
        remote_folder = _FileInfo('sftp://host/project')
        items = menu.get_file_items([folder])
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['修改描述', '归档'])
        # Remote members are dropped; the local one still gets the toggle.
        items = menu.get_file_items([folder, remote_folder])
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['归档'])
        self.assertEqual(menu.get_file_items([remote_folder]), [])

    def test_multi_select_shows_only_archive_toggle(self):
        menu = nautilus_meta.FolderMetaMenu()
        folders = [_FileInfo('file:///tmp/a'), _FileInfo('file:///tmp/b')]
        items = menu.get_file_items(folders)
        labels = [item.kwargs['label'] for item in items]
        self.assertEqual(labels, ['归档'])

    def test_all_archived_selection_offers_unarchive(self):
        menu = nautilus_meta.FolderMetaMenu()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / nautilus_meta.YAML_NAME
            path.write_text('archived: true\n', encoding='utf-8')
            folder = _FileInfo('file://' + d)
            items = menu.get_file_items([folder])
            self.assertEqual(items[-1].kwargs['label'], '取消归档')

    def test_single_local_file_gets_annotation_menu(self):
        menu = nautilus_meta.FolderMetaMenu()
        regular_file = _FileInfo('file:///tmp/notes.txt', directory=False)
        items = menu.get_file_items([regular_file])
        self.assertEqual([item.kwargs['label'] for item in items], ['修改注释'])

    def test_remote_file_gets_nothing(self):
        menu = nautilus_meta.FolderMetaMenu()
        remote_file = _FileInfo('sftp://host/notes.txt', directory=False)
        self.assertEqual(menu.get_file_items([remote_file]), [])


class FileDescYamlTests(unittest.TestCase):
    """file-desc holds per-file annotations in the folder's .folder.yaml."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / nautilus_meta.YAML_NAME

    def tearDown(self):
        self.folder.cleanup()

    def read(self):
        return self.path.read_text(encoding='utf-8')

    def test_creates_block_mapping(self):
        nautilus_meta._write_file_desc(self.folder.name, 'notes.txt', '会议记录')
        self.assertEqual(self.read(), 'file-desc:\n  notes.txt: 会议记录\n')

    def test_appends_to_existing_block_mapping(self):
        self.path.write_text('desc: 项目\nfile-desc:\n  a.txt: 甲\n',
                             encoding='utf-8')
        nautilus_meta._write_file_desc(self.folder.name, 'b.txt', '乙')
        self.assertEqual(self.read(),
                         'desc: 项目\nfile-desc:\n  a.txt: 甲\n  b.txt: 乙\n')

    def test_replaces_one_entry_and_keeps_its_comment(self):
        self.path.write_text('file-desc:\n  a.txt: 旧  # keep\n  b.txt: 乙\n',
                             encoding='utf-8')
        nautilus_meta._write_file_desc(self.folder.name, 'a.txt', '新')
        self.assertEqual(self.read(),
                         'file-desc:\n  a.txt: 新  # keep\n  b.txt: 乙\n')

    def test_extends_flow_mapping(self):
        self.path.write_text('file-desc: {a.txt: 甲}\n', encoding='utf-8')
        nautilus_meta._write_file_desc(self.folder.name, 'b.txt', '乙')
        self.assertEqual(self.read(), 'file-desc: {a.txt: 甲, b.txt: 乙}\n')

    def test_quotes_awkward_file_names(self):
        nautilus_meta._write_file_desc(self.folder.name, 'a: b.txt', '含冒号')
        self.assertEqual(self.read(), "file-desc:\n  'a: b.txt': 含冒号\n")

    def test_rejects_duplicate_entries_without_overwriting(self):
        original = 'file-desc:\n  a.txt: 甲\n  a.txt: 乙\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_file_desc(self.folder.name, 'a.txt', '新')
        self.assertEqual(self.read(), original)

    def test_rejects_non_mapping_file_desc(self):
        original = 'file-desc:\n  - a.txt\n'
        self.path.write_text(original, encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_file_desc(self.folder.name, 'a.txt', '甲')
        self.assertEqual(self.read(), original)

    def test_rejects_blank_annotation(self):
        self.path.write_text('file-desc:\n  a.txt: 甲\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            nautilus_meta._write_file_desc(self.folder.name, 'a.txt', '   ')

    def test_removing_an_entry_keeps_the_others(self):
        self.path.write_text(
            'desc: 项目\nfile-desc:\n  a.txt: 甲\n  b.txt: 乙\n',
            encoding='utf-8')
        nautilus_meta._remove_file_desc_in_folder(self.folder.name, 'a.txt')
        self.assertEqual(self.read(), 'desc: 项目\nfile-desc:\n  b.txt: 乙\n')

    def test_removing_the_last_entry_drops_the_key(self):
        self.path.write_text('desc: 项目\nfile-desc:\n  a.txt: 甲\n',
                             encoding='utf-8')
        nautilus_meta._remove_file_desc_in_folder(self.folder.name, 'a.txt')
        self.assertEqual(self.read(), 'desc: 项目\n')

    def test_removing_the_last_entry_drops_an_empty_file(self):
        self.path.write_text('file-desc:\n  a.txt: 甲\n', encoding='utf-8')
        nautilus_meta._remove_file_desc_in_folder(self.folder.name, 'a.txt')
        self.assertFalse(self.path.exists())

    def test_removing_an_unknown_entry_keeps_the_file(self):
        original = 'file-desc:\n  a.txt: 甲\n'
        self.path.write_text(original, encoding='utf-8')
        nautilus_meta._remove_file_desc_in_folder(self.folder.name, 'zzz.txt')
        self.assertEqual(self.read(), original)

    def test_removal_without_a_yaml_file_does_nothing(self):
        nautilus_meta._remove_file_desc_in_folder(self.folder.name, 'a.txt')
        self.assertFalse(self.path.exists())

    def test_lookup_skips_blank_annotations(self):
        self.path.write_text(
            'file-desc:\n  a.txt: 甲\n  空.txt: "  "\n  b.txt: 乙\n',
            encoding='utf-8')
        self.assertEqual(nautilus_meta._yaml_file_descs(self.folder.name),
                         {'a.txt': '甲', 'b.txt': '乙'})


class ApplyAnnotationTests(unittest.TestCase):
    """A file's annotation is read from its parent folder's .folder.yaml."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / nautilus_meta.YAML_NAME
        self.addCleanup(self.folder.cleanup)
        for cache in (nautilus_meta._shown, nautilus_meta._grouped,
                      nautilus_meta._yaml_cache):
            cache.clear()
        self.addCleanup(nautilus_meta._shown.clear)
        self.addCleanup(nautilus_meta._grouped.clear)
        self.addCleanup(nautilus_meta._yaml_cache.clear)

    def item(self, name='notes.txt'):
        uri = 'file://' + os.path.join(self.folder.name, name)
        return _FileInfo(uri, directory=False)

    def write(self, text):
        self.path.write_text(text, encoding='utf-8')
        nautilus_meta._yaml_cache.clear()

    def test_annotation_becomes_the_description_attribute(self):
        self.write('file-desc:\n  notes.txt: 会议记录\n')
        item = self.item()
        nautilus_meta._apply(item)
        self.assertEqual(item.attributes.get('desc'), '会议记录')

    def test_file_without_annotation_gets_none(self):
        self.write('desc: 项目\n')
        item = self.item()
        nautilus_meta._apply(item)
        self.assertNotIn('desc', item.attributes)

    def test_blank_annotation_is_not_shown(self):
        self.write('file-desc:\n  notes.txt: "  "\n')
        item = self.item()
        nautilus_meta._apply(item)
        self.assertNotIn('desc', item.attributes)

    def test_switch_off_hides_annotations(self):
        self.write('file-desc:\n  notes.txt: 会议记录\n')
        nautilus_meta._set_enabled(False)
        self.addCleanup(nautilus_meta._set_enabled, True)
        item = self.item()
        nautilus_meta._apply(item)
        self.assertNotIn('desc', item.attributes)

    def test_removed_annotation_clears_a_shown_one(self):
        self.write('file-desc:\n  notes.txt: 会议记录\n')
        item = self.item()
        nautilus_meta._apply(item)
        self.assertEqual(item.attributes.get('desc'), '会议记录')
        self.write('desc: 项目\n')
        nautilus_meta._apply(item)
        self.assertEqual(item.attributes.get('desc'), '')

    def test_other_files_in_the_folder_are_unaffected(self):
        self.write('file-desc:\n  notes.txt: 会议记录\n')
        other = self.item('other.txt')
        nautilus_meta._apply(other)
        self.assertNotIn('desc', other.attributes)


if __name__ == '__main__':
    unittest.main()
