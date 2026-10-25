import type { Field, Values } from './types';
export function fieldDefaults(fields: Field[]): Values {
  return Object.fromEntries(
    fields.map((field) => [
      field.id,
      field.default ?? (field.type === 'select' ? (field.options?.[0]?.value ?? '') : ''),
    ]),
  );
}
