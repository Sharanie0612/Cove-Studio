"""Reversible client configuration, separate from the MCP transport and plugin runtime."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
import uuid

import json5
import tomlkit
import yaml
from toolbench.client_backups import ClientBackups
from toolbench.plugin_framework.persistence import atomic_bytes, atomic_text

CLIENTS = {
    'codex': ('Codex', '.codex/config.toml', 'OpenAI'),
    'claude-code': ('Claude Code', '.claude.json', 'Anthropic'),
    'cursor': ('Cursor', '.cursor/mcp.json', 'Cursor'),
    'deepseek-harness': ('DeepSeek Harness', '.dsh/cordis.patch.yml', 'DeepSeek'),
    'zcode': ('ZCode', '.zcode/cli/config.json', 'Z.ai'),
    'workbuddy': ('WorkBuddy', '.workbuddy/mcp.json', 'Tencent'),
    'trae': ('TRAE', '.trae/mcp.json', 'ByteDance'),
}
BEGIN, END = '# Cove MCP begin', '# Cove MCP end'


def digest(content):
    return hashlib.sha256(content).hexdigest()


class Connections:
    def __init__(self, data_dir, home=None):
        self.home = Path(home) if home else Path.home()
        self.data_dir = Path(data_dir) / 'client-backups'
        self.backups = ClientBackups(self.data_dir)
        self.lock = threading.RLock()
        self.managed_path = Path(data_dir) / 'client-connections.json'
        self.issues = {}
        self.backup_cleanup_pending = not self.backups.prune(CLIENTS)

    def _managed(self):
        if not self.managed_path.exists():
            return {}
        records = json.loads(self.managed_path.read_text(encoding='utf-8'))
        if not isinstance(records, dict):
            raise ValueError('自动维护记录无法读取，请重新连接客户端')
        return records

    def _save_managed(self, records):
        from toolbench.sdk import atomic_json
        atomic_json(self.managed_path, records)

    def _entry(self, client, text):
        if client == 'codex':
            return tomlkit.parse(text).get('mcp_servers', {}).get('cove')
        if client == 'deepseek-harness':
            yaml.compose(text)
            block = re.search(r'(?ms)^# Cove MCP begin\r?\n(.*?)^# Cove MCP end(?:\r?\n|$)', text)
            return block.group(1).strip() if block else None
        document = json5.loads(text) if text.strip() else {}
        servers = document.get('mcp', {}).get('servers', {}) if client == 'zcode' else document.get('mcpServers', {})
        return servers.get('cove') if isinstance(servers, dict) else None

    def _signature(self, client, text):
        return digest(json.dumps(self._entry(client, text), sort_keys=True, ensure_ascii=True).encode())

    def maintain(self, profiles):
        """Repair only explicitly enrolled, unchanged Cove entries after upgrades."""
        with self.lock:
            try:
                records = self._managed()
            except (OSError, ValueError):
                return  # A damaged registry must never prevent the desktop opening.
            for profile in profiles:
                client = profile['id']
                record = records.get(client)
                if not record or not record.get('enabled'):
                    continue
                try:
                    path = self.path(client)
                    if str(path) != record['path']:
                        raise ValueError('客户端配置目录已改变，请点击修复连接')
                    text = self._read(path)
                    if self._signature(client, text) != record['signature']:
                        raise ValueError('Cove 条目已被修改或停用；自动维护已暂停，请检查后修复连接')
                    self.install(client, profile)
                except Exception as exc:
                    self.issues[client] = str(exc)

    def manage(self, client, enabled):
        if type(enabled) is not bool:
            raise ValueError('无效的自动维护设置')
        with self.lock:
            records = self._managed()
            if client not in records:
                raise ValueError('请先连接客户端')
            # Re-enrolling requires explicit repair, so changed entries are never adopted silently.
            record = records[client]
            if enabled and (str(self.path(client)) != record['path'] or self._signature(client, self._read(self.path(client))) != record['signature']):
                raise ValueError('配置已变化，请先点击修复连接')
            record['enabled'] = enabled
            self._save_managed(records)
            return {'managed': enabled}

    def path(self, client):
        if client not in CLIENTS:
            raise ValueError('请选择支持的客户端')
        if client == 'deepseek-harness' and os.environ.get('DSH_HOME') and self.home == Path.home():
            return Path(os.environ['DSH_HOME']).expanduser() / 'cordis.patch.yml'
        if client == 'codex' and os.environ.get('CODEX_HOME') and self.home == Path.home():
            return Path(os.environ['CODEX_HOME']).expanduser() / 'config.toml'
        return self.home / CLIENTS[client][1]

    def client_allowed(self, client):
        with self.lock:
            return not self._managed().get(client, {}).get('paused', False)

    def set_connection(self, client, enabled):
        """Pause future requests without terminating adapters or changing client files."""
        if client not in CLIENTS or type(enabled) is not bool:
            raise ValueError('无效的客户端连接设置')
        with self.lock:
            records = self._managed()
            record = records.setdefault(client, {})
            record['paused'] = not enabled
            self._save_managed(records)
        return {'paused': not enabled}

    def catalog(self, profiles, live=()):
        result = []
        try:
            records = self._managed()
        except (OSError, ValueError):
            records = {}
        for profile in profiles:
            client = profile['id']
            path = self.path(client)
            configured = False
            issue = ''
            outdated = False
            try:
                if path.exists():
                    text = self._read(path)
                    if client == 'codex':
                        configured = bool(tomlkit.parse(text).get('mcp_servers', {}).get('cove'))
                    elif client == 'deepseek-harness':
                        yaml.compose(text)
                        configured = BEGIN in text and END in text
                    else:
                        parsed = json5.loads(text)
                        servers = parsed.get('mcp', {}).get('servers', {}) if client == 'zcode' else parsed.get('mcpServers', {})
                        configured = isinstance(servers, dict) and bool(servers.get('cove'))
            except Exception:
                issue = '现有配置无法读取，可在详情中手动接入'
            record = records.get(client, {})
            if configured and client != 'trae' and not issue:
                try:
                    entry = self._entry(client, text)
                    expected = self._entry(client, self.merge(client, text, profile))
                    outdated = entry != expected
                    if record.get('enabled') and (str(path) != record['path'] or self._signature(client, text) != record['signature']):
                        issue = 'Cove 条目已变化，自动维护暂停；请检查后修复连接'
                except Exception as exc:
                    issue = str(exc)
            issue = issue or self.issues.get(client, '')
            result.append({**profile, 'vendor': CLIENTS[client][2], 'path': str(path), 'configured': configured,
                           'connected': client in live and not record.get('paused', False),
                           'paused': bool(record.get('paused', False)), 'issue': issue, 'canInstall': client != 'trae',
                           'managed': bool(record.get('enabled')), 'needsRepair': outdated or bool(issue),
                           'backupCleanupPending': self.backup_cleanup_pending})
        return result

    def _read(self, path):
        return self._read_bytes(path).decode('utf-8-sig')

    def _read_bytes(self, path):
        if path.is_symlink():
            raise ValueError('配置文件过大或使用了符号链接，请在客户端中手动配置')
        with path.open('rb') as stream:
            content = stream.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError('配置文件过大或使用了符号链接，请在客户端中手动配置')
        return content

    def merge(self, client, original, profile):
        server = profile['server']
        if client == 'codex':
            document = tomlkit.parse(original)
            if 'mcp_servers' not in document:
                document['mcp_servers'] = tomlkit.table()
            existing = document['mcp_servers'].get('cove', {})
            if not isinstance(existing, dict):
                raise ValueError('Cove 配置必须是 TOML 表')
            # Preserve client-side approval/tool policies and comments.
            if 'cove' not in document['mcp_servers']:
                document['mcp_servers']['cove'] = tomlkit.table()
            for key in ('url', 'bearer_token_env_var', 'http_headers', 'env_http_headers', 'http_headers_helper', 'auth'):
                document['mcp_servers']['cove'].pop(key, None)
            from toolbench.plugin_framework.policy import POLICY
            document['mcp_servers']['cove'].update({**server, 'startup_timeout_sec': 30, 'tool_timeout_sec': int(POLICY.client)})
            return tomlkit.dumps(document)
        if client == 'deepseek-harness':
            yaml.compose(original)
            if (BEGIN in original) != (END in original):
                raise ValueError('Cove 配置块不完整，请先在客户端中修复')
            cleaned = re.sub(r'(?ms)^# Cove MCP begin\r?\n.*?^# Cove MCP end(?:\r?\n|$)', '', original)
            # Preserve arbitrary !!js expressions and existing comments byte for byte.
            node = yaml.compose(cleaned)
            def has_cove(value):
                if isinstance(value, yaml.MappingNode):
                    return any((getattr(k, 'value', '') == 'serverName' and getattr(v, 'value', '') == 'cove') or has_cove(v) for k, v in value.value)
                if isinstance(value, yaml.SequenceNode):
                    return any(has_cove(v) for v in value.value)
                return False
            if has_cove(node):
                raise ValueError('已有手动配置的 Cove 服务，请先在详情中检查，避免重复连接')
            return cleaned.rstrip() + '\n\n' + BEGIN + '\n' + profile['config'].rstrip() + '\n' + END + '\n'
        document = json5.loads(original) if original.strip() else {}
        if not isinstance(document, dict):
            raise ValueError('客户端配置必须是 JSON 对象')
        if client == 'zcode':
            document.setdefault('mcp', {}).setdefault('servers', {})['cove'] = server
        else:
            document.setdefault('mcpServers', {})['cove'] = server
        # Keep all values; the original formatting/comments remain in the backup.
        return json.dumps(document, ensure_ascii=False, indent=2) + '\n'

    def install(self, client, profile):
        if client == 'trae':
            raise ValueError('请在 TRAE 的 MCP 设置中导入配置；其全局存储由客户端管理')
        with self.lock:
            path = self.path(client)
            existed = path.exists()
            before = self._read_bytes(path) if existed else b''
            original = before.decode('utf-8-sig')
            merged = self.merge(client, original, profile)
            if len(merged.encode('utf-8')) > 2_000_000:
                raise ValueError('合并后的配置过大，请在客户端中手动配置')
            records = self._managed()
            def enroll():
                records[client] = {'path': str(path), 'signature': self._signature(client, merged), 'enabled': True,
                                   'paused': records.get(client, {}).get('paused', False)}
                self._save_managed(records)
                self.issues.pop(client, None)
            if merged.encode('utf-8') == before:
                enroll()
                return {'path': str(path), 'changed': False, 'backupId': None}
            self.data_dir.mkdir(parents=True, exist_ok=True)
            ticket = uuid.uuid4().hex
            from base64 import b64encode
            self.backups.write(ticket, {'path': str(path), 'existed': existed, 'before': b64encode(before).decode(),
                                       'afterHash': digest(merged.encode('utf-8')), 'client': client, 'time': time.time()})
            if path.exists() != existed or (existed and self._read_bytes(path) != before):
                self.backups.remove(ticket)
                raise ValueError('配置在保存前发生变化，请重试')
            atomic_text(path, merged)
            enroll()
            self.backup_cleanup_pending = not self.backups.prune(CLIENTS)
            return {'path': str(path), 'changed': True, 'backupId': ticket}

    def restore(self, ticket):
        if not isinstance(ticket, str) or not re.fullmatch('[a-f0-9]{32}', ticket):
            raise ValueError('备份无效')
        with self.lock:
            record = self.backups.read(ticket)
            path = self.path(record['client'])
            if str(path) != record['path'] or not path.exists() or path.is_symlink() or digest(self._read_bytes(path)) != record['afterHash']:
                raise ValueError('配置已被其他程序修改，为保留新设置，无法自动撤销')
            if record['existed']:
                import base64
                original = base64.b64decode(record['before'], validate=True)
                atomic_bytes(path, original)
            else:
                path.unlink()
            records = self._managed()
            records.pop(record['client'], None)
            self._save_managed(records)
            self.issues.pop(record['client'], None)
            try:
                self.backups.remove(ticket)
            except OSError:
                self.backup_cleanup_pending = True
            return {'restored': True}
