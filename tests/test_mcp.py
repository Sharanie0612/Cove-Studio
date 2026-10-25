import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from toolbench.host import Host, ROOT
from fixtures_runtime import APPROVAL, TERMINAL, write_approval_fixture, write_terminal_fixture

class McpTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temp.name)
        self.host = Host(data_dir=self.root / 'data')
    def tearDown(self):
        self.host.close()
        self.temp.cleanup()
    def fixture(self):
        self.host._plugin_drop_root = self.root / 'fixtures'
        write_terminal_fixture(self.host._plugin_drop_root / 'terminal')
        self.host.rescan_plugins()
        self.assertTrue(self.host.assistant_allow([TERMINAL])['ok'])
    def test_default_catalog_contains_only_builtin_mcp(self):
        self.assertEqual(set(self.host.plugins), {'dev.cove.mcp'})
        self.assertEqual(self.host._assistant_broker.definitions(), [])
        result = self.host.assistant_check()
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['result']['toolCount'], 0)
    def test_explicit_authorization_routes_reads_to_same_worker(self):
        self.fixture()
        definition = next(t for t in self.host._assistant_broker.definitions() if t['readOnly'])
        call = lambda: self.host._assistant_broker.call('mcp', definition['name'], {})
        self.assertFalse(call()['result']['connected'])
        pid = self.host.workers[TERMINAL].process.pid
        self.assertTrue(call()['ok'])
        self.assertEqual(self.host.workers[TERMINAL].process.pid, pid)
        self.host.assistant_allow([])
        with self.assertRaises(ValueError): call()
    def test_write_executes_only_after_explicit_confirmation(self):
        self.fixture()
        definition = next(t for t in self.host._assistant_broker.definitions() if not t['readOnly'])
        with ThreadPoolExecutor() as pool:
            result = pool.submit(self.host._assistant_broker.call, 'mcp', definition['name'], {'value':'approved'})
            until = time.monotonic()+4
            while time.monotonic()<until:
                pending = self.host.assistant_state()['result']['pending']
                if pending: break
                time.sleep(.02)
            self.assertTrue(pending)
            self.assertEqual(self.host.invoke(TERMINAL,'snapshot')['result']['records'], [])
            self.assertTrue(self.host.assistant_decide(pending[0]['id'], True)['ok'])
            self.assertEqual(result.result(timeout=4)['result']['recorded'], 'approved')
    def test_disabling_mcp_preserves_independent_worker(self):
        self.fixture()
        self.host.invoke(TERMINAL,'snapshot')
        process = self.host.workers[TERMINAL].process
        self.assertTrue(self.host.plugin_action('dev.cove.mcp','disable')['ok'])
        self.assertIsNone(process.poll())
        self.assertFalse(self.host.assistant_bridge()['ok'])
        self.assertFalse((self.host.data_dir/'mcp-bridge.json').exists())
        self.assertTrue(self.host.plugin_action('dev.cove.mcp','enable')['ok'])
        self.assertEqual(self.host._assistant_broker.allowed, {TERMINAL})
