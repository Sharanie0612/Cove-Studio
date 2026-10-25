import { t } from '../core/i18n.ts';
import { Eye, EyeOff } from 'lucide-react';
import { useState } from 'react';
import type { Field, Values } from '../core/types';

export function visible(field: Field, values: Values) {
  const condition = field.showWhen;
  return (
    !condition ||
    ((condition.equals === undefined || values[condition.field] === condition.equals) &&
      (condition.notEquals === undefined || values[condition.field] !== condition.notEquals))
  );
}
export default function SchemaFields({
  fields,
  values,
  onChange,
  disabled,
}: {
  fields: Field[];
  values: Values;
  onChange: (values: Values) => void;
  disabled: boolean;
}) {
  const [revealed, setRevealed] = useState<Record<string, boolean>>({});
  return (
    <div className="schema-fields">
      {fields
        .filter((field) => visible(field, values))
        .map((field) => (
          <label className="field" key={field.id} style={{ gridColumn: `span ${field.span || 4}` }}>
            <span>{field.label}</span>
            <div className="input-wrap">
              {field.type === 'select' ? (
                <select
                  aria-label={field.label}
                  disabled={disabled}
                  value={values[field.id] ?? ''}
                  onChange={(e) => onChange({ ...values, [field.id]: e.target.value })}
                >
                  {field.options?.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  aria-label={field.label}
                  name={field.id}
                  autoComplete="off"
                  spellCheck={false}
                  disabled={disabled}
                  value={values[field.id] ?? ''}
                  placeholder={field.placeholder}
                  type={field.type === 'password' && revealed[field.id] ? 'text' : field.type}
                  required={field.required}
                  min={field.min}
                  max={field.max}
                  onChange={(e) =>
                    onChange({
                      ...values,
                      [field.id]:
                        field.type === 'number'
                          ? e.target.value === ''
                            ? ''
                            : Number(e.target.value)
                          : e.target.value,
                    })
                  }
                />
              )}
              {field.type === 'password' && (
                <button
                  type="button"
                  className="reveal"
                  aria-label={revealed[field.id] ? t('隐藏密码') : t('显示密码')}
                  onClick={() =>
                    setRevealed({
                      ...revealed,
                      [field.id]: !revealed[field.id],
                    })
                  }
                >
                  {revealed[field.id] ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              )}
            </div>
          </label>
        ))}
    </div>
  );
}
