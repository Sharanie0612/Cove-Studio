"""Installer preflight, run from its temporary runtime before touching an install.

Only requests WM_CLOSE after the installer obtains consent. Never kills a process.
The helper's exit codes are consumed by NSIS: 0 ready, 10 busy, 20 check failed.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import hashlib
import os
from pathlib import Path
import sys
import re
import time
import uuid

import psutil


def installation_in_progress():
    if os.name != 'nt':
        return False
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenMutexW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenMutexW(0x00100000, False, 'Local\\Cove.Workbench.Upgrade')
    if handle:
        kernel.CloseHandle(handle)
        return True
    return False


def installed_processes(installation: Path, recursive=False, gui_only=False):
    expected = {os.path.normcase(str(installation / name)) for name in ('Cove.exe', 'Cove-worker.exe')}
    matches = []
    for process in psutil.process_iter(['pid', 'name']):
        try:
            if (process.info['name'] or '').lower() not in ('cove.exe', 'cove-worker.exe'):
                continue
            if gui_only and (process.info['name'] or '').lower() != 'cove.exe':
                continue
            executable = Path(process.exe()).resolve()
            relative = executable.relative_to(installation) if executable.is_relative_to(installation) else None
            versioned = recursive and relative and len(relative.parts) == 3 and relative.parts[0] == 'versions' and executable.name.lower() in ('cove.exe','cove-worker.exe')
            if os.path.normcase(str(executable)) in expected or versioned:
                matches.append(process)
        except psutil.NoSuchProcess:
            continue
        except psutil.AccessDenied:
            # Do not silently allow an upgrade when a Cove process cannot be checked.
            raise RuntimeError('无法检查 Cove 进程，请用安装时的账户重试')
    return matches


def request_close(processes):
    from ctypes import wintypes
    desktops = {}
    for process in processes:
        try:
            if process.name().lower() == 'cove.exe' and process.is_running():
                desktops[process.pid] = process
        except psutil.NoSuchProcess:
            pass
    user = ctypes.WinDLL('user32', use_last_error=True)
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user.IsWindowVisible.argtypes = [wintypes.HWND]

    @callback_type
    def visit(handle, _):
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(handle, ctypes.byref(pid))
        process = desktops.get(pid.value)
        if process and process.is_running() and user.IsWindowVisible(handle):
            user.PostMessageW(handle, 0x10, 0, 0)  # WM_CLOSE follows shared active-work confirmation.
        return True

    user.EnumWindows(visit, 0)


def check_files(installation: Path, relative_files: list[str]):
    """Probe write access without modifying files, including mapped DLL/EXE locks."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                  wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    locked = []
    for relative in relative_files:
        path = (installation / relative).resolve()
        if not path.is_relative_to(installation):
            raise ValueError('安装文件路径无效')
        if not path.exists():
            continue
        # GENERIC_WRITE, share read/write/delete, OPEN_EXISTING: never truncates.
        handle = kernel.CreateFileW(str(path), 0x40000000, 7, None, 3, 0x80, None)
        if handle == ctypes.c_void_p(-1).value:
            error = ctypes.get_last_error()
            if error in (32, 33):
                locked.append(relative)
            else:
                raise OSError(error, f'无法更新文件 {relative}')
        else:
            kernel.CloseHandle(handle)
    return locked


def runtime_path(installation, version):
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('安装版本无效')
    target = installation / 'versions' / version
    # Refuse linked installation components rather than write through a junction.
    for path in (installation, installation/'versions', installation/'plugins', target):
        if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
            raise ValueError('安装目录不能使用符号链接或目录联接')
    return target


