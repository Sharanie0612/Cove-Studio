"""Versioned host/plugin contracts; independent of desktop and subprocess code."""
import re

SDK_VERSION = 1
CAPABILITIES = frozenset({'ui.form', 'ui.result', 'ui.terminal', 'ui.mcp', 'ui.profiles',
                          'ui.job', 'ui.instrument', 'ui.i18n', 'ai.tools', 'host.tools'})


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('兼容版本必须使用 major.minor.patch 格式')
    return tuple(map(int, value.split('.')))


def validate_compatibility(value):
    if not isinstance(value, dict) or set(value) - {'minHostVersion', 'maxHostVersion', 'capabilities'}:
        raise ValueError('compatibility 仅支持宿主版本范围与 capabilities')
    for key in ('minHostVersion', 'maxHostVersion'):
        if key in value:
            version_tuple(value[key])
    if 'minHostVersion' in value and 'maxHostVersion' in value and version_tuple(value['minHostVersion']) > version_tuple(value['maxHostVersion']):
        raise ValueError('最低宿主版本不能高于最高版本')
    required = value.get('capabilities', [])
    if not isinstance(required, list) or any(not isinstance(item, str) or not re.fullmatch(r'[a-z][a-z0-9_.-]*', item) for item in required) or len(required) != len(set(required)):
        raise ValueError('capabilities 必须是无重复的能力名称数组')


def compatibility_report(manifest, host_version=None):
    if host_version is None:
        from toolbench import __version__
        host_version = __version__
    requirement = manifest.get('compatibility', {})
    validate_compatibility(requirement)
    current = version_tuple(host_version)
    reasons = []
    if 'minHostVersion' in requirement and current < version_tuple(requirement['minHostVersion']):
        reasons.append(f"需要 Cove {requirement['minHostVersion']} 或更新版本")
    if 'maxHostVersion' in requirement and current > version_tuple(requirement['maxHostVersion']):
        reasons.append(f"仅支持 Cove {requirement['maxHostVersion']} 及之前版本")
    missing = sorted(set(requirement.get('capabilities', [])) - CAPABILITIES)
    if missing:
        reasons.append('当前宿主缺少能力：' + '、'.join(missing))
    return {'supported': not reasons, 'reasons': reasons}


def require_compatible(manifest):
    report = compatibility_report(manifest)
    if not report['supported']:
        raise ValueError('；'.join(report['reasons']))
