import type { Manifest } from './types';
export type View = 'home' | 'ai-tools' | 'plugins' | 'guide' | 'tool';
export interface WorkbenchState {
  view: View;
  activeId: string;
  tabs: Manifest[];
  epochs: Record<string, number>;
}
export type WorkbenchAction =
  | { type: 'view'; view: View }
  | { type: 'open'; tool: Manifest; activate?: boolean }
  | { type: 'activate'; id: string }
  | { type: 'close' | 'restart'; id: string }
  | { type: 'reconcile'; tools: Manifest[] };
export const initialWorkbench: WorkbenchState = {
  view: 'home',
  activeId: '',
  tabs: [],
  epochs: {},
};
export function workbenchReducer(state: WorkbenchState, action: WorkbenchAction): WorkbenchState {
  switch (action.type) {
    case 'view':
      return { ...state, view: action.view };
    case 'open':
      return {
        ...state,
        ...(action.activate === false ? {} : { view: 'tool' as const, activeId: action.tool.id }),
        tabs: state.tabs.some((tool) => tool.id === action.tool.id)
          ? state.tabs
          : [...state.tabs, action.tool],
      };
    case 'activate':
      return state.tabs.some((tool) => tool.id === action.id)
        ? { ...state, view: 'tool', activeId: action.id }
        : state;
    case 'restart':
      return {
        ...state,
        epochs: {
          ...state.epochs,
          [action.id]: (state.epochs[action.id] || 0) + 1,
        },
      };
    case 'close': {
      const index = state.tabs.findIndex((tool) => tool.id === action.id);
      if (index < 0) return state;
      const tabs = state.tabs.filter((tool) => tool.id !== action.id);
      const activeId =
        state.activeId === action.id
          ? tabs[Math.min(index, tabs.length - 1)]?.id || ''
          : state.activeId;
      return {
        ...state,
        tabs,
        activeId,
        view: state.view === 'tool' && !activeId ? 'home' : state.view,
      };
    }
    case 'reconcile': {
      const allowed = new Set(
        action.tools.filter((tool) => tool.enabled !== false).map((tool) => tool.id),
      );
      return state.tabs
        .filter((tool) => !allowed.has(tool.id))
        .reduce((next, tool) => workbenchReducer(next, { type: 'close', id: tool.id }), state);
    }
  }
}
