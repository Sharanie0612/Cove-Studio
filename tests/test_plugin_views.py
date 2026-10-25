from concurrent.futures import ThreadPoolExecutor
import copy
import io
import inspect
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile

from toolbench.host import Host, ROOT
from toolbench.contracts import compatibility_report
from toolbench.manifest import validate_manifest
from toolbench.packages import build_package, inspect_archive
from toolbench.bridge import API_METHODS


class PluginViewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'artifacts')
        self.root = Path(self.temp.name)
        self.patch = patch('toolbench.assistance.AssistanceApi._sync_mcp_service', lambda self: None)
        self.patch.start()
        self.host = Host(plugins_dir=self.root / 'empty', data_dir=self.root / 'data')
        source = ROOT / 'docs/examples/web-starter'
        self.package = self.root / 'example.cove-plugin'
        self.package.write_bytes(build_package(source)['content'])
        self.assertFalse(self.host.workers)
        preview = self.host._inspect_package(self.package)
        self.assertTrue(self.host.install_plugin(preview['ticket'])['ok'])
        self.identity = 'community.web-starter'
        self.ticket = self.host.plugin_view_open(self.identity)['result']['ticket']

    def tearDown(self):
        self.host.close()
        self.patch.stop()
        self.temp.cleanup()

    def pending(self):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            items = self.host.assistant_state()['result']['pending']
            if items:
                return items[0]
            time.sleep(.01)
        self.fail('Approval was not presented')

    def test_metadata_open_does_not_execute_plugin_and_reads_need_no_ai_grant(self):
        self.assertFalse(self.host.workers)
        self.host._preferences['disabled'].append('dev.cove.mcp')
        reply = self.host.plugin_view_call(self.ticket, 'snapshot', {})
        self.assertTrue(reply['ok'], reply)
        self.assertEqual(reply['result']['value'], 0)
        self.assertFalse(self.host._assistant_broker.allowed)
        self.assertFalse(self.host.plugin_view_call(self.ticket, 'undeclared', {})['ok'])
        self.assertFalse(self.host.plugin_view_call(self.ticket, 'increment', {'amount': 100})['ok'])

    def test_native_bridge_parameters_do_not_shadow_the_javascript_arguments_object(self):
        for method in API_METHODS:
            self.assertNotIn('arguments', inspect.signature(getattr(self.host, method)).parameters, method)

    def test_write_requires_approval_even_when_mcp_is_disabled(self):
        self.host._preferences['disabled'].append('dev.cove.mcp')
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.plugin_view_call, self.ticket, 'increment', {'amount': 2})
            pending = self.pending()
            self.assertEqual(pending['arguments'], {'amount': 2})
            self.assertFalse(self.host.workers)
            self.host.assistant_decide(pending['id'], True)
            self.assertEqual(future.result(timeout=5)['result']['value'], 2)

    def test_close_revokes_pending_writes_and_late_decisions(self):
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.plugin_view_call, self.ticket, 'increment', {'amount': 1})
            pending = self.pending()
            self.host.plugin_view_close(self.ticket)
            self.assertFalse(future.result(timeout=5)['ok'])
            self.assertFalse(self.host.assistant_decide(pending['id'], True)['ok'])
        self.assertFalse(self.host.workers)

    def test_grants_are_independent_and_stop_invalidates_sessions(self):
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.plugin_view_call, self.ticket, 'increment', {'amount': 1})
            pending = self.pending()
            self.host.assistant_allow([])
            self.assertFalse(future.done())
            self.host.assistant_decide(pending['id'], False)
            self.assertFalse(future.result(timeout=5)['ok'])
        self.host.plugin_action(self.identity, 'stop', True)
        self.assertFalse(self.host.plugin_view_call(self.ticket, 'snapshot', {})['ok'])

    def test_manifest_change_invalidates_an_approved_but_not_executed_call(self):
        with ThreadPoolExecutor() as pool:
            future = pool.submit(self.host.plugin_view_call, self.ticket, 'increment', {'amount': 1})
            pending = self.pending()
            self.host.plugins[self.identity][1]['version'] = 'changed'
            self.host.assistant_decide(pending['id'], True)
            self.assertFalse(future.result(timeout=5)['ok'])
        self.assertFalse(self.host.workers)

    def test_download_includes_nested_ui_assets_and_packages_remain_independent(self):
        with zipfile.ZipFile(io.BytesIO(self.host._starter_bytes())) as archive:
            html = archive.read('cove-plugin-starter/examples/web-starter/ui/index.html')
        self.assertIn(b'window.Cove', html)
        self.assertNotIn(b'pywebview', html)

    def test_unsafe_entry_and_missing_resource_are_rejected_without_execution(self):
        manifest = json.loads((ROOT / 'docs/examples/web-starter/manifest.json').read_text(encoding='utf-8'))
        for entry in ('../private.html', '/absolute.html', 'https://example.com/ui.html', 'ui\\index.html'):
            changed = copy.deepcopy(manifest)
            changed['ui']['web']['entry'] = entry
            with self.assertRaises(ValueError):
                validate_manifest(changed)
        content = io.BytesIO()
        with zipfile.ZipFile(content, 'w') as archive:
            archive.writestr('manifest.json', json.dumps(manifest))
            archive.writestr('plugin.py', 'raise RuntimeError("must not execute")')
        with self.assertRaisesRegex(ValueError, 'missing'):
            inspect_archive(content.getvalue())

    def test_retired_extension_is_diagnosable_instead_of_silent_fallback(self):
        manifest = json.loads((ROOT / 'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        manifest['ui']['legacy-domain'] = {}
        validate_manifest(manifest)
        self.assertFalse(compatibility_report(manifest)['supported'])


if __name__ == '__main__':
    unittest.main()
