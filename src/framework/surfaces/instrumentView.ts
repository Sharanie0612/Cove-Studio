/** Engineering units and local screen cursor calculations, without instrument I/O. */
export function engineering(value: number | null | undefined, unit = '', digits = 4): string {
  if (value == null || !Number.isFinite(value)) return '—';
  const prefixes = ['p', 'n', 'µ', 'm', '', 'k', 'M', 'G'];
  const exponent =
    value === 0 ? 0 : Math.max(-12, Math.min(9, Math.floor(Math.log10(Math.abs(value)) / 3) * 3));
  return `${Number((value / 10 ** exponent).toPrecision(digits))} ${prefixes[(exponent + 12) / 3]}${unit}`.trim();
}

export function divisions(minimum: number, maximum: number): number[] {
  const values = [minimum];
  for (
    let exponent = Math.floor(Math.log10(minimum));
    exponent <= Math.ceil(Math.log10(maximum));
    exponent++
  )
    for (const factor of [1, 2, 5]) {
      const value = Number((factor * 10 ** exponent).toPrecision(12));
      if (value > minimum && value < maximum) values.push(value);
    }
  values.push(maximum);
  return [...new Set(values)];
}

export function nearestDivision(value: number, values: number[]) {
  return values.reduce(
    (best, candidate, i) =>
      Math.abs(Math.log(candidate / value)) < Math.abs(Math.log(values[best] / value)) ? i : best,
    0,
  );
}

export function cursorReadout(time: number[], volts: number[], a: number, b: number) {
  if (!time.length || time.length !== volts.length) return null;
  const index = (percent: number) =>
    Math.round((Math.max(0, Math.min(100, percent)) / 100) * (time.length - 1));
  const ia = index(a),
    ib = index(b),
    dt = Math.abs(time[ib] - time[ia]);
  return {
    ia,
    ib,
    ta: time[ia],
    tb: time[ib],
    va: volts[ia],
    vb: volts[ib],
    dt,
    dv: volts[ib] - volts[ia],
    reciprocal: dt ? 1 / dt : null,
  };
}
