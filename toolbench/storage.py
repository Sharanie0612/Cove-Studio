"""Installation-local data, with verified non-destructive legacy migration."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import sys
from urllib.parse import urlsplit
import uuid

from toolbench.plugin_framework.persistence import atomic_json, protect_private, reject_linked_path
from toolbench.plugin_framework.transactions import rename_directory

MARKER = '.cove-data-migration.json'
LOCK = '.cove-data-migration.lock'


class StorageBusy(RuntimeError):
    pass


def legacy_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'Cove'


def endpoint_active(directory):
    try:
        value = json.loads((directory / 'mcp-bridge.json').read_text(encoding='utf-8'))
        url = urlsplit(value['url'])
        if url.scheme != 'http' or url.hostname != '127.0.0.1' or url.path != '/tools':
            return True
        with socket.create_connection(('127.0.0.1', url.port), timeout=.2):
            return True
    except FileNotFoundError:
        return False
    except (OSError, ValueError, KeyError, TypeError):
        return False


def legacy_in_use(source):
    import psutil
    if endpoint_active(source):
        return True
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['pid'] == os.getpid():
            continue
        try:
            name = (process.info['name'] or '').lower()
            if name == 'cove.exe':
                executable = Path(process.exe()).resolve()
                from toolbench.paths import active_runtime
                # The stable NSIS entry waits for its child, but never opens data.
                # Check its owned routing records rather than ignoring ancestors:
                # an actual older desktop ancestor must still protect its data.
                if (executable.parent / '.cove-install').is_file() and active_runtime(executable.parent):
                    continue
                environment = process.environ()
                explicit = environment.get('TOOLBENCH_DATA_DIR')
                directory = Path(explicit) if explicit else desktop_default_directory(executable, environment)
                if directory.resolve() == source.resolve():
                    return True
            if name in ('cove-worker.exe', 'python.exe', 'pythonw.exe'):
                args = process.cmdline()
                if '--worker' in args:
                    index = args.index('--worker')
                    if len(args) > index + 2 and Path(args[index + 2]).resolve().is_relative_to(source.resolve()):
                        return True
                elif 'toolbench.worker' in args:
                    index = args.index('toolbench.worker')
                    if len(args) > index + 2 and Path(args[index + 2]).resolve().is_relative_to(source.resolve()):
                        return True
        except psutil.NoSuchProcess:
            continue
        except (psutil.AccessDenied, OSError, ValueError):
            if name in ('cove.exe', 'cove-worker.exe'):
                return True
            # An unrelated protected Python process is not evidence of a Cove
            # worker. A managed interpreter inside the source remains protected.
            try:
                if Path(process.exe()).resolve().is_relative_to(source.resolve()):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError, ValueError):
                pass
    return False


def desktop_default_directory(executable, environment):
    """Resolve a frozen desktop's storage policy without importing its code."""
    runtime = executable.parent
    try:
        version = json.loads((runtime / 'runtime-manifest.json').read_text(encoding='utf-8'))['version']
        if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', version) and tuple(map(int, version.split('.'))) >= (0, 13, 2):
            installation = runtime.parent.parent if runtime.parent.name == 'versions' else runtime
            return installation / 'data'
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return Path(environment.get('LOCALAPPDATA', str(Path.home()))) / 'Cove'


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def inventory(root):
    result = {}
    reject_linked_path(root)
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(folder) / name
            reject_linked_path(path)
            if path.is_dir():
                result[path.relative_to(root).as_posix() + '/'] = None
            elif path.parent != root or path.name not in (MARKER, LOCK):
                result[path.relative_to(root).as_posix()] = digest(path)
    return result


