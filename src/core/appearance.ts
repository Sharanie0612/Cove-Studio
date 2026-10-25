export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedMode = 'light' | 'dark';
export type SchemeId = 'vscode' | 'github' | 'paper' | 'cove' | 'custom';
export interface CustomColors {
  background: string;
  surface: string;
  sidebar: string;
  accent: string;
}
export interface Appearance {
  mode: ThemeMode;
  scheme: SchemeId;
  custom: Record<ResolvedMode, CustomColors>;
}
interface Palette extends CustomColors {
  text: string;
  muted: string;
  border: string;
  primary?: string;
  green: string;
  red: string;
}
export const schemes = [
  { id: 'cove', name: 'Cove', description: '通透白 · 雾蓝点缀' },
  { id: 'vscode', name: 'VS Code', description: '中性底色 · 清晰蓝' },
  { id: 'github', name: 'GitHub', description: '黑白层次 · 经典绿' },
  { id: 'paper', name: '暖纸', description: '奶油白 · 茶褐色' },
] as const;

// Cove palettes adapted from VS Code Modern and GitHub's official theme sources.
// Sources and attribution: docs/appearance.md. These are independent UI presets.
const palettes: Record<Exclude<SchemeId, 'custom'>, Record<ResolvedMode, Palette>> = {
  vscode: {
    light: {
      background: '#ffffff',
      surface: '#ffffff',
      sidebar: '#f8f8f8',
      accent: '#005fb8',
      text: '#3b3b3b',
      muted: '#616161',
      border: '#e5e5e5',
      green: '#2e7d32',
      red: '#c72e0f',
    },
    dark: {
      background: '#1f1f1f',
      surface: '#252526',
      sidebar: '#181818',
      accent: '#0078d4',
      text: '#cccccc',
      muted: '#a3a3a3',
      border: '#3c3c3c',
      green: '#73c991',
      red: '#f48771',
    },
  },
  github: {
    light: {
      background: '#ffffff',
      surface: '#ffffff',
      sidebar: '#f6f8fa',
      accent: '#0969da',
      primary: '#1f883d',
      text: '#1f2328',
      muted: '#656d76',
      border: '#d0d7de',
      green: '#1f883d',
      red: '#cf222e',
    },
    dark: {
      background: '#0d1117',
      surface: '#161b22',
      sidebar: '#010409',
      accent: '#58a6ff',
      primary: '#238636',
      text: '#e6edf3',
      muted: '#9aa5b1',
      border: '#30363d',
      green: '#3fb950',
      red: '#f85149',
    },
  },
  paper: {
    light: {
      background: '#faf7f0',
      surface: '#fffdf8',
      sidebar: '#f3ede2',
      accent: '#95613b',
      text: '#463b31',
      muted: '#796b5e',
      border: '#e5dac9',
      green: '#5f7c47',
      red: '#b95a4c',
    },
    dark: {
      background: '#27231f',
      surface: '#302a24',
      sidebar: '#211d19',
      accent: '#d3ac7b',
      text: '#eee2d2',
      muted: '#bdb09f',
      border: '#4b4137',
      green: '#a2bd83',
      red: '#df9585',
    },
  },
  cove: {
    light: {
      background: '#fafbfc',
      surface: '#ffffff',
      sidebar: '#f3f5f7',
      accent: '#536f94',
      text: '#2c3440',
      muted: '#697586',
      border: '#e4e8ed',
      green: '#32815f',
      red: '#bb4b5f',
    },
    dark: {
      background: '#20242b',
      surface: '#282d35',
      sidebar: '#191d23',
      accent: '#a0b6d3',
      text: '#eef0f3',
      muted: '#aab0bb',
      border: '#383f49',
      green: '#78c5a1',
      red: '#ed9cae',
    },
  },
};
export function validColor(value: unknown): value is string {
  return typeof value === 'string' && /^#[\da-f]{6}$/i.test(value);
}
export function mix(a: string, b: string, weight: number): string {
  return (
    '#' +
    [1, 3, 5]
      .map((i) =>
        Math.round(
          parseInt(a.slice(i, i + 2), 16) * (1 - weight) + parseInt(b.slice(i, i + 2), 16) * weight,
        )
          .toString(16)
          .padStart(2, '0'),
      )
      .join('')
  );
}
function luminance(color: string): number {
  const values = [1, 3, 5]
    .map((i) => parseInt(color.slice(i, i + 2), 16) / 255)
    .map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
}
export function contrast(a: string, b: string): number {
  const values = [luminance(a), luminance(b)].sort((x, y) => x - y);
  return (values[1] + 0.05) / (values[0] + 0.05);
}
export function onColor(background: string): string {
  return contrast('#ffffff', background) >= contrast('#171717', background) ? '#ffffff' : '#171717';
}
export function customFromScheme(scheme: Exclude<SchemeId, 'custom'>): Appearance['custom'] {
  const pick = (mode: ResolvedMode) => {
    const { background, surface, sidebar, accent } = palettes[scheme][mode];
    return { background, surface, sidebar, accent };
  };
  return { light: pick('light'), dark: pick('dark') };
}
export function normalizeAppearance(value: unknown, legacyMode: unknown = 'light'): Appearance {
  const item = value && typeof value === 'object' ? (value as Partial<Appearance>) : {};
  const mode = item.mode ?? legacyMode;
  const defaults = customFromScheme('cove');
  const custom = defaults;
  for (const mode of ['light', 'dark'] as const)
    for (const field of ['background', 'surface', 'sidebar', 'accent'] as const) {
      const color = item.custom?.[mode]?.[field];
      if (validColor(color)) custom[mode][field] = color.toLowerCase();
    }
  return {
    mode: mode === 'dark' || mode === 'system' ? mode : 'light',
    scheme:
      schemes.some((s) => s.id === item.scheme) || item.scheme === 'custom' ? item.scheme! : 'cove',
    custom,
  };
}
export function resolvedMode(mode: ThemeMode, systemDark: boolean): ResolvedMode {
  return mode === 'system' ? (systemDark ? 'dark' : 'light') : mode;
}
export function getPalette(appearance: Appearance, mode: ResolvedMode): Palette {
  if (appearance.scheme !== 'custom') return palettes[appearance.scheme][mode];
  const colors = appearance.custom[mode];
  const text = ['#202124', '#f0f1f2'].sort(
    (a, b) =>
      Math.min(
        contrast(b, colors.background),
        contrast(b, colors.surface),
        contrast(b, colors.sidebar),
      ) -
      Math.min(
        contrast(a, colors.background),
        contrast(a, colors.surface),
        contrast(a, colors.sidebar),
      ),
  )[0];
  return {
    ...colors,
    text,
    muted: mix(text, colors.background, 0.24),
    border: mix(colors.surface, text, 0.18),
    green: mode === 'dark' ? '#84c99e' : '#287d45',
    red: mode === 'dark' ? '#f19a96' : '#b83f45',
  };
}
export function themeTokens(appearance: Appearance, mode: ResolvedMode): Record<string, string> {
  const p = getPalette(appearance, mode),
    primary = p.primary || p.accent;
  const soft = mix(p.background, p.accent, mode === 'dark' ? 0.12 : 0.075);
  const terminal = p.background;
  return {
    bg: p.background,
    surface: p.surface,
    'surface-2': mix(p.surface, p.text, 0.025),
    fill: mix(p.surface, p.text, 0.045),
    text: p.text,
    'text-2': p.muted,
    'text-3': p.muted,
    border: p.border,
    'border-strong': mix(p.border, p.text, 0.17),
    blue: p.accent,
    'blue-hover': mix(p.accent, onColor(p.accent) === '#ffffff' ? '#000000' : '#ffffff', 0.12),
    'blue-soft': soft,
    'on-accent': onColor(p.accent),
    primary: primary,
    'primary-hover': mix(primary, onColor(primary) === '#ffffff' ? '#000000' : '#ffffff', 0.1),
    'on-primary': onColor(primary),
    green: p.green,
    red: p.red,
    sidebar: p.sidebar,
    chrome: p.sidebar,
    'glyph-tile-top': mode === 'dark' ? '#383838' : '#ffffff',
    'glyph-tile-bottom': mode === 'dark' ? '#2c2c2c' : '#f3f3f3',
    'glyph-border': mode === 'dark' ? '#494949' : '#e3e3e3',
    'glyph-edge': mode === 'dark' ? '#1b1b1b' : '#d7d7d7',
    'glyph-highlight': mode === 'dark' ? '#ffffff24' : '#ffffff',
    'glyph-ink-top': mode === 'dark' ? '#f5f5f5' : '#555555',
    'glyph-ink-bottom': mode === 'dark' ? '#bfbfbf' : '#1c1c1c',
    'glyph-mid-top': mode === 'dark' ? '#a6a6a6' : '#ababab',
    'glyph-mid-bottom': mode === 'dark' ? '#737373' : '#777777',
    'glyph-face-top': mode === 'dark' ? '#656565' : '#fafafa',
    'glyph-face-bottom': mode === 'dark' ? '#3e3e3e' : '#cecece',
    'glyph-inset': mode === 'dark' ? '#ffffff24' : '#00000018',
    'glyph-on-ink': mode === 'dark' ? '#303030' : '#ffffff',
    'glyph-shadow-opacity': mode === 'dark' ? '.22' : '.12',
    'nav-active': soft,
    'nav-text': p.text,
    shadow: mode === 'dark' ? '0 2px 8px #00000018' : '0 2px 6px #304d7610, 0 8px 24px #304d7606',
    'terminal-bg': terminal,
    'terminal-fg': p.text,
    'terminal-black': mix(terminal, p.text, 0.8),
    'terminal-muted': p.muted,
    'terminal-cursor': p.accent,
    'terminal-selection': mix(terminal, p.accent, 0.27),
    'terminal-red': p.red,
    'terminal-green': p.green,
    'terminal-blue': mode === 'dark' ? mix(p.accent, '#ffffff', 0.3) : p.accent,
    'terminal-yellow': mode === 'dark' ? '#e5c07b' : '#946b0c',
    'terminal-magenta': mode === 'dark' ? '#c99ce8' : '#8950a2',
    'terminal-cyan': mode === 'dark' ? '#7dcad4' : '#277d88',
  };
}
