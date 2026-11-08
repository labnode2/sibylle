// The time left, short, on la une's line of Pixel mystère.
import { expect, it } from 'vitest';

import i18n from '../../src/i18n';
import { shortTimeLeft } from '../../src/ui/Countdown';

const NOW = Date.parse('2026-11-08T10:00:00+01:00');
const at = (minutes: number) => new Date(NOW + minutes * 60_000).toISOString();

it('says the days and hours, the hours and minutes, or the minutes left', () => {
  const t = i18n.t.bind(i18n);
  expect(shortTimeLeft(t, at(2 * 1440 + 5 * 60 + 30), NOW)).toBe('2 J 5 H');
  expect(shortTimeLeft(t, at(5 * 60 + 12), NOW)).toBe('5 H 12 MIN');
  expect(shortTimeLeft(t, at(12), NOW)).toBe('12 MIN');
  // Past the end (the worker ends the drawing within a minute): nothing left.
  expect(shortTimeLeft(t, at(-3), NOW)).toBe('0 MIN');
});
