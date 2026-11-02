"""Exercise actual native page construction and primary-button drawing without installing."""
import json
from pathlib import Path
import subprocess
import tempfile
import os
import configparser

ROOT = Path(__file__).resolve().parent.parent


def main():
    version = json.loads((ROOT/'package.json').read_text())['version']
    executable = ROOT/f'artifacts/Cove-{version}-setup.exe'
    results = []
    native_results = []
    with tempfile.TemporaryDirectory(dir=ROOT/'artifacts/validation') as folder:
        root = Path(folder)
        for language in ('1033', '2052'):
            for page in ('language', 'location', 'license', 'installing', 'finish'):
                report = root/f'{language}-{page}.json'
                installation = root/'not-installed'
                # NSIS requires /D last and unquoted, even for paths with spaces.
                command = subprocess.list2cmdline([str(executable), '/TESTMODE', f'/LANGUAGE={language}']) + f' /D={installation}'
                result = subprocess.run(command,
                    env={**os.environ, 'COVE_INSTALL_UI_REPORT': str(report),
                         'COVE_INSTALL_UI_PAGE': page}, timeout=30)
                assert result.returncode == 0, result.returncode
                values = json.loads(report.read_text(encoding='utf-8'))
                assert values['version'] == version
                assert values['language'] == ('en-US' if language == '1033' else 'zh-CN'), values
                assert values['page'] == page, values
                assert values['buttonRadius'] == '8px', values
                assert values['theme'] in ('light','dark'), values
                assert values['buttonColor'] == ('rgb(40, 40, 40)' if values['theme']=='light' else 'rgb(229, 229, 229)'), values
                assert 'Cove Sans' in values['font'] and values['fontSize'] == '13px', values
                assert values['frame'] in ('alpha', 'native'), values
                if values['frame'] == 'alpha': assert values['radius'] == '16px', values
                assert not values['overflow'] and not values['contentOverflow'], values
                assert values['buttonTextColor']==('rgb(255, 255, 255)' if values['theme']=='light' else 'rgb(36, 36, 36)'), values
                assert values['auxiliaryNotes']==0, values
                if page in ('language','finish'):assert 150<=values['bannerWidth']<=190,values
                else:assert values['bannerWidth']==0,values
                expected = ({'language':'Next','location':'Next','license':'Install','installing':'Installing','finish':'Done'} if language == '1033' else {'language':'下一步','location':'下一步','license':'安装','installing':'正在安装','finish':'完成'})[page]
                assert expected in values['caption'], values
                assert not installation.exists()
                results.append(values)
        for language in ('1033', '2052'):
            for page in ('welcome', 'finish'):
                report = root / f'fallback-{language}-{page}.ini'
                command = subprocess.list2cmdline([str(executable), '/TESTMODE', '/SIMULATE_MISSING_WEBVIEW2', f'/LANGUAGE={language}']) + f' /D={root / "not-installed"}'
                result = subprocess.run(command, env={**os.environ, 'COVE_INSTALL_UI_REPORT': str(report), 'COVE_INSTALL_UI_PAGE': page}, timeout=30)
                assert result.returncode == 0, result.returncode
                config = configparser.ConfigParser(interpolation=None)
                config.read(report, encoding='utf-16')
                values = dict(config['UI'])
                assert values['version'] == version and values['page'] == page, values
                assert int(values['color']) == 0x282828, values
                assert int(values['textcolor']) == 0xFFFFFF, values
                assert 'Preview' not in values['title'], values
                assert not (root / 'not-installed').exists()
                native_results.append(values)
    output = ROOT/f'artifacts/validation/installer-ui-{version}.json'
    output.write_text(json.dumps({'passed': True, 'nativeWebViewPages': results, 'nativeFallbackPages': native_results,
        'note': 'Real installer WebView, Morning White and Gray, classic wizard composition, system theme, shared typography and control/window radii verified. Full-page screenshot review is separate.'}, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
