import { getLocale } from '../../../core/i18n.ts';
import { t } from '../../../core/i18n.ts';
import type { Dispatch, SetStateAction } from 'react';
import type { Manifest } from '../../../core/types';
import type { Screen } from './types';

type Toggle = Dispatch<SetStateAction<boolean>>;
export default function DisplayOptions({
  manifest,
  screenshot,
  grid,
  setGrid,
  dots,
  setDots,
  fit,
  setFit,
}: {
  manifest: Manifest;
  screenshot: Screen | undefined;
  grid: boolean;
  setGrid: Toggle;
  dots: boolean;
  setDots: Toggle;
  fit: boolean;
  setFit: Toggle;
}) {
  return (
    <details className="instrument-card scope-display-options">
      <summary>{t('显示选项与屏幕快照')}</summary>
      <div className="scope-checks">
        <label>
          <input type="checkbox" checked={grid} onChange={(e) => setGrid(e.target.checked)} />
          {t('网格')}
        </label>
        <label>
          <input type="checkbox" checked={dots} onChange={(e) => setDots(e.target.checked)} />
          {t('采样点')}
        </label>
        <label>
          <input type="checkbox" checked={fit} onChange={(e) => setFit(e.target.checked)} />
          {t('适配信号幅度')}
        </label>
      </div>
      <p className="instrument-caption">
        {fit ? t('幅度已适配显示，垂直档位仍控制仪器。') : t('按仪器垂直档位显示，共 8 格。')}
        {t('显示选项与游标仅在本地生效。')}
      </p>
      {screenshot ? (
        <>
          <img
            className="instrument-screen"
            src={screenshot.data_url}
            alt={t('{p0} 屏幕快照', { p0: manifest.name })}
          />
          <a
            className="quiet-button"
            href={screenshot.data_url}
            download={`${manifest.id}-screen.png`}
          >
            {t('保存 PNG')}
          </a>
          <span className="instrument-caption">
            {new Date(screenshot.timestamp).toLocaleTimeString(getLocale())}
            {t('· 单张快照')}
          </span>
        </>
      ) : (
        <p className="instrument-caption">{t('点击相机按钮获取仪器原始屏幕。')}</p>
      )}
    </details>
  );
}
