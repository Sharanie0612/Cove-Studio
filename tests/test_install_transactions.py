import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from toolbench.host import Host, ROOT
from toolbench.plugin_framework.transactions import rename_directory


def locked():
    error = PermissionError(13, 'temporary scanner lock')
    error.winerror = 5
    return error


class InstallTransactionsTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.root = Path(self.temp.name)
        self.host = Host(data_dir=self.root / 'data')
        self.manifest = json.loads((ROOT / 'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        self.identity = self.manifest['id']

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def install(self, version):
        self.manifest['version'] = version
        archive = self.root / 'tool.cove-plugin'
        with zipfile.ZipFile(archive, 'w') as package:
            package.writestr('manifest.json', json.dumps(self.manifest))
            package.write(ROOT / 'docs/templates/starter/plugin.py', 'plugin.py')
        ticket = self.host._inspect_package(archive)['ticket']
        return self.host.install_plugin(ticket)

    def test_new_install_recovers_after_transient_windows_access_denial(self):
        actual = Path.rename
        attempts = []
        def rename(source, destination):
            if source.name.startswith('.staging-'):
                attempts.append(source)
                if len(attempts) < 4:
                    raise locked()
            return actual(source, destination)
        with patch.object(Path, 'rename', rename), patch('toolbench.plugin_framework.transactions.time.sleep'):
            result = self.install('0.1.0')
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(attempts), 4)
        self.assertTrue(self.host.invoke(self.identity, 'greet', {'name': 'retry'})['ok'])

    def test_failed_update_rolls_back_original_and_preserves_user_data(self):
        self.assertTrue(self.install('0.1.0')['ok'])
        original = self.host._managed_root / self.identity / 'plugin.py'
        content = original.read_bytes()
        data = self.host.data_dir / self.identity / 'keep.txt'
        data.parent.mkdir(exist_ok=True)
        data.write_text('keep')
        actual = Path.rename
        def rename(source, destination):
            if source.name.startswith('.staging-'):
                raise locked()
            return actual(source, destination)
        with patch.object(Path, 'rename', rename), patch('toolbench.plugin_framework.transactions.time.sleep'):
            result = self.install('0.2.0')
        self.assertFalse(result['ok'])
        self.assertEqual(original.read_bytes(), content)
        self.assertEqual(json.loads(original.with_name('manifest.json').read_text())['version'], '0.1.0')
        self.assertEqual(data.read_text(), 'keep')
        self.assertTrue(self.host.invoke(self.identity, 'greet', {})['ok'])

    def test_failed_rollback_retains_exact_original_in_reported_backup(self):
        self.assertTrue(self.install('0.1.0')['ok'])
        original = (self.host._managed_root / self.identity / 'plugin.py').read_bytes()
        actual = Path.rename
        def rename(source, destination):
            if source.name.startswith(('.staging-', '.backup-')):
                raise locked()
            return actual(source, destination)
        with patch.object(Path, 'rename', rename), patch('toolbench.plugin_framework.transactions.time.sleep'):
            result = self.install('0.2.0')
        self.assertFalse(result['ok'])
        recovery = Path(result['recoveryPath'])
        self.assertTrue(recovery.is_relative_to(self.host._managed_root))
        self.assertEqual((recovery / 'plugin.py').read_bytes(), original)
        self.assertEqual(json.loads((recovery / 'manifest.json').read_text())['version'], '0.1.0')

    def test_non_windows_failures_are_not_retried_or_overwritten(self):
        source = self.root / 'source'
        destination = self.root / 'destination'
        source.mkdir()
        destination.mkdir()
        error = FileExistsError('destination exists')
        with patch.object(Path, 'rename', side_effect=error) as rename, \
             patch('toolbench.plugin_framework.transactions.time.sleep') as sleep:
            with self.assertRaises(FileExistsError):
                rename_directory(source, destination)
        rename.assert_called_once()
        sleep.assert_not_called()
        self.assertTrue(source.is_dir())
        self.assertTrue(destination.is_dir())

    @unittest.skipUnless(os.name == 'nt', 'requires Windows sharing semantics')
    def test_real_windows_directory_lock_is_retried_then_installed(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                      ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
        kernel.CreateFileW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        actual = Path.rename
        observed = []
        def rename(source, destination):
            if not source.name.startswith('.staging-') or observed:
                return actual(source, destination)
            # Share reads and writes, deliberately not DELETE: a real scanner-style lock.
            handle = kernel.CreateFileW(str(source), 0x80000000, 3, None, 3, 0x02000000, None)
            self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
            try:
                return actual(source, destination)
            except OSError as error:
                observed.append(error.winerror)
                raise
            finally:
                kernel.CloseHandle(handle)
        with patch.object(Path, 'rename', rename):
            result = self.install('0.1.0')
        self.assertTrue(result['ok'], result)
        self.assertEqual(len(observed), 1)
        self.assertIn(observed[0], {5, 32, 33})
        self.assertTrue(self.host.invoke(self.identity, 'greet', {})['ok'])
