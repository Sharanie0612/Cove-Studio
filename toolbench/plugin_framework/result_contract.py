"""Declarative result layout validation, with no plugin execution or UI imports."""
import re

KEY = re.compile(r'[a-zA-Z][a-zA-Z0-9_]{0,63}')


def _text(value, name, limit=120):
    if not isinstance(value, str) or not 1 <= len(value) <= limit:
        raise ValueError(f'{name} 必须是 1–{limit} 字符的文字')


def _fields(fields, limit):
    if not isinstance(fields, list) or not 1 <= len(fields) <= limit:
        raise ValueError(f'结果字段必须是 1–{limit} 项的数组')
    seen = set()
    for field in fields:
        if not isinstance(field, dict) or set(field) - {'key', 'label', 'format', 'unit'}:
            raise ValueError('结果字段仅支持 key、label、format、unit')
        key = field.get('key')
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in seen:
            raise ValueError('结果字段 key 必须是唯一的顶层数据键名')
        seen.add(key)
        _text(field.get('label'), '结果字段 label')
        if field.get('format', 'text') not in ('text', 'number', 'json'):
            raise ValueError('结果字段 format 必须是 text、number 或 json')
        if 'unit' in field:
            _text(field['unit'], '结果字段 unit', 24)


def validate_result_layout(ui, capabilities):
    if 'result' not in ui:
        return
    if ui['surface'] != 'form' or 'job' in ui:
        raise ValueError('ui.result 仅用于普通 form，不能与 job 同时声明')
    if 'ui.result' not in capabilities:
        raise ValueError('ui.result 需要在 compatibility.capabilities 中声明 ui.result')
    layout = ui['result']
    if not isinstance(layout, dict) or set(layout) - {'title', 'fields', 'table'}:
        raise ValueError('ui.result 仅支持 title、fields、table')
    if not ('fields' in layout or 'table' in layout):
        raise ValueError('ui.result 至少需要 fields 或 table')
    if 'title' in layout:
        _text(layout['title'], '结果 title')
    if 'fields' in layout:
        _fields(layout['fields'], 24)
    if 'table' in layout:
        table = layout['table']
        if not isinstance(table, dict) or set(table) - {'key', 'columns', 'emptyText'}:
            raise ValueError('结果表格仅支持 key、columns、emptyText')
        if not isinstance(table.get('key'), str) or not KEY.fullmatch(table['key']):
            raise ValueError('结果表格 key 必须是顶层数据键名')
        _fields(table.get('columns'), 12)
        if 'emptyText' in table:
            _text(table['emptyText'], '表格 emptyText')
