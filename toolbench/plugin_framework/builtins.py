"""Host-owned service identities and legacy distribution rules."""
MCP_ID = 'dev.cove.mcp'
RETIRED_IDS = frozenset()


def is_host_service(identity):
    return identity == MCP_ID
