"""Exercise one real stdio process across desktop absence, restart and revocation."""
import json
import io
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from toolbench.host import Host, ROOT
from fixtures_runtime import TERMINAL,write_terminal_fixture

def fixture_host(data):
    host=Host(data_dir=data)
    host._plugin_drop_root=data/'fixtures'
    write_terminal_fixture(host._plugin_drop_root/'terminal')
    host.rescan_plugins()
    return host


class LifecycleTests(unittest.TestCase):
    def test_session_versions_distinguish_old_adapters_from_the_current_host(self):
        from toolbench import __version__
        from toolbench.mcp_bridge import forward
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            host = fixture_host(Path(temp))
            child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'], stdin=subprocess.PIPE)
            try:
                path = Path(temp) / 'mcp-bridge.json'
                hello = {'operation': 'hello', 'client': 'codex', 'pid': os.getpid(), 'connectionControl': True}
                # Recover a version from a pre-reporting frozen adapter without executing it.
                with patch('psutil.Process.exe', return_value=str(Path(temp) / 'versions/0.12.4/Cove-worker.exe')):
                    forward(path, hello)
                forward(path, {**hello, 'pid': child.pid, 'runtimeVersion': __version__})
                client = next(c for c in host.mcp_clients()['result'] if c['id'] == 'codex')
                self.assertEqual(client['adapterVersions'], ['0.12.4', __version__])
                self.assertTrue(client['needsUpdate'])
                self.assertFalse(client['needsReload'])
                self.assertTrue(host.mcp_connection('codex', False)['ok'])
                self.assertTrue(host.mcp_connection('codex', True)['ok'])
                forward(path, {**hello, 'runtimeVersion': __version__})
                self.assertFalse(next(c for c in host.mcp_clients()['result'] if c['id'] == 'codex')['needsUpdate'])
                with patch('toolbench.mcp_bridge.time.monotonic', return_value=time.monotonic() + 9):
                    self.assertEqual(host._assistant_gateway.client_versions(), {})
            finally:
                child.stdin.close(); child.wait(timeout=5)
                host.close()

    def test_legacy_adapters_require_reload_and_stale_heartbeats_are_not_online(self):
        from toolbench.mcp_bridge import forward
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            host = fixture_host(Path(temp))
            try:
                path = Path(temp) / 'mcp-bridge.json'
                hello = {'operation': 'hello', 'client': 'codex', 'pid': os.getpid()}
                forward(path, hello)
                clients = host.mcp_clients()['result']
                self.assertTrue(next(client for client in clients if client['id'] == 'codex')['needsReload'])
                self.assertFalse(host.mcp_connection('codex', False)['ok'])
                self.assertTrue(host._client_connections.client_allowed('codex'))
                forward(path, {**hello, 'connectionControl': True})
                self.assertTrue(host.mcp_connection('codex', False)['ok'])
                self.assertTrue(host.mcp_connection('codex', True)['ok'])
                self.assertIn('codex', host._assistant_gateway.live_clients())
                with patch('toolbench.mcp_bridge.time.monotonic', return_value=time.monotonic() + 9):
                    self.assertEqual(host._assistant_gateway.live_clients(), [])
            finally:
                host.close()

    def test_authorized_catalog_survives_desktop_exit_and_revocation(self):
        from toolbench.mcp_bridge import serve
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            data=Path(temp)
            host=fixture_host(data)
            host.assistant_allow([TERMINAL])
            host.close()
            incoming=io.StringIO('{"jsonrpc":"2.0","id":1,"method":"initialize"}\n{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n')
            outgoing=io.StringIO()
            serve(data/'mcp-bridge.json',incoming,outgoing,'codex')
            replies=[json.loads(line) for line in outgoing.getvalue().splitlines()]
            self.assertEqual(len(replies[1]['result']['tools']),2)
            host=fixture_host(data)
            host.assistant_allow([])
            host.close()
            outgoing=io.StringIO()
            serve(data/'mcp-bridge.json',io.StringIO('{"jsonrpc":"2.0","id":2,"method":"tools/list"}\n'),outgoing,'codex')
            self.assertEqual(json.loads(outgoing.getvalue())['result']['tools'],[])

    def test_handshake_before_desktop_then_discover_call_restart_and_revoke(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            data = Path(temp)/'data'
            process = subprocess.Popen([sys.executable,'-m','toolbench.mcp_bridge','--connection',str(data/'mcp-bridge.json'),'--client','codex'],
                                       cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            messages = queue.Queue()
            def read():
                for line in process.stdout:
                    messages.put(json.loads(line))
            reader = threading.Thread(target=read,daemon=True)
            reader.start()
            def send(method, identity=None, params=None):
                value = {'jsonrpc':'2.0','method':method}
                if identity is not None: value['id']=identity
                if params is not None: value['params']=params
                process.stdin.write(json.dumps(value)+'\n');process.stdin.flush()
            def receive(predicate):
                deadline = time.monotonic()+8
                while time.monotonic()<deadline:
                    item = messages.get(timeout=max(.01,deadline-time.monotonic()))
                    if predicate(item): return item
                self.fail('Expected MCP message did not arrive')
            host = None
            try:
                start = time.monotonic()
                send('initialize',1,{'protocolVersion':'2025-11-25'})
                reply = receive(lambda m:m.get('id')==1)
                self.assertLess(time.monotonic()-start,2)
                self.assertTrue(reply['result']['capabilities']['tools']['listChanged'])
                send('notifications/initialized')
                send('tools/list',2)
                self.assertEqual(receive(lambda m:m.get('id')==2)['result']['tools'],[])
                host = fixture_host(data)
                self.assertTrue((data/'mcp-bridge.json').exists())  # No MCP page needed.
                host.assistant_allow([TERMINAL])
                receive(lambda m:m.get('method')=='notifications/tools/list_changed')
                send('tools/list',3)
                tools = receive(lambda m:m.get('id')==3)['result']['tools']
                self.assertEqual(len(tools),2)
                tool = next(t for t in tools if t['name'].endswith('_read'))['name']
                send('tools/call',4,{'name':tool,'arguments':{}})
                self.assertFalse(receive(lambda m:m.get('id')==4)['result']['isError'])
                host.close();host=None
                send('tools/call',5,{'name':tool,'arguments':{}})
                offline = receive(lambda m:m.get('id')==5)['result']
                self.assertTrue(offline['isError'])
                self.assertIn('请打开 Cove',offline['content'][0]['text'])
                host = fixture_host(data)
                host.assistant_allow([TERMINAL])
                send('tools/list',6)
                self.assertEqual(len(receive(lambda m:m.get('id')==6)['result']['tools']),2)
                send('tools/call',7,{'name':tool,'arguments':{}})
                self.assertFalse(receive(lambda m:m.get('id')==7)['result']['isError'])
                self.assertIn('codex',host._assistant_gateway.live_clients())
                self.assertTrue(host.mcp_connection('codex', False)['ok'])
                self.assertNotIn('codex', host._assistant_gateway.live_clients())
                receive(lambda m:m.get('method')=='notifications/tools/list_changed')
                send('tools/list', 20)
                self.assertEqual(receive(lambda m:m.get('id')==20)['result']['tools'], [])
                send('tools/call', 21, {'name':tool,'arguments':{}})
                blocked = receive(lambda m:m.get('id')==21)['result']
                self.assertTrue(blocked['isError'])
                self.assertIn('断开', blocked['content'][0]['text'])
                self.assertTrue(host.mcp_connection('codex', True)['ok'])
                receive(lambda m:m.get('method')=='notifications/tools/list_changed')
                send('tools/call', 22, {'name':tool,'arguments':{}})
                self.assertFalse(receive(lambda m:m.get('id')==22)['result']['isError'])
                host.assistant_allow([])
                receive(lambda m:m.get('method')=='notifications/tools/list_changed')
                send('tools/list',8)
                self.assertEqual(receive(lambda m:m.get('id')==8)['result']['tools'],[])
                send('tools/call',9,{'name':tool,'arguments':{}})
                self.assertTrue(receive(lambda m:m.get('id')==9)['result']['isError'])
            finally:
                process.stdin.close();process.wait(timeout=6)
                reader.join(timeout=2)
                process.stdout.close();process.stderr.close()
                if host: host.close()

    def test_one_exiting_adapter_does_not_hide_another_live_client(self):
        from toolbench.mcp_bridge import forward
        with tempfile.TemporaryDirectory(dir=ROOT) as temp:
            host = fixture_host(Path(temp))
            child = subprocess.Popen([sys.executable,'-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE)
            try:
                path = Path(temp)/'mcp-bridge.json'
                for pid in (os.getpid(),child.pid):
                    forward(path,{'operation':'hello','client':'codex','pid':pid})
                child.stdin.close();child.wait(timeout=5)
                self.assertEqual(host._assistant_gateway.live_clients(),['codex'])
            finally:
                if child.poll() is None:
                    child.stdin.close();child.wait(timeout=5)
                host.close()

