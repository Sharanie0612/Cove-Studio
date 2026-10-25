"""Own plugin UI sessions; the iframe receives no native API or filesystem paths."""
import copy
import hashlib
import secrets
from toolbench.contracts import require_compatible
from toolbench.plugin_framework.web_ui import read_web_document


class PluginViews:
    def __init__(self, host):
        self.host = host
        self.sessions = {}

    def declaration(self, ticket, name):
        with self.host.lock:
            session = self.sessions.get(ticket)
            if not session:
                raise ValueError('Plugin UI session has closed')
            identity, folder, fingerprint = session
            current = self.host.plugins.get(identity)
            if (self.host._closing or not current or str(current[0]) != folder or
                    identity in self.host._preferences['disabled'] or
                    self._fingerprint(current[1]) != fingerprint):
                raise ValueError('Plugin UI session is no longer valid')
            manifest = current[1]
        require_compatible(manifest)
        tool = next((tool for tool in manifest['ui']['web']['tools'] if tool['name'] == name), None)
        if tool is None:
            raise ValueError('Plugin UI command is not declared')
        return {**copy.deepcopy(tool), 'pluginId': identity, 'pluginName': manifest['name']}

    @staticmethod
    def _fingerprint(manifest):
        import json
        return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()

    def open(self, identity):
        with self.host._management_lock:
            if identity not in self.host.plugins or identity in self.host._preferences['disabled'] or self.host._closing:
                raise ValueError('Plugin UI is unavailable')
            folder, manifest = self.host.plugins[identity]
            require_compatible(manifest)
            if manifest['ui']['surface'] != 'web':
                raise ValueError('Plugin does not declare a web UI')
            document = read_web_document(folder, manifest)
            ticket = secrets.token_urlsafe(32)
            with self.host.lock:
                if len(self.sessions) >= 64:
                    raise ValueError('Too many plugin UI sessions')
                self.sessions[ticket] = (identity, str(folder), self._fingerprint(manifest))
            return {'ticket': ticket, 'html': document}

    def close(self, ticket):
        with self.host.lock:
            self.sessions.pop(ticket, None)
        self.host._assistant_broker.cancel_owner('view:' + ticket)

    def close_plugin(self, identity):
        with self.host.lock:
            tickets = [ticket for ticket, value in self.sessions.items() if value[0] == identity]
        for ticket in tickets:
            self.close(ticket)


class ViewApi:
    def plugin_view_open(self, identity):
        try:
            return {'ok': True, 'result': self._views.open(identity)}
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    def plugin_view_close(self, ticket):
        self._views.close(ticket)
        return {'ok': True}

    def plugin_view_call(self, ticket, name, payload):
        try:
            return self._assistant_broker.call_view(ticket, name, payload)
        except Exception as error:
            return {'ok': False, 'error': str(error)}
