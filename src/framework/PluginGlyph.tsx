import { useId } from 'react';
import type { Manifest } from '../core/types';

type Glyph =
  | 'terminal'
  | 'plug'
  | 'activity'
  | 'circuit-board'
  | 'file-chart-column'
  | 'list-todo'
  | 'folder'
  | 'wrench'
  | 'braces';

const glyphs = new Set<Glyph>([
  'terminal',
  'plug',
  'activity',
  'circuit-board',
  'file-chart-column',
  'list-todo',
  'folder',
  'wrench',
  'braces',
]);

function glyphKind(tool: Manifest): Glyph {
  if (glyphs.has(tool.icon as Glyph)) return tool.icon as Glyph;
  if (tool.ui.surface === 'terminal') return 'terminal';
  if (tool.ui.surface === 'mcp') return 'plug';
  if (tool.ui.instrument) return 'activity';
  if (tool.ui.job) return 'list-todo';
  if (tool.ui.result) return 'file-chart-column';
  return 'braces';
}

interface Paint {
  ink: string;
  mid: string;
  face: string;
  inset: string;
}

// Rounded silhouettes share a neutral material; overlapping faces provide depth.
function Drawing({ kind, paint }: { kind: Glyph; paint: Paint }) {
  switch (kind) {
    case 'terminal':
      return (
        <>
          <path
            d="M46 35c-12 0-17 6-17 18v23c0 12 6 18 18 18h35c12 0 18-6 18-18V53c0-12-6-18-18-18H46Z"
            fill={paint.ink}
            stroke="none"
          />
          <path d="M43 39h40" stroke="var(--glyph-on-ink)" strokeWidth="1.5" opacity=".25" />
          <path
            d="M45 53c5 4 9 8 13 12-4 4-8 8-13 11m27 1h12"
            stroke="var(--glyph-on-ink)"
            strokeWidth="6"
          />
        </>
      );
    case 'plug':
      return (
        <>
          <path d="m55 75-11 11a17 17 0 0 1-24-24l18-18a17 17 0 0 1 24 0" stroke={paint.mid} />
          <path d="m73 53 11-11a17 17 0 0 1 24 24L90 84a17 17 0 0 1-24 0" />
          <path d="m47 81 34-34" strokeWidth="7" />
        </>
      );
    case 'activity':
      return (
        <>
          <rect
            x="28"
            y="31"
            width="72"
            height="63"
            rx="15"
            fill={paint.face}
            stroke={paint.inset}
            strokeWidth="1.5"
          />
          <path d="M38 64h10l9-17 12 32 9-17h12" strokeWidth="6" />
          <path d="M48 102h32" stroke={paint.mid} strokeWidth="4" />
        </>
      );
    case 'circuit-board':
      return (
        <>
          <path
            d="M53 29v13m22-13v13M53 86v13m22-13v13M29 53h13m-13 22h13m44-22h13M86 75h13"
            stroke={paint.mid}
            strokeWidth="6.5"
          />
          <rect x="40" y="40" width="48" height="48" rx="13" fill={paint.ink} stroke="none" />
          <rect x="53" y="53" width="22" height="22" rx="5" fill={paint.face} stroke="none" />
        </>
      );
    case 'file-chart-column':
      return (
        <>
          <rect x="34" y="69" width="12" height="22" rx="6" fill={paint.mid} stroke="none" />
          <rect x="58" y="51" width="12" height="40" rx="6" fill={paint.ink} stroke="none" />
          <rect x="82" y="33" width="12" height="58" rx="6" fill={paint.ink} stroke="none" />
          <path d="M85 38v47" stroke="var(--glyph-on-ink)" strokeWidth="1.5" opacity=".22" />
        </>
      );
    case 'list-todo':
      return (
        <>
          <path d="M29 45c3 3 6 6 10 9l14-19m-24 45c3 3 6 6 10 9l14-19" />
          <path
            d="M68 45c10-1 19-1 28 0M68 80c7-1 13-1 20 0"
            stroke={paint.mid}
            strokeWidth="6.5"
          />
        </>
      );
    case 'folder':
      return (
        <>
          <path
            d="M29 53V45c0-9 4-13 13-13h11c6 0 8 2 12 7l6 6h15c10 0 14 5 14 15v21c0 10-5 15-15 15H44c-10 0-15-5-15-15Z"
            fill={paint.mid}
            stroke="none"
          />
          <path
            d="M41 49h45c10 0 14 5 14 15v17c0 10-5 15-15 15H44c-10 0-15-5-15-15V61c0-8 4-12 12-12Z"
            fill={paint.face}
            stroke={paint.inset}
            strokeWidth="1.5"
          />
          <path d="M42 52h41" stroke="var(--glyph-highlight)" strokeWidth="1.5" />
        </>
      );
    case 'wrench':
      return (
        <>
          <path
            d="M78 29a24 24 0 0 0-25 29L29 82a12 12 0 0 0 17 17l25-25a24 24 0 0 0 29-30L85 59l-13-4-4-13 15-15c-2 0-3 1-5 2Z"
            fill={paint.ink}
            stroke="none"
          />
          <circle cx="38" cy="90" r="4" fill="var(--glyph-on-ink)" stroke="none" />
        </>
      );
    default:
      return (
        <>
          <path d="M50 33c-15-2-16 6-15 17 1 9-2 14-10 14 8 0 11 5 10 14-1 11 0 19 15 17M78 33c15-2 16 6 15 17-1 9 2 14 10 14-8 0-11 5-10 14 1 11 0 19-15 17" />
          <path d="M64 64v.1" stroke={paint.mid} strokeWidth="9" />
        </>
      );
  }
}

