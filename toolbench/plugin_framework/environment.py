"""Keep plugin-owned temporary files and common Python caches beside its data."""
import os
from pathlib import Path
from toolbench.plugin_framework.persistence import reject_linked_path


def worker_environment(data_dir, environment=None):
    reject_linked_path(Path(data_dir))
    cache = Path(data_dir).resolve() / '.cache'
    temporary = cache / 'tmp'
    reject_linked_path(temporary)
    temporary.mkdir(parents=True, exist_ok=True)
    return {**(os.environ if environment is None else environment),
            'TEMP': str(temporary), 'TMP': str(temporary), 'TMPDIR': str(temporary),
            'XDG_CACHE_HOME': str(cache), 'PIP_CACHE_DIR': str(cache / 'pip'),
            'PYTHONDONTWRITEBYTECODE': '1'}
