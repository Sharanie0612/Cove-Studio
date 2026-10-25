"""Run one Cove plugin as a read-only MCP server, including in DeepSeek Harness."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator
from toolbench.manifest import validate_manifest
from toolbench.protocol import serve_rpc, tool_name
from toolbench.sdk import Context


class PluginServer:
    def __init__(self, directory, data_dir):
        self.directory = Path(directory).resolve()
        self.manifest = json.loads((self.directory / 'manifest.json').read_text(encoding='utf-8-sig'))
        validate_manifest(self.manifest)
        import uuid
        self.module_name = 'cove_portable_' + uuid.uuid4().hex
        spec = importlib.util.spec_from_file_location(self.module_name, self.directory / 'plugin.py', submodule_search_locations=[str(self.directory)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        sys.path.insert(0, str(self.directory))
        vendor = self.directory / 'vendor'
        if vendor.is_dir():
            sys.path.insert(1, str(vendor))
        try:
            import contextlib
            with contextlib.redirect_stdout(sys.stderr):
                spec.loader.exec_module(module)
        finally:
            sys.path.pop(0)
            if vendor.is_dir():
                sys.path.remove(str(vendor))
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        with contextlib.redirect_stdout(sys.stderr):
            self.plugin = module.Tool(Context(lambda event: None, str(data_dir),
                                              localization=self.manifest.get('localization')))

    def definitions(self):
        return [{**tool, 'name': tool_name(self.manifest['id'], tool['name'])}
                for tool in self.manifest.get('ai', {}).get('tools', []) if tool['readOnly']]

    def call(self, name, arguments):
        tool = next((item for item in self.definitions() if item['name'] == name), None)
        if tool is None:
            raise ValueError('Tool is unavailable. Portable mode exposes read-only tools; use Cove for approved write operations.')
        if not isinstance(arguments, dict) or len(json.dumps(arguments)) > 65536:
            raise ValueError('Invalid tool arguments')
        Draft202012Validator(tool['parameters']).validate(arguments)
        try:
            # Plugin logging must not corrupt MCP stdout.
            import contextlib
            with contextlib.redirect_stdout(sys.stderr):
                result = getattr(self.plugin, tool['command'])(**arguments)
            return {'ok': True, 'result': result}
        except Exception as exc:
            return {'ok': False, 'error': str(exc)}

    def close(self):
        import contextlib
        with contextlib.redirect_stdout(sys.stderr):
            self.plugin.close()
        for name in list(sys.modules):
            if name == self.module_name or name.startswith(self.module_name + '.'):
                del sys.modules[name]


def main():
    parser = argparse.ArgumentParser(description='Expose a trusted Cove plugin as read-only MCP tools')
    parser.add_argument('--plugin', required=True, type=Path)
    parser.add_argument('--data', type=Path)
    args = parser.parse_args()
    if hasattr(sys.stdin, 'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    identity = json.loads((args.plugin / 'manifest.json').read_text(encoding='utf-8-sig'))['id']
    data = args.data or Path.home() / '.cove' / 'portable' / identity
    server = PluginServer(args.plugin, data)
    try:
        serve_rpc(sys.stdin, sys.stdout, server.definitions, server.call)
    finally:
        server.close()


if __name__ == '__main__':
    main()