/** Local vector icons use only neutral tones, with the same material in every theme. */
export default function PluginGlyph({ tool }: { tool: Manifest }) {
  const id = `plugin-${useId().replace(/:/g, '')}`;
  const kind = glyphKind(tool);
  const paint = {
    ink: `url(#${id}-ink)`,
    mid: `url(#${id}-mid)`,
    face: `url(#${id}-face)`,
    inset: 'var(--glyph-inset)',
  };
  return (
    <svg
      viewBox="0 0 128 128"
      fill="none"
      focusable="false"
      aria-hidden="true"
      data-glyph={kind}
      data-icon-style="hello"
      data-icon-palette="monochrome"
    >
      <defs>
        <linearGradient
          id={`${id}-tile`}
          x1="36"
          y1="3"
          x2="86"
          y2="125"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="var(--glyph-tile-top)" />
          <stop offset="1" stopColor="var(--glyph-tile-bottom)" />
        </linearGradient>
        <linearGradient
          id={`${id}-ink`}
          x1="42"
          y1="30"
          x2="88"
          y2="98"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="var(--glyph-ink-top)" />
          <stop offset="1" stopColor="var(--glyph-ink-bottom)" />
        </linearGradient>
        <linearGradient
          id={`${id}-mid`}
          x1="42"
          y1="30"
          x2="88"
          y2="98"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="var(--glyph-mid-top)" />
          <stop offset="1" stopColor="var(--glyph-mid-bottom)" />
        </linearGradient>
        <linearGradient
          id={`${id}-face`}
          x1="54"
          y1="45"
          x2="74"
          y2="98"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="var(--glyph-face-top)" />
          <stop offset="1" stopColor="var(--glyph-face-bottom)" />
        </linearGradient>
        <filter
          id={`${id}-depth`}
          x="-20%"
          y="-20%"
          width="150%"
          height="150%"
          colorInterpolationFilters="sRGB"
        >
          <feDropShadow
            dx="0"
            dy="2"
            stdDeviation="1.1"
            floodColor="#000000"
            floodOpacity="var(--glyph-shadow-opacity)"
          />
        </filter>
      </defs>
      <rect x="3" y="5" width="122" height="121" rx="29" fill="var(--glyph-edge)" />
      <rect
        x="3"
        y="2"
        width="122"
        height="122"
        rx="29"
        fill={`url(#${id}-tile)`}
        stroke="var(--glyph-border)"
        strokeWidth=".8"
      />
      <path d="M32 4h64" stroke="var(--glyph-highlight)" strokeLinecap="round" />
      <g
        stroke={paint.ink}
        strokeWidth="7.6"
        strokeLinecap="round"
        strokeLinejoin="round"
        filter={`url(#${id}-depth)`}
      >
        <Drawing kind={kind} paint={paint} />
      </g>
    </svg>
  );
}
