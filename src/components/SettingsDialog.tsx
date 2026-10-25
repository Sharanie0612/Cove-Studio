import { t } from '../core/i18n.ts';
import { languages, setLocale } from '../core/i18n.ts';
import { useLocale } from '../core/useLocale';
import { X } from 'lucide-react';
import type { Appearance, ResolvedMode } from '../core/appearance';
import type { Catalog } from '../core/types';
import Dialog from './Dialog';
import AppearancePicker from './AppearancePicker';
import coveIcon from '../../assets/cove-mark.svg';
import { productName } from '../core/identity';

export default function SettingsDialog({
  appearance,
  mode,
  onAppearance,
  fontSize,
  onFontSize,
  catalog,
  onClose,
}: {
  appearance: Appearance;
  mode: ResolvedMode;
  onAppearance: (next: Appearance) => void;
  fontSize: number;
  onFontSize: (next: number) => void;
  catalog: Catalog;
  onClose: () => void;
}) {
  const locale = useLocale();
  return (
    <Dialog labelId="settings-title" onClose={onClose} className="settings-dialog">
      <div className="dialog-heading">
        <div>
          <h2 id="settings-title">{t('设置')}</h2>
        </div>
        <button className="icon-button" aria-label={t('关闭设置')} onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="settings-body">
        <div className="setting-row language-setting">
          <div>
            <b>{t('界面语言')}</b>
            <p>{t('立即生效，保留当前连接和工作区。')}</p>
          </div>
          <select
            aria-label={t('界面语言')}
            value={locale}
            onChange={(event) => setLocale(event.target.value === 'en-US' ? 'en-US' : 'zh-CN')}
          >
            {languages.map((language) => (
              <option key={language.id} value={language.id} lang={language.id}>
                {language.name}
              </option>
            ))}
          </select>
        </div>
        <AppearancePicker appearance={appearance} mode={mode} onChange={onAppearance} />
        <div className="setting-row">
          <div>
            <b>{t('终端字号')}</b>
          </div>
          <select
            aria-label={t('终端字号')}
            value={fontSize}
            onChange={(event) => onFontSize(Number(event.target.value))}
          >
            {[12, 13, 14, 15, 16, 18].map((size) => (
              <option key={size} value={size}>
                {size} px
              </option>
            ))}
          </select>
        </div>
        <div className="setting-row">
          <div>
            <b>{t('数据保存在本机')}</b>
            <p className="data-path">{catalog.dataPath || t('桌面版中显示实际位置')}</p>
          </div>
        </div>
      </div>
      <div className="about-line settings-footer">
        <span className="cove-mark">
          <img src={coveIcon} alt="" />
        </span>
        <b>{productName}</b>
        <small>{catalog.hostVersion}</small>
        <button className="button primary" onClick={onClose}>
          {t('完成')}
        </button>
      </div>
    </Dialog>
  );
}
