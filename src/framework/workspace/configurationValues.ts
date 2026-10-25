import { fieldDefaults } from '../../core/fields';
import type { Field, Values } from '../../core/types';

export function isSecret(field: Field) {
  return Boolean(field.secret || field.type === 'password');
}

export function configurationValues(fields: Field[], saved: Values = {}): Values {
  const defaults = fieldDefaults(fields);
  return Object.fromEntries(
    fields.map((field) => [
      field.id,
      isSecret(field) ? '' : (saved[field.id] ?? defaults[field.id]),
    ]),
  );
}

export function publicValues(fields: Field[], values: Values): Values {
  return Object.fromEntries(
    fields.filter((field) => !isSecret(field)).map((field) => [field.id, values[field.id]]),
  );
}

export function clearSecrets(fields: Field[], values: Values): Values {
  const secrets = new Set(fields.filter(isSecret).map((field) => field.id));
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, secrets.has(key) ? '' : value]),
  );
}
