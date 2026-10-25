"""One deadline budget across command, SDK, approval and adapter layers."""
from dataclasses import dataclass
import time


@dataclass(frozen=True)
class ExecutionPolicy:
    startup: float = 12
    command: float = 20
    approval: float = 180
    host_call: float = 220
    poll: float = .05

    @property
    def request(self):
        return self.command + self.host_call + 5

    @property
    def client(self):
        return self.request + 5

    def wait(self, event, host_waiting, *, startup=False):
        remaining = self.startup if startup else self.command
        deadline = time.monotonic() + self.request
        while not event.is_set() and remaining > 0 and time.monotonic() < deadline:
            start = time.monotonic()
            event.wait(self.poll)
            if not host_waiting():
                remaining -= time.monotonic() - start
        return event.is_set()


POLICY = ExecutionPolicy()
