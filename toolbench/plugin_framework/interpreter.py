"""Interpreter selection shared by runtime launch and read-only diagnostics."""
from dataclasses import dataclass
import os
from pathlib import Path
import sys


MIN_PYTHON_VERSION = (3, 11)


@dataclass(frozen=True)
class Interpreter:
    executable: Path
    source: str
    frozen_worker: bool = False


def select_interpreter(folder, configured=None):
    if configured:
        return Interpreter(Path(configured), 'configured')
    project = Path(folder) / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if project.is_file():
        return Interpreter(project, 'project-venv')
    executable = Path(sys.executable)
    if getattr(sys, 'frozen', False):
        return Interpreter(executable.with_name('Cove-worker.exe'), 'bundled-worker', True)
    if os.name == 'nt' and executable.name.lower() == 'pythonw.exe':
        executable = executable.with_name('python.exe')
    return Interpreter(executable, 'host-python')
