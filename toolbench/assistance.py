"""One tool registry for the built-in MCP center and SDK tool callers."""
from __future__ import annotations
from collections import Counter, deque
import copy
import json
from pathlib import Path
import threading
import time
import uuid

from jsonschema import Draft202012Validator
from toolbench.sdk import atomic_json
from toolbench.protocol import tool_name
from toolbench.plugin_framework.builtins import MCP_ID
from toolbench.plugin_framework.policy import POLICY


def public_value(value, compact=True, *, redactions=None):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if any(word in key.lower() for word in ('password', 'passphrase', 'api_key', 'token', 'secret')):
                result[key] = '[redacted]'
                if redactions is not None:
                    redactions['fields'] += 1
            else:
                result[key] = public_value(item, compact, redactions=redactions)
        return result
    if isinstance(value, list):
        return [public_value(item, compact, redactions=redactions)
                for item in (value[:100] if compact else value)]
    if isinstance(value, str):
        return value[:16000] if compact else value
    return value


def approval_view(pending):
    """Review every accepted argument; identify every field hidden by the redactor."""
    redactions = Counter()
    result = {key: value for key, value in pending.items() if key not in ('event', 'approved', 'arguments')}
    result['arguments'] = public_value(pending['arguments'], compact=False, redactions=redactions)
    result['redactedCount'] = redactions['fields']
    return result


