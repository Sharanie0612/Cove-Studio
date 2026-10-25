"""Deterministic lock-order and offline catalog publication regressions."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from toolbench.host import Host, ROOT
from fixtures_runtime import TERMINAL, write_terminal_fixture
from toolbench.mcp_bridge import atomic_json


class BoundedRLock:
    """Make an incorrect lock order fail rather than hang test teardown."""
    def __init__(self):
        self.lock = threading.RLock()

    def __enter__(self):
        if not self.lock.acquire(timeout=3):
            raise RuntimeError('Broker lock was held while waiting on another subsystem')
        return self

    def __exit__(self, *_):
        self.lock.release()


class McpLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.host = Host(data_dir=Path(self.temp.name) / 'data')
        self.host._plugin_drop_root = Path(self.temp.name) / 'fixtures'
        write_terminal_fixture(self.host._plugin_drop_root / 'terminal')
        self.host.rescan_plugins()
        self.broker = self.host._assistant_broker
        self.gateway = self.host._assistant_gateway
        self.errors = []
        self.results = {}

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def start(self, name, operation):
        def run():
            try:
                self.results[name] = operation()
            except Exception as exc:
                self.errors.append((name, exc))
        thread = threading.Thread(target=run, name=name, daemon=True)
        thread.start()
        return thread

    def finish(self, *threads):
        for thread in threads:
            thread.join(timeout=6)
            self.assertFalse(thread.is_alive(), f'{thread.name} did not finish')
        self.assertEqual(self.errors, [])

    def test_publication_and_approval_snapshot_never_invert_session_and_broker_locks(self):
        self.broker.lock = BoundedRLock()
        rendezvous = threading.Barrier(2, timeout=3)
        definitions = self.broker.definitions
        live_clients = self.gateway.live_clients

        def catalog(selected_only=True):
            if threading.current_thread().name == 'publisher':
                rendezvous.wait()
            return definitions(selected_only)

        def clients():
            rendezvous.wait()
            return live_clients()

        with patch.object(self.broker, 'definitions', side_effect=catalog), \
                patch.object(self.gateway, 'live_clients', side_effect=clients):
            publisher = self.start('publisher', self.gateway.publish_tools)
            reader = self.start('reader', self.host.assistant_state)
            self.finish(publisher, reader)
        self.assertTrue(self.results['reader']['ok'])
        self.assertEqual(self.results['reader']['result']['clients'], [])

    def test_revocation_waits_for_old_publication_and_leaves_latest_catalog(self):
        self.assertTrue(self.host.assistant_allow([TERMINAL])['ok'])
        path = self.host.data_dir / 'mcp-tools.json'
        path.unlink()
        write_started = threading.Event()
        release_write = threading.Event()
        revoked = threading.Event()
        tracking = threading.Lock()
        active = 0
        maximum = 0
        writes = 0
        select = self.broker.select

        def write(destination, content, **kwargs):
            nonlocal active, maximum, writes
            if destination != path:
                return atomic_json(destination, content, **kwargs)
            with tracking:
                active += 1
                maximum = max(maximum, active)
                writes += 1
                first = writes == 1
            try:
                if first:
                    write_started.set()
                    if not release_write.wait(timeout=3):
                        raise RuntimeError('Test did not release the initial publication')
                return atomic_json(destination, content, **kwargs)
            finally:
                with tracking:
                    active -= 1

        def revoke(plugins):
            select(plugins)
            revoked.set()

        with patch('toolbench.mcp_bridge.atomic_json', side_effect=write), \
                patch.object(self.broker, 'select', side_effect=revoke):
            publisher = self.start('publisher', self.gateway.publish_tools)
            revoker = None
            try:
                self.assertTrue(write_started.wait(timeout=3))
                revoker = self.start('revoker', lambda: self.host.assistant_allow([]))
                self.assertTrue(revoked.wait(timeout=3))
            finally:
                release_write.set()
                self.finish(*[thread for thread in (publisher, revoker) if thread])
        self.assertTrue(self.results['revoker']['ok'])
        self.assertEqual(maximum, 1)
        self.assertEqual(writes, 2)
        self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'tools': []})
        self.assertEqual(self.broker.definitions(), [])


if __name__ == '__main__':
    unittest.main()
