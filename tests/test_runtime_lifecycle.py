from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock

from toolbench.host import Host, ROOT
from toolbench.plugin_framework.policy import POLICY
from toolbench.runtime import Worker, PluginFailure


class RuntimeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.root = Path(self.temporary.name)
        self.manifest = json.loads((ROOT / 'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        self.host = Host(plugins_dir=self.root / 'plugins', data_dir=self.root / 'data')

    def tearDown(self):
        self.host.close()
        self.temporary.cleanup()

    def project(self, identity, source, commands):
        folder = self.root / 'plugins' / identity
        folder.mkdir(parents=True)
        manifest = {**self.manifest, 'id': identity, 'commands': commands,
                    'permissions': ['host.tools'],
                    'ui': {**self.manifest['ui'], 'actions': [{'command': commands[0], 'label': 'Run'}]}}
        manifest.pop('ai', None)
        (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        (folder / 'plugin.py').write_text(source, encoding='utf-8')
        return folder, manifest

    def pending(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            pending = self.host.assistant_state()['result']['pending']
            if pending:
                return pending[0]
            time.sleep(.02)
        self.fail('Approval did not appear')

    def test_constructor_sdk_reply_is_read_before_ready(self):
        folder, manifest = self.project('test.constructor',
            'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
            ' def __init__(self, context):\n  super().__init__(context)\n  self.items = context.tools()\n'
            ' def run(self): return self.items\n', ['run'])
        worker = Worker(folder, manifest, self.root / 'constructor', lambda *_: None,
                        host_call=lambda *_: ['ready'], root=ROOT)
        try:
            self.assertEqual(worker.invoke('run', {}), ['ready'])
        finally:
            worker.close()

    def test_sdk_wait_longer_than_normal_command_budget_keeps_worker_alive(self):
        folder, manifest = self.project('test.wait',
            'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
            ' def run(self): return self.context.tools()\n', ['run'])
        def delayed(*_):
            time.sleep(21)
            return ['completed after original twenty-second deadline']
        worker = Worker(folder, manifest, self.root / 'wait', lambda *_: None,
                        host_call=delayed, root=ROOT)
        try:
            self.assertEqual(len(worker.invoke('run', {})), 1)
            self.assertIsNone(worker.process.poll())
        finally:
            worker.close()

    def test_approval_wait_and_caller_cancellation_cross_the_real_sdk(self):
        target, manifest = self.project('test.target',
            'from toolbench.sdk import Plugin\nfrom pathlib import Path\nclass Tool(Plugin):\n'
            ' def write(self):\n  Path(self.context.data_dir,"executed").write_text("yes")\n  return True\n', ['write'])
        manifest['ai'] = {'tools': [{'name': 'write', 'command': 'write', 'description': 'Test write',
                                    'readOnly': False, 'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}}]}
        (target / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        self.project('test.caller',
            'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
            ' def run(self, name): return self.context.call_tool(name,{})\n', ['run'])
        self.host.rescan_plugins()
        self.host.assistant_allow(['test.target'])
        name = self.host._assistant_broker.definitions()[0]['name']
        self.host.plugin_action('test.caller', 'start')
        worker = self.host.workers['test.caller']
        worker.policy = replace(POLICY, command=.12, poll=.01)
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.invoke, 'test.caller', 'run', {'name': name})
            approval = self.pending()
            time.sleep(.3)
            self.assertFalse(future.done())
            self.assertIsNone(worker.process.poll())
            self.host.assistant_decide(approval['id'], True)
            self.assertTrue(future.result(timeout=4)['result']['ok'])
            marker = self.host.data_dir / 'test.target/executed'
            marker.unlink()
            future = pool.submit(self.host.invoke, 'test.caller', 'run', {'name': name})
            approval = self.pending()
            protected = self.host.plugin_action('test.caller', 'stop')['result']
            self.assertTrue(protected['needsConfirmation'])
            self.assertTrue(self.host.plugin_action('test.caller', 'stop', True)['ok'])
            self.assertFalse(future.result(timeout=4)['ok'])
            self.assertFalse(self.host.assistant_decide(approval['id'], True)['ok'])
            self.assertFalse(marker.exists())
            future = pool.submit(self.host._assistant_broker.call, 'mcp', name, {})
            approval = self.pending()
            self.assertTrue(self.host.plugin_action('test.target', 'stop')['result']['needsConfirmation'])
            self.assertTrue(self.host.plugin_action('test.target', 'stop', True)['ok'])
            with self.assertRaises(ValueError):
                future.result(timeout=4)
            self.assertFalse(marker.exists())

    def test_background_work_guards_exit_stop_restart_disable_and_idle_release(self):
        self.project('test.activity', 'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
                     ' def run(self):\n  self.context.emit("activity",active=True)\n  return True\n', ['run'])
        self.host.rescan_plugins()
        self.assertTrue(self.host.invoke('test.activity', 'run')['ok'])
        worker = self.host.workers['test.activity']
        self.host._window = Mock()
        for operation in ('stop', 'restart', 'disable', 'remove'):
            result = self.host.plugin_action('test.activity', operation)['result']
            self.assertTrue(result['needsConfirmation'], operation)
            self.assertEqual(result['backgroundTasks'], 1)
            self.assertIsNone(worker.process.poll())
        self.assertEqual(self.host.plugin_action('', 'stop_idle')['result']['stopped'], 0)
        self.assertTrue(self.host.window_action('close')['result']['needsConfirmation'])
        self.host._window.destroy.assert_not_called()
        self.assertTrue(self.host.plugin_action('test.activity', 'stop', True)['ok'])
        self.assertFalse(self.host._work_state('test.activity')['active'])

    def test_startup_diagnostics_explain_missing_dependency_without_stderr_secrets(self):
        self.project('test.broken', 'print("token=do-not-store",file=__import__("sys").stderr)\n'
                     'import missing_test_dependency\n', ['run'])
        self.host.rescan_plugins()
        result = self.host.plugin_action('test.broken', 'start')
        self.assertFalse(result['ok'])
        self.assertEqual(result['code'], 'STARTUP_FAILED')
        self.assertIn('missing_test_dependency', result['error'])
        report = self.host.plugin_diagnostics('test.broken')['result']
        serialized = json.dumps(report)
        self.assertNotIn('do-not-store', serialized)
        self.assertNotIn(str(self.root), serialized)
        self.assertIn('ModuleNotFoundError', serialized)
        self.assertFalse(self.host.workers)

    def test_invalid_interpreter_is_a_recoverable_startup_error(self):
        self.project('test.interpreter', 'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n def run(self): return True\n', ['run'])
        self.host.rescan_plugins()
        self.host._preferences['interpreters']['test.interpreter'] = str(self.root / 'absent/python.exe')
        reply = self.host.plugin_action('test.interpreter', 'start')
        self.assertFalse(reply['ok'])
        self.assertEqual(reply['code'], 'STARTUP_FAILED')
        report = self.host.plugin_diagnostics('test.interpreter')['result']
        self.assertEqual(report['phase'], 'launch')
        self.assertFalse(self.host.workers)

    def test_close_during_sdk_constructor_protects_startup_and_leaves_no_worker(self):
        self.project('test.starting', 'from toolbench.sdk import Plugin\nclass Tool(Plugin):\n'
                     ' def __init__(self,context):\n  super().__init__(context)\n  context.tools()\n'
                     ' def run(self): return True\n', ['run'])
        self.host.rescan_plugins()
        entered, release = threading.Event(), threading.Event()
        def delayed(*_):
            entered.set()
            release.wait(3)
            return []
        self.host._host_tool_call = delayed
        self.host._window = Mock()
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.plugin_action, 'test.starting', 'start')
            self.assertTrue(entered.wait(2))
            self.assertTrue(self.host.window_action('close')['result']['needsConfirmation'])
            self.assertTrue(self.host.window_action('close', True)['ok'])
            release.set()
            self.assertFalse(future.result(timeout=5)['ok'])
        self.assertFalse(self.host.workers)

    def test_unexpected_exit_clears_activity_and_next_start_recovers(self):
        folder, _ = self.project('test.exit', 'from toolbench.sdk import Plugin\nimport os\nclass Tool(Plugin):\n'
                                ' def run(self):\n  self.context.emit("activity",active=True)\n  os._exit(7)\n', ['run'])
        self.host.rescan_plugins()
        self.assertFalse(self.host.invoke('test.exit', 'run')['ok'])
        time.sleep(.1)
        self.assertFalse(self.host._work_state('test.exit')['background'])
        self.assertEqual(self.host.plugin_diagnostics('test.exit')['result']['exitCode'], 7)
        (folder / 'plugin.py').write_text('from toolbench.sdk import Plugin\nclass Tool(Plugin):\n def run(self): return "recovered"\n', encoding='utf-8')
        self.assertEqual(self.host.invoke('test.exit', 'run')['result'], 'recovered')
