import unittest
from unittest.mock import Mock, patch
import types
import os
from toolbench.desktop import DesktopApi


@unittest.skipUnless(os.name == 'nt', 'Windows native interaction')
class NativeInteractionTests(unittest.TestCase):
    def test_size_is_dispatched_on_ui_thread_with_current_pointer(self):
        host=DesktopApi();host._maximized=False;host._window=Mock()
        host._window.native.Handle.ToInt64.return_value=1234567890123
        host._window.native.BeginInvoke.side_effect=lambda callback:callback()
        user=Mock();user.GetAsyncKeyState.return_value=-32768
        def pointer(value):value._obj.x=700;value._obj.y=400
        user.GetCursorPos.side_effect=pointer
        with patch.dict('sys.modules',{'System':types.SimpleNamespace(Action=lambda callback:callback)}), patch('ctypes.windll',types.SimpleNamespace(user32=user)):
            self.assertTrue(host.resize_window('e')['ok'])
            user.PostMessageW.assert_called_once_with(1234567890123,0x112,0xF002,(400<<16)|700)
            host._window.native.BeginInvoke.assert_called_once()
            host.resize_window('s')
            user.PostMessageW.assert_called_with(1234567890123,0x112,0xF006,(400<<16)|700)
            user.PostMessageW.reset_mock();user.GetAsyncKeyState.return_value=0
            host.resize_window('s');user.PostMessageW.assert_not_called()
