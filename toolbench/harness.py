"""Client-specific MCP contracts, generated from one server definition."""
from __future__ import annotations
import json
import yaml
from toolbench.plugin_framework.policy import POLICY


def powershell(value):
    return "'" + value.replace("'", "''") + "'"


CLIENTS = [
    ('codex', 'Codex', '~/.codex/config.toml', 'TOML',
     '重新加载 MCP 后用 /mcp 检查连接。', 'https://learn.chatgpt.com/docs/extend/mcp?surface=cli'),
    ('claude-code', 'Claude Code', '~/.claude.json', 'JSON',
     '重启 Claude Code，再用 /mcp 检查。项目级配置也可放在 .mcp.json。', 'https://code.claude.com/docs/en/mcp'),
    ('cursor', 'Cursor', '~/.cursor/mcp.json', 'JSON',
     '在 Cursor 的 MCP 设置中启用 Cove。', 'https://prod.cursor.com/help/customization/mcp'),
    ('deepseek-harness', 'DeepSeek Harness', '~/.dsh/cordis.patch.yml', 'YAML',
     '重启 dsh web；此配置使用官方 dsh-mcp-client 插件。自定义 DSH_HOME 时自动使用该目录。',
     'https://github.com/deepseek-ai/deepseek-harness/blob/master/packages/mcp/mcp-client/README.md'),
    ('zcode', 'ZCode', '~/.zcode/cli/config.json', 'JSON',
     '在 MCP Servers 中重新加载 Cove。', 'https://zcode.z.ai/en/docs/mcp-services'),
    ('workbuddy', 'WorkBuddy', '~/.workbuddy/mcp.json', 'JSON',
     '插件 → MCP 服务器 → 重新加载 Cove。',
     'https://www.codebuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/MCP-Guide'),
    ('trae', 'TRAE', '设置 → MCP → 手动添加 → 原始配置', 'JSON',
     '导入 JSON 后为当前智能体启用 Cove。若客户端拒绝带空格的命令路径，使用无空格的 Cove 安装目录。',
     'https://docs.trae.cn/ide_add-mcp-servers'),
]


def client_profiles(command, args, env):
    profiles = []
    dump = lambda value: json.dumps(value, ensure_ascii=False, indent=2)
    env_flags = ''.join(' --env ' + powershell(key + '=' + value) for key, value in env.items())
    for identity, name, location, format, steps, docs in CLIENTS:
        server = {'command': command, 'args': [*args, '--compact', '--client', identity], 'env': dict(env)}
        profile = dict(id=identity, name=name, location=location, format=format, steps=steps, docs=docs)
        launch = ' '.join(powershell(value) for value in [command, *server['args']])
        if identity == 'codex':
            server['enabled'] = True
            config = '[mcp_servers.cove]\nenabled = true\ncommand = ' + json.dumps(command) + '\nargs = ' + json.dumps(server['args']) + f'\nstartup_timeout_sec = 30\ntool_timeout_sec = {int(POLICY.client)}\n'
            if env:
                config += '\n[mcp_servers.cove.env]\n' + ''.join(key + ' = ' + json.dumps(value) + '\n' for key, value in env.items())
            profile['installCommand'] = 'codex mcp add cove' + env_flags + ' -- ' + launch
        elif identity == 'deepseek-harness':
            config = yaml.safe_dump([{'insert': [{'id': 'cove-mcp', 'name': '@deepseek-ai/dsh-mcp-client',
                'config': {'serverName': 'cove', 'transport': 'stdio', **server, 'toolCallTimeoutMs': int(POLICY.client * 1000)}}]}], sort_keys=False, allow_unicode=True)
        else:
            if identity in ('claude-code', 'workbuddy'):
                server = {'type': 'stdio', **server, 'timeout': int(POLICY.client * 1000)}
            if identity == 'zcode':
                server = {'type': 'stdio', **server, 'timeoutMs': int(POLICY.client * 1000)}
                config = dump({'mcp': {'servers': {'cove': server}}})
            else:
                if identity == 'trae':
                    server['env']['RUN_MCP_TIMEOUT_MS'] = str(int(POLICY.client * 1000))
                config = dump({'mcpServers': {'cove': server}})
            if identity == 'claude-code':
                profile['installCommand'] = 'claude mcp add --transport stdio --scope user cove' + env_flags + ' -- ' + launch
        profiles.append({**profile, 'server': server, 'config': config})
    return profiles
