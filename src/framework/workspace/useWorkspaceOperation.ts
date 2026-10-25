import { useRef, useState } from 'react';

/** One gate for configuration writes, undo and plugin commands in a mounted workspace. */
export function useWorkspaceOperation() {
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  async function runExclusive(operation: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try {
      await operation();
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }
  return { busy, busyRef, runExclusive };
}

export type WorkspaceOperation = ReturnType<typeof useWorkspaceOperation>;
