"""Verify the frozen MCP adapter with the MCP-only built-in catalog without a model service."""
from pathlib import Path
import json
import os
import subprocess
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from toolbench.host import Host
sys.path.insert(0,str(ROOT/'tests'))
from fixtures_runtime import TERMINAL,write_terminal_fixture


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('installation', type=Path)
    installation = parser.parse_args().installation.resolve()
    data = ROOT / 'artifacts/validation/frozen-mcp' / uuid.uuid4().hex
    data.mkdir(parents=True)
    smoke = data / 'smoke.json'
    env = dict(os.environ, TOOLBENCH_DATA_DIR=str(data / 'clean-data'))
    result = subprocess.run([str(installation / 'Cove.exe'), '--smoke', str(smoke)], capture_output=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    tools = json.loads(smoke.read_text(encoding='utf-8'))['catalog']['tools']
    assert {tool['id'] for tool in tools} == {'dev.cove.mcp'}
    assert all(tool['builtin'] for tool in tools)
    report = {'mcpOnlyBuiltin': True}
    with patch('toolbench.host.ROOT', installation / '_internal'), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(installation / 'Cove.exe')):
        host = Host(data_dir=data / 'data')
        try:
            setup = host.assistant_bridge()
            assert setup['ok'], setup
            assert len(setup['result']['clients']) == 7
            assert host.assistant_check()['result']['toolCount'] == 0
            host._plugin_drop_root=data/'fixtures'
            write_terminal_fixture(host._plugin_drop_root/'terminal')
            host.rescan_plugins()
            assert host.assistant_allow([TERMINAL])['ok']
            check = host.assistant_check()
            assert check['ok'] and check['result']['toolCount'] == 2, check
            tool = next(item for item in host._assistant_broker.definitions() if item['command'] == 'snapshot')
            requests = [{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-11-25'}}, {'jsonrpc':'2.0','id':2,'method':'tools/list'}, {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'cove_read','arguments':{'tool':tool['name'],'arguments':{}}}}]
            result = subprocess.run([str(installation / 'Cove-worker.exe'), '--mcp', '--compact', '--connection', str(host.data_dir / 'mcp-bridge.json')], input=''.join(json.dumps(item, ensure_ascii=False)+'\n' for item in requests), capture_output=True, encoding='utf-8', timeout=20)
            assert result.returncode == 0, result.stderr
            replies = [json.loads(line) for line in result.stdout.splitlines()]
            assert len(replies) == 3 and json.loads(replies[2]['result']['content'][0]['text'])['ok'], replies
            assert {item['name'] for item in replies[1]['result']['tools']} == {'cove_tools', 'cove_read', 'cove_write'}
            def client_call(client):
                value = subprocess.run([str(installation / 'Cove-worker.exe'), '--mcp', '--compact',
                                        '--client', client, '--connection', str(host.data_dir / 'mcp-bridge.json')],
                                       input=''.join(json.dumps(item) + '\n' for item in requests),
                                       capture_output=True, encoding='utf-8', timeout=20)
                assert value.returncode == 0, value.stderr
                return [json.loads(line) for line in value.stdout.splitlines()][2]['result']
            assert host.mcp_connection('codex', False)['ok']
            blocked = client_call('codex')
            assert blocked.get('isError') and '断开' in blocked['content'][0]['text'], blocked
            assert not client_call('cursor').get('isError')
            assert host.mcp_connection('codex', True)['ok']
            assert not client_call('codex').get('isError')
            report['frozenClientDisconnectReconnect'] = True
            # The installed export runtime must also be complete.
            from toolbench.distribution import portable_archive
            import io, zipfile
            portable = zipfile.ZipFile(io.BytesIO(portable_archive(host._plugin_drop_root/'terminal')))
            assert 'runtime/toolbench/plugin_mcp.py' in portable.namelist()
            assert 'setup_dsh.py' in portable.namelist()
            report.update(sevenClientProfiles=True, frozenSelfCheck=True, frozenToolCalls=True, frozenPortableExport=True)
        finally:
            host.close()
    (ROOT / 'artifacts/validation/mcp.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()