class ToolBroker:
    def __init__(self, host):
        self.host = host
        self.path = host.data_dir / 'ai-tools.json'
        saved = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}
        self.allowed = set(saved.get('plugins', []))
        self.pending = {}
        self.audit = deque(maxlen=60)
        self.lock = threading.RLock()
        self.closed = False
        self.owner_revisions = {}

    def definitions(self, selected_only=True):
        if selected_only and MCP_ID in self.host._preferences['disabled']:
            return []
        tools = self.host.catalog()['tools']
        with self.lock:
            allowed = self.allowed.copy()
        result = []
        for tool in tools:
            if not tool['enabled'] or not tool.get('compatibilityStatus', {}).get('supported', True) or (selected_only and tool['id'] not in allowed):
                continue
            for declaration in tool.get('ai', {}).get('tools', []):
                name = tool_name(tool['id'], declaration['name'])
                result.append({'name': name, 'description': tool['name'] + '：' + declaration['description'],
                               'parameters': declaration['parameters'], 'readOnly': declaration['readOnly'],
                               'pluginId': tool['id'], 'pluginName': tool['name'], 'command': declaration['command']})
        return result

    def select(self, plugins):
        if not isinstance(plugins, list) or any(not isinstance(item, str) for item in plugins):
            raise ValueError('请选择有效的插件列表')
        # Disabled plugins may retain an explicit grant; definitions() still
        # excludes them from discovery/execution until the plugin is enabled.
        eligible = {tool['id'] for tool in self.host.catalog()['tools'] if tool.get('ai', {}).get('tools')}
        if set(plugins) - eligible:
            raise ValueError('所选插件不存在或没有声明 AI 工具')
        with self.lock:
            self.allowed = set(plugins)
            atomic_json(self.path, {'plugins': sorted(self.allowed)})
            for pending in self.pending.values():
                if pending['pluginId'] not in self.allowed:
                    pending['approved'] = False
                    pending['event'].set()

    def call(self, owner, name, arguments):
        if self.closed:
            raise ValueError('工作台正在关闭')
        with self.lock:
            revision = self.owner_revisions.get(owner, 0)
        declaration = next((item for item in self.definitions() if item['name'] == name), None)
        if not declaration:
            raise ValueError('工具未授权、已停用或不存在')
        with self.lock:
            target_revision = self.owner_revisions.get(declaration['pluginId'], 0)
        if not isinstance(arguments, dict) or len(json.dumps(arguments)) > 65536:
            raise ValueError('工具参数必须是小于 64 KiB 的对象')
        arguments = copy.deepcopy(arguments)
        errors = list(Draft202012Validator(declaration['parameters']).iter_errors(arguments))
        if errors:
            raise ValueError('工具参数不符合声明：' + errors[0].message[:180])
        if not declaration['readOnly']:
            ticket = uuid.uuid4().hex
            pending = {'id': ticket, 'owner': owner, 'name': name, 'pluginId': declaration['pluginId'],
                       'pluginName': declaration['pluginName'], 'description': declaration['description'],
                       'arguments': arguments, 'created': time.time(), 'approved': False, 'event': threading.Event()}
            with self.lock:
                if len(self.pending) >= 8:
                    raise ValueError('待确认操作过多，请先处理现有请求')
                if revision != self.owner_revisions.get(owner, 0):
                    raise ValueError('调用方已停止，未执行')
                self.pending[ticket] = pending
            try:
                if not pending['event'].wait(POLICY.approval) or not pending['approved']:
                    raise ValueError('操作未获批准或确认已超时，未执行')
            finally:
                with self.lock:
                    self.pending.pop(ticket, None)
        # Permission/lifecycle can change while the confirmation is open.
        def admit():
            available = any(item['name'] == name for item in self.definitions())
            with self.lock:
                cancelled = (revision != self.owner_revisions.get(owner, 0)
                             or target_revision != self.owner_revisions.get(declaration['pluginId'], 0))
                if self.closed or cancelled or declaration['pluginId'] not in self.allowed or not available:
                    raise ValueError('调用方、目标或工具授权已失效，未执行')
        reply = self.host._invoke(declaration['pluginId'], declaration['command'], arguments, admission=admit)
        if not reply['ok'] and not self.closed:
            admit()
        record = {'id': uuid.uuid4().hex, 'time': time.time(), 'owner': owner, 'name': name,
                  'pluginName': declaration['pluginName'], 'readOnly': declaration['readOnly'], 'ok': reply['ok']}
        with self.lock:
            self.audit.append(record)
        # Compact previews must not silently corrupt scientific arrays or images.
        if len(json.dumps(reply, ensure_ascii=True)) > 16 * 1024 * 1024:
            raise ValueError('工具结果超过 16 MiB，请减少采集数据量')
        return public_value(reply, compact=False)

    def decide(self, ticket, approve):
        if not isinstance(approve, bool):
            raise ValueError('无效的确认结果')
        with self.lock:
            pending = self.pending.get(ticket)
            if not pending or pending['event'].is_set():
                raise ValueError('此操作已处理或已过期')
            pending['approved'] = approve
            pending['event'].set()

    def cancel_owner(self, owner):
        with self.lock:
            self.owner_revisions[owner] = self.owner_revisions.get(owner, 0) + 1
            for pending in self.pending.values():
                if pending['owner'] == owner or pending['pluginId'] == owner:
                    pending['approved'] = False
                    pending['event'].set()

    def close(self):
        with self.lock:
            self.closed = True
            for pending in self.pending.values():
                pending['approved'] = False
                pending['event'].set()


