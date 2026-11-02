from contextlib import contextmanager
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from toolbench.host import Host, ROOT
from toolbench.storage import resolve_storage, migrate, legacy_in_use, MARKER
from toolbench.plugin_framework.environment import worker_environment
from toolbench.mcp_bridge import Adapter
from fixtures_runtime import TERMINAL, write_terminal_fixture


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.root = Path(self.temporary.name)
        self.installation = self.root / 'chosen-drive' / 'Cove'
        self.runtime = self.installation / 'versions' / '0.13.2'
        self.runtime.mkdir(parents=True)
        self.environment = patch.dict(os.environ, {'LOCALAPPDATA': str(self.root / 'profile')})
        self.environment.start()
        os.environ.pop('TOOLBENCH_DATA_DIR', None)
        self.home = patch('pathlib.Path.home', return_value=self.root / 'home')
        self.home.start()
        self.source = self.root / 'profile' / 'Cove'
        self.target = self.installation / 'data'

    def tearDown(self):
        self.home.stop()
        self.environment.stop()
        self.temporary.cleanup()

    @contextmanager
    def frozen(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(self.runtime / 'Cove.exe')):
            yield

    def legacy(self):
        (self.source / 'webview' / 'Local Storage').mkdir(parents=True)
        (self.source / 'webview' / 'Local Storage' / 'draft').write_text('retained draft')
        (self.source / 'installed' / 'empty').mkdir(parents=True)
        (self.source / 'plugin-preferences.json').write_text('{"disabled":[],"interpreters":{},"removed":[]}')

    def test_new_frozen_data_uses_selected_installation_and_not_localappdata(self):
        with self.frozen():
            directory, status = resolve_storage(ROOT)
        self.assertEqual(directory, self.target)
        self.assertEqual(status['mode'], 'installation')
        self.assertFalse(self.source.exists())
        self.assertTrue(directory.is_dir())

    def test_explicit_and_environment_overrides_do_not_trigger_migration(self):
        self.legacy()
        os.environ['TOOLBENCH_DATA_DIR'] = str(self.root / 'environment')
        with self.frozen():
            self.assertEqual(resolve_storage(ROOT)[0], self.root / 'environment')
            self.assertEqual(resolve_storage(ROOT, self.root / 'explicit')[0], self.root / 'explicit')
        self.assertFalse(self.target.exists())
        self.assertFalse((self.source / MARKER).exists())

    def test_development_storage_is_unchanged(self):
        self.assertEqual(resolve_storage(ROOT)[0], ROOT / '.local')
        self.assertFalse(self.source.exists())

    def test_verified_copy_preserves_profiles_drafts_empty_folders_and_originals(self):
        self.legacy()
        self.target.mkdir()  # An empty directory is safe to adopt.
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False):
            directory, status = resolve_storage(ROOT)
        self.assertEqual(directory, self.target)
        self.assertEqual(status['legacyBackup'], str(self.source.resolve()))
        self.assertEqual((directory / 'webview/Local Storage/draft').read_text(), 'retained draft')
        self.assertTrue((directory / 'installed/empty').is_dir())
        self.assertEqual((self.source / 'webview/Local Storage/draft').read_text(), 'retained draft')
        self.assertTrue((self.source / MARKER).exists())
        (directory / 'webview/Local Storage/draft').write_text('new draft')
        with self.frozen():
            self.assertEqual(resolve_storage(ROOT)[0], directory)
        self.assertEqual((directory / 'webview/Local Storage/draft').read_text(), 'new draft')

    def test_managed_interpreters_are_relocated_but_external_choices_are_retained(self):
        self.legacy()
        internal = self.source / 'installed/tool/.venv/Scripts/python.exe'
        external = self.root / 'external/Python/python.exe'
        prefs = self.source / 'plugin-preferences.json'
        prefs.write_text(json.dumps({'interpreters': {'owned': str(internal), 'external': str(external)}}))
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False):
            resolve_storage(ROOT)
        actual = json.loads((self.target / 'plugin-preferences.json').read_text())['interpreters']
        self.assertEqual(actual['owned'], str(self.target / 'installed/tool/.venv/Scripts/python.exe'))
        self.assertEqual(actual['external'], str(external))
        self.assertEqual(json.loads(prefs.read_text())['interpreters']['owned'], str(internal))

    def test_invalid_claim_record_keeps_legacy_data_visible(self):
        self.legacy()
        (self.source / MARKER).write_text('[]')
        with self.frozen():
            directory, status = resolve_storage(ROOT)
        self.assertEqual(directory, self.source)
        self.assertEqual(status['mode'], 'legacy-pending')
        self.assertFalse(self.target.exists())

    def test_busy_legacy_is_not_copied_or_interrupted(self):
        self.legacy()
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=True):
            directory, status = resolve_storage(ROOT)
        self.assertEqual(directory, self.source)
        self.assertEqual(status['mode'], 'legacy-pending')
        self.assertFalse(self.target.exists())
        self.assertFalse((self.source / MARKER).exists())

    def test_changed_source_aborts_copy_and_keeps_working_data(self):
        self.legacy()
        import shutil
        copy = shutil.copy2
        def changed(source, destination):
            result = copy(source, destination)
            if source.name == 'draft':
                source.write_text('concurrent edit')
            return result
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False), patch('toolbench.storage.shutil.copy2', side_effect=changed):
            directory, status = resolve_storage(ROOT)
        self.assertEqual(directory, self.source)
        self.assertEqual(status['mode'], 'legacy-pending')
        self.assertEqual((self.source / 'webview/Local Storage/draft').read_text(), 'concurrent edit')
        self.assertFalse(self.target.exists())
        self.assertEqual(list(self.installation.glob('.cove-data-*')), [])

    def test_corrupted_copy_is_never_published(self):
        self.legacy()
        def corrupt(source, destination):
            destination.write_bytes(b'corrupt')
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False), patch('toolbench.storage.shutil.copy2', side_effect=corrupt):
            directory, _ = resolve_storage(ROOT)
        self.assertEqual(directory, self.source)
        self.assertFalse(self.target.exists())
        self.assertEqual((self.source / 'webview/Local Storage/draft').read_text(), 'retained draft')

    def test_existing_destination_is_never_merged_or_overwritten(self):
        self.legacy()
        self.target.mkdir()
        (self.target / 'new-profile').write_text('keep')
        with self.frozen():
            self.assertEqual(resolve_storage(ROOT)[0], self.target)
        self.assertEqual((self.target / 'new-profile').read_text(), 'keep')
        self.assertFalse((self.target / 'plugin-preferences.json').exists())
        self.assertFalse((self.source / MARKER).exists())

    def test_nested_migration_is_rejected_without_changes(self):
        self.legacy()
        with self.assertRaises(ValueError):
            migrate(self.source, self.source / 'nested-data')
        self.assertFalse((self.source / 'nested-data').exists())

    def test_a_second_installation_does_not_reimport_a_claimed_backup(self):
        self.legacy()
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False):
            resolve_storage(ROOT)
        self.runtime = self.root / 'another-drive' / 'Cove' / 'versions' / '0.13.2'
        self.runtime.mkdir(parents=True)
        with self.frozen():
            directory, _ = resolve_storage(ROOT)
        self.assertFalse((directory / 'plugin-preferences.json').exists())
        self.assertEqual((self.source / 'webview/Local Storage/draft').read_text(), 'retained draft')

    def test_busy_startup_does_not_replace_an_existing_bridge(self):
        from toolbench.storage import StorageBusy
        old=Host(data_dir=self.source)
        try:
            descriptor=self.source/'mcp-bridge.json'
            before=descriptor.read_bytes()
            with self.frozen():
                with self.assertRaises(StorageBusy):Host()
            self.assertEqual(descriptor.read_bytes(),before)
            self.assertFalse(self.target.exists())
        finally:old.close()

    def process(self, name, executable):
        process = Mock()
        process.info = {'pid': os.getpid() + 100000, 'name': name}
        process.exe.return_value = str(executable)
        process.environ.return_value = {'LOCALAPPDATA': str(self.root / 'profile')}
        process.cmdline.return_value = []
        return process

    def test_waiting_stable_launcher_does_not_block_its_child_migration(self):
        self.legacy()
        (self.installation / '.cove-install').write_text('cove-preview-v1')
        (self.installation / '.cove-current').write_text('0.13.2')
        (self.runtime / '.cove-runtime').write_text('cove-runtime-v1')
        (self.runtime / 'Cove.exe').touch()
        launcher = self.process('Cove.exe', self.installation / 'Cove.exe')
        # Launcher environment inspection is unnecessary, even when denied.
        import psutil
        launcher.environ.side_effect = psutil.AccessDenied(launcher.info['pid'])
        with self.frozen(), patch('psutil.process_iter', return_value=[launcher]):
            host = Host()
        try:
            self.assertEqual(host.data_dir, self.target)
            self.assertEqual((self.target / 'webview/Local Storage/draft').read_text(), 'retained draft')
            self.assertEqual((self.source / 'webview/Local Storage/draft').read_text(), 'retained draft')
        finally:
            host.close()

    def test_modern_desktop_only_blocks_legacy_when_explicitly_using_it(self):
        (self.runtime / 'runtime-manifest.json').write_text('{"version":"0.13.2"}')
        process = self.process('Cove.exe', self.runtime / 'Cove.exe')
        with patch('psutil.process_iter', return_value=[process]):
            self.assertFalse(legacy_in_use(self.source))
            process.environ.return_value['TOOLBENCH_DATA_DIR'] = str(self.source)
            self.assertTrue(legacy_in_use(self.source))

    def test_actual_legacy_desktop_and_worker_still_block_migration(self):
        desktop = self.process('Cove.exe', self.root / 'old/Cove.exe')
        worker = self.process('Cove-worker.exe', self.root / 'old/Cove-worker.exe')
        worker.cmdline.return_value = ['Cove-worker.exe', '--worker', 'plugin', str(self.source / 'test.tool')]
        for process in (desktop, worker):
            with patch('psutil.process_iter', return_value=[process]):
                self.assertTrue(legacy_in_use(self.source))

    def test_unrelated_protected_python_does_not_block_but_managed_worker_does(self):
        import psutil
        process = self.process('python.exe', self.root / 'unrelated/python.exe')
        process.cmdline.side_effect = psutil.AccessDenied(process.info['pid'])
        with patch('psutil.process_iter', return_value=[process]):
            self.assertFalse(legacy_in_use(self.source))
            process.exe.return_value = str(self.source / 'installed/tool/.venv/Scripts/python.exe')
            self.assertTrue(legacy_in_use(self.source))

    def test_inaccessible_cove_desktop_remains_conservatively_blocked(self):
        import psutil
        process = self.process('Cove.exe', self.root / 'old/Cove.exe')
        process.exe.side_effect = psutil.AccessDenied(process.info['pid'])
        with patch('psutil.process_iter', return_value=[process]):
            self.assertTrue(legacy_in_use(self.source))

    def test_startup_notice_uses_the_shared_translation_catalog(self):
        from toolbench.native_messages import t
        message='旧数据目录仍在使用。请先正常退出相关 Cove 窗口和插件任务，再重新打开以迁移数据。'
        with patch('toolbench.native_messages._language',return_value='en-US'):
            self.assertIn('previous data folder',t(message))
        with patch('toolbench.native_messages._language',return_value='zh-CN'):
            self.assertEqual(t(message),message)

    def test_running_legacy_adapter_reconnects_after_migration_and_respects_revocation(self):
        old = Host(data_dir=self.source)
        try:
            write_terminal_fixture(self.source / 'installed' / 'terminal')
            old.rescan_plugins()
            old.assistant_allow([TERMINAL])
            name = next(t['name'] for t in old._assistant_broker.definitions() if t['readOnly'])
            adapter = Adapter(self.source / 'mcp-bridge.json', io.StringIO())
            self.assertTrue(adapter.refresh())
        finally:
            old.close()
        with self.frozen(), patch('toolbench.storage.legacy_in_use', return_value=False):
            current = Host()
        try:
            self.assertEqual(current.data_dir, self.target)
            self.assertTrue(adapter.call(name, {})['ok'])
            current.assistant_allow([])
            self.assertEqual(adapter.refresh(), [])
            self.assertEqual(json.loads((self.source / 'ai-tools.json').read_text())['plugins'], [])
            self.assertTrue(current.plugin_action('dev.cove.mcp', 'disable')['ok'])
            self.assertFalse((self.source / 'mcp-bridge.json').exists())
            self.assertEqual(json.loads((self.source / 'mcp-tools.json').read_text())['tools'], [])
        finally:
            adapter.close()
            current.close()

    def test_child_temporary_and_cache_paths_are_local_without_changing_parent_environment(self):
        original = dict(os.environ)
        env = worker_environment(self.root / 'plugin-data')
        self.assertEqual(dict(os.environ), original)
        for name in ('TEMP','TMP','TMPDIR','PIP_CACHE_DIR','XDG_CACHE_HOME'):
            self.assertTrue(Path(env[name]).is_relative_to(self.root / 'plugin-data'))
        result = subprocess.run([sys.executable, '-c', 'import tempfile; print(tempfile.gettempdir())'],
                                cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(Path(result.stdout.strip()), Path(env['TMP']))


if __name__ == '__main__':
    unittest.main()
