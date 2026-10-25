import { t } from '../core/i18n.ts';
import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { Check, Monitor, Moon, Palette, Sun } from 'lucide-react';
import {
  contrast,
  customFromScheme,
  getPalette,
  schemes,
  validColor,
  type Appearance,
  type CustomColors,
  type ResolvedMode,
} from '../core/appearance';

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  const [draft, setDraft] = useState(value),
    [invalid, setInvalid] = useState(false);
  useEffect(() => {
    setDraft(value);
    setInvalid(false);
  }, [value]);
  function update(next: string) {
    setDraft(next);
    setInvalid(false);
    if (validColor(next)) onChange(next);
  }
  return (
    <div className="theme-color-field">
      <label>
        {label}
        <span>
          <input
            type="color"
            aria-label={t('选择{p0}', { p0: label })}
            value={value}
            onChange={(event) => update(event.target.value)}
          />
          <input
            type="text"
            aria-label={`${label} HEX`}
            value={draft}
            spellCheck={false}
            maxLength={7}
            onChange={(event) => update(event.target.value)}
            onBlur={() => setInvalid(!validColor(draft))}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                setInvalid(!validColor(draft));
              }
            }}
            aria-invalid={invalid}
          />
        </span>
      </label>
      {invalid && <p role="alert">{t('请输入 # 加六位颜色代码')}</p>}
    </div>
  );
}

export default function AppearancePicker({
  appearance,
  mode,
  onChange,
}: {
  appearance: Appearance;
  mode: ResolvedMode;
  onChange: (next: Appearance) => void;
}) {
  const editor = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (appearance.scheme === 'custom')
      editor.current?.scrollIntoView({
        block: 'nearest',
        behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth',
      });
  }, [appearance.scheme]);
  const p = getPalette(appearance, mode);
  const custom = appearance.custom[mode];
  const clarity = Math.min(
    ...[p.background, p.surface, p.sidebar].map((color) => contrast(p.text, color)),
  );
  const customFields: [keyof CustomColors, string][] = [
    ['background', t('页面背景')],
    ['surface', t('卡片与弹窗')],
    ['sidebar', t('侧栏与标签栏')],
    ['accent', t('强调色')],
  ];
  return (
    <section className="appearance-picker" aria-label={t('外观设置')}>
      <div className="appearance-section-heading">
        <h3>{t('外观模式')}</h3>
        <span>{t('更改自动保存')}</span>
      </div>
      <div className="appearance-modes" role="group" aria-label={t('外观模式')}>
        {(
          [
            { id: 'light', name: t('浅色'), Icon: Sun },
            { id: 'dark', name: t('深色'), Icon: Moon },
            { id: 'system', name: t('跟随系统'), Icon: Monitor },
          ] as const
        ).map(({ id, name, Icon }) => (
          <button
            key={id}
            aria-pressed={appearance.mode === id}
            onClick={() => onChange({ ...appearance, mode: id })}
          >
            <Icon size={16} />
            {name}
          </button>
        ))}
      </div>
      <div className="appearance-section-heading">
        <h3>{t('配色方案')}</h3>
        <span>{mode === 'dark' ? t('深色预览') : t('浅色预览')}</span>
      </div>
      <div className="theme-grid" role="group" aria-label={t('配色方案')}>
        {schemes.map((scheme) => {
          const colors = getPalette({ ...appearance, scheme: scheme.id }, mode);
          const style = {
            '--preview-bg': colors.background,
            '--preview-surface': colors.surface,
            '--preview-sidebar': colors.sidebar,
            '--preview-accent': colors.accent,
            '--preview-text': colors.text,
            '--preview-border': colors.border,
            '--preview-primary': colors.primary || colors.accent,
          } as CSSProperties;
          return (
            <button
              className="theme-card"
              key={scheme.id}
              aria-label={t('{p0} 配色', { p0: t(scheme.name) })}
              aria-pressed={appearance.scheme === scheme.id}
              onClick={() => onChange({ ...appearance, scheme: scheme.id })}
            >
              <span className="theme-preview" style={style} aria-hidden="true">
                <span className="preview-sidebar">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="preview-content">
                  <span className="preview-tabs">
                    <i />
                    <i />
                  </span>
                  <span className="preview-cards">
                    <i />
                    <i />
                  </span>
                  <span className="preview-line" />
                  <span className="preview-button" />
                </span>
              </span>
              <span className="theme-card-label">
                <span>
                  <b>{t(scheme.name)}</b>
                  <span>{t(scheme.description)}</span>
                </span>
                <span className="theme-selection">
                  {appearance.scheme === scheme.id && <Check size={14} />}
                </span>
              </span>
            </button>
          );
        })}
      </div>
      <div className={`custom-theme-entry ${appearance.scheme === 'custom' ? 'selected' : ''}`}>
        <Palette size={19} />
        <div>
          <b>{t('我的配色')}</b>
          <span>
            {appearance.scheme === 'custom'
              ? t('正在使用自定义颜色')
              : t('保留一套自己的浅色与深色方案')}
          </span>
        </div>
        <button
          className="button"
          aria-pressed={appearance.scheme === 'custom'}
          onClick={() => onChange({ ...appearance, scheme: 'custom' })}
        >
          {appearance.scheme === 'custom' ? (
            <>
              <Check size={14} />
              {t('使用中')}
            </>
          ) : (
            t('使用')
          )}
        </button>
        {appearance.scheme !== 'custom' && (
          <button
            className="button"
            onClick={() =>
              onChange({
                ...appearance,
                scheme: 'custom',
                custom: customFromScheme(
                  appearance.scheme as Exclude<Appearance['scheme'], 'custom'>,
                ),
              })
            }
          >
            {t('基于当前配色调整')}
          </button>
        )}
      </div>
      {appearance.scheme === 'custom' && (
        <div className="custom-theme-editor" ref={editor}>
          <div className="appearance-section-heading">
            <h3>
              {t('调整')}
              {mode === 'dark' ? t('深色') : t('浅色')}
              {t('颜色')}
            </h3>
            <button
              className="text-button"
              onClick={() =>
                onChange({
                  ...appearance,
                  custom: {
                    ...appearance.custom,
                    [mode]: customFromScheme('vscode')[mode],
                  },
                })
              }
            >
              {t('恢复 VS Code 默认颜色')}
            </button>
          </div>
          <div className="theme-color-grid">
            {customFields.map(([key, label]) => (
              <ColorField
                key={`${mode}-${key}`}
                label={label}
                value={custom[key]}
                onChange={(value) =>
                  onChange({
                    ...appearance,
                    custom: {
                      ...appearance.custom,
                      [mode]: { ...custom, [key]: value },
                    },
                  })
                }
              />
            ))}
          </div>
          <p className={`theme-clarity ${clarity < 4.5 ? 'needs-adjustment' : ''}`} role="status">
            {clarity < 4.5
              ? t('背景、侧栏与卡片的明暗差距较大，建议选用相近的底色以保持文字清晰。')
              : t('文字对比清晰 · 强调色会自动搭配按钮文字')}
          </p>
        </div>
      )}
    </section>
  );
}
