"""Isolated installer frontend. NSIS still owns extraction, activation and upgrade policy."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import tempfile
import configparser

from toolbench import __version__
from toolbench.desktop import DesktopApi, bind_window_frame, window_frame_options
from toolbench.maintenance import preflight


class SetupBridge:
    def __init__(self, engine, directory, locale, test_mode=False):
        self._engine = Path(engine).resolve()
        self._directory = str(directory)
        self._locale = locale
        self._test_mode = test_mode
        self._window = None
        self._maximized = False
        self._lock = threading.Lock()
        self._busy = False
        self._completed = False
        self._progress_path = None
        self._phase = 'preparing'
        self._install_target = None
        self._runtime = Path(sys.executable).resolve().parent
        self._resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))

    def state(self):
        return {'version': __version__, 'directory': self._directory, 'locale': self._locale,
                'completed': self._completed, 'busy': self._busy,
                'license': (self._resources / 'LICENSE').read_text(encoding='utf-8'),
                'previewPage': os.environ.get('COVE_INSTALL_UI_PAGE', '') if self._probe_enabled() else ''}

    def _probe_enabled(self):
        return self._test_mode and bool(os.environ.get('COVE_INSTALL_UI_REPORT'))

    def set_locale(self, locale):
        if locale not in ('zh-CN', 'en-US'):
            return {'ok': False}
        self._locale = locale
        DesktopApi.set_locale(self, locale)
        return {'ok': True}

    def browse(self):
        if self._busy:
            return None
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return result[0] if result else None

    def progress(self):
        if self._completed:
            return {'phase': 'finished', 'percent': 100}
        phase = self._phase
        progress_path = self._progress_path
        if progress_path:
            try:
                config = configparser.ConfigParser()
                config.read(progress_path, encoding='utf-16')
                phase = config.get('Setup', 'Phase', fallback=phase)
            except (OSError, ValueError, configparser.Error):
                pass
        percent, completed, total = None, 0, 0
        if phase == 'copying' and self._install_target:
            try:
                manifest = json.loads((self._runtime/'runtime-manifest.json').read_text(encoding='utf-8'))
                for item in manifest['files']:
                    relative = Path(item['path'])
                    if relative.is_absolute() or '..' in relative.parts: continue
                    source, destination = self._runtime/relative, self._install_target/'versions'/__version__/relative
                    total += 1
                    try:
                        completed += int(destination.is_file() and destination.stat().st_size == source.stat().st_size)
                    except OSError: pass
                if total: percent = 10 + int(70 * completed / total)
            except (OSError, ValueError, KeyError): pass
        elif phase == 'verifying': percent = 85
        elif phase == 'finishing': percent = 95
        return {'phase': phase, 'percent': percent, 'completedFiles': completed, 'totalFiles': total}

    def install(self, directory, accepted=False, close_existing=False):
        if accepted is not True or self._probe_enabled():
            return {'ok': False, 'code': 'LICENSE_REQUIRED'}
        if not self._lock.acquire(blocking=False):
            return {'ok': False, 'code': 'BUSY'}
        self._busy = True
        try:
            if not isinstance(directory, str) or any(char in directory for char in ('"', '\x00', '\n', '\r')):
                return {'ok': False, 'code': 'INVALID_DIRECTORY'}
            target = Path(directory)
            if not target.is_absolute() or target == Path(target.anchor):
                return {'ok': False, 'code': 'INVALID_DIRECTORY'}
            self._install_target = target
            self._phase = 'closing' if close_existing else 'checking'
            check = preflight(target, self._runtime, close=close_existing is True, version=__version__)
            if not check['ready']:
                return {'ok': False, 'code': 'DESKTOP_RUNNING' if check['reason'] == 'desktop-running' else 'FILES_BUSY'}
            arguments = [str(self._engine), '/S', '/NO_DESKTOP_SHORTCUT', f'/LANGUAGE={2052 if self._locale == "zh-CN" else 1033}']
            if self._test_mode:
                arguments.append('/TESTMODE')
            # NSIS /D must be the final, unquoted parameter, including spaces.
            command = subprocess.list2cmdline(arguments) + f' /D={target}'
            with tempfile.TemporaryDirectory(prefix='cove-setup-progress-', ignore_cleanup_errors=True) as folder:
                progress = Path(folder)/'progress.ini'
                progress.write_text(f'[Setup]\nOwner=cove-setup-progress-v1\nVersion={__version__}\nPhase=preparing\n', encoding='utf-16')
                self._progress_path = progress
                process = subprocess.Popen(command, env={**os.environ, 'COVE_SETUP_PROGRESS': str(progress)},
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                code = process.wait()  # Never kill an installer while it owns active writes.
                self._progress_path = None
            if code:
                return {'ok': False, 'code': 'SETUP_BUSY' if code == 1618 else 'INSTALL_FAILED'}
            self._directory = str(target)
            self._completed = True
            return {'ok': True}
        except (ValueError, OSError):
            return {'ok': False, 'code': 'INVALID_DIRECTORY'}
        finally:
            self._busy = False
            self._progress_path = None
            self._lock.release()

    def finish(self, launch=False, desktop=True):
        if not self._completed or self._busy:
            return {'ok': False}
        if desktop:
            from toolbench.windows_shortcuts import create_desktop_shortcut
            if self._test_mode:
                folder = Path(self._directory)/'_shortcuts/Desktop'
            else:
                from System import Environment
                folder = Path(str(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory)))
                if not folder.is_absolute():
                    return {'ok': False, 'code': 'SHORTCUT_FAILED'}
            try:
                create_desktop_shortcut(Path(self._directory), folder)
            except OSError:
                return {'ok': False, 'code': 'SHORTCUT_FAILED'}
        if launch and not self._test_mode:
            from toolbench.paths import active_runtime
            root = Path(self._directory)
            if not active_runtime(root):
                return {'ok': False}
            subprocess.Popen([str(root / 'Cove.exe')], cwd=root)
        self._window.destroy()
        return {'ok': True}

    def window_action(self, action):
        if action == 'close':
            if not self._busy:
                self._window.destroy()
        elif action == 'minimize':
            self._window.minimize()
        elif action == 'drag' and os.name == 'nt':
            DesktopApi._native_drag(self)
        return {'ok': True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', required=True, type=Path)
    parser.add_argument('--directory', required=True)
    parser.add_argument('--language', choices=('1033', '2052'), default='1033')
    parser.add_argument('--test-mode', action='store_true')
    args = parser.parse_args()
    import webview
    bridge = SetupBridge(args.engine, args.directory, 'zh-CN' if args.language == '2052' else 'en-US', args.test_mode)
    window = webview.create_window('Cove Studio · Setup', str(bridge._resources / 'dist/setup.html'),
        js_api=bridge, width=700, height=560, min_size=(640, 520), resizable=False,
        frameless=True, easy_drag=False, text_select=True, **window_frame_options())
    bridge._window = window
    bind_window_frame(window, bridge)
    window.events.closing += lambda: not bridge._busy
    webview.settings['DRAG_REGION_SELECTOR'] = '.cove-unused-drag-region'

    def probe():
        if not bridge._probe_enabled():
            return
        report = Path(os.environ['COVE_INSTALL_UI_REPORT'])
        try:
            if not report.is_absolute() or report.exists():
                raise ValueError('A fresh absolute report path is required')
            until = time.monotonic() + 20
            while time.monotonic() < until:
                if window.evaluate_js('Boolean(document.querySelector(".setup-ready")) && document.fonts.status === "loaded"'):
                    break
                time.sleep(.1)
            values = window.evaluate_js('''(() => {
              const button=document.querySelector('.setup-footer .primary'), shell=document.querySelector('.setup-shell');
              return {version:document.querySelector('[data-version]').dataset.version,
                language:document.documentElement.lang, page:document.querySelector('[data-page]').dataset.page,
                buttonRadius:getComputedStyle(button).borderRadius, buttonColor:getComputedStyle(button).backgroundColor,
                font:getComputedStyle(button).fontFamily, fontSize:getComputedStyle(button).fontSize,
                fonts:Array.from(document.fonts).map(font=>({family:font.family,status:font.status})),
                frame:document.documentElement.dataset.windowFrame, radius:getComputedStyle(shell).borderRadius,
                width:innerWidth,height:innerHeight,overflow:document.body.scrollWidth>innerWidth,
                caption:button.textContent};})()''')
            report.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding='utf-8')
        finally:
            window.destroy()

    with tempfile.TemporaryDirectory(prefix='cove-setup-ui-', ignore_cleanup_errors=True) as storage:
        webview.start(probe, private_mode=False, storage_path=storage, http_port=0)
    return 0 if bridge._completed or bridge._probe_enabled() else 1602
