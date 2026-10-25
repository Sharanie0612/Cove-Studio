"""Exercise downloadable examples and real imported plugins in a frozen host."""
import argparse
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from toolbench.host import Host
from toolbench.packages import build_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('installation', type=Path)
    installation = parser.parse_args().installation.resolve()
    executable = installation / 'Cove.exe'
    assert executable.is_file()
    report = {'worker': str(installation / 'Cove-worker.exe'), 'examples': []}
    with tempfile.TemporaryDirectory(prefix='sdk-frozen-', dir=ROOT / 'artifacts') as temporary:
        data = Path(temporary)
        python = sys.executable
        with patch('toolbench.host.ROOT', installation / '_internal'), \
             patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', str(executable)):
            host = Host(data_dir=data / 'data')
            try:
                with zipfile.ZipFile(io.BytesIO(host._starter_bytes())) as archive:
                    archive.extractall(data / 'download')
                starter = data / 'download/cove-plugin-starter'
                projects = [(starter, ['greet', 'name=Cove']),
                            (starter / 'examples/result-starter', ['analyze', 'text=one two one']),
                            (starter / 'examples/job-starter', [])]
                for project, arguments in projects:
                    result = subprocess.run([python, '-S', str(project / 'dev.py'), *arguments],
                                            cwd=data, capture_output=True, text=True, encoding='utf-8', timeout=15)
                    assert result.returncode == 0, result.stderr
                    value = json.loads(result.stdout)
                    assert value and (value.get('state', 'completed') == 'completed'), value
                    content = build_package(project)
                    assert not any(name.startswith(('sdk/', 'examples/')) for name in content['files'])
                    archive_path = data / (content['manifest']['id'] + '.cove-plugin')
                    archive_path.write_bytes(content['content'])
                    preview = host._inspect_package(archive_path)
                    installed = host.install_plugin(preview['ticket'])
                    assert installed['ok'], installed
                    identity = content['manifest']['id']
                    command = content['manifest']['ui']['actions'][0]['command']
                    payload = {'greet': {'name': 'Cove'}, 'analyze': {'text': 'one two one'},
                               'run': {'text': 'frozen', 'batches': 3}}[command]
                    reply = host.invoke(identity, command, payload)
                    assert reply['ok'], reply
                    if command == 'analyze':
                        assert reply['result']['unique'] == 2
                    if command == 'run':
                        deadline = time.monotonic() + 5
                        while time.monotonic() < deadline:
                            snapshot = host.invoke(identity, 'snapshot')['result']
                            if snapshot['state'] != 'running':
                                break
                            time.sleep(.05)
                        assert snapshot['state'] == 'completed', snapshot
                        assert snapshot['completed'] == 3
                    report['examples'].append({'id': identity, 'standaloneWithoutSitePackages': True,
                                               'packageExcludesDeveloperFiles': True, 'frozenWorkerCall': True})
                report['passed'] = True
            finally:
                host.close()
    output = ROOT / 'artifacts/validation/sdk-examples.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
