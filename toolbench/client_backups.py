"""Bounded retention for exact, private client-configuration undo records."""
from __future__ import annotations

import json
from pathlib import Path
import re
import time

from toolbench.plugin_framework.persistence import atomic_json, protect_private

RETENTION_DAYS = 30
MAX_PER_CLIENT = 5
MAX_RECORD_BYTES = 3_000_000
TICKET = re.compile(r'[a-f0-9]{32}')


class ClientBackups:
    def __init__(self, directory: Path):
        self.directory = directory

    def path(self, ticket):
        if not isinstance(ticket, str) or not TICKET.fullmatch(ticket):
            raise ValueError('备份无效')
        return self.directory / (ticket + '.json')

    def read(self, ticket):
        path = self.path(ticket)
        if path.is_symlink():
            raise ValueError('备份不能使用符号链接')
        try:
            with path.open('rb') as stream:
                content = stream.read(MAX_RECORD_BYTES + 1)
        except FileNotFoundError as exc:
            raise ValueError('备份已清理或不存在；自动撤销保留每个客户端最近 5 份、最长 30 天的备份') from exc
        if len(content) > MAX_RECORD_BYTES:
            raise ValueError('备份过大')
        record = json.loads(content)
        if not isinstance(record, dict):
            raise ValueError('备份无效')
        return record

    def write(self, ticket, record):
        atomic_json(self.path(ticket), record, private=True)

    def remove(self, ticket):
        self.path(ticket).unlink(missing_ok=True)

    def prune(self, clients):
        """Best-effort housekeeping must not undo or misreport a successful save."""
        if not self.directory.exists():
            return True
        try:
            protect_private(self.directory)
            paths = list(self.directory.glob('*.json'))
        except (OSError, ValueError):
            return False
        complete = True
        retained = {}
        cutoff = time.time() - RETENTION_DAYS * 86400
        for path in paths:
            if not TICKET.fullmatch(path.stem) or path.is_symlink():
                continue
            try:
                record = self.read(path.stem)
                client, created = record.get('client'), record.get('time')
                if client not in clients or type(created) not in (int, float):
                    continue
                if not isinstance(record.get('path'), str) or not isinstance(record.get('before'), str):
                    continue
                protect_private(path)
                if created < cutoff:
                    self.remove(path.stem)
                else:
                    retained.setdefault(client, []).append((created, path.stem))
            except OSError:
                complete = False
            except (ValueError, TypeError):
                continue
        for records in retained.values():
            for _, ticket in sorted(records, reverse=True)[MAX_PER_CLIENT:]:
                try:
                    self.remove(ticket)
                except OSError:
                    complete = False
        return complete
