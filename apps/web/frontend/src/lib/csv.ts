/**
 * RFC 4180-compliant CSV parser.
 *
 * Handles:
 * - UTF-8 BOM stripping
 * - Quoted fields with embedded commas, newlines, and escaped quotes ("")
 * - CRLF and LF line endings (mixed)
 * - Trailing newline at EOF (no phantom row)
 * - Empty cells coerced to null (pandas NaN compatibility)
 *
 * Does NOT handle: alternate delimiters, UTF-16, multi-char quote chars.
 */

export interface ParsedCSV {
  columns: string[];
  rows: Record<string, unknown>[];
  rowCount: number;
}

export function parseCSV(input: string): ParsedCSV {
  // Strip UTF-8 BOM
  const text = input.charCodeAt(0) === 0xfeff ? input.slice(1) : input;

  const records: string[][] = [];
  let field = '';
  let record: string[] = [];
  let inQuotes = false;
  let i = 0;
  const n = text.length;

  while (i < n) {
    const ch = text[i];

    if (inQuotes) {
      if (ch === '"') {
        // Escaped double-quote: ""
        if (i + 1 < n && text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i++;
        continue;
      }
      field += ch;
      i++;
      continue;
    }

    if (ch === '"') {
      // Only treat as quote-open at start of field
      if (field.length === 0) {
        inQuotes = true;
        i++;
        continue;
      }
      // Stray quote mid-field — keep literal (lenient)
      field += ch;
      i++;
      continue;
    }

    if (ch === ',') {
      record.push(field);
      field = '';
      i++;
      continue;
    }

    if (ch === '\r' || ch === '\n') {
      record.push(field);
      field = '';
      // Skip blank trailing line
      if (record.length > 1 || record[0] !== '') {
        records.push(record);
      }
      record = [];
      // Consume CRLF as a single newline
      if (ch === '\r' && i + 1 < n && text[i + 1] === '\n') {
        i += 2;
      } else {
        i++;
      }
      continue;
    }

    field += ch;
    i++;
  }

  // Flush final field/record (file without trailing newline)
  if (field.length > 0 || record.length > 0) {
    record.push(field);
    if (record.length > 1 || record[0] !== '') {
      records.push(record);
    }
  }

  if (records.length < 2) {
    return { columns: [], rows: [], rowCount: 0 };
  }

  const columns = records[0].map((c) => c.trim());
  const rows: Record<string, unknown>[] = [];
  for (let r = 1; r < records.length; r++) {
    const cells = records[r];
    const row: Record<string, unknown> = {};
    for (let c = 0; c < columns.length; c++) {
      const raw = cells[c] ?? '';
      row[columns[c]] = coerce(raw);
    }
    rows.push(row);
  }
  return { columns, rows, rowCount: rows.length };
}

/**
 * Coerce a raw cell string to its typed value.
 *
 * - Empty string → null (pandas NaN compat)
 * - Strict integer → number (preserves "007" as string for IDs)
 * - Strict decimal → number
 * - Everything else → string
 */
export function coerce(raw: string): unknown {
  if (raw === '') return null;
  // Strict integer pattern. "007" stays a string (zip codes, IDs).
  if (/^-?[1-9]\d*$/.test(raw) || raw === '0' || raw === '-0') {
    return parseInt(raw, 10);
  }
  // Strict decimal pattern. "1,000" stays a string (thousands separator).
  if (/^-?\d+\.\d+$/.test(raw)) return parseFloat(raw);
  return raw;
}
