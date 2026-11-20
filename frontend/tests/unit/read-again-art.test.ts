// « Tuto » and « Charte » as pixel art playing in a loop, like GIFs (card #27): drawings of
// 16 × 16 in known colours, the still image first and last; both loops last the same and take
// turns, the book never moving while the scroll does.
import { describe, expect, it } from 'vitest';

import { ART, BOOK, COLORS, SCROLL } from '../../src/features/welcome/art';

const ROW = new RegExp(`^[.${Object.keys(COLORS).join('')}]{16}$`);
const DRAWINGS = { tuto: BOOK, charter: SCROLL };

/** The steps whose drawing is not the one of the step before. */
const moving = (sequence: readonly number[]) =>
  sequence.flatMap((frame, at) => (at > 0 && frame !== sequence[at - 1] ? [at] : []));

describe('« Tuto » and « Charte » pixel art', () => {
  it.each(Object.entries(DRAWINGS))('%s: drawings of 16 × 16 known colours', (_, drawing) => {
    for (const frame of drawing.frames) {
      expect(frame).toHaveLength(16);
      for (const row of frame) expect(row).toMatch(ROW);
    }
  });

  it.each(Object.entries(DRAWINGS))(
    '%s: every step shows a drawing, every drawing shows, the still one first and last',
    (_, drawing) => {
      expect(drawing.sequence.every((index) => index in drawing.frames)).toBe(true);
      expect(new Set(drawing.sequence).size).toBe(drawing.frames.length);
      // The first step is what « couper les animations » shows; the loop comes back to it.
      expect(drawing.sequence[0]).toBe(0);
      expect(drawing.sequence.at(-1)).toBe(0);
    },
  );

  it('loops as long as each other and takes turns', () => {
    expect(ART.tuto.steps).toBe(ART.charter.steps);
    expect(ART.tuto.duration).toBe(ART.charter.duration);
    const book = moving(BOOK.sequence);
    const scroll = moving(SCROLL.sequence);
    expect(book.length).toBeGreaterThan(0);
    expect(scroll.length).toBeGreaterThan(0);
    expect(book.filter((at) => scroll.includes(at))).toEqual([]);
  });

  it.each(Object.entries(ART))('%s: a strip of well-formed SVG, one copy per step', (name, art) => {
    const drawing = DRAWINGS[name as keyof typeof DRAWINGS];
    const svg = decodeURIComponent(art.src.replace('data:image/svg+xml,', ''));
    const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
    expect(doc.querySelector('parsererror')).toBeNull();
    expect(doc.querySelectorAll('defs > g')).toHaveLength(drawing.frames.length);
    expect(doc.querySelectorAll('svg > use')).toHaveLength(drawing.sequence.length);
    expect(art.steps).toBe(drawing.sequence.length);
    expect(art.duration).toBe(drawing.step * drawing.sequence.length);
  });
});
