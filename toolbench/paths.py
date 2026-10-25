"""Installation paths shared by the desktop and plugin management."""
from pathlib import Path
import sys
import re


def installation_root():
    runtime = Path(sys.executable).resolve().parent
    return runtime.parent.parent if runtime.parent.name == 'versions' else runtime


def active_runtime(installation):
    """Resolve the installer's published version without executing metadata."""
    from toolbench.maintenance import runtime_path
    pointer = installation / '.cove-current'
    if not pointer.exists():
        return None
    if pointer.is_symlink() or (installation / '.cove-install').read_text(encoding='utf-8') != 'cove-preview-v1':
        raise ValueError('Cove 安装入口无效，请重新运行安装器')
    version = pointer.read_text(encoding='utf-8')
    if not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('Cove 当前版本记录无效，请重新运行安装器')
    runtime = runtime_path(installation, version)
    if not (runtime / 'Cove.exe').is_file() or (runtime / '.cove-runtime').read_text(encoding='utf-8') != 'cove-runtime-v1':
        raise ValueError('Cove 运行文件不完整，请重新运行安装器')
    return runtime
