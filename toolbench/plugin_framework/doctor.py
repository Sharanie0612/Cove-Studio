"""Read-only source-project diagnostics; never import plugin code or install dependencies."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import subprocess

from toolbench.contracts import compatibility_report
from toolbench.packages import build_package
from toolbench.plugin_framework.interpreter import MIN_PYTHON_VERSION, select_interpreter
from toolbench.plugin_framework.policy import POLICY


# -I -S excludes the project, PYTHONPATH, .pth execution and sitecustomize.
# Importing stdlib site with -S only exposes path helpers; it does not run site.main().
PROBE = r'''
import importlib.metadata as metadata
import json, os, site, struct, sys
from pathlib import Path
names = json.load(sys.stdin)
executable = Path(sys.executable)
candidate = executable.parent.parent if executable.parent.name.lower() in ('scripts', 'bin') else executable.parent
config = candidate / 'pyvenv.cfg'
venv = config.is_file()
settings = {}
if venv:
    for line in config.read_text(encoding='utf-8').splitlines():
        key, separator, value = line.partition('=')
        if separator:
            settings[key.strip().lower()] = value.strip().lower()
system_site = not venv or settings.get('include-system-site-packages') == 'true'
prefixes = [str(candidate)] if venv else [sys.prefix, sys.exec_prefix]
if venv and system_site:
    prefixes.extend([sys.base_prefix, sys.base_exec_prefix])
paths = site.getsitepackages(prefixes)
if system_site and not os.environ.get('PYTHONNOUSERSITE'):
    paths.append(site.getusersitepackages())
paths = list(dict.fromkeys(path for path in paths if Path(path).is_dir()))
versions = {}
for name in names:
    distribution = next(iter(metadata.distributions(name=name, path=paths)), None)
    versions[name] = str(distribution.version)[:256] if distribution else None
print(json.dumps({'executable': sys.executable, 'version': sys.version.split()[0],
                  'versionInfo': list(sys.version_info[:3]),
                  'implementation': sys.implementation.name, 'architectureBits': struct.calcsize('P') * 8,
                  'platform': sys.platform, 'venv': venv, 'sitePaths': paths, 'versions': versions}))
'''


def declared_requirements(text):
    if len(text.encode('utf-8')) > 131072:
        raise ValueError('requirements.txt exceeds the 128 KiB diagnostic limit')
    lines = []
    for line in text.splitlines():
        line = re.split(r'\s+#', line, maxsplit=1)[0].strip()
        if not line or line.startswith('#'):
            continue
        if len(lines) >= 256:
            raise ValueError('requirements.txt exceeds the 256 declaration diagnostic limit')
        match = re.match(r'^([A-Za-z0-9][A-Za-z0-9._-]*)(?=\s*(?:$|\[|[<>=!~;@]))', line)
        name = match.group(1) if match else None
        if name and name.lower().endswith(('.whl', '.zip', '.tar.gz')):
            name = None
        lines.append({'declaration': line, 'name': name, 'availability': 'unverified',
                      'installedVersion': None,
                      'constraints': 'none' if name == line else 'unverified'})
    return lines


def diagnose_plugin(folder, interpreter=None, *, timeout=POLICY.startup):
    """Report identified failures separately from checks that cannot be verified."""
    folder = Path(folder).resolve()
    report = {'ok': False, 'status': 'error', 'pluginCodeExecuted': False,
              'dependenciesInstalled': False, 'errors': [], 'requirements': [],
              'limitations': [
                  'Distribution metadata does not verify module imports, native DLL loading, plugin behavior or hardware.',
                  'Version constraints, extras, environment markers, direct URLs and nested requirements are not evaluated.',
                  'Executable .pth files and sitecustomize are skipped; their additional import paths are not inspected.',
                  'Standalone diagnostics do not load Cove saved interpreter overrides; pass --python to select one.',
              ]}
    try:
        package = build_package(folder)
        manifest = package['manifest']
        report['plugin'] = {key: manifest[key] for key in ('id', 'version', 'sdkVersion')}
        report['compatibility'] = compatibility_report(manifest)
        report['requirements'] = declared_requirements(package['requirements'])
    except (ValueError, OSError, KeyError) as exc:
        report['errors'].append(str(exc))
        return report
    if not report['compatibility']['supported']:
        report['errors'].extend(report['compatibility']['reasons'])
    # CLI-relative paths belong to the caller, not the plugin working directory.
    configured = Path(interpreter).expanduser().resolve() if interpreter else None
    selected = select_interpreter(folder, configured)
    report['interpreter'] = {'selectedPath': str(selected.executable), 'source': selected.source,
                             'probeStatus': 'unverified',
                             'minimumVersion': '.'.join(map(str, MIN_PYTHON_VERSION))}
    if selected.frozen_worker:
        report['errors'].append('The bundled Cove worker is not a Python CLI; select a Python executable with --python for environment diagnostics.')
        return report
    names = list(dict.fromkeys(item['name'] for item in report['requirements'] if item['name']))
    try:
        process = subprocess.run([str(selected.executable), '-I', '-S', '-B', '-c', PROBE],
                                 input=json.dumps(names), cwd=folder, capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=timeout,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if process.returncode:
            raise ValueError(f'Python metadata probe failed (exit {process.returncode}); check the selected interpreter installation.')
        probe = json.loads(process.stdout)
        versions = probe.pop('versions')
        if not isinstance(versions, dict):
            raise ValueError('Python metadata probe returned invalid distribution information')
        report['interpreter'].update(probe, probeStatus='ok')
        if tuple(probe['versionInfo'][:2]) < MIN_PYTHON_VERSION:
            report['errors'].append('The Cove SDK requires Python ' + report['interpreter']['minimumVersion'] + ' or newer.')
    except subprocess.TimeoutExpired:
        report['errors'].append('Python metadata probe timed out; no plugin code was requested.')
        report['interpreter']['probeStatus'] = 'error'
        return report
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report['errors'].append(str(exc))
        report['interpreter']['probeStatus'] = 'error'
        return report
    for requirement in report['requirements']:
        name = requirement['name']
        if not name:
            continue
        version = versions.get(name)
        requirement['installedVersion'] = version
        requirement['availability'] = 'installed' if version is not None else 'missing'
        # A missing conditional distribution is not a proven failure until its marker is evaluated.
        if version is None and ';' not in requirement['declaration']:
            report['errors'].append(f'Missing installed distribution: {name}')
    report['ok'] = not report['errors']
    partial = any(item['constraints'] == 'unverified' for item in report['requirements'])
    report['status'] = 'error' if not report['ok'] else 'partial' if partial else 'checked'
    return report
