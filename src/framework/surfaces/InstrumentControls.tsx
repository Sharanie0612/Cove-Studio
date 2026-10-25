import { t } from '../../core/i18n.ts';
import { useEffect, useRef, useState } from 'react';
import { Minus, Plus } from 'lucide-react';
import { engineering, nearestDivision } from './instrumentView';
import { stepDivision } from './instrumentLive';

/** Drag previews locally; release, keyboard release or blur commits exactly once. */
export function CommitSlider({
  label,
  value,
  min,
  max,
  step = 1,
  disabled,
  onCommit,
  display,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  disabled?: boolean;
  onCommit: (value: number) => void;
  display?: (value: number) => string;
}) {
  const [draft, setDraft] = useState(value);
  const pending = useRef<number | null>(null);
  useEffect(() => {
    if (pending.current == null) setDraft(value);
  }, [value]);
  useEffect(() => {
    if (disabled) {
      pending.current = null;
      setDraft(value);
    }
  }, [disabled, value]);
  const commit = () => {
    if (pending.current == null || disabled) return;
    const next = pending.current;
    pending.current = null;
    if (next !== value) onCommit(next);
  };
  return (
    <div className="scope-slider">
      {display && (
        <output>
          {display(draft)}
          {pending.current != null && <small>{t('· 松开应用')}</small>}
        </output>
      )}
      <input
        type="range"
        aria-label={label}
        min={min}
        max={max}
        step={step}
        value={draft}
        disabled={disabled}
        onChange={(e) => {
          pending.current = Number(e.target.value);
          setDraft(pending.current);
        }}
        onPointerUp={commit}
        onKeyUp={(e) => {
          if (
            [
              'ArrowLeft',
              'ArrowRight',
              'ArrowUp',
              'ArrowDown',
              'Home',
              'End',
              'PageUp',
              'PageDown',
            ].includes(e.key)
          )
            commit();
        }}
        onBlur={commit}
        onPointerCancel={() => {
          pending.current = null;
          setDraft(value);
        }}
      />
    </div>
  );
}

export function DivisionControl({
  label,
  value,
  values,
  unit,
  disabled,
  onCommit,
}: {
  label: string;
  value: number;
  values: number[];
  unit: string;
  disabled: boolean;
  onCommit: (value: number) => void;
}) {
  const index = nearestDivision(value, values);
  return (
    <div className="scope-division">
      <div className="scope-control-label">
        <label>{label}</label>
        <b>{engineering(value, unit)}/div</b>
      </div>
      <div className="scope-stepper">
        <button
          className="icon-button"
          aria-label={t('减小{p0}', { p0: label })}
          disabled={disabled || value <= values[0]}
          onClick={() => onCommit(stepDivision(value, -1, values[0], values.at(-1)!))}
        >
          <Minus size={15} />
        </button>
        <CommitSlider
          label={label.endsWith(t('档位')) ? label : t('{p0}档位', { p0: label })}
          value={index}
          min={0}
          max={values.length - 1}
          disabled={disabled}
          onCommit={(i) => onCommit(values[i])}
          display={(i) => `${engineering(values[i], unit)}/div`}
        />
        <button
          className="icon-button"
          aria-label={t('增大{p0}', { p0: label })}
          disabled={disabled || value >= values.at(-1)!}
          onClick={() => onCommit(stepDivision(value, 1, values[0], values.at(-1)!))}
        >
          <Plus size={15} />
        </button>
      </div>
    </div>
  );
}
