"""Bounded diagnostics containing structure, never stderr messages or source."""
from collections import deque
import json
from pathlib import Path
import re
import threading
import time
import uuid

from toolbench.sdk import atomic_json

_FRAME = re.compile(r'^\s*File "([^"\r\n]+)", line (\d+)(?:, in ([\w<>]+))?')
_ERROR = re.compile(r'^([A-Za-z_]\w*(?:Error|Exception|Exit|Interrupt))(?::|$)')
_MODULE = re.compile(r"^ModuleNotFoundError: No module named '([A-Za-z_][\w.]*)'$")


class Diagnostics:
    def __init__(self, path):
        self.path = Path(path)
        self.records = deque(maxlen=32)
        self.lock = threading.Lock()
        self.id = uuid.uuid4().hex[:12]

    def add(self, kind, **fields):
        with self.lock:
            self.records.append({'kind': kind, **fields})

    def stderr(self, line):
        frame = _FRAME.match(line)
        error = _ERROR.match(line)
        module = _MODULE.match(line.strip())
        if frame:
            name = Path(frame[1].replace('\\', '/')).name
            name = re.sub(r'[^\w.-]', '_', name)[:80]
            self.add('frame', file=name, line=int(frame[2]), function=frame[3] or '')
        elif error:
            self.add('exception', type=error[1], **({'module': module[1]} if module else {}))

    def save(self, phase, exit_code=None):
        with self.lock:
            result = {'id': self.id, 'phase': phase, 'exitCode': exit_code,
                      'time': time.time(), 'records': list(self.records)}
        atomic_json(self.path, result)
        return result


def load_diagnostics(path):
    try:
        content = Path(path).read_text(encoding='utf-8')
        if len(content) > 32768:
            return None
        return json.loads(content)
    except (OSError, ValueError):
        return None
