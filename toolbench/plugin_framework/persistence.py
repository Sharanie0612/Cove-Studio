"""Atomic local persistence; private data is protected before any bytes are written."""
from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import uuid


def reject_linked_path(path: Path):
    """Never change private permissions through a symlink or Windows junction."""
    for entry in (path, *path.parents):
        try:
            info = entry.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('私密数据目录或文件不能使用符号链接或目录联接')


def protect_private(path: Path):
    """Restrict a Cove-owned path to its owner and SYSTEM, not other local users.

    This deliberately does not claim isolation from processes running as the owner.
    Directories propagate the restriction to new children before secret files exist.
    """
    path = Path(path)
    reject_linked_path(path)
    if os.name != 'nt':
        path.chmod(0o700 if path.is_dir() else 0o600)
        return
    import ctypes
    from ctypes import wintypes

    advapi = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
                        ctypes.POINTER(wintypes.DWORD)]
    convert.restype = wintypes.BOOL
    apply = advapi.SetFileSecurityW
    apply.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p]
    apply.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    inherit = 'OICI' if path.is_dir() else ''
    descriptor = ctypes.c_void_p()
    if not convert(f'D:P(A;{inherit};FA;;;SY)(A;{inherit};FA;;;OW)', 1,
                   ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        # A protected DACL must not inherit a broader permission from the parent.
        if not apply(str(path), 0x00000004 | 0x80000000, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.LocalFree(descriptor)


def atomic_bytes(path: Path, content: bytes, *, private=False):
    path = Path(path)
    if private:
        reject_linked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('不能替换符号链接文件')
    if private:
        protect_private(path.parent)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_BINARY', 0),
                             0o600 if private else 0o666)
        with os.fdopen(descriptor, 'wb') as stream:
            if private:
                protect_private(temporary)
            stream.write(content)
            stream.flush()
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_text(path: Path, content: str, *, private=False):
    atomic_bytes(path, content.encode('utf-8'), private=private)


def atomic_json(path: Path, value, *, private=False):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2), private=private)
