import { useEffect, useState } from 'react';
import type { WorkspaceConfiguration } from './useWorkspaceConfiguration';
import type { WorkspaceOperation } from './useWorkspaceOperation';

export function useWorkspaceFocus({
  id,
  active,
  configuration,
  operation,
  confirming,
  onFocusChange,
}: {
  id: string;
  active: boolean;
  configuration: WorkspaceConfiguration;
  operation: WorkspaceOperation;
  confirming: boolean;
  onFocusChange: (id: string, focused: boolean) => void;
}) {
  const [focused, setFocused] = useState(false);
  const { configOpen, setConfigOpen, form } = configuration;
  const { busyRef } = operation;
  useEffect(() => {
    if (!active) {
      setFocused(false);
      return;
    }
    function keydown(event: KeyboardEvent) {
      const modal = Boolean(document.querySelector('dialog[open]'));
      if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !busyRef.current) {
        if (modal && (!configOpen || confirming)) return;
        event.preventDefault();
        event.stopPropagation();
        if (configOpen) form.current?.requestSubmit();
        else setConfigOpen(true);
      }
      if (
        !modal &&
        (event.ctrlKey || event.metaKey) &&
        event.shiftKey &&
        event.key.toLowerCase() === 'f'
      ) {
        event.preventDefault();
        event.stopPropagation();
        setFocused((value) => !value);
      }
    }
    window.addEventListener('keydown', keydown, true);
    return () => window.removeEventListener('keydown', keydown, true);
  }, [active, configOpen, confirming, busyRef, form, setConfigOpen]);
  useEffect(() => {
    onFocusChange(id, focused);
    return () => onFocusChange(id, false);
  }, [focused, id, onFocusChange]);
  return { focused, toggleFocus: () => setFocused((value) => !value) };
}
