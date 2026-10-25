"""STDIO MCP adapter forwards calls to the currently open Cove, never another Host."""
from __future__ import annotations
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.parse

from toolbench.sdk import atomic_json
from toolbench import __version__
from toolbench.plugin_framework.policy import POLICY


class ConnectionPaused(ValueError):
    pass


class Gateway:
    def __init__(self, broker, data_dir, client_allowed=None):
        self.token = secrets.token_urlsafe(32)
        self.path = data_dir / 'mcp-bridge.json'
        self.broker = broker
        self.client_allowed = client_allowed or (lambda client: True)
        self.client_sessions = {}
        self.session_lock = threading.Lock()
        self.publication_lock = threading.Lock()
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                supplied = self.headers.get('Authorization', '')
                if self.path != '/tools' or self.headers.get('Origin') or not hmac.compare_digest(supplied, 'Bearer ' + gateway.token):
                    self.send_error(403)
                    return
                try:
                    length = int(self.headers.get('Content-Length', '0'))
                    if not 0 < length <= 131072:
                        raise ValueError('请求过大或无效')
                    request = json.loads(self.rfile.read(length))
                    client = request.get('client')
                    if client and not gateway.client_allowed(client):
                        raise ConnectionPaused('此客户端已在 Cove 中断开，请在 MCP 连接页重新连接。')
                    if request.get('operation') == 'hello':
                        from toolbench.connections import CLIENTS
                        import psutil
                        if request.get('client') not in CLIENTS or type(request.get('pid')) is not int:
                            raise ValueError('无效的客户端标识')
                        process = psutil.Process(request['pid'])
                        version = request.get('runtimeVersion', '')
                        if not isinstance(version, str) or not re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', version):
                            # Earlier frozen adapters did not report a version. Inspect
                            # only the executable path, never launch their code.
                            try:
                                executable = Path(process.exe())
                            except psutil.Error:
                                executable = Path()
                            version = executable.parent.name if (
                                executable.name.lower() == 'cove-worker.exe'
                                and executable.parent.parent.name == 'versions'
                                and re.fullmatch(r'[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}', executable.parent.name)
                            ) else ''
                        with gateway.session_lock:
                            gateway.client_sessions[(request['client'], request['pid'])] = (
                                process.create_time(), time.monotonic(),
                                request.get('connectionControl') is True, version)
                        result = {}
                    elif request.get('operation') == 'list':
                        result = gateway.publish_tools()
                    elif request.get('operation') == 'call':
                        result = broker.call('mcp', request.get('name'), request.get('arguments', {}))
                    else:
                        raise ValueError('未知工具操作')
                    reply = {'ok': True, 'result': result}
                except Exception as exc:
                    reply = {'ok': False, 'error': str(exc)}
                    if isinstance(exc, ConnectionPaused):
                        reply['code'] = 'CONNECTION_PAUSED'
                try:
                    content = json.dumps(reply, ensure_ascii=True).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except OSError:
                    pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.daemon_threads = True
        try:
            atomic_json(self.path, {'url': f'http://127.0.0.1:{self.server.server_port}/tools', 'token': self.token}, private=True)
            # Finish initial publication before accepting requests: the caller
            # may still own the host lock while constructing this gateway.
            self.publish_tools()
        except Exception:
            self.server.server_close()
            raise
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.closed = False

    def publish_tools(self):
        path = self.path.with_name('mcp-tools.json')
        # A stable authorized catalog lets clients with a fixed per-session tool
        # list start while the desktop is closed. Execution always stays live.
        # Serialize the catalog snapshot with its write, independently of client
        # sessions. Broker/catalog inspection must never hold session_lock.
        with self.publication_lock:
            tools = self.broker.definitions()
            content = {'tools': tools}
            try:
                unchanged = json.loads(path.read_text(encoding='utf-8')) == content
            except (OSError, ValueError):
                unchanged = False
            if not unchanged:
                atomic_json(path, content)
        return tools

    def _live_sessions(self):
        import psutil
        result = []
        with self.session_lock:
            stale = []
            for (client, pid), (created, seen, controlled, version) in self.client_sessions.items():
                try:
                    if time.monotonic() - seen <= 8 and psutil.Process(pid).create_time() == created:
                        result.append((client, controlled, version))
                    else:
                        stale.append((client, pid))
                except psutil.Error:
                    stale.append((client, pid))
            for key in stale:
                del self.client_sessions[key]
        return result

    def live_clients(self):
        return sorted({client for client, _, _ in self._live_sessions() if self.client_allowed(client)})

    def legacy_clients(self):
        return {client for client, controlled, _ in self._live_sessions() if not controlled}

    def client_versions(self):
        versions = {}
        for client, _, version in self._live_sessions():
            if version:
                versions.setdefault(client, set()).add(version)
        return {client: sorted(values, key=lambda value: tuple(map(int, value.split('.'))))
                for client, values in versions.items()}

    def instructions(self):
        from toolbench.harness import client_profiles
        frozen = bool(getattr(sys, 'frozen', False))
        command = str(Path(sys.executable).with_name('Cove-worker.exe')) if frozen else sys.executable
        if not frozen and Path(command).name.lower() == 'pythonw.exe':
            command = str(Path(command).with_name('python.exe'))
        args = ['--mcp'] if frozen else ['-m', 'toolbench.mcp_bridge']
        args += ['--connection', str(self.path)]
        env = {} if frozen else {'PYTHONPATH': str(Path(__file__).resolve().parent.parent)}
        clients = client_profiles(command, args, env)
        return {'config': clients[0]['config'], 'command': command, 'args': args, 'env': env, 'clients': clients,
                'description': 'Cove 启动时自动提供连接。通过固定入口发现 智能体工具页已授权的插件；写操作在 Cove 内确认。'}

    def check(self):
        """Exercise the exported adapter from an unrelated working directory."""
        import os
        setup = self.instructions()
        requests = [{'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2025-11-25'}},
                    {'jsonrpc': '2.0', 'method': 'notifications/initialized'},
                    {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'},
                    {'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call', 'params': {'name': 'cove_tools', 'arguments': {}}}]
        process = subprocess.run([setup['command'], *setup['args'], '--compact'], cwd=str(self.path.parent),
                                 env={**os.environ, **setup['env']},
                                 input=''.join(json.dumps(item) + '\n' for item in requests),
                                 capture_output=True, encoding='utf-8', timeout=15,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            replies = [item for line in process.stdout.splitlines() if 'id' in (item := json.loads(line))]
            if process.returncode or len(replies) != 3 or any('error' in reply for reply in replies):
                raise ValueError('适配器未完成 MCP 握手或工具发现')
            tools = replies[1]['result']['tools']
            discovery = replies[2]['result']
            catalog = json.loads(discovery['content'][0]['text'])
            if discovery.get('isError') or not catalog.get('ok') or len(tools) != 3:
                raise ValueError('动态工具发现失败')
            count = catalog['result']['total']
            return {'toolCount': count, 'entryCount': len(tools), 'discoveryCall': True,
                    'protocolVersion': replies[0]['result']['protocolVersion'],
                    'message': f'本机 MCP 握手与动态发现调用成功，{count} 个工具已授权。目标客户端在线状态单独显示。'}
        except (ValueError, KeyError, TypeError):
            raise ValueError('本机 MCP 自检失败，请检查运行时路径并重新打开连接中心') from None

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        try:
            if json.loads(self.path.read_text(encoding='utf-8')).get('token') == self.token:
                self.path.unlink()
        except (FileNotFoundError, ValueError):
            pass


def forward(connection, request, timeout=POLICY.request):
    config = json.loads(connection.read_text(encoding='utf-8'))
    parsed = urllib.parse.urlsplit(config['url'])
    if parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.path != '/tools':
        raise ValueError('无效的本地 Cove 连接配置')
    operation = urllib.request.Request(config['url'], json.dumps(request).encode(),
                                       {'Authorization': 'Bearer ' + config['token'], 'Content-Type': 'application/json'})
    # Do not use an HTTP proxy for a loopback-only bridge.
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(operation, timeout=timeout) as response:
        result = json.load(response)
    if not result['ok']:
        if result.get('code') == 'CONNECTION_PAUSED':
            raise ConnectionPaused(result['error'])
        raise ValueError(result.get('error', 'Cove 工具调用失败'))
    return result['result']


class Adapter:
    """The MCP process outlives the desktop; desktop availability is not a handshake dependency."""
    def __init__(self, connection, outgoing, client=None, compact=False):
        self.connection, self.outgoing, self.client = connection, outgoing, client
        self.output_lock, self.refresh_lock = threading.RLock(), threading.Lock()
        self.stopped = threading.Event()
        self.tools, self.thread = [], None
        self.compact = compact

    def write(self, value):
        with self.output_lock:
            return self.outgoing.write(value)

    def flush(self):
        with self.output_lock:
            self.outgoing.flush()

    def request(self, operation, **values):
        return {'operation': operation, 'client': self.client, **values}

    def refresh(self, notify=False):
        import os
        with self.refresh_lock:
            try:
                if self.client:
                    forward(self.connection, {'operation':'hello', 'client':self.client, 'pid':os.getpid(),
                                              'connectionControl': True, 'runtimeVersion': __version__}, timeout=2)
                if self.compact:
                    from toolbench.mcp_router import definitions
                    return definitions()
                tools = forward(self.connection, self.request('list'), timeout=2)
            except ConnectionPaused:
                if self.compact:
                    from toolbench.mcp_router import definitions
                    return definitions()
                tools = []
            except (OSError, ValueError, KeyError):
                if self.compact:
                    from toolbench.mcp_router import definitions
                    return definitions()
                try:
                    path = self.connection.with_name('mcp-tools.json')
                    if path.stat().st_size <= 1048576:
                        cached = json.loads(path.read_text(encoding='utf-8'))['tools']
                        allowed = json.loads(self.connection.with_name('ai-tools.json').read_text(encoding='utf-8')).get('plugins', [])
                        if isinstance(cached, list) and all(isinstance(t,dict) and isinstance(t.get('name'),str) and isinstance(t.get('description'),str) and isinstance(t.get('parameters'),dict) and isinstance(t.get('readOnly'),bool) for t in cached):
                            self.tools = [t for t in cached if t.get('pluginId') in allowed]
                except (OSError, ValueError, KeyError, TypeError):
                    pass
                return self.tools
            changed = tools != self.tools
            self.tools = tools
            if notify and changed and not self.stopped.is_set():
                with self.output_lock:
                    self.write(json.dumps({'jsonrpc':'2.0', 'method':'notifications/tools/list_changed'})+'\n')
                    self.flush()
            return tools

    def initialized(self):
        if self.thread:
            return
        def monitor():
            while not self.stopped.is_set():
                try:
                    self.refresh(notify=True)
                except (OSError, ValueError):
                    break  # Client closed stdout.
                if self.stopped.wait(1):
                    break
        self.thread = threading.Thread(target=monitor, daemon=True)
        self.thread.start()

    def call(self, name, arguments):
        try:
            return forward(self.connection, self.request('call', name=name, arguments=arguments))
        except (OSError, KeyError, json.JSONDecodeError):
            raise ValueError('Cove 暂未运行或正在重启。请打开 Cove，保留已授权的工具后重试；无需重新添加 MCP 配置。') from None

    def close(self):
        self.stopped.set()
        if self.thread:
            self.thread.join(timeout=2.5)


def serve(connection, incoming, outgoing, client=None, compact=False):
    from toolbench.protocol import serve_rpc
    adapter = Adapter(connection, outgoing, client, compact)
    try:
        if compact:
            from toolbench.mcp_router import definitions, route
            def discover():
                try:
                    return forward(connection, adapter.request('list'), timeout=5)
                except (OSError, KeyError, json.JSONDecodeError):
                    raise ValueError('Cove 暂未运行或正在重启。请打开 Cove 后重试，无需重新添加 MCP 配置。') from None
            serve_rpc(incoming, adapter, definitions,
                      lambda name, arguments: route(name, arguments, discover, adapter.call), on_initialized=adapter.initialized)
        else:
            serve_rpc(incoming, adapter, adapter.refresh, adapter.call, on_initialized=adapter.initialized)
    finally:
        adapter.close()


def main():
    # MCP stdio is UTF-8 even when a Windows console uses a legacy code page.
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--connection', required=True, type=Path)
    parser.add_argument('--client')
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    serve(args.connection, sys.stdin, sys.stdout, args.client, args.compact)


if __name__ == '__main__':
    main()
