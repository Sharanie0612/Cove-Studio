import { t } from '../core/i18n.ts';
import { Component, lazy, Suspense, type ReactNode } from 'react';
import { LoaderCircle, RefreshCw, SquareTerminal } from 'lucide-react';
import type { PluginSurfaceProps } from './contracts';
import { surfaceKind } from '../core/pluginPresentation';

const surfaces = {
  form: lazy(() => import('./surfaces/FormSurface')),
  terminal: lazy(() => import('./surfaces/TerminalSurface')),
  instrument: lazy(() => import('./surfaces/InstrumentSurface')),
  job: lazy(() => import('./surfaces/JobSurface')),
};

class SurfaceBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="list-empty" role="alert">
          <SquareTerminal size={28} />
          <b>{t('这个工具的界面暂时无法显示')}</b>
          <p>{t('其他工作区仍可使用。重新加载界面会清除界面草稿，后台连接保持运行。')}</p>
          <button className="button" onClick={() => this.setState({ failed: false })}>
            <RefreshCw size={14} />
            {t('重新加载界面')}
          </button>
        </div>
      );
    return this.props.children;
  }
}

export default function PluginSurface(props: PluginSurfaceProps) {
  const kind = surfaceKind(props.manifest);
  const Renderer = surfaces[kind];
  return (
    <SurfaceBoundary>
      <Suspense
        fallback={
          <div className="list-empty">
            <LoaderCircle size={22} className="spin" />
            <p>{t('正在打开工具…')}</p>
          </div>
        }
      >
        <Renderer {...props} />
      </Suspense>
    </SurfaceBoundary>
  );
}
