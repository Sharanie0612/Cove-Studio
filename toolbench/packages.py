"""Portable, standard-library-only plugin packaging. Never imports plugin code."""
from __future__ import annotations
import fnmatch
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import uuid
import zipfile
from toolbench.manifest import validate_manifest

MAX_FILES = 500
MAX_EXPANDED = 50 * 1024 * 1024
MAX_ARCHIVE = 20 * 1024 * 1024
SKIP_DIRS = {'.git', '.venv', 'venv', '__pycache__', 'node_modules', '.local', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.idea', '.vscode'}
SKIP_FILES = {'profiles.json', 'known_hosts', 'plugin-preferences.json', '.ds_store'}

def package_filename(manifest):
    version = re.sub(r'[^a-zA-Z0-9._-]+', '-', manifest['version']).strip('.-')[:48] or 'version'
    return f"{manifest['id']}-{version}.cove-plugin"

def safe_name(name):
    name = name.replace('\\', '/')
    parts = PurePosixPath(name).parts
    if not parts or name.startswith('/') or any(p.lower() in {'..', '.venv', '.git', '__pycache__'} or ':' in p or p.endswith((' ', '.')) or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?', p) for p in parts):
        raise ValueError(f'不安全的插件路径：{name}')
    return PurePosixPath(name).as_posix()

def inspect_archive(content):
    if len(content) > MAX_ARCHIVE:
        raise ValueError('插件包不能超过 20 MB')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        entries = [item for item in archive.infolist() if not item.is_dir()]
        if not entries or len(entries) > MAX_FILES or sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise ValueError('插件包最多 500 个文件，解压后不能超过 50 MB')
        normalized = {}
        for item in entries:
            name = safe_name(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16) or item.flag_bits & 1:
                raise ValueError('不接受符号链接或加密的插件包')
            if name.lower() in normalized:
                raise ValueError('插件包含重复文件')
            normalized[name.lower()] = name
        manifests = [item for item in entries if safe_name(item.filename) == 'manifest.json']
        if not manifests:
            roots = {PurePosixPath(safe_name(item.filename)).parts[0] for item in entries}
            if len(roots) == 1:
                manifests = [item for item in entries if safe_name(item.filename) == next(iter(roots)) + '/manifest.json']
        if len(manifests) != 1:
            raise ValueError('插件包需要且只能有一个 manifest.json')
        prefix = PurePosixPath(safe_name(manifests[0].filename)).parent
        manifest = json.loads(archive.read(manifests[0]).decode('utf-8-sig'))
        validate_manifest(manifest)
        files = {}
        for item in entries:
            try:
                relative = PurePosixPath(safe_name(item.filename)).relative_to(prefix).as_posix()
            except ValueError:
                raise ValueError('插件包必须是单个插件目录')
            files[relative] = item.filename
        if 'plugin.py' not in files:
            raise ValueError('插件包缺少 plugin.py')
        requirements = archive.read(files['requirements.txt']).decode('utf-8-sig') if 'requirements.txt' in files else ''
        return {'manifest': manifest, 'files': files, 'requirements': requirements}

def build_package(folder: Path):
    folder = Path(folder).resolve()
    if not folder.is_dir() or not (folder / 'manifest.json').is_file():
        raise ValueError('请选择包含 manifest.json 和 plugin.py 的插件项目目录')
    patterns = []
    ignore = folder / '.coveignore'
    if ignore.is_file():
        patterns = [line.strip().replace('\\', '/') for line in ignore.read_text(encoding='utf-8-sig').splitlines() if line.strip() and not line.lstrip().startswith('#')]
        if any(line.startswith('!') for line in patterns):
            raise ValueError('.coveignore 使用排除规则，不支持 ! 反选')
    files, excluded, total = {}, [], 0
    def omitted(relative):
        parts = relative.parts
        name = parts[-1].lower()
        text = relative.as_posix()
        return any(part.lower() in SKIP_DIRS for part in parts) or name.startswith('.env') or name.endswith(('.pyc', '.pyo', '.pem', '.key', '.cove-plugin')) or name.startswith(('id_rsa', 'id_ed25519', 'id_ecdsa')) or (len(parts) == 1 and name in SKIP_FILES) or any(fnmatch.fnmatchcase(text, pattern.rstrip('/') + '/*' if pattern.endswith('/') else pattern) or fnmatch.fnmatchcase(name, pattern) for pattern in patterns)
    def walk(directory):
        nonlocal total
        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            relative = path.relative_to(folder)
            if omitted(relative):
                if len(excluded) < 100: excluded.append(relative.as_posix() + ('/' if path.is_dir() else ''))
                continue
            if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
                raise ValueError(f'插件项目包含符号链接，请移除或复制实际文件：{relative}')
            if path.is_dir():
                walk(path)
            elif path.is_file():
                name = safe_name(relative.as_posix())
                total += path.stat().st_size
                if len(files) >= MAX_FILES or total > MAX_EXPANDED:
                    raise ValueError('项目超过打包限制：最多 500 个文件、50 MB；可使用 .coveignore 排除开发文件')
                files[name] = path.read_bytes()
    walk(folder)
    if not {'manifest.json', 'plugin.py'}.issubset(files):
        raise ValueError('manifest.json 和 plugin.py 必须存在，且不能被排除')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content)
    content = buffer.getvalue()
    inspected = inspect_archive(content)
    return {**inspected, 'content': content, 'fileCount': len(files), 'expandedBytes': total, 'excluded': excluded}

def write_bytes_atomic(path: Path, content: bytes):
    path = Path(path)
    if path.is_dir():
        raise ValueError('请指定文件名，不能保存到目录本身')
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('xb') as output:
            output.write(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
