import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from toolbench.plugin_framework.persistence import atomic_json, atomic_bytes


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_failed_replace_keeps_previous_bytes_and_removes_temporary(self):
        target = self.root / 'state.json'
        target.write_bytes(b'previous')
        with patch('toolbench.plugin_framework.persistence.os.replace', side_effect=OSError('locked')):
            with self.assertRaises(OSError):
                atomic_json(target, {'value': 'new'})
        self.assertEqual(target.read_bytes(), b'previous')
        self.assertEqual(list(self.root.glob('*.tmp')), [])

    def test_private_write_fails_closed_if_protection_cannot_be_applied(self):
        target = self.root / 'secret.json'
        with patch('toolbench.plugin_framework.persistence.protect_private', side_effect=OSError('ACL failed')):
            with self.assertRaises(OSError):
                atomic_json(target, {'token': 'must-not-be-written'}, private=True)
        self.assertFalse(target.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_private_bytes_roundtrip_and_atomic_replacement(self):
        target = self.root / 'private' / 'state.json'
        atomic_json(target, {'token': 'test-only', 'unicode': '中文'}, private=True)
        self.assertEqual(json.loads(target.read_bytes())['unicode'], '中文')
        atomic_bytes(target, b'exact\r\nbytes\x00', private=True)
        self.assertEqual(target.read_bytes(), b'exact\r\nbytes\x00')
        self.assertEqual(list(target.parent.glob('*.tmp')), [])
        if os.name == 'nt':
            # Inspect actual Windows ACLs, not chmod bits or mocked calls.
            import ctypes
            from ctypes import wintypes
            advapi = ctypes.WinDLL('advapi32', use_last_error=True)
            kernel = ctypes.WinDLL('kernel32')
            advapi.GetFileSecurityW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p,
                                               wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
            advapi.GetFileSecurityW.restype = wintypes.BOOL
            convert = advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
            convert.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
            convert.restype = wintypes.BOOL
            kernel.LocalFree.argtypes = [ctypes.c_void_p]
            kernel.LocalFree.restype = ctypes.c_void_p
            for path in (target.parent, target):
                size = wintypes.DWORD()
                advapi.GetFileSecurityW(str(path), 4, None, 0, ctypes.byref(size))
                descriptor = ctypes.create_string_buffer(size.value)
                self.assertTrue(advapi.GetFileSecurityW(str(path), 4, descriptor, size.value, ctypes.byref(size)))
                sddl = wintypes.LPWSTR()
                self.assertTrue(convert(descriptor, 1, 4, ctypes.byref(sddl), None))
                try:
                    flags = 'OICI' if path.is_dir() else ''
                    self.assertEqual(sddl.value, f'D:P(A;{flags};FA;;;SY)(A;{flags};FA;;;OW)')
                finally:
                    kernel.LocalFree(sddl)
        else:
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
