import { describe, it, expect } from 'vitest';
import { profileColumn, pickTableTypes } from '../profile';

describe('profileColumn', () => {
  it('classifies all-numeric few-uniques as categorical', () => {
    const rows = [
      { gender: 1 }, { gender: 2 }, { gender: 1 }, { gender: 2 }, { gender: 1 },
    ];
    const profile = profileColumn('gender', rows);
    expect(profile.kind).toBe('categorical');
    expect(profile.uniqueCount).toBe(2);
    expect(profile.valueLabels).toEqual({ 1: 'Code 1', 2: 'Code 2' });
  });

  it('classifies all-numeric many-uniques as continuous', () => {
    const rows = Array.from({ length: 100 }, (_, i) => ({ age: 18 + i }));
    const profile = profileColumn('age', rows);
    expect(profile.kind).toBe('continuous');
    expect(profile.valueLabels).toEqual({});
  });

  it('classifies all-text columns as text', () => {
    const rows = [
      { name: 'Alice' }, { name: 'Bob' }, { name: 'Carol' },
    ];
    const profile = profileColumn('name', rows);
    expect(profile.kind).toBe('text');
    expect(profile.valueLabels).toEqual({});
  });

  it('classifies mixed numeric+text as text', () => {
    const rows = [{ x: 1 }, { x: 'two' }, { x: 3 }];
    const profile = profileColumn('x', rows);
    expect(profile.kind).toBe('text');
  });

  it('classifies all-null columns as empty', () => {
    const rows = [{ x: null }, { x: null }, { x: '' }];
    const profile = profileColumn('x', rows);
    expect(profile.kind).toBe('empty');
    expect(profile.nonNullCount).toBe(0);
  });

  it('skips null and empty values from counts', () => {
    const rows = [{ q: 1 }, { q: null }, { q: 2 }, { q: '' }, { q: 1 }];
    const profile = profileColumn('q', rows);
    expect(profile.nonNullCount).toBe(3);
    expect(profile.uniqueCount).toBe(2);
    expect(profile.kind).toBe('categorical');
  });

  it('handles boundary at 20 unique values', () => {
    const rows = Array.from({ length: 20 }, (_, i) => ({ x: i }));
    const profile = profileColumn('x', rows);
    expect(profile.kind).toBe('categorical');
    expect(profile.uniqueCount).toBe(20);
  });

  it('treats 21 unique values as continuous', () => {
    const rows = Array.from({ length: 21 }, (_, i) => ({ x: i }));
    const profile = profileColumn('x', rows);
    expect(profile.kind).toBe('continuous');
  });

  it('handles decimal values', () => {
    const rows = [{ score: 1.5 }, { score: 2.75 }, { score: 3.0 }];
    const profile = profileColumn('score', rows);
    expect(profile.kind).toBe('categorical');
    expect(profile.uniqueCount).toBe(3);
  });
});

describe('pickTableTypes', () => {
  it('returns frequency+crosstab+top2box for all-categorical', () => {
    const profiles = [
      { name: 'a', kind: 'categorical' as const, numericCount: 0, nonNullCount: 0, uniqueCount: 0, valueLabels: {} },
    ];
    expect(pickTableTypes(profiles)).toEqual(['frequency', 'crosstab', 'top2box']);
  });

  it('returns mean only for all-continuous', () => {
    const profiles = [
      { name: 'a', kind: 'continuous' as const, numericCount: 0, nonNullCount: 0, uniqueCount: 0, valueLabels: {} },
    ];
    expect(pickTableTypes(profiles)).toEqual(['mean']);
  });

  it('returns frequency+mean for mixed', () => {
    const profiles = [
      { name: 'a', kind: 'categorical' as const, numericCount: 0, nonNullCount: 0, uniqueCount: 0, valueLabels: {} },
      { name: 'b', kind: 'continuous' as const, numericCount: 0, nonNullCount: 0, uniqueCount: 0, valueLabels: {} },
    ];
    expect(pickTableTypes(profiles)).toEqual(['frequency', 'mean']);
  });

  it('returns frequency+mean for empty input', () => {
    expect(pickTableTypes([])).toEqual(['frequency', 'mean']);
  });
});