@contextmanager
def migration_lock(source):
    """The OS releases this lock if a migration process exits unexpectedly."""
    path = source / LOCK
    reject_linked_path(path)
    with path.open('a+b') as stream:
        if not path.stat().st_size:
            stream.write(b'0')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def migrate(source, target):
    """Publish a verified copy only; never delete or overwrite original data."""
    stage = target.parent / ('.cove-data-' + uuid.uuid4().hex)
    reject_linked_path(source)
    reject_linked_path(target)
    if target.resolve().is_relative_to(source.resolve()) or source.resolve().is_relative_to(target.resolve()):
        raise ValueError('Data migration paths overlap')
    with migration_lock(source):
        if target.exists() or (source / MARKER).exists():
            return False
        if legacy_in_use(source):
            raise OSError('Legacy data is in use')
        before = inventory(source)
        stage.mkdir()
        protect_private(stage)
        try:
            for relative in before:
                original, destination = source / relative, stage / relative
                reject_linked_path(original)
                if relative.endswith('/'):
                    destination.mkdir(parents=True, exist_ok=True)
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
            if before != inventory(stage) or before != inventory(source) or legacy_in_use(source):
                raise OSError('Legacy data changed during migration')
            preferences = stage / 'plugin-preferences.json'
            if preferences.is_file():
                saved = json.loads(preferences.read_text(encoding='utf-8'))
                interpreters = saved.get('interpreters', {}) if isinstance(saved, dict) else {}
                if isinstance(interpreters, dict):
                    for identity, value in list(interpreters.items()):
                        if isinstance(value, str) and Path(value).is_absolute() and Path(value).is_relative_to(source):
                            interpreters[identity] = str(target / Path(value).relative_to(source))
                    atomic_json(preferences, saved, private=True)
            record = {'owner': 'cove-data-v1', 'source': str(source.resolve()), 'target': str(target.resolve())}
            atomic_json(stage / MARKER, record, private=True)
            rename_directory(stage, target)
            # This small record prevents another installation importing a stale backup.
            atomic_json(source / MARKER, record, private=True)
            return True
        finally:
            if stage.exists():
                # stage is created by this call, adjacent to the exact destination.
                assert stage.parent.resolve() == target.parent.resolve() and stage.name.startswith('.cove-data-')
                reject_linked_path(stage)
                shutil.rmtree(stage)


def resolve_storage(project_root, explicit=None):
    override = explicit if explicit is not None else os.environ.get('TOOLBENCH_DATA_DIR')
    if override is not None:
        return Path(override), {'mode': 'override'}
    if not getattr(sys, 'frozen', False):
        return project_root / '.local', {'mode': 'development'}
    from toolbench.paths import installation_root
    target = installation_root() / 'data'
    source = legacy_directory()
    reject_linked_path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_dir() and not any(target.iterdir()):
        target.rmdir()  # An empty pre-created data folder is safe to adopt.
    if not target.exists() and (source / MARKER).exists():
        try:
            record = json.loads((source / MARKER).read_text(encoding='utf-8'))
            claimed = (isinstance(record, dict) and record.get('owner') == 'cove-data-v1'
                       and Path(record['source']).resolve() == source.resolve()
                       and Path(record['target']).is_absolute() and Path(record['target']).is_dir())
        except (OSError, ValueError, KeyError, TypeError):
            claimed = False
        if not claimed:
            return source, {'mode': 'legacy-pending', 'preferredPath': str(target)}
    if not target.exists() and source.is_dir() and source.resolve() != target.resolve() and not (source / MARKER).exists():
        try:
            migrate(source, target)
        except (OSError, ValueError, shutil.Error):
            # Preserve working data rather than starting with a partially copied profile.
            if not target.exists():
                return source, {'mode': 'legacy-pending', 'preferredPath': str(target)}
    target.mkdir(parents=True, exist_ok=True)
    protect_private(target)
    record = migration_record(target)
    return target, {'mode': 'installation', **({'legacyBackup': record['source']} if record else {})}


def migration_record(data):
    try:
        record = json.loads((data / MARKER).read_text(encoding='utf-8'))
        if (isinstance(record, dict) and record.get('owner') == 'cove-data-v1' and
                Path(record['source']).resolve() == legacy_directory().resolve() and
                Path(record['target']).resolve() == data.resolve()):
            return record
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def compatibility_directories(host):
    """Retain only tiny bridge metadata for already-running legacy MCP adapters."""
    if host.storage.get('mode') != 'installation' or not migration_record(host.data_dir):
        return []
    source = legacy_directory()
    try:
        reject_linked_path(source)
        record = json.loads((source / MARKER).read_text(encoding='utf-8'))
        if record == migration_record(host.data_dir) and not endpoint_active(source):
            return [source]
    except (OSError, ValueError, TypeError):
        pass
    return []
