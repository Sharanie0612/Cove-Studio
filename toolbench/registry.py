"""Discover plugin metadata without importing or starting third-party code."""
import json
from toolbench.manifest import validate_manifest

from toolbench.plugin_framework.builtins import RETIRED_IDS, is_host_service


def discover_plugins(builtin_root, managed_root, drop_root, removed):
    plugins, issues, available = {}, [], []
    for root in dict.fromkeys((builtin_root, managed_root, drop_root)):
        if not root.is_dir():
            continue
        for folder in sorted(root.iterdir()):
            if folder.name.startswith('.') or not (folder / 'manifest.json').is_file():
                continue
            try:
                manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8-sig'))
                if isinstance(manifest, dict) and manifest.get('id') in RETIRED_IDS:
                    continue
                validate_manifest(manifest)
                identity = manifest['id']
                if identity in removed and not is_host_service(identity):
                    if root == builtin_root:
                        available.append({**manifest, 'builtin': True, 'enabled': False})
                    continue
                if identity in plugins:
                    if root == managed_root and plugins[identity][0].parent == builtin_root:
                        continue  # Preserve old managed core copies; use the bundled version.
                    raise ValueError('插件 id 重复')
                if not (folder / 'plugin.py').is_file():
                    raise ValueError('缺少 plugin.py')
                plugins[identity] = (folder, manifest)
            except Exception as exc:
                issues.append({'folder': folder.name, 'error': str(exc)})
    return plugins, issues, available
