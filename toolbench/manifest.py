"""Standard-library-only validation for Cove SDK v1 manifests."""
import re
from toolbench.contracts import validate_compatibility
from toolbench.plugin_framework.builtins import is_host_service
from toolbench.plugin_framework.result_contract import validate_result_layout
from toolbench.plugin_framework.localization import validate_localization

SURFACES = {"terminal", "form", "mcp"}


def validate_manifest(manifest: dict) -> None:
    if not isinstance(manifest, dict):
        raise ValueError("插件清单必须为对象")
    if manifest.get("sdkVersion") != 1:
        raise ValueError("仅支持 SDK v1")
    if 'compatibility' in manifest:
        validate_compatibility(manifest['compatibility'])
    if 'localization' in manifest:
        validate_localization(manifest['localization'])
    if not re.fullmatch(r"[a-z][a-z0-9.-]{1,63}", manifest.get("id", "")):
        raise ValueError("插件 id 格式无效")
    if manifest['id'].endswith('.') or '..' in manifest['id'] or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?", manifest['id']):
        raise ValueError("插件 id 不能使用空段、末尾点或 Windows 保留名称")
    if not isinstance(manifest.get("name"), str) or not manifest["name"]:
        raise ValueError("缺少工具名称")
    for key in ("description", "version", "author", "category"):
        if not isinstance(manifest.get(key), str):
            raise ValueError(f"缺少或无效的 {key}")
    if not isinstance(manifest.get("permissions"), list) or any(not isinstance(p, str) for p in manifest["permissions"]):
        raise ValueError("permissions 必须为字符串数组")
    if not isinstance(manifest.get("ui"), dict):
        raise ValueError("ui 必须为对象")
    if manifest.get("ui", {}).get("surface") not in SURFACES:
        raise ValueError("不支持的界面部件")
    if manifest['ui']['surface'] == 'mcp' and not is_host_service(manifest['id']):
        raise ValueError('mcp 界面仅供内置 MCP 插件使用')
    commands = manifest.get("commands")
    validate_result_layout(manifest['ui'], manifest.get('compatibility', {}).get('capabilities', []))
    if not isinstance(commands, list) or not commands or any(
        not isinstance(c, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", c) for c in commands
    ):
        raise ValueError("commands 必须包含公开命令名称")
    fields = manifest["ui"].get("fields")
    if not isinstance(fields, list) or len(fields) > 40:
        raise ValueError("fields 必须是最多 40 项的数组")
    seen = set()
    for field in fields:
        if not isinstance(field, dict) or field.get("type") not in {"text", "password", "number", "select"}:
            raise ValueError("字段类型无效")
        if not re.fullmatch(r"[a-z][a-z0-9_]*", field.get("id", "")) or field["id"] in seen:
            raise ValueError("字段 id 重复或无效")
        seen.add(field["id"])
        if not isinstance(field.get("label"), str):
            raise ValueError("字段缺少 label")
        for flag in ('required', 'secret', 'advanced'):
            if flag in field and not isinstance(field[flag], bool):
                raise ValueError(f"字段 {field['id']} 的 {flag} 必须为布尔值")
        if 'default' in field and (not isinstance(field['default'], (str, int, float)) or isinstance(field['default'], bool)):
            raise ValueError(f"字段 {field['id']} 的 default 必须为字符串或数字")
        if field.get("span", 4) not in (1, 2, 3, 4):
            raise ValueError("字段 span 必须在 1 到 4 之间")
        if field["type"] == "select":
            options = field.get("options")
            if not isinstance(options, list) or not options or any(
                not isinstance(o, dict) or not isinstance(o.get("value"), str) or not isinstance(o.get("label"), str) for o in options
            ):
                raise ValueError("select 字段需要 value / label 选项数组")
            if 'default' in field and field['default'] not in {item['value'] for item in options}:
                raise ValueError(f"字段 {field['id']} 的默认值不在选项中")
    for field in fields:
        condition = field.get("showWhen")
        if condition is not None and (not isinstance(condition, dict) or condition.get("field") not in seen):
            raise ValueError("showWhen 引用了不存在的字段")
    actions = manifest["ui"].get("actions")
    if not isinstance(actions, list) or len(actions) != 1:
        raise ValueError("SDK v1 需要且仅支持一个主界面动作")
    if manifest["ui"]["surface"] == "terminal":
        for group, keys in {"connection": ["connect", "disconnect"], "terminal": ["write", "resize"]}.items():
            for key in keys:
                if manifest["ui"].get(group, {}).get(key) not in commands:
                    raise ValueError(f"{group}.{key} 必须引用已声明命令")
        if not isinstance(manifest["ui"].get("terminal", {}).get("dataEvent"), str):
            raise ValueError("终端必须声明 dataEvent")
    if 'ai' in manifest:
        declarations = manifest['ai'].get('tools') if isinstance(manifest['ai'], dict) else None
        if not isinstance(declarations, list) or len(declarations) > 24:
            raise ValueError('ai.tools 必须是最多 24 项的数组')
        names = set()
        for tool in declarations:
            if not isinstance(tool, dict) or not re.fullmatch(r'[a-z][a-z0-9_]{0,39}', tool.get('name', '')) or tool['name'] in names:
                raise ValueError('AI 工具名称无效或重复')
            names.add(tool['name'])
            if tool.get('command') not in commands or not isinstance(tool.get('description'), str) or not isinstance(tool.get('readOnly'), bool):
                raise ValueError('AI 工具必须声明命令、用途与 readOnly')
            parameters = tool.get('parameters')
            if not isinstance(parameters, dict) or parameters.get('type') != 'object' or not isinstance(parameters.get('properties'), dict) or parameters.get('additionalProperties') is not False:
                raise ValueError('AI 工具参数必须是 additionalProperties=false 的对象 Schema')
            secrets = {field['id'] for field in fields if field.get('secret') or field['type'] == 'password'}
            if secrets.intersection(parameters['properties']):
                raise ValueError('AI 工具不能声明密码或秘密字段')
    for action in actions:
        if not isinstance(action, dict) or action.get("command") not in commands or not isinstance(action.get("label"), str):
            raise ValueError("界面动作引用了未声明命令")
    if "profiles" in manifest["ui"]:
        if not isinstance(manifest['ui']['profiles'], dict):
            raise ValueError('ui.profiles 必须是命令绑定对象')
        for command in ("list", "scan", "save", "remove"):
            if manifest["ui"]["profiles"].get(command) not in commands:
                raise ValueError("连接管理引用了未声明的命令")
        if 'restore' in manifest['ui']['profiles'] and manifest['ui']['profiles']['restore'] not in commands:
            raise ValueError('撤销引用了未声明的命令')
    if 'job' in manifest['ui']:
        bindings = manifest['ui']['job']
        if manifest['ui']['surface'] != 'form' or not isinstance(bindings, dict) or set(bindings) != {'snapshot', 'cancel'} or any(v not in commands for v in bindings.values()):
            raise ValueError('job 必须在 form 中绑定 snapshot 与 cancel 命令')
    if 'instrument' in manifest['ui']:
        if 'job' in manifest['ui']:
            raise ValueError('同一界面不能同时声明 job 和 instrument')
        bindings = manifest['ui']['instrument']
        keys = {'status', 'measure', 'waveform', 'screenshot', 'acquisition', 'timebase', 'channel', 'trigger', 'snapshot'}
        if manifest['ui']['surface'] != 'form' or not isinstance(bindings, dict) or set(bindings) != keys or any(v not in commands for v in bindings.values()):
            raise ValueError('instrument 必须在 form 中绑定完整的仪器命令')
    confirmations = manifest["ui"].get("confirmations", [])
    if not isinstance(confirmations, list):
        raise ValueError("confirmations 必须为数组")
    for rule in confirmations:
        if not isinstance(rule, dict) or any(not isinstance(rule.get(k), str) for k in ("code", "title", "description", "confirmLabel")):
            raise ValueError("确认规则缺少文字字段")
        details = rule.get("details")
        if not isinstance(details, list) or not details or any(not isinstance(d, dict) or not isinstance(d.get("key"), str) or not isinstance(d.get("label"), str) for d in details):
            raise ValueError("确认详情格式无效")
        payload = rule.get("payload")
        detail_keys = {d["key"] for d in details}
        if not isinstance(payload, dict) or any(not re.fullmatch(r"[a-z][a-z0-9_]*", k) or not isinstance(v, dict) or v.get("fromDetail") not in detail_keys for k, v in payload.items()):
            raise ValueError("确认参数必须引用已声明详情")