class AssistanceApi:
    def _setup_assistance(self):
        self._assistant_broker = ToolBroker(self)
        self._assistant_gateway = None
        from toolbench.connections import Connections
        self._client_connections = Connections(self.data_dir)
        # Publish the descriptor at app startup, before a client opens the MCP page.
        self._sync_mcp_service()

    def _sync_mcp_service(self):
        """Change transport exposure without changing execution ownership."""
        if MCP_ID in self._preferences['disabled']:
            self._assistant_broker.cancel_owner('mcp')
            if self._assistant_gateway:
                self._assistant_gateway.publish_tools()
                self._assistant_gateway.close()
                self._assistant_gateway = None
            atomic_json(self.data_dir / 'mcp-tools.json', {'tools': []})
        else:
            setup = self.assistant_bridge()
            if not setup['ok']:
                raise RuntimeError(setup['error'])
            self._client_connections.maintain(setup['result']['clients'])

    def _host_tool_call(self, owner, operation, payload):
        manifest = self.plugins.get(owner, (None, {}))[1]
        if operation == 'host.locale' and owner in self.plugins and owner not in self._preferences['disabled']:
            return getattr(self, '_ui_locale', 'en-US')
        if 'host.tools' not in manifest.get('permissions', []) or owner in self._preferences['disabled']:
            raise ValueError('该插件未声明工作台工具访问能力')
        if operation == 'tools.list':
            return self._assistant_broker.definitions()
        if operation == 'tools.call':
            return self._assistant_broker.call(owner, payload.get('name'), payload.get('arguments'))
        raise ValueError('不支持的工具桥接操作')

    def assistant_state(self):
        broker = self._assistant_broker
        tools = broker.definitions(False)
        with broker.lock:
            result = {'tools': tools, 'selected': sorted(broker.allowed),
                    'pending': [approval_view(item) for item in broker.pending.values() if not item['event'].is_set()],
                    'audit': list(broker.audit), 'enabled': MCP_ID not in self._preferences['disabled']}
        # Host catalog and gateway sessions have independent locks. Only copy
        # broker-owned state under its lock, never call either subsystem here.
        gateway = self._assistant_gateway
        result['clients'] = gateway.live_clients() if gateway else []
        return {'ok': True, 'result': result}

    def assistant_allow(self, plugins):
        try:
            self._assistant_broker.select(plugins)
            if self._assistant_gateway:
                self._assistant_gateway.publish_tools()
            return self.assistant_state()
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def assistant_decide(self, ticket, approve):
        try:
            self._assistant_broker.decide(ticket, approve)
            return {'ok': True}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def assistant_bridge(self):
        try:
            if MCP_ID in self._preferences['disabled']:
                raise ValueError('MCP 连接插件已停用，请在插件页启用')
            from toolbench.mcp_bridge import Gateway
            with self.lock:
                if self._assistant_gateway is None:
                    self._assistant_gateway = Gateway(self._assistant_broker, self.data_dir,
                                                      client_allowed=lambda client: self._client_connections.client_allowed(client))
            return {'ok': True, 'result': self._assistant_gateway.instructions()}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def assistant_check(self):
        setup = self.assistant_bridge()
        if not setup['ok']:
            return setup
        try:
            return {'ok': True, 'result': self._assistant_gateway.check()}
        except Exception:
            return {'ok': False, 'error': '本机 MCP 自检失败，请检查运行时路径并重新打开连接中心'}

    def mcp_clients(self):
        try:
            setup = self.assistant_bridge()
            if not setup['ok']:
                return setup
            clients = self._client_connections.catalog(setup['result']['clients'], self._assistant_gateway.live_clients())
            legacy = self._assistant_gateway.legacy_clients()
            from toolbench import __version__
            versions = self._assistant_gateway.client_versions()
            current = tuple(map(int, __version__.split('.')))
            for client in clients:
                client['needsReload'] = client['id'] in legacy
                client['adapterVersions'] = versions.get(client['id'], [])
                client['needsUpdate'] = any(tuple(map(int, value.split('.'))) < current
                                            for value in client['adapterVersions'])
            return {'ok': True, 'result': clients}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def mcp_install(self, client):
        try:
            setup = self.assistant_bridge()
            if not setup['ok']:
                return setup
            profile = next(item for item in setup['result']['clients'] if item['id'] == client)
            return {'ok': True, 'result': self._client_connections.install(client, profile)}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def mcp_restore(self, ticket):
        try:
            return {'ok': True, 'result': self._client_connections.restore(ticket)}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def mcp_manage(self, client, enabled):
        try:
            return {'ok': True, 'result': self._client_connections.manage(client, enabled)}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def mcp_connection(self, client, enabled):
        try:
            if enabled is False and self._assistant_gateway and client in self._assistant_gateway.legacy_clients():
                raise ValueError('此客户端仍使用旧版适配器，请在客户端重新加载 Cove MCP 后再断开。')
            return {'ok': True, 'result': self._client_connections.set_connection(client, enabled)}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}
