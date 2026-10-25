import copy
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator, ValidationError
from toolbench.contracts import compatibility_report
from toolbench.host import Host, ROOT
from toolbench.manifest import validate_manifest
from toolbench.packages import build_package


class ResultContractTests(unittest.TestCase):
    def setUp(self):
        self.source = ROOT / 'docs/examples/result-starter'
        self.manifest = json.loads((self.source / 'manifest.json').read_text(encoding='utf-8'))
        self.schema = Draft202012Validator(json.loads((ROOT / 'schemas/plugin-manifest.schema.json').read_text(encoding='utf-8')))

    def test_layout_contract_and_real_worker_without_core_registration(self):
        self.schema.validate(self.manifest)
        validate_manifest(self.manifest)
        self.assertTrue(compatibility_report(self.manifest)['supported'])
        self.assertFalse(compatibility_report(self.manifest, '0.10.1')['supported'])
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            data = Path(temporary)
            archive = data / 'example.cove-plugin'
            archive.write_bytes(build_package(self.source)['content'])
            host = Host(plugins_dir=data / 'empty', data_dir=data / 'data')
            try:
                preview = host._inspect_package(archive)
                self.assertFalse(host.workers, 'metadata inspection must not execute the plugin')
                installed = host.install_plugin(preview['ticket'])
                self.assertTrue(installed['ok'], installed)
                reply = host.invoke(self.manifest['id'], 'analyze', {'text': 'Cove cove tools'})
                self.assertTrue(reply['ok'], reply)
                self.assertEqual(reply['result']['words'], 3)
                self.assertEqual(reply['result']['frequencies'][0], {'word': 'cove', 'count': 2})
            finally:
                host.close()

    def test_metadata_free_legacy_form_still_valid(self):
        self.manifest.pop('compatibility')
        self.manifest['ui'].pop('result')
        self.schema.validate(self.manifest)
        validate_manifest(self.manifest)

    def test_new_layout_requires_explicit_capability_and_cannot_override_other_surfaces(self):
        invalid = []
        missing = copy.deepcopy(self.manifest)
        missing.pop('compatibility')
        invalid.append(missing)
        for key in ('job', 'web'):
            item = copy.deepcopy(self.manifest)
            item['ui'][key] = {}
            invalid.append(item)
        terminal = copy.deepcopy(self.manifest)
        terminal['ui']['surface'] = 'terminal'
        invalid.append(terminal)
        for manifest in invalid:
            with self.subTest(ui=manifest['ui']):
                with self.assertRaises(ValueError): validate_manifest(manifest)
                with self.assertRaises(ValidationError): self.schema.validate(manifest)

    def test_invalid_result_layout_is_rejected_by_both_validators(self):
        for layout in ({}, {'fields': []}, {'fields': [{'key': 'a.b', 'label': 'Bad'}]},
                       {'fields': [{'key': 'a', 'label': 'Bad', 'format': 'html'}]},
                       {'fields': [{'key': 'a', 'label': ''}]},
                       {'table': {'key': 'rows', 'columns': []}},
                       {'fields': [{'key': 'a', 'label': 'A'}], 'html': '<script/>'}):
            with self.subTest(layout=layout):
                self.manifest['ui']['result'] = layout
                with self.assertRaises(ValueError): validate_manifest(self.manifest)
                with self.assertRaises(ValidationError): self.schema.validate(self.manifest)

    def test_duplicate_keys_are_diagnosable_before_launch(self):
        self.manifest['ui']['result']['fields'] *= 2
        with self.assertRaisesRegex(ValueError, '唯一'):
            validate_manifest(self.manifest)
