"""Metadata and local document bounds for plugin-owned, sandboxed interfaces."""
from pathlib import Path, PurePosixPath
import re

MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
UI_KEYS = frozenset({'surface', 'fields', 'actions', 'connection', 'terminal', 'profiles',
                     'empty', 'status', 'confirmations', 'result', 'job', 'web'})


def validate_web_ui(ui, commands, capabilities):
    if ui.get('surface') != 'web' and 'web' not in ui:
        return
    if ui.get('surface') != 'web' or 'ui.web' not in capabilities:
        raise ValueError('Plugin web UI requires surface=web and the ui.web capability')
    if 'result' in ui or 'job' in ui:
        raise ValueError('A plugin web UI owns its result and task presentation')
    view = ui.get('web')
    if not isinstance(view, dict) or set(view) != {'entry', 'tools'}:
        raise ValueError('ui.web requires only entry and tools')
    entry = view['entry']
    if (not isinstance(entry, str) or '\\' in entry or ':' in entry or
            not re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', entry) or
            entry.startswith('/') or any(part in ('', '.', '..') for part in entry.split('/')) or
            not entry.endswith('.html')):
        raise ValueError('ui.web.entry must be a relative HTML file inside the plugin')
    tools = view['tools']
    if not isinstance(tools, list) or not 1 <= len(tools) <= 40:
        raise ValueError('ui.web.tools must declare 1–40 commands')
    names = set()
    for tool in tools:
        if (not isinstance(tool, dict) or set(tool) != {'name', 'command', 'description', 'readOnly', 'parameters'} or
                not isinstance(tool['name'], str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', tool['name']) or
                tool['name'] in names or tool['command'] not in commands or
                type(tool['readOnly']) is not bool or not isinstance(tool['description'], str) or
                not 1 <= len(tool['description']) <= 500):
            raise ValueError('Invalid plugin web command declaration')
        names.add(tool['name'])
        schema = tool['parameters']
        if (not isinstance(schema, dict) or schema.get('type') != 'object' or
                not isinstance(schema.get('properties'), dict) or schema.get('additionalProperties') is not False):
            raise ValueError('Web commands require a closed object parameter Schema')


def read_web_document(folder, manifest):
    """Read bytes only; never start a Worker or execute a document during inspection."""
    folder = Path(folder)
    if folder.is_symlink() or getattr(folder, 'is_junction', lambda: False)():
        raise ValueError('Plugin UI resources cannot use linked paths')
    root = folder.resolve()
    relative = PurePosixPath(manifest['ui']['web']['entry'])
    path = root.joinpath(*relative.parts)
    for part in (path, *list(path.parents)[:len(relative.parts) - 1]):
        if part.is_symlink() or getattr(part, 'is_junction', lambda: False)():
            raise ValueError('Plugin UI resources cannot use linked paths')
    if not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Plugin UI entry is missing or outside the plugin')
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise ValueError('Plugin UI entry exceeds 4 MiB')
    with path.open('rb') as source:
        content = source.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise ValueError('Plugin UI entry exceeds 4 MiB')
    return content.decode('utf-8-sig')
