import { describe, expect, it } from 'vitest';
import { isSameLocalDay, statusLabel, toLocalInputValue } from './format';

describe('formátování', () => {
  it('popisky stavů v češtině, neznámé stavy se nezobrazí jako prázdné', () => {
    expect(statusLabel('late')).toBe('Pozdě');
    expect(statusLabel(null)).toBe('Nezapsán');
    expect(statusLabel('neco-jineho')).toBe('neco-jineho');
  });

  it('porovnává dny v lokálním čase', () => {
    const ref = new Date(2026, 10, 5, 12, 0, 0);
    expect(isSameLocalDay(new Date(2026, 10, 5, 8, 0).toISOString(), ref)).toBe(true);
    expect(isSameLocalDay(new Date(2026, 10, 6, 8, 0).toISOString(), ref)).toBe(false);
  });

  it('převede datum na hodnotu pro datetime-local', () => {
    expect(toLocalInputValue(new Date(2026, 0, 3, 9, 5))).toBe('2026-01-03T09:05');
  });
});