def identical_payload(target, payload, files):
    if not files:
        return False
    for relative in files:
        source, destination = payload / relative, target / relative
        if not destination.is_file() or destination.is_symlink() or destination.stat().st_size != source.stat().st_size:
            return False
        if hashlib.sha256(destination.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            return False
    return True


def preflight(installation: Path, payload: Path, close=False, wait_seconds=8, version=None):
    original = installation.absolute()
    if original.is_symlink() or (hasattr(original,'is_junction') and original.is_junction()):
        raise ValueError('安装目录不能使用符号链接或目录联接')
    installation = installation.resolve()
    if installation == Path(installation.anchor) or installation == payload.resolve():
        raise ValueError('请选择有效的软件安装目录')
    files = [path.relative_to(payload).as_posix() for path in payload.rglob('*') if path.is_file()]
    if version:
        target = runtime_path(installation, version)
        # A new version must never be published while an older desktop is still
        # displaying its cached UI. External MCP adapters keep their own files.
        desktops = installed_processes(installation, recursive=True, gui_only=True)
        if desktops and close:
            request_close(desktops)
            deadline = time.monotonic() + wait_seconds
            while desktops and time.monotonic() < deadline:
                time.sleep(.2)
                desktops = installed_processes(installation, recursive=True, gui_only=True)
        if desktops:
            return {'ready': False, 'reason': 'desktop-running', 'pids': [p.pid for p in desktops]}
        root_locks = check_files(installation, ['Uninstall.exe', 'Cove.exe']) if installation.exists() else []
        if root_locks:
            return {'ready':False,'reason':'locked','files':root_locks}
        if identical_payload(target, payload, files):
            return {'ready':True,'reusePayload':True,'reason':'identical','runtime':str(target)}
        # Old versions, including MCP processes owned by Codex, keep their exact
        # files. Probe only the runtime this installer is going to write.
        installation = target
    running = installed_processes(installation)
    if running and close:
        request_close(running)
        deadline = time.monotonic() + wait_seconds
        while running and time.monotonic() < deadline:
            time.sleep(.2)
            running = installed_processes(installation)
    if running:
        return {'ready': False, 'reason': 'running', 'pids': [process.pid for process in running]}
    locked = check_files(installation, files) if installation.exists() else []
    return {'ready': not locked, 'reason': 'locked' if locked else '', 'files': locked[:8]}


def verify_runtime_payload(runtime, version):
    """Verify extracted bytes before switching the installation's active entry."""
    manifest = json.loads((runtime / 'runtime-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('version') != version or not isinstance(manifest.get('files'), list):
        raise ValueError('安装版本与运行文件不一致')
    required = {'Cove.exe', 'Cove-worker.exe', '_internal/dist/index.html', '_internal/dist/build-manifest.json'}
    if not required.issubset({item['path'] for item in manifest['files']}):
        raise ValueError('运行文件清单不完整')
    if json.loads((runtime / '_internal/dist/build-manifest.json').read_text(encoding='utf-8')).get('version') != version:
        raise ValueError('界面版本与运行版本不一致')
    for item in manifest['files']:
        relative = Path(item['path'])
        path = runtime / relative
        if relative.is_absolute() or '..' in relative.parts or path.is_symlink() or not path.resolve().is_relative_to(runtime.resolve()):
            raise ValueError('运行文件路径无效')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(f'运行文件校验失败: {relative}')
    return len(manifest['files'])


def activate_runtime(installation, version, shortcut_dirs=()):
    from toolbench import __version__
    from toolbench.plugin_framework.persistence import atomic_text
    from toolbench.windows_shortcuts import repair_shortcuts
    root = installation.resolve()
    runtime = runtime_path(root, version)
    if version != __version__ or (root / '.cove-install').read_text(encoding='utf-8') != 'cove-preview-v1':
        raise ValueError('安装目录或运行版本不一致')
    if not (root / 'Cove.exe').is_file():
        raise ValueError('固定启动入口缺失')
    if installed_processes(root, recursive=True, gui_only=True):
        raise ValueError('旧版 Cove 主窗口仍在运行，请正常退出后重试')
    count = verify_runtime_payload(runtime, version)
    manifest = json.loads((runtime / 'runtime-manifest.json').read_text(encoding='utf-8'))
    if hashlib.sha256((root / 'Cove.exe').read_bytes()).hexdigest() != manifest.get('launcherSha256'):
        raise ValueError('固定启动入口校验失败')
    repaired = repair_shortcuts(root, shortcut_dirs)
    atomic_text(root / '.cove-current', version)
    return {'ready': True, 'version': version, 'verifiedFiles': count, 'shortcutsUpdated': repaired}


def cleanup_legacy_icons(installation):
    """Remove only legacy Cove icons in an installer-owned top-level directory."""
    if installation.is_symlink() or (hasattr(installation, 'is_junction') and installation.is_junction()):
        raise ValueError('安装目录不能使用符号链接或目录联接')
    root = installation.resolve()
    marker = root / '.cove-install'
    if not marker.is_file() or marker.read_text(encoding='utf-8') != 'cove-preview-v1':
        raise ValueError('安装目录缺少 Cove 标记')
    removed = []
    for path in root.glob('*.ico'):
        if re.fullmatch(r'Cove(?:-\d+\.\d+\.\d+)?\.ico', path.name, re.IGNORECASE) and path.is_file() and not path.is_symlink() and path.resolve().parent == root:
            try:
                path.unlink()
            except PermissionError:
                # Explorer can map an old shortcut icon even after uninstall.
                # A rename still works without restarting Explorer or any session.
                archive = root / '.cove-retired-icons'
                if archive.is_symlink() or (hasattr(archive, 'is_junction') and archive.is_junction()):
                    raise ValueError('旧图标归档目录不能使用链接')
                archive.mkdir(exist_ok=True)
                path.rename(archive / f'{uuid.uuid4().hex}-{path.name}')
            removed.append(path.name)
    return removed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', required=True, type=Path)
    parser.add_argument('--request-close', action='store_true')
    parser.add_argument('--version')
    parser.add_argument('--uninstall-check', action='store_true')
    parser.add_argument('--cleanup-icons', action='store_true')
    parser.add_argument('--activate', action='store_true')
    parser.add_argument('--shortcut-dir', action='append', type=Path, default=[])
    args = parser.parse_args()
    payload = Path(sys.executable).resolve().parent
    try:
        if args.activate:
            result = activate_runtime(args.install, args.version, args.shortcut_dir)
        elif args.cleanup_icons:
            result = {'ready': True, 'removed': cleanup_legacy_icons(args.install)}
        elif args.uninstall_check:
            root = args.install.resolve()
            for folder in (root/'_internal',root/'versions'):
                if folder.exists():
                    for base, dirs, files in os.walk(folder, followlinks=False):
                        for path in [Path(base), *(Path(base)/name for name in dirs+files)]:
                            if path.is_symlink() or (hasattr(path,'is_junction') and path.is_junction()):
                                raise ValueError('安装目录包含链接，请手动检查后卸载')
            running = [p for p in installed_processes(args.install.resolve(), recursive=True) if p.pid != os.getpid()]
            result = {'ready':not running,'reason':'running' if running else '', 'pids':[p.pid for p in running]}
        else:
            result = preflight(args.install, payload, args.request_close, version=args.version)
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if result.get('reusePayload'):
            return 30
        return 0 if result['ready'] else 10
    except Exception as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=True), flush=True)
        return 20
