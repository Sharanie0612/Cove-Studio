import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from toolbench.contracts import compatibility_report
from toolbench.host import Host, ROOT
from toolbench.manifest import validate_manifest
from toolbench.packages import build_package


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((ROOT / 'docs/templates/starter/manifest.json').read_text(encoding='utf-8'))
        self.schema = Draft202012Validator(json.loads((ROOT / 'schemas/plugin-manifest.schema.json').read_text(encoding='utf-8')))

    def test_legacy_manifest_and_inclusive_version_bounds(self):
        self.manifest.pop('compatibility', None)  # Model a legacy manifest, not the new localized starter.
        self.assertTrue(compatibility_report(self.manifest, '0.9.0')['supported'])
        self.manifest['compatibility'] = {'minHostVersion':'0.9.0', 'maxHostVersion':'0.10.0', 'capabilities':['ui.form']}
        self.schema.validate(self.manifest)
        validate_manifest(self.manifest)
        for version, expected in [('0.8.9',False),('0.9.0',True),('0.10.0',True),('0.10.1',False)]:
            self.assertEqual(compatibility_report(self.manifest,version)['supported'], expected)

    def test_missing_capabilities_are_reported_without_importing_code(self):
        self.manifest['compatibility'] = {'capabilities':['ui.form', 'ui.future']}
        self.schema.validate(self.manifest)
        validate_manifest(self.manifest)
        report = compatibility_report(self.manifest)
        self.assertFalse(report['supported'])
        self.assertIn('ui.future', report['reasons'][0])

    def test_invalid_compatibility_declarations_are_rejected(self):
        for value in ([], {'minHostVersion':'latest'}, {'minHostVersion':'2.0.0','maxHostVersion':'1.0.0'}, {'capabilities':['ui.form','ui.form']}, {'capabilities':None}, {'unknown':1}):
            with self.subTest(value=value):
                self.manifest['compatibility'] = value
                with self.assertRaises(ValueError): validate_manifest(self.manifest)

    def test_third_party_cannot_claim_host_mcp_surface(self):
        self.manifest['ui']['surface'] = 'mcp'
        with self.assertRaisesRegex(ValueError, 'MCP'):
            validate_manifest(self.manifest)

    def test_incompatible_archive_rejected_before_installation(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            base = Path(temporary)
            folder = base / 'source'
            folder.mkdir()
            self.manifest['compatibility'] = {'capabilities': ['ui.future']}
            (folder/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
            (folder/'plugin.py').write_text('raise RuntimeError("must never import")',encoding='utf-8')
            archive = base/'future.cove-plugin'
            archive.write_bytes(build_package(folder)['content'])
            host = Host(plugins_dir=base/'empty',data_dir=base/'data')
            try:
                with self.assertRaisesRegex(ValueError, 'ui.future'):
                    host._inspect_package(archive)
                self.assertFalse(host._package_tickets)
                self.assertFalse(host.workers)
            finally:
                host.close()

    def test_incompatible_discovered_plugin_cannot_start_or_reach_mcp(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            base = Path(temporary)
            folder = base / 'plugins/example'
            folder.mkdir(parents=True)
            self.manifest['compatibility'] = {'minHostVersion':'99.0.0'}
            (folder/'manifest.json').write_text(json.dumps(self.manifest),encoding='utf-8')
            (folder/'plugin.py').write_text('raise RuntimeError("must never import")',encoding='utf-8')
            host = Host(plugins_dir=base/'plugins',data_dir=base/'data')
            try:
                tool = next(t for t in host.catalog()['tools'] if t['id'] == self.manifest['id'])
                self.assertFalse(tool['compatibilityStatus']['supported'])
                with patch('toolbench.host.Worker') as worker:
                    self.assertFalse(host.plugin_action(tool['id'],'start')['ok'])
                    self.assertFalse(host.invoke(tool['id'],self.manifest['commands'][0])['ok'])
                    worker.assert_not_called()
                self.assertFalse(host._assistant_broker.definitions(False))
            finally:
                host.close()
