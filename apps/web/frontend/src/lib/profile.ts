/**
 * Column profiler — classifies each CSV column for the backend table generator.
 *
 * The backend's _gen_frequency, _gen_crosstab, and _gen_t2b call int(code) on
 * every unique value, which crashes on text columns. Mean requires numeric
 * dtype. So we filter and classify client-side before sending to the backend.
 *
 * Decision rules:
 * - All non-null values numeric, ≤ MAX_CATEGORICAL_UNIQUE uniques → categorical
 * - All non-null values numeric, > MAX_CATEGORICAL_UNIQUE uniques → continuous
 * - Any non-numeric value → text (skipped, can't be tabulated)
 * - All values null/empty → empty (skipped)
 */

export type ColumnKind = 'categorical' | 'continuous' | 'text' | 'empty';

export interface ColumnProfile {
  name: string;
  kind: ColumnKind;
  numericCount: number;
  nonNullCount: number;
  uniqueCount: number;
  valueLabels: Record<number, string>; // populated only for categorical
}

const MAX_CATEGORICAL_UNIQUE = 20;
const HIGH_CARDINALITY_BAILOUT = 1000;

export function profileColumn(
  name: string,
  rows: Record<string, unknown>[],
): ColumnProfile {
  const uniques = new Set<number | string>();
  let numericCount = 0;
  let nonNullCount = 0;
  let hasString = false;

  for (const row of rows) {
    const v = row[name];
    if (v === null || v === undefined || v === '') continue;
    nonNullCount++;
    if (typeof v === 'number' && Number.isFinite(v)) {
      numericCount++;
      uniques.add(v);
    } else {
      hasString = true;
      uniques.add(String(v));
    }
    if (uniques.size > HIGH_CARDINALITY_BAILOUT) break;
  }

  const uniqueCount = uniques.size;

  if (nonNullCount === 0) {
    return {
      name,
      kind: 'empty',
      numericCount: 0,
      nonNullCount: 0,
      uniqueCount: 0,
      valueLabels: {},
    };
  }

  if (hasString) {
    return {
      name,
      kind: 'text',
      numericCount,
      nonNullCount,
      uniqueCount,
      valueLabels: {},
    };
  }

  // All numeric. Decide categorical vs continuous by unique count.
  if (uniqueCount <= MAX_CATEGORICAL_UNIQUE) {
    const valueLabels: Record<number, string> = {};
    const sorted = (Array.from(uniques) as number[]).sort((a, b) => a - b);
    for (const code of sorted) {
      if (Number.isInteger(code)) {
        valueLabels[code] = `Code ${code}`;
      }
    }
    return {
      name,
      kind: 'categorical',
      numericCount,
      nonNullCount,
      uniqueCount,
      valueLabels,
    };
  }

  return {
    name,
    kind: 'continuous',
    numericCount,
    nonNullCount,
    uniqueCount,
    valueLabels: {},
  };
}

/**
 * Pick the table_types config that matches the profiled columns.
 *
 * Rationale: per Codex review, _gen_frequency/_gen_crosstab/_gen_t2b all call
 * int(code) so they only work on integer-coded columns. Mean works on any
 * numeric column. We never send text columns. Multi-select needs item_columns
 * config we don't compute here, so we skip it.
 */
export function pickTableTypes(profiles: ColumnProfile[]): string[] {
  const hasCategorical = profiles.some((p) => p.kind === 'categorical');
  const hasContinuous = profiles.some((p) => p.kind === 'continuous');

  if (hasCategorical && !hasContinuous) {
    return ['frequency', 'crosstab', 'top2box'];
  }
  if (hasContinuous && !hasCategorical) {
    return ['mean'];
  }
  // Mixed or empty
  return ['frequency', 'mean'];
}
