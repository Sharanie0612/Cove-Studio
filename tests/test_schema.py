import json
import unittest

from jsonschema import Draft202012Validator

from toolbench.host import ROOT, validate_manifest


class SchemaTests(unittest.TestCase):
    def test_manifest_schema_and_examples(self):
        schema = json.loads((ROOT / "schemas/plugin-manifest.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        manifests = list((ROOT / "plugins/projects").glob("*/manifest.json")) + list((ROOT / "docs/templates").glob("*/manifest.json"))
        for path in manifests:
            with self.subTest(plugin=path.parent.name):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                validator.validate(manifest)
                validate_manifest(manifest)

    def test_invalid_field_reference_is_rejected(self):
        manifest = json.loads((ROOT / "docs/templates/starter/manifest.json").read_text(encoding="utf-8"))
        manifest["ui"]["fields"][0]["showWhen"] = {"field": "missing", "equals": "x"}
        with self.assertRaises(ValueError):
            validate_manifest(manifest)
