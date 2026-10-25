import { useCallback, useSyncExternalStore } from 'react';
import { hostCall, subscribe } from './bridge';
import { AssistantStateStore } from './assistantStateStore';
import type { AssistantState } from './types';

const store = new AssistantStateStore(() => hostCall<AssistantState>('assistant_state'));
let subscribers = 0;
let disconnect = () => {};

function observe(listener: () => void, active: boolean) {
  if (subscribers++ === 0) {
    const visibility = () => store.setVisible(!document.hidden);
    visibility();
    document.addEventListener('visibilitychange', visibility);
    const off = subscribe((event) => {
      if (event.event === 'approval_pending') {
        void store.refresh().catch(() => undefined);
        return;
      }
      if (!document.hidden && ['status', 'runtime_failure'].includes(event.event))
        store.invalidate();
    });
    disconnect = () => {
      document.removeEventListener('visibilitychange', visibility);
      off();
    };
  }
  const release = store.subscribe(listener, active);
  return () => {
    release();
    if (--subscribers === 0) disconnect();
  };
}

export function useAssistantState(native: boolean, active = true) {
  const subscribe = useCallback(
    (listener: () => void) => (native ? observe(listener, active) : () => {}),
    [native, active],
  );
  const snapshot = useSyncExternalStore(subscribe, store.getSnapshot);
  return { ...snapshot, refresh: store.refresh, dismissApproval: store.dismissApproval };
}
