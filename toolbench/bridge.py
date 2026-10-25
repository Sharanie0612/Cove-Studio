"""Expose only deliberate frontend calls, never recursively expose host state."""
API_METHODS = ('catalog', 'invoke', 'set_locale', 'drain_events', 'plugin_view_open', 'plugin_view_close', 'plugin_view_call', 'plugin_action', 'plugin_diagnostics', 'inspect_plugin_package', 'install_plugin',
               'configure_plugin_runtime', 'open_plugins_folder', 'rescan_plugins', 'window_action', 'resize_window', 'prepare_plugin_export',
               'save_plugin_export', 'export_plugin_starter', 'assistant_state', 'assistant_allow',
               'assistant_decide', 'assistant_bridge', 'assistant_check', 'mcp_clients', 'mcp_install', 'mcp_restore', 'mcp_manage', 'mcp_connection', 'export_dsh_plugin')

class DesktopBridge:
    def __init__(self, host):
        # pywebview recursively inspects public objects. Paths, locks and workers
        # must stay off that surface; the bound methods preserve their signatures.
        for name in API_METHODS:
            setattr(self, name, getattr(host, name))
