from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from toolbench.setup_ui import SetupBridge


class SetupUiTests(unittest.TestCase):
    def test_progress_tracks_real_files_and_engine_phase(self):
        from toolbench import __version__
        import json
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); runtime=root/'runtime'; runtime.mkdir()
            (runtime/'a').write_text('abc');(runtime/'b').write_text('defg')
            (runtime/'runtime-manifest.json').write_text(json.dumps({'files':[{'path':'a'},{'path':'b'}]}))
            target=root/'app'; files=target/'versions'/__version__;files.mkdir(parents=True)
            (files/'a').write_text('abc');(files/'b').write_text('d')
            progress=root/'progress.ini';progress.write_text('[Setup]\nPhase=copying\n',encoding='utf-16')
            bridge=SetupBridge('setup.exe',target,'en-US',True)
            bridge._runtime=runtime;bridge._install_target=target;bridge._progress_path=progress
            value=bridge.progress()
            self.assertEqual((value['completedFiles'],value['totalFiles'],value['percent']),(1,2,45))
            progress.write_text('[Setup]\nPhase=verifying\n',encoding='utf-16')
            self.assertEqual(bridge.progress()['percent'],85)
            bridge._completed=True;self.assertEqual(bridge.progress()['percent'],100)

    def test_finish_only_creates_opted_in_shortcut(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);bridge=SetupBridge('setup.exe',root,'en-US',True)
            bridge._completed=True;bridge._window=Mock()
            with patch('toolbench.windows_shortcuts.create_desktop_shortcut') as create:
                self.assertTrue(bridge.finish(False,False)['ok']);create.assert_not_called()
                self.assertTrue(bridge.finish(False,True)['ok'])
                create.assert_called_once_with(root,root/'_shortcuts/Desktop')
    def test_license_path_and_close_consent_gate_backend(self):
        bridge=SetupBridge('setup.exe',r'C:\Cove','en-US',True)
        with patch('toolbench.setup_ui.preflight') as check, patch('toolbench.setup_ui.subprocess.Popen') as launch:
            self.assertFalse(bridge.install(r'C:\Cove')['ok'])
            self.assertFalse(bridge.install('relative',True)['ok'])
            self.assertFalse(bridge.install('C:\\bad" /S',True)['ok'])
            check.assert_not_called(); launch.assert_not_called()
            check.return_value={'ready':False,'reason':'desktop-running'}
            self.assertEqual(bridge.install(r'C:\Cove',True)['code'],'DESKTOP_RUNNING')
            self.assertFalse(check.call_args.kwargs['close'])
            self.assertEqual(bridge.install(r'C:\Cove',True,True)['code'],'DESKTOP_RUNNING')
            self.assertTrue(check.call_args.kwargs['close']); launch.assert_not_called()
            self.assertFalse(bridge._busy)

    def test_backend_is_serial_and_successful_only_after_exit(self):
        bridge=SetupBridge('setup.exe',r'C:\Cove Folder','en-US',True)
        worker=Mock(); worker.wait.return_value=5
        with patch('toolbench.setup_ui.preflight',return_value={'ready':True}), patch('toolbench.setup_ui.subprocess.Popen',return_value=worker) as launch:
            self.assertFalse(bridge.install(r'C:\Cove Folder',True)['ok'])
            self.assertFalse(bridge._completed)
            worker.wait.return_value=0
            self.assertTrue(bridge.install(r'C:\Cove Folder',True)['ok'])
            self.assertTrue(bridge._completed)
            self.assertIn('/TESTMODE',launch.call_args.args[0])
            self.assertTrue(launch.call_args.args[0].endswith('/D=C:\\Cove Folder'))
            self.assertNotIn('timeout',launch.call_args.kwargs)
            bridge._lock.acquire()
            try: self.assertEqual(bridge.install(r'C:\Cove Folder',True)['code'],'BUSY')
            finally: bridge._lock.release()
        bridge._window=Mock(); bridge._busy=True
        bridge.window_action('close'); bridge._window.destroy.assert_not_called()
        bridge._busy=False; bridge.window_action('close'); bridge._window.destroy.assert_called_once()
