import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from toolbench.maintenance import preflight, installed_processes, check_files, installation_in_progress


class MaintenanceTests(unittest.TestCase):
    def test_legacy_icon_cleanup_is_scoped_to_owned_installation(self):
        from toolbench.maintenance import cleanup_legacy_icons
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with self.assertRaises(ValueError):
                cleanup_legacy_icons(root)
            (root / '.cove-install').write_text('cove-preview-v1')
            for name in ('Cove-0.7.4.ico', 'Cove-0.7.6.ico', 'Cove.ico', 'personal.ico', 'Cove-artwork.ico'):
                (root / name).write_bytes(b'icon')
            self.assertEqual(set(cleanup_legacy_icons(root)), {'Cove-0.7.4.ico', 'Cove-0.7.6.ico', 'Cove.ico'})
            self.assertTrue((root / 'personal.ico').exists())
            self.assertTrue((root / 'Cove-artwork.ico').exists())

    def test_versioned_upgrade_checks_all_desktops_but_preserves_old_adapter_files(self):
        with tempfile.TemporaryDirectory() as folder:
            install=Path(folder)/'app';install.mkdir()
            payload=Path(folder)/'payload';payload.mkdir()
            (install/'Cove-worker.exe').write_bytes(b'old locked adapter')
            (payload/'Cove-worker.exe').write_bytes(b'new adapter')
            with patch('toolbench.maintenance.installed_processes',return_value=[]) as processes, patch('toolbench.maintenance.check_files',return_value=[]) as check, patch('toolbench.maintenance.request_close') as close:
                result=preflight(install,payload,version='0.7.2',close=True)
                self.assertTrue(result['ready'])
                self.assertEqual(processes.call_args_list[0].args, (install.resolve(),))
                self.assertEqual(processes.call_args_list[0].kwargs, {'recursive': True, 'gui_only': True})
                self.assertEqual(processes.call_args_list[1].args, (install.resolve()/'versions/0.7.2',))
                check.assert_called_once_with(install.resolve(),['Uninstall.exe', 'Cove.exe'])
                close.assert_not_called()
                self.assertEqual((install/'Cove-worker.exe').read_bytes(),b'old locked adapter')

    def test_mapped_legacy_icons_are_archived_without_overwriting_other_files(self):
        from toolbench.maintenance import cleanup_legacy_icons
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / '.cove-install').write_text('cove-preview-v1')
            icon = root / 'Cove-0.7.4.ico'
            icon.write_bytes(b'mapped icon')
            archive = root / '.cove-retired-icons'
            archive.mkdir()
            (archive / icon.name).write_bytes(b'previous backup')
            with patch.object(Path, 'unlink', side_effect=PermissionError('mapped icon')):
                self.assertEqual(cleanup_legacy_icons(root), [icon.name])
            self.assertFalse(icon.exists())
            self.assertEqual((archive / icon.name).read_bytes(), b'previous backup')
            self.assertEqual([p.read_bytes() for p in archive.glob('*-Cove-0.7.4.ico')], [b'mapped icon'])

    def test_identical_reinstall_reuses_active_files_but_mismatch_does_not(self):
        with tempfile.TemporaryDirectory() as folder:
            install=Path(folder)/'app';target=install/'versions/0.7.2';target.mkdir(parents=True)
            payload=Path(folder)/'payload';payload.mkdir()
            for root in (target,payload): (root/'Cove.exe').write_bytes(b'exact same build')
            def running(path, **options):
                return [] if options.get('gui_only') else [Mock(pid=1)]
            with patch('toolbench.maintenance.installed_processes',side_effect=running) as processes,patch('toolbench.maintenance.check_files',return_value=[]),patch('toolbench.maintenance.request_close') as close:
                self.assertTrue(preflight(install,payload,version='0.7.2')['reusePayload'])
                processes.assert_called_once_with(install.resolve(), recursive=True, gui_only=True)
                close.assert_not_called()
                (payload/'Cove.exe').write_bytes(b'different build')
                self.assertFalse(preflight(install,payload,version='0.7.2')['ready'])
                close.assert_not_called()

    def test_old_desktop_blocks_new_version_and_identical_reinstall_without_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); install = root/'app'; payload = root/'payload'; payload.mkdir()
            desktop = Mock(pid=123)
            with patch('toolbench.maintenance.installed_processes', return_value=[desktop]), \
                 patch('toolbench.maintenance.request_close') as close, \
                 patch('toolbench.maintenance.check_files') as probe:
                result = preflight(install, payload, version='0.12.10')
                self.assertEqual(result['reason'], 'desktop-running')
                close.assert_not_called(); probe.assert_not_called()
                result = preflight(install, payload, version='0.12.10', close=True, wait_seconds=0)
                self.assertFalse(result['ready']); close.assert_called_once_with([desktop])
                desktop.kill.assert_not_called(); desktop.terminate.assert_not_called()
                self.assertFalse(install.exists())

    def test_new_version_waits_for_all_desktops_to_exit_normally(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); install = root/'app'; payload = root/'payload'; payload.mkdir()
            desktops = [Mock(pid=123), Mock(pid=456)]
            with patch('toolbench.maintenance.installed_processes', side_effect=[desktops, [], []]), \
                 patch('toolbench.maintenance.request_close') as close:
                self.assertTrue(preflight(install, payload, version='0.12.10', close=True)['ready'])
                close.assert_called_once_with(desktops)

    def test_activation_verifies_payload_and_preserves_pointer_on_corruption(self):
        import hashlib, json
        from toolbench import __version__
        from toolbench.maintenance import activate_runtime
        from toolbench.paths import active_runtime
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); runtime = root/'versions'/__version__; runtime.mkdir(parents=True)
            (root/'.cove-install').write_text('cove-preview-v1')
            (root/'Cove.exe').write_bytes(b'launcher')
            (runtime/'.cove-runtime').write_text('cove-runtime-v1')
            files = {'Cove.exe':b'desktop', 'Cove-worker.exe':b'worker', '_internal/dist/index.html':b'ui',
                     '_internal/dist/build-manifest.json':json.dumps({'version':__version__}).encode()}
            for name, data in files.items():
                path=runtime/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
            manifest={'version':__version__,'launcherSha256':hashlib.sha256(b'launcher').hexdigest(),
                      'files':[{'path':name,'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()]}
            (runtime/'runtime-manifest.json').write_text(json.dumps(manifest))
            with patch('toolbench.maintenance.installed_processes',return_value=[]):
                self.assertTrue(activate_runtime(root,__version__)['ready'])
                self.assertEqual(active_runtime(root),runtime)
                (runtime/'Cove.exe').write_bytes(b'corrupted')
                with self.assertRaisesRegex(ValueError,'校验失败'):activate_runtime(root,__version__)
                self.assertEqual((root/'.cove-current').read_text(),__version__)
                (root/'.cove-current').write_text('../outside')
                with self.assertRaises(ValueError):active_runtime(root)

    def test_version_cannot_escape_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            payload=Path(folder)/'payload';payload.mkdir()
            for version in ('../outside','0.7.2/../x','',r'..\outside'):
                from toolbench.maintenance import runtime_path
                with self.assertRaises(ValueError): runtime_path(Path(folder)/'app',version)

    def test_checks_exact_installation_and_does_not_kill_or_close(self):
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder) / 'app'
            payload = Path(folder) / 'payload'
            payload.mkdir()
            process = Mock(pid=123)
            with patch('toolbench.maintenance.installed_processes', return_value=[process]), patch('toolbench.maintenance.request_close') as close:
                result = preflight(install, payload)
                self.assertFalse(result['ready'])
                self.assertEqual(result['pids'], [123])
                close.assert_not_called()
                process.kill.assert_not_called()
                process.terminate.assert_not_called()

    def test_explicit_close_waits_for_app_then_checks_files(self):
        with tempfile.TemporaryDirectory() as folder:
            install = Path(folder) / 'app'
            install.mkdir()
            payload = Path(folder) / 'payload'
            payload.mkdir()
            (payload / 'Cove.exe').write_bytes(b'fixture')
            with patch('toolbench.maintenance.installed_processes', side_effect=[[Mock(pid=1)], []]), patch('toolbench.maintenance.request_close') as close, patch('toolbench.maintenance.check_files', return_value=[]) as check:
                self.assertTrue(preflight(install, payload, close=True)['ready'])
                close.assert_called_once()
                check.assert_called_once_with(install.resolve(), ['Cove.exe'])

    def test_filters_unrelated_copy_by_full_path(self):
        install = Path.cwd() / 'app'
        own = Mock(info={'name': 'Cove.exe'})
        own.exe.return_value = str(install / 'Cove.exe')
        other = Mock(info={'name': 'Cove.exe'})
        other.exe.return_value = str(Path.cwd() / 'another-app/Cove.exe')
        with patch('toolbench.maintenance.psutil.process_iter', return_value=[own, other]):
            self.assertEqual(installed_processes(install), [own])

    @unittest.skipUnless(os.name == 'nt', 'Windows file sharing and mutex semantics')
    def test_locked_file_prevents_write_without_changing_it(self):
        import ctypes
        from ctypes import wintypes
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            target = root / 'Cove.exe'
            target.write_bytes(b'old app, retain exactly')
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            kernel.CreateFileW.restype = wintypes.HANDLE
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.CreateFileW(str(target), 0x80000000, 1, None, 3, 0x80, None)
            self.assertNotEqual(handle, ctypes.c_void_p(-1).value)
            try:
                self.assertEqual(check_files(root, ['Cove.exe']), ['Cove.exe'])
                self.assertEqual(target.read_bytes(), b'old app, retain exactly')
            finally:
                kernel.CloseHandle(handle)
            self.assertEqual(check_files(root, ['Cove.exe']), [])

    @unittest.skipUnless(os.name == 'nt', 'Windows named mutex')
    def test_upgrade_gate_detects_installer_mutex(self):
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        kernel.CreateMutexW.restype = wintypes.HANDLE
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.CreateMutexW(None, False, 'Local\\Cove.Workbench.Upgrade')
        try:
            self.assertTrue(installation_in_progress())
        finally:
            kernel.CloseHandle(handle)
