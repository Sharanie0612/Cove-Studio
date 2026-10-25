import io
import json
from pathlib import Path
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
import unittest

from toolbench.host import Host
from fixtures_runtime import TERMINAL,write_terminal_fixture
from toolbench.mcp_bridge import serve, forward
from toolbench.mcp_router import route, definitions


class RouterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.host = Host(data_dir=Path(self.temp.name) / 'data')
        self.host._plugin_drop_root=Path(self.temp.name)/'fixtures'
        write_terminal_fixture(self.host._plugin_drop_root/'terminal')
        self.host.rescan_plugins()
        self.connection = self.host._assistant_gateway.path

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def call(self, name, args):
        return route(name, args, lambda: forward(self.connection, {'operation': 'list'}),
                     lambda tool, arguments: forward(self.connection, {'operation': 'call', 'name': tool, 'arguments': arguments}))

    def test_fixed_catalog_works_offline_and_new_grants_need_no_refresh(self):
        original = definitions()
        self.assertEqual(self.call('cove_tools', {})['result']['total'], 0)
        self.host.assistant_allow([TERMINAL])
        catalog = self.call('cove_tools', {})['result']
        self.assertEqual(catalog['total'], 2)
        self.assertNotIn('parameters', catalog['tools'][0])
        tool = next(t['name'] for t in catalog['tools'] if t['readOnly'])
        schema = self.call('cove_tools', {'tool': tool})['result']
        self.assertIn('parameters', schema)
        result = self.call('cove_read', {'tool': tool, 'arguments': {}})
        self.assertTrue(result['ok']); self.assertFalse(result['result']['connected'])
        self.host.assistant_allow([])
        with self.assertRaisesRegex(ValueError, '未授权'):
            self.call('cove_read', {'tool': tool, 'arguments': {}})
        self.assertEqual(definitions(), original)
        self.host.close()
        outgoing = io.StringIO()
        serve(self.connection, io.StringIO('{"id":1,"method":"tools/list"}\n{"id":2,"method":"tools/call","params":{"name":"cove_tools","arguments":{}}}\n'), outgoing, compact=True)
        replies = [json.loads(line) for line in outgoing.getvalue().splitlines()]
        self.assertEqual({t['name'] for t in replies[0]['result']['tools']}, {'cove_tools', 'cove_read', 'cove_write'})
        self.assertTrue(replies[1]['result']['isError'])
        self.assertIn('请打开 Cove', replies[1]['result']['content'][0]['text'])

    def test_router_cannot_disguise_writes_or_bypass_validation(self):
        self.host.assistant_allow([TERMINAL])
        tools = self.call('cove_tools', {})['result']['tools']
        write = next(t['name'] for t in tools if not t['readOnly'])
        read = next(t['name'] for t in tools if t['readOnly'])
        with self.assertRaisesRegex(ValueError, '写入'):
            self.call('cove_read', {'tool': write, 'arguments': {'value': 'echo forbidden'}})
        with self.assertRaisesRegex(ValueError, '写入'):
            self.call('cove_write', {'tool': read, 'arguments': {}})
        with self.assertRaises(ValueError): self.call('cove_read', {'tool': read, 'arguments': {'unexpected': True}})
        with self.assertRaises(ValueError): self.call('cove_tools', {'query': 'x' * 257})
        self.assertEqual(self.host.assistant_state()['result']['pending'], [])

    def test_compact_client_pause_blocks_discovery_and_calls_without_affecting_other_clients(self):
        self.host.assistant_allow([TERMINAL])
        tool = next(t['name'] for t in self.call('cove_tools', {})['result']['tools'] if t['readOnly'])
        requests = ''.join(json.dumps(item) + '\n' for item in [
            {'id': 1, 'method': 'tools/call', 'params': {'name': 'cove_tools', 'arguments': {}}},
            {'id': 2, 'method': 'tools/call', 'params': {'name': 'cove_read', 'arguments': {'tool': tool, 'arguments': {}}}},
        ])
        def probe(client):
            output = io.StringIO()
            serve(self.connection, io.StringIO(requests), output, client=client, compact=True)
            return [json.loads(line)['result'] for line in output.getvalue().splitlines()]
        self.host.mcp_connection('codex', False)
        for result in probe('codex'):
            self.assertTrue(result['isError'])
            self.assertIn('断开', result['content'][0]['text'])
        self.assertTrue(all(not result.get('isError') for result in probe('cursor')))
        self.host.mcp_connection('codex', True)
        self.assertTrue(all(not result.get('isError') for result in probe('codex')))

    def test_compact_write_still_waits_for_cove_approval_and_denial_blocks_it(self):
        self.host.assistant_allow([TERMINAL])
        tool = next(t['name'] for t in self.call('cove_tools', {})['result']['tools'] if not t['readOnly'])
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.call, 'cove_write', {'tool': tool, 'arguments': {'value': 'echo not-approved'}})
            deadline = time.monotonic() + 5
            pending = []
            while not pending and time.monotonic() < deadline:
                pending = self.host.assistant_state()['result']['pending']
                time.sleep(.02)
            if not pending:
                self.host._assistant_broker.close()
                self.fail('Write did not appear in Cove approval queue')
            self.assertFalse(future.done())
            self.assertEqual(pending[0]['arguments'], {'value': 'echo not-approved'})
            self.host.assistant_decide(pending[0]['id'], False)
            with self.assertRaises(ValueError): future.result(timeout=5)

