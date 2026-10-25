"""A common active-work snapshot for all destructive lifecycle actions."""


def work_state(host, identity):
    with host.lock:
        worker = host.workers.get(identity)
        connected = bool(host._connected.get(identity))
        background = bool(host._active_tasks.get(identity))
        invoking = bool(host._invocations.get(identity)) or identity in host._starting
    if worker:
        with worker.lock:
            invoking = invoking or bool(worker.pending)
    broker = getattr(host, '_assistant_broker', None)
    if broker:
        with broker.lock:
            invoking = invoking or any(
                not item['event'].is_set() and (item['owner'] == identity or item['pluginId'] == identity)
                for item in broker.pending.values()
            )
    return {'connected': connected, 'background': background, 'invoking': invoking,
            'active': connected or background or invoking}


def work_summary(host, identity=None):
    with host.lock:
        identities = {identity} if identity else (
            set(host.workers) | set(host._connected) | set(host._active_tasks) | set(host._invocations) | host._starting
        )
    broker = getattr(host, '_assistant_broker', None)
    if broker and identity is None:
        with broker.lock:
            identities |= {item['pluginId'] for item in broker.pending.values() if not item['event'].is_set()}
    states = [work_state(host, item) for item in identities]
    return {'connections': sum(state['connected'] for state in states),
            'backgroundTasks': sum(state['background'] for state in states),
            'commands': sum(state['invoking'] for state in states),
            'activePlugins': sum(state['active'] for state in states)}


def confirmation(host, identity=None):
    summary = work_summary(host, identity)
    return {'needsConfirmation': bool(summary['activePlugins']), **summary}
