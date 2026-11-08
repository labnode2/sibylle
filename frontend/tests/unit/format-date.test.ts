// A date the interface does not expect (a tab left open across a deploy) shows as nothing
// instead of breaking the page.
import { expect, it } from 'vitest';

import { formatDate } from '../../src/i18n';

it('formats in Paris time, and shows nothing for a date that is not one', () => {
  expect(formatDate('2026-11-08T23:30:00Z', { day: 'numeric', month: 'long' })).toBe('9 novembre');
  expect(formatDate(new Date(2026, Number.NaN, 15), { month: 'long' })).toBe('');
  expect(formatDate('2026-autumn', { month: 'long' })).toBe('');
});
