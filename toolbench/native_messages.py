"""Translate startup notices before a desktop Host can safely be opened."""
import json
import locale
import os
from pathlib import Path
import sys


def _language():
    if os.name == 'nt':
        import ctypes
        return 'zh-CN' if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3ff == 4 else 'en-US'
    return 'zh-CN' if (locale.getlocale()[0] or '').lower().startswith('zh') else 'en-US'


def t(message):
    if _language() == 'zh-CN':
        return message
    root = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    catalog = root / ('locales/en-US.json' if getattr(sys, 'frozen', False) else 'src/locales/en-US.json')
    return json.loads(catalog.read_text(encoding='utf-8')).get(message, message)


def show_notice(message):
    if os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'Cove Studio', 0x30)
    else:
        sys.stderr.write(message + '\n')
