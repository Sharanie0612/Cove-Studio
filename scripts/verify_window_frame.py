"""Exercise the real native frame and built UI with disposable data (Windows)."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from toolbench.host import Host
from toolbench.bridge import DesktopBridge
from toolbench.desktop import bind_window_frame, window_frame_options, uses_alpha_frame


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser()
    parser.add_argument('--hold', type=int, default=0, help='Keep the isolated window visible briefly for visual review')
    args = parser.parse_args()
    import webview
    data = ROOT / 'artifacts/validation/frame' / uuid.uuid4().hex
    host = Host(data_dir=data)
    window = webview.create_window('Cove · Frame Check', str(ROOT / 'dist/index.html'),
        js_api=DesktopBridge(host), width=1000, height=700, min_size=(960, 660),
        frameless=True, easy_drag=False, text_select=True, **window_frame_options())
    host._window, host._maximized = window, False
    bind_window_frame(window, host)
    webview.settings['DRAG_REGION_SELECTOR'] = '.cove-unused-drag-region'
    window.events.closed += host.close
    report = {'windowsBuild': sys.getwindowsversion().build}
    def native_ready():
        report['nativeConfigured'] = getattr(window, '_cove_frame', None)
        def ready(sender, args):
            report['webviewInitialized'] = bool(args.IsSuccess)
            report['initializationError'] = str(args.InitializationException)
        window.native.webview.CoreWebView2InitializationCompleted += ready
        window.native.webview.NavigationStarting += lambda sender, args: report.update(navigationStarted=str(args.Uri))
        window.native.webview.NavigationCompleted += lambda sender, args: report.update(navigationCompleted=bool(args.IsSuccess))
    window.events.before_show += native_ready

    def wait_for(expression):
        until = time.monotonic() + 8
        while time.monotonic() < until:
            if window.evaluate_js(expression):
                return
            time.sleep(.05)
        raise AssertionError(expression)

    def exercise():
        try:
            assert window.events.loaded.wait(20), 'Page did not load'
            expected = 'alpha' if uses_alpha_frame() else 'native'
            wait_for(f"document.documentElement.dataset.windowFrame === '{expected}'")
            report['frame'] = window._cove_frame
            wait_for("document.documentElement.dataset.windowDrag === 'native'")
            report['nativeTitleRegionsEnabled'] = bool(window._cove_native_drag)
            assert report['nativeTitleRegionsEnabled']
            assert window.evaluate_js("getComputedStyle(document.querySelector('.window-titlebar')).getPropertyValue('app-region')") == 'drag'
            # The visible curve must not be a binary GDI region.
            user, gdi = ctypes.windll.user32, ctypes.windll.gdi32
            user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
            rect, client = wintypes.RECT(), wintypes.RECT()
            handle = int(window.native.Handle.ToInt64())
            user.GetWindowRect(handle, ctypes.byref(rect))
            user.GetClientRect(handle, ctypes.byref(client))
            report['nativeBounds'] = [rect.right - rect.left, rect.bottom - rect.top]
            report['nativeClient'] = [client.right, client.bottom]
            report['borderStyle'] = str(window.native.FormBorderStyle)
            get_style = user.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user.GetWindowLongW
            get_style.argtypes = [wintypes.HWND, ctypes.c_int]
            get_style.restype = ctypes.c_ssize_t
            required_style = 0x00CF0000
            assert get_style(handle, -16) & required_style == required_style, 'Windows Snap sizing styles missing'
            assert report['nativeBounds'] == report['nativeClient'], 'System chrome must stay hidden'
            report['nativeSnapStylesPresent'] = True
            user.GetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN]
            gdi.CreateRectRgn.restype = wintypes.HRGN
            gdi.DeleteObject.argtypes = [wintypes.HRGN]
            region = gdi.CreateRectRgn(0, 0, 0, 0)
            try:
                assert user.GetWindowRgn(int(window.native.Handle.ToInt64()), region) == 0
                report['noBinaryWindowRegion'] = True
            finally:
                gdi.DeleteObject(region)
            for theme in ('light', 'dark'):
                window.evaluate_js(f"document.documentElement.dataset.theme='{theme}'")
                metrics = window.evaluate_js("""(() => {
                    const root = document.documentElement, app = document.querySelector('.app-shell');
                    const rect = app.getBoundingClientRect(), style = getComputedStyle(app);
                    return {background:getComputedStyle(document.body).backgroundColor,
                        clip:style.clipPath, radius:style.borderRadius, width:innerWidth,
                        height:innerHeight, x:rect.x,y:rect.y,right:rect.right,bottom:rect.bottom};
                })()""")
                if expected == 'alpha':
                    assert metrics['background'] == 'rgba(0, 0, 0, 0)', metrics
                    assert metrics['radius'] == '16px', metrics
                    assert metrics['x'] == 8 and metrics['width'] - metrics['right'] == 8, metrics
                    assert metrics['y'] == 8 and metrics['height'] - metrics['bottom'] == 8, metrics
                report[theme] = metrics
            for cycle in range(3):
                window.maximize()
                wait_for("document.documentElement.dataset.windowMaximized === 'true'")
                assert window.evaluate_js("getComputedStyle(document.documentElement).getPropertyValue('--window-radius').trim()") == '0px'
                from System.Windows.Forms import Screen
                work = Screen.FromHandle(window.native.Handle).WorkingArea
                user.GetClientRect(handle, ctypes.byref(client))
                origin = wintypes.POINT(0, 0)
                user.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
                user.ClientToScreen(handle, ctypes.byref(origin))
                actual = [origin.x, origin.y, origin.x + client.right, origin.y + client.bottom]
                expected_bounds = [work.Left, work.Top, work.Right, work.Bottom]
                assert get_style(handle, -4) == ctypes.cast(window._cove_native_frame[0], ctypes.c_void_p).value
                assert actual == expected_bounds, f'Maximize must fit the monitor working area: {actual} != {expected_bounds}'
                window.restore()
                wait_for("document.documentElement.dataset.windowMaximized === 'false'")
                if expected == 'alpha':
                    assert window.evaluate_js("getComputedStyle(document.querySelector('.app-shell')).borderRadius") == '16px'
            report['maximizeRestoreCycles'] = 3
            report['maximizeFitsWorkingArea'] = True
            window.resize(1100, 750)
            wait_for('innerWidth >= 1100')
            report['resizePreservesCompositedFrame'] = window._cove_frame == expected
            report['ok'] = True
        except Exception as exc:
            report['ok'], report['error'] = False, repr(exc)
        finally:
            (ROOT / 'artifacts/validation/window-frame.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False), flush=True)
            if report.get('ok') and args.hold:
                # Record real input outcomes while a human/computer-use reviewer
                # exercises this isolated window. This never injects mouse input.
                states = []
                until = time.monotonic() + min(args.hold, 1800)
                while time.monotonic() < until and not window.events.closed.is_set():
                    user.GetWindowRect(handle, ctypes.byref(rect))
                    sample = {'bounds': [rect.left, rect.top, rect.right, rect.bottom], 'maximized': bool(host._maximized)}
                    if not states or any(sample[key] != states[-1][key] for key in sample):
                        states.append({**sample, 'time': time.time()})
                        (ROOT / 'artifacts/validation/window-input-states.json').write_text(json.dumps(states, indent=2), encoding='utf-8')
                    time.sleep(.2)
            window.destroy()

    webview.start(exercise, private_mode=False, storage_path=str(data / 'webview'), http_port=18312)
    if not report.get('ok'):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
