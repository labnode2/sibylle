import { describe, expect, it } from 'vitest';

import { fromParisInput, parisDay, parseDecimal, toParisInput } from '../../src/i18n';

describe('Paris time fields', () => {
  it('reads a winter time in Paris', () => {
    expect(fromParisInput('2026-11-05T18:00').toISOString()).toBe('2026-11-05T17:00:00.000Z');
  });

  it('reads a summer time in Paris', () => {
    expect(fromParisInput('2027-07-14T09:30').toISOString()).toBe('2027-07-14T07:30:00.000Z');
  });

  it('reads the day after the change to winter time', () => {
    expect(fromParisInput('2026-10-26T00:30').toISOString()).toBe('2026-10-25T23:30:00.000Z');
  });

  it('writes an instant back as Paris time', () => {
    expect(toParisInput(new Date('2026-11-05T17:00:00Z'))).toBe('2026-11-05T18:00');
    expect(toParisInput(new Date('2026-11-05T23:30:00Z'))).toBe('2026-11-06T00:30');
    expect(parisDay(new Date('2026-11-05T23:30:00Z'))).toBe('2026-11-06');
  });
});

describe('numbers typed in French', () => {
  it('reads a comma or a dot, and spaces between thousands', () => {
    expect(parseDecimal('12,5')).toBe('12.5');
    expect(parseDecimal(' 12.50 ')).toBe('12.50');
    expect(parseDecimal('1 200')).toBe('1200');
    expect(parseDecimal('-3')).toBe('-3');
    expect(parseDecimal('douze')).toBe('');
  });
});
