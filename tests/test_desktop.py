from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import ctypes

from toolbench.host import Host, ROOT
from toolbench.desktop import configure_native_frame


class FakeWindow:
    def __init__(self, host):
        self.host = host
        self.calls = []

    def minimize(self):
        self.calls.append('minimize')

    def maximize(self):
        self.calls.append('maximize')
        self.host._maximized = True

    def restore(self):
        self.calls.append('restore')
        self.host._maximized = False

    def destroy(self):
        self.calls.append('destroy')


class DesktopTests(unittest.TestCase):
    def test_locale_updates_only_native_labels_and_preserves_activity(self):
        self.window.localization = {'windows.fileFilter.allFiles': 'All files'}
        self.host._connected['test.connection'] = True
        self.assertTrue(self.host.set_locale('en-US')['ok'])
        self.assertEqual(self.window.localization['global.cancel'], 'Cancel')
        self.assertTrue(self.host.set_locale('zh-CN')['ok'])
        self.assertEqual(self.window.localization['global.cancel'], '取消')
        self.assertFalse(self.host.set_locale('invalid')['ok'])
        self.assertEqual(self.host._ui_locale, 'zh-CN')
        self.assertTrue(self.host._connected['test.connection'])
        self.assertEqual(self.window.calls, [])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.host = Host(data_dir=Path(self.temp.name))
        self.window = FakeWindow(self.host)
        self.host._window = self.window

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def test_close_guard_preserves_active_connection_until_confirmed(self):
        self.host._connected['test.connection'] = True
        result = self.host.window_action('close')
        self.assertTrue(result['result']['needsConfirmation'])
        self.assertEqual(result['result']['connections'], 1)
        self.assertFalse(self.window.calls)
        self.assertTrue(self.host.window_action('close', True)['ok'])
        self.assertEqual(self.window.calls, ['destroy'])

    def test_window_operations_and_maximize_toggle(self):
        self.host.window_action('minimize')
        self.host.window_action('maximize')
        self.host.window_action('maximize')
        self.assertEqual(self.window.calls, ['minimize', 'maximize', 'restore'])

    def test_unknown_window_action_is_rejected(self):
        self.assertFalse(self.host.window_action('arbitrary-action')['ok'])
        self.assertFalse(self.window.calls)

    def test_native_dwm_rounding_removes_binary_region_and_hides_border(self):
        window = MagicMock()
        window.native.Handle.ToInt64.return_value = 123
        dll = MagicMock()
        dll.dwmapi.DwmSetWindowAttribute.return_value = 0
        with patch('toolbench.desktop.set_maximized_bounds'), patch('toolbench.desktop.uses_alpha_frame', return_value=False), patch.object(ctypes, 'windll', dll):
            self.assertEqual(configure_native_frame(window), 'native')
        dll.user32.SetWindowRgn.assert_called_once_with(123, None, False)
        self.assertEqual([call.args[1] for call in dll.dwmapi.DwmSetWindowAttribute.call_args_list], [33, 34])
        dll.gdi32.CreateRoundRectRgn.assert_not_called()

    def test_unavailable_native_rounding_falls_back_without_binary_cutout(self):
        window = MagicMock()
        window.native.Handle.ToInt64.return_value = 123
        dll = MagicMock()
        dll.dwmapi.DwmSetWindowAttribute.return_value = -1
        with patch('toolbench.desktop.set_maximized_bounds'), patch('toolbench.desktop.uses_alpha_frame', return_value=False), patch.object(ctypes, 'windll', dll):
            self.assertEqual(configure_native_frame(window), 'opaque')
        dll.gdi32.CreateRoundRectRgn.assert_not_called()
