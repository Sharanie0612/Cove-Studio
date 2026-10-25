import { flushSync } from 'react-dom';
let transition: ViewTransition | undefined;
export function changeView(update: () => void) {
  if (
    !document.startViewTransition ||
    matchMedia('(prefers-reduced-motion: reduce)').matches ||
    document.querySelector('dialog[open]')
  ) {
    update();
    return;
  }
  transition?.skipTransition();
  transition = document.startViewTransition(() => flushSync(update));
  void transition.finished.catch(() => undefined);
}
