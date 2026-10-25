"""Disposable desktop bridge for browser integration tests; no personal data."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import shutil
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from toolbench.bridge import API_METHODS
from toolbench.host import Host
from toolbench.connections import Connections
from fixtures_runtime import write_terminal_fixture
from test_mcp import APPROVAL, write_approval_fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=18320)
    parser.add_argument('--showcase', action='store_true', help='Use the MCP-only catalog for documentation captures')
    options = parser.parse_args()
    (ROOT / 'artifacts').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='cove-e2e-', dir=ROOT / 'artifacts') as temporary:
        data = Path(temporary)
        with patch('pathlib.Path.home', return_value=data / 'home'):
            host = Host(data_dir=data / 'data')
        host._client_connections = Connections(data, home=data / 'home')
        host._plugin_drop_root = data / 'plugins'
        write_terminal_fixture(host._plugin_drop_root / 'terminal')
        terminal_manifest_path = host._plugin_drop_root / 'terminal/manifest.json'
        terminal_manifest = json.loads(terminal_manifest_path.read_text(encoding='utf-8'))
        terminal_manifest['localization'] = {'defaultLocale': 'zh-CN', 'messages': {'en-US': {
            '终端夹具': 'Terminal fixture', '测试': 'Tests', '测试地址': 'Test address',
            '测试用户名': 'Test username', '测试秘密': 'Test secret', '连接测试': 'Connect fixture'}}}
        terminal_manifest_path.write_text(json.dumps(terminal_manifest), encoding='utf-8')
        folder = host._plugin_drop_root / 'job'
        folder.mkdir(parents=True)
        manifest = {
            'sdkVersion': 1, 'id': 'test.background', 'name': '后台任务测试',
            'version': '1.0.0', 'author': 'Cove tests', 'description': 'Disposable background work',
            'category': '测试', 'icon': 'terminal', 'color': 'blue', 'permissions': [],
            'commands': ['start', 'snapshot', 'cancel'],
            'ui': {'surface': 'form', 'fields': [], 'actions': [{'command': 'start', 'label': '启动测试任务'}],
                   'job': {'snapshot': 'snapshot', 'cancel': 'cancel'}}}
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (folder / 'plugin.py').write_text('from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
            ' def __init__(self,context):\n  super().__init__(context)\n  self.running=False\n'
            ' def snapshot(self): return {"state":"running" if self.running else "idle","completed":0}\n'
            ' def start(self):\n  self.running=True\n  self.context.emit("activity",active=True)\n  return self.snapshot()\n'
            ' def cancel(self):\n  self.running=False\n  self.context.emit("activity",active=False)\n  return self.snapshot()\n', encoding='utf-8')
        broken = host._plugin_drop_root / 'broken'
        broken.mkdir()
        (broken / 'manifest.json').write_text(json.dumps({**manifest, 'id': 'test.broken', 'name': '启动失败测试'}), encoding='utf-8')
        (broken / 'plugin.py').write_text('import missing_e2e_dependency\n', encoding='utf-8')
        write_approval_fixture(host._plugin_drop_root / 'approval')
        shutil.copytree(ROOT / 'docs/templates/starter', host._plugin_drop_root / 'localized-hello')
        shutil.copytree(ROOT / 'docs/examples/result-starter', host._plugin_drop_root / 'result')
        shutil.copytree(ROOT / 'docs/examples/job-starter', host._plugin_drop_root / 'sdk-job')
        # Exercise plain-text output with deliberately hostile-looking plugin data.
        result_folder = host._plugin_drop_root / 'result'
        result_manifest = json.loads((result_folder / 'manifest.json').read_text(encoding='utf-8'))
        result_manifest['ui']['result']['fields'].append({'key': 'echo', 'label': '原文'})
        (result_folder / 'manifest.json').write_text(json.dumps(result_manifest), encoding='utf-8')
        with (result_folder / 'plugin.py').open('a', encoding='utf-8') as source:
            source.write('\nOriginalTool = Tool\nclass Tool(OriginalTool):\n'
                         '    def analyze(self, text=""):\n'
                         '        return {**super().analyze(text), "echo": text}\n')
        if options.showcase:
            # Documentation uses the real catalog and isolated host; never a user's data.
            host._plugin_drop_root = data / 'showcase-plugins'
            for source in []:
                if source.is_dir() and (source / 'manifest.json').is_file():
                    shutil.copytree(source, host._plugin_drop_root / source.name,
                                    ignore=shutil.ignore_patterns('__pycache__', '.venv', '.git'))
        host.rescan_plugins()

        class Window:
            def destroy(self): pass
            def minimize(self): pass
            def maximize(self): pass
            def restore(self): pass
        host._window = Window()

        class Handler(SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=str(ROOT / 'dist'), **kwargs)

            def log_message(self, *_): pass

            def do_GET(self):
                if self.path == '/fixture':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'port': 0}).encode())
                elif self.path in ('/', '/index.html'):
                    page = (ROOT / 'dist/index.html').read_text(encoding='utf-8')
                    bridge = '<script>window.pywebview={api:Object.fromEntries(' + json.dumps(API_METHODS) + '.map(name=>[name,async(...args)=>(await fetch("/api/"+name,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(args)})).json()]))};</script>'
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(page.replace('</head>', bridge + '</head>').encode('utf-8'))
                else:
                    super().do_GET()

            def do_POST(self):
                operation = self.path.removeprefix('/api/')
                fixture_approval = self.path == '/fixture/approval'
                if (operation not in API_METHODS and not fixture_approval) or self.headers.get('Origin') not in (None, f'http://127.0.0.1:{options.port}'):
                    self.send_error(403)
                    return
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 1000000:
                    self.send_error(400)
                    return
                args = json.loads(self.rfile.read(size))
                if fixture_approval:
                    try:
                        name = next(tool['name'] for tool in host._assistant_broker.definitions()
                                    if tool['pluginId'] == APPROVAL and tool['command'] == 'record')
                        reply = host._assistant_broker.call('mcp', name, args)
                    except (StopIteration, ValueError) as exc:
                        reply = {'ok': False, 'error': str(exc)}
                else:
                    reply = getattr(host, operation)(*args)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                try:
                    self.wfile.write(json.dumps(reply).encode())
                except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                    pass  # A disposed browser page may stop listening after its command completes.

        server = ThreadingHTTPServer(('127.0.0.1', options.port), Handler)
        try:
            print(f'Isolated UI checks: http://127.0.0.1:{options.port}', flush=True)
            server.serve_forever()
        finally:
            host.close()
            server.server_close()


if __name__ == '__main__':
    main()
