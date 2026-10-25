type Kind = 'workbench' | 'agents' | 'plugins' | 'guide' | 'settings' | 'collapse' | 'expand';

/** One optical size and stroke weight for management navigation. */
export default function NavigationIcon({ kind }: { kind: Kind }) {
  let drawing;
  switch (kind) {
    case 'workbench':
      drawing = (
        <>
          <rect x="4" y="4.5" width="16" height="15" rx="3" />
          <path d="M4 10h16M10 10v9.5" />
        </>
      );
      break;
    case 'agents':
      drawing = (
        <>
          <rect x="4.5" y="7" width="15" height="12.5" rx="4" />
          <path d="M12 4v3M9 12v2m6-2v2" />
        </>
      );
      break;
    case 'plugins':
      drawing = (
        <>
          <rect x="8.5" y="8.5" width="11" height="11" rx="3" />
          <path d="M15.5 8.5v-2a3 3 0 0 0-3-3h-6a3 3 0 0 0-3 3v6a3 3 0 0 0 3 3h2" />
        </>
      );
      break;
    case 'guide':
      drawing = (
        <>
          <path d="M12 6c-2-1.5-5-2-8-1v14c3-1 6-.5 8 1 2-1.5 5-2 8-1V5c-3-1-6-.5-8 1Zm0 0v14" />
          <path d="M7 9h2m6 0h2" opacity=".65" />
        </>
      );
      break;
    case 'settings':
      drawing = (
        <>
          <path d="m10 4-1 2.5-2.7.5-2 3 1.5 2-1 2.5 2 3 2.7.3L11 20h3l1-2.5 2.7-.5 2-3-1.5-2 1-2.5-2-3-2.7-.3L13 4Z" />
          <circle cx="12" cy="12" r="3" />
        </>
      );
      break;
    case 'collapse':
      drawing = (
        <>
          <path d="M5 5v14m11-12-5 5 5 5" />
        </>
      );
      break;
    case 'expand':
      drawing = (
        <>
          <path d="M19 5v14M8 7l5 5-5 5" />
        </>
      );
      break;
  }
  return (
    <svg
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      focusable="false"
      aria-hidden="true"
    >
      {drawing}
    </svg>
  );
}
