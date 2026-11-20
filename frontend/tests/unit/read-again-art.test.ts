// « Tuto » and « Charte » as still pixel art (card #27): drawings of 32 × 32 in known colours,
// each one SVG image of its size.
import { describe, expect, it } from 'vitest';

import { ART, BOOK, COLORS, SCROLL } from '../../src/features/welcome/art';

const ROW = new RegExp(`^[.${Object.keys(COLORS).join('')}]{32}$`);
const DRAWINGS = { tuto: BOOK, charter: SCROLL };

describe('« Tuto » and « Charte » pixel art', () => {
  it.each(Object.entries(DRAWINGS))('%s: a drawing of 32 × 32 known colours', (_, rows) => {
    expect(rows).toHaveLength(32);
    for (const row of rows) expect(row).toMatch(ROW);
  });

  it.each(Object.entries(ART))('%s: one well-formed SVG image of 32 × 32', (_, src) => {
    const svg = decodeURIComponent(src.replace('data:image/svg+xml,', ''));
    const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
    expect(doc.querySelector('parsererror')).toBeNull();
    expect(doc.documentElement.getAttribute('viewBox')).toBe('0 0 32 32');
  });
});
