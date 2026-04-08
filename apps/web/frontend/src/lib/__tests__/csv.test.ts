import { describe, it, expect } from 'vitest';
import { parseCSV, coerce } from '../csv';

describe('parseCSV', () => {
  it('parses basic CSV', () => {
    const result = parseCSV('a,b,c\n1,2,3');
    expect(result.columns).toEqual(['a', 'b', 'c']);
    expect(result.rowCount).toBe(1);
    expect(result.rows[0]).toEqual({ a: 1, b: 2, c: 3 });
  });

  it('strips UTF-8 BOM from header', () => {
    const result = parseCSV('\ufeffa,b\n1,2');
    expect(result.columns).toEqual(['a', 'b']);
    expect(result.rows[0]).toEqual({ a: 1, b: 2 });
  });

  it('handles quoted fields with embedded commas', () => {
    const result = parseCSV('name,age\n"Smith, John",42');
    expect(result.columns).toEqual(['name', 'age']);
    expect(result.rows[0]).toEqual({ name: 'Smith, John', age: 42 });
  });

  it('handles escaped double quotes inside quoted fields', () => {
    const result = parseCSV('a,b\n"she said ""hi""",2');
    expect(result.rows[0]).toEqual({ a: 'she said "hi"', b: 2 });
  });

  it('handles embedded newlines inside quoted fields', () => {
    const result = parseCSV('a,b\n"line1\nline2",2');
    expect(result.rows[0]).toEqual({ a: 'line1\nline2', b: 2 });
  });

  it('handles CRLF line endings with trailing newline', () => {
    const result = parseCSV('a,b\r\n1,2\r\n');
    expect(result.columns).toEqual(['a', 'b']);
    expect(result.rowCount).toBe(1);
    expect(result.rows[0]).toEqual({ a: 1, b: 2 });
  });

  it('coerces empty cells to null (not empty string)', () => {
    const result = parseCSV('a,b,c\n1,,3');
    expect(result.rows[0]).toEqual({ a: 1, b: null, c: 3 });
  });

  it('handles empty trailing cell', () => {
    const result = parseCSV('a,b\n1,');
    expect(result.rows[0]).toEqual({ a: 1, b: null });
  });

  it('handles empty leading cell', () => {
    const result = parseCSV('a,b\n,2');
    expect(result.rows[0]).toEqual({ a: null, b: 2 });
  });

  it('preserves leading-zero IDs as strings', () => {
    const result = parseCSV('ID,name\n007,Alice\n008,Bob');
    expect(result.rows[0]).toEqual({ ID: '007', name: 'Alice' });
    expect(result.rows[1]).toEqual({ ID: '008', name: 'Bob' });
  });

  it('handles decimal values', () => {
    const result = parseCSV('x,y\n1.5,2.75');
    expect(result.rows[0]).toEqual({ x: 1.5, y: 2.75 });
  });

  it('handles negative numbers', () => {
    const result = parseCSV('x\n-1\n-1.5');
    expect(result.rows[0]).toEqual({ x: -1 });
    expect(result.rows[1]).toEqual({ x: -1.5 });
  });

  it('does not coerce thousands-separator strings', () => {
    const result = parseCSV('amount\n"1,000"\n2');
    expect(result.rows[0]).toEqual({ amount: '1,000' });
    expect(result.rows[1]).toEqual({ amount: 2 });
  });

  it('handles multiple rows', () => {
    const result = parseCSV('a,b\n1,2\n3,4\n5,6');
    expect(result.rowCount).toBe(3);
    expect(result.rows[2]).toEqual({ a: 5, b: 6 });
  });

  it('skips blank trailing line', () => {
    const result = parseCSV('a,b\n1,2\n\n');
    expect(result.rowCount).toBe(1);
  });

  it('handles realistic Qualtrics-style row with quotes and commas', () => {
    const csv = 'ResponseId,Q1,OpenEnd\n"R_abc123",4,"Great service, would recommend!"';
    const result = parseCSV(csv);
    expect(result.rows[0]).toEqual({
      ResponseId: 'R_abc123',
      Q1: 4,
      OpenEnd: 'Great service, would recommend!',
    });
  });

  it('returns empty result for empty input', () => {
    expect(parseCSV('')).toEqual({ columns: [], rows: [], rowCount: 0 });
  });

  it('returns empty result for header-only input', () => {
    expect(parseCSV('a,b,c').rowCount).toBe(0);
  });
});

describe('coerce', () => {
  it('returns null for empty string', () => {
    expect(coerce('')).toBeNull();
  });

  it('coerces strict integers', () => {
    expect(coerce('42')).toBe(42);
    expect(coerce('-7')).toBe(-7);
    expect(coerce('0')).toBe(0);
  });

  it('preserves leading-zero strings', () => {
    expect(coerce('007')).toBe('007');
    expect(coerce('001')).toBe('001');
  });

  it('coerces strict decimals', () => {
    expect(coerce('1.5')).toBe(1.5);
    expect(coerce('-2.75')).toBe(-2.75);
  });

  it('keeps thousands-separator strings as strings', () => {
    expect(coerce('1,000')).toBe('1,000');
  });

  it('keeps non-numeric strings as strings', () => {
    expect(coerce('hello')).toBe('hello');
    expect(coerce('Male')).toBe('Male');
  });
});
