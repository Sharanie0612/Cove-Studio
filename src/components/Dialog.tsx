import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type RefObject,
} from 'react';
import { createPortal } from 'react-dom';

const ExitContext = createContext(false);
let lastInteractive: HTMLElement | null = null;
document.addEventListener('focusin', (event) => {
  if (
    event.target instanceof HTMLElement &&
    event.target.matches('button, input, select, textarea, a, [tabindex]')
  )
    lastInteractive = event.target;
});
/** Retain the modal during its exit, while the native dialog still traps focus. */
export function DialogPresence({ children }: { children: ReactNode }) {
  const open = Boolean(children);
  const last = useRef(children);
  const [retained, setRetained] = useState(open);
  if (open) last.current = children;
  useEffect(() => {
    if (open) {
      setRetained(true);
      return;
    }
    const timer = setTimeout(
      () => setRetained(false),
      matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 160,
    );
    return () => clearTimeout(timer);
  }, [open]);
  if (!open && !retained) {
    last.current = null;
    return null;
  }
  return (
    <ExitContext.Provider value={!open}>{open ? children : last.current}</ExitContext.Provider>
  );
}

/** Shared native modal semantics: focus trapping, Escape, and return to the opener. */
export default function Dialog({
  children,
  labelId,
  onClose,
  busy = false,
  className = '',
  initialFocus,
  returnFocus,
}: {
  children: ReactNode;
  labelId: string;
  onClose: () => void;
  busy?: boolean;
  className?: string;
  initialFocus?: string;
  returnFocus?: RefObject<HTMLElement | null>;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const exiting = useContext(ExitContext);
  useEffect(() => {
    const dialog = ref.current!;
    const previousFocus =
      document.activeElement === document.body ? lastInteractive : document.activeElement;
    dialog.showModal();
    if (initialFocus) dialog.querySelector<HTMLElement>(initialFocus)?.focus();
    return () => {
      dialog.close();
      const target = returnFocus?.current || previousFocus;
      if (
        target instanceof HTMLElement &&
        target.isConnected &&
        target.checkVisibility() &&
        !target.closest('dialog:not([open])')
      )
        target.focus({ preventScroll: true });
    };
  }, []);
  return createPortal(
    <dialog
      ref={ref}
      aria-labelledby={labelId}
      aria-busy={busy}
      className={`dialog-window ${className} ${exiting ? 'is-exiting' : ''}`}
      onCancel={(event) => {
        event.preventDefault();
        if (!busy && !exiting) onClose();
      }}
      onClick={(event) => {
        if (event.target !== event.currentTarget || busy || exiting) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        if (
          event.clientX < bounds.left ||
          event.clientX > bounds.right ||
          event.clientY < bounds.top ||
          event.clientY > bounds.bottom
        )
          onClose();
      }}
    >
      {children}
    </dialog>,
    document.body,
  );
}
