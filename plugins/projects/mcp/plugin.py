"""Cove MCP plugin facade. Transport and approvals are supplied by the host."""
from toolbench.sdk import Plugin


class Tool(Plugin):
    def status(self):
        return {'tools': self.context.tools()}
