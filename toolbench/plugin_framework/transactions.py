"""Bounded retries for Windows scanners briefly holding transaction paths."""
from pathlib import Path
import time


def rename_directory(source: Path, destination: Path):
    """Keep rename atomic; retry only known Windows access/sharing failures.

    Never replace a destination, copy/delete as a fallback, or treat a permanent
    failure as success. The caller owns rollback and retains its original backup.
    """
    delays = (0.025, 0.05, 0.1, 0.2, 0.4, 0.4, 0.4)
    for attempt in range(len(delays) + 1):
        try:
            source.rename(destination)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in {5, 32, 33} or attempt == len(delays):
                raise
            time.sleep(delays[attempt])
