"""Optional SDK v1 helper for one cooperative background job per plugin."""
from __future__ import annotations

import copy
import json
import threading


class JobCancelled(Exception):
    """Raised at a cooperative cancellation point; not a task failure."""


def _progress(values):
    for key in ('completed', 'total'):
        if key in values and (type(values[key]) is not int or values[key] < 0):
            raise ValueError(f'{key} must be a non-negative integer')
    if 'message' in values and not isinstance(values['message'], str):
        raise ValueError('message must be a string')
    if 'total' in values and values.get('completed', 0) > values['total']:
        raise ValueError('completed must not exceed total')


class JobControl:
    """The callback's progress and cancellation handle for this run only."""
    def __init__(self, job, cancelled):
        self._job = job
        self._cancelled = cancelled

    @property
    def cancelled(self):
        return self._cancelled.is_set()

    def check_cancelled(self):
        if self.cancelled:
            raise JobCancelled()

    def wait(self, seconds):
        """Wait interruptibly, raising JobCancelled when cancellation arrives."""
        if self._cancelled.wait(seconds):
            raise JobCancelled()

    def update(self, *, completed=None, total=None, message=None):
        """Publish known progress. Leave total unset for indeterminate work."""
        values = {key: value for key, value in
                  (('completed', completed), ('total', total), ('message', message)) if value is not None}
        with self._job._lock:
            if self._job._control is not self or self._job._state['state'] != 'running':
                raise RuntimeError('This job has already finished')
            self.check_cancelled()
            _progress({**self._job._state, **values})
            return self._job._publish(**values)


class BackgroundJob:
    """Run one task at a time with the existing ui.job snapshot/event contract.

    The callback receives JobControl and returns a JSON object (or None). Result
    fields match JobSurface; state defaults to completed and may be partial.
    Use exactly one BackgroundJob per plugin. It owns activity events, but not
    business rollback, persistence or forcibly stopping external operations.
    """
    def __init__(self, context):
        self._context = context
        self._lock = threading.RLock()
        self._state = {'state': 'idle', 'revision': 0}
        self._revision = 0
        self._thread = None
        self._control = None
        self._closed = False

    def _publish(self, **changes):
        self._state.update(copy.deepcopy(changes))
        self._revision += 1
        self._state['revision'] = self._revision
        value = copy.deepcopy(self._state)
        # Publish while holding the job lock so terminal state cannot be
        # followed by an older progress event from another callback thread.
        self._context.emit('job', result=copy.deepcopy(value))
        return value

    def snapshot(self):
        with self._lock:
            return copy.deepcopy(self._state)

    def start(self, work, *, total=None, message=''):
        """Start promptly; reject overlapping runs. work(control) runs in a thread."""
        if not callable(work):
            raise ValueError('work must be callable')
        values = {'completed': 0, 'message': message}
        if total is not None:
            values['total'] = total
        _progress(values)
        with self._lock:
            if self._closed:
                raise RuntimeError('The job is closed')
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError('A job is already running')
            self._control = JobControl(self, threading.Event())
            self._state = {}
            self._context.emit('activity', active=True)
            try:
                value = self._publish(state='running', **values)
                self._thread = threading.Thread(target=self._run, args=(work, self._control), daemon=True)
                self._thread.start()
            except Exception:
                self._thread = None
                self._publish(state='failed', message='任务无法启动。')
                self._context.emit('activity', active=False)
                raise
            return value

    def _run(self, work, control):
        result = {}
        try:
            control.check_cancelled()
            returned = work(control)
            if returned is not None:
                if not isinstance(returned, dict):
                    raise TypeError('A job result must be an object')
                # Validate and detach JSON data before exposing it in events.
                result = json.loads(json.dumps(returned, allow_nan=False))
            if result.get('state', 'completed') not in ('completed', 'partial'):
                raise ValueError('A job result state must be completed or partial')
            if 'revision' in result:
                raise ValueError('revision is managed by BackgroundJob')
            with self._lock:
                _progress({**self._state, **result})
            result.setdefault('state', 'completed')
        except JobCancelled:
            result = {'state': 'cancelled', 'message': '任务已停止。'}
        except Exception as exc:
            # SDK exports this helper, so resolve its public exception only
            # when a task runs, after SDK initialization has completed.
            from toolbench.sdk import CommandError
            # Ordinary exception messages may contain paths, credentials or
            # source values. Only deliberate CommandError text is public.
            message = str(exc) if isinstance(exc, CommandError) else f'任务失败（{type(exc).__name__}）。'
            result = {'state': 'failed', 'message': message}
        finally:
            with self._lock:
                if control.cancelled:
                    result.update(state='cancelled', message='任务已停止。')
                elif not result.get('state'):
                    result = {'state': 'failed', 'message': '任务意外终止。'}
                try:
                    self._publish(**result)
                finally:
                    self._context.emit('activity', active=False)

    def cancel(self):
        """Request cancellation; stay active until the callback actually exits."""
        with self._lock:
            if self._state['state'] == 'running' and not self._control.cancelled:
                self._control._cancelled.set()
                self._publish(message='正在停止，请等待当前操作结束…')
            return self.snapshot()

    def close(self, timeout=1):
        """Request cancellation and wait up to timeout seconds; safe to repeat.

        A callback that ignores cancellation can outlive this wait. Its activity
        remains true until it returns; this method never claims a forced stop.
        """
        if not isinstance(timeout, (int, float)) or timeout < 0:
            raise ValueError('timeout must be non-negative')
        with self._lock:
            self._closed = True
            self.cancel()
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
