import { describe, expect, it } from 'vitest';

import { fill, floodFill, line, paint, resize, stroke } from '../../src/features/pixel-editor/grid';
import { decodePixels, encodePixels } from '../../src/ui/PixelImage';

describe('the drawing format', () => {
  it('goes to base64 and back without losing a pixel', () => {
    for (const size of [16, 32] as const) {
      const pixels = new Uint8Array(size * size).map((_, i) => i % 53);
      const image = { size, palette: 'base-v1', pixels: encodePixels(pixels) };
      expect(decodePixels(image)).toEqual(pixels);
    }
  });

  it('matches the server for a known drawing', () => {
    // backend: base64.b64encode(bytes([0, 1, 32, 52])) == b"AAEgNA=="
    expect(encodePixels(new Uint8Array([0, 1, 32, 52]))).toBe('AAEgNA==');
  });
});

describe('drawing', () => {
  it('paints one pixel without touching the original', () => {
    const blank = new Uint8Array(16 * 16);
    const painted = paint(blank, 16, 3, 2, 7);
    expect(painted[2 * 16 + 3]).toBe(7);
    expect(blank[2 * 16 + 3]).toBe(0);
  });

  it('fills the touching area of the same colour only', () => {
    const pixels = new Uint8Array(16 * 16);
    // A wall down the middle column.
    for (let y = 0; y < 16; y += 1) pixels[y * 16 + 8] = 1;
    const filled = floodFill(pixels, 16, 0, 0, 5);
    expect(filled[0]).toBe(5);
    expect(filled[15 * 16 + 7]).toBe(5);
    expect(filled[8]).toBe(1);
    expect(filled[9]).toBe(0);
    expect(floodFill(filled, 16, 0, 0, 5)).toEqual(filled);
  });

  it('doubles each pixel going to 32, and keeps one in four going back', () => {
    const small = new Uint8Array(16 * 16).map((_, i) => i % 7);
    const big = resize(small, 16, 32);
    expect(big.length).toBe(32 * 32);
    expect([big[0], big[1], big[32], big[33]]).toEqual([0, 0, 0, 0]);
    expect(big[2]).toBe(small[1]);
    expect(resize(big, 32, 16)).toEqual(small);
  });
});

describe('strokes, the mirror and the fill', () => {
  const at = (pixels: Uint8Array, size: number, x: number, y: number) => pixels[y * size + x];

  it('goes through every cell between two points, however fast the pointer went', () => {
    expect(line([0, 0], [3, 0])).toEqual([
      [0, 0],
      [1, 0],
      [2, 0],
      [3, 0],
    ]);
    expect(line([2, 5], [2, 2])).toEqual([
      [2, 5],
      [2, 4],
      [2, 3],
      [2, 2],
    ]);
    const steep = line([0, 0], [2, 6]);
    expect(steep).toHaveLength(7);
    // Each cell touches the one before: no gap.
    steep.slice(1).forEach(([x, y], i) => {
      const [px, py] = steep[i]!;
      expect(Math.max(Math.abs(x - px), Math.abs(y - py))).toBe(1);
    });
    expect(line([4, 4], [4, 4])).toEqual([[4, 4]]);
  });

  it('draws a stroke, and its reflection in the mirror', () => {
    const blank = new Uint8Array(16 * 16);
    const plain = stroke(blank, 16, [1, 3], [3, 3], 7, false);
    expect([1, 2, 3].map((x) => at(plain, 16, x, 3))).toEqual([7, 7, 7]);
    expect(at(plain, 16, 14, 3)).toBe(0);
    const mirrored = stroke(blank, 16, [1, 3], [3, 3], 7, true);
    expect([12, 13, 14].map((x) => at(mirrored, 16, x, 3))).toEqual([7, 7, 7]);
    expect(blank.every((value) => value === 0)).toBe(true);
  });

  it('fills both halves in the mirror', () => {
    const pixels = new Uint8Array(16 * 16);
    // Two closed boxes, one on each side.
    for (let y = 0; y < 16; y += 1) {
      pixels[y * 16 + 4] = 1;
      pixels[y * 16 + 11] = 1;
    }
    const plain = fill(pixels, 16, 0, 0, 5, false);
    expect([at(plain, 16, 0, 0), at(plain, 16, 15, 0)]).toEqual([5, 0]);
    const both = fill(pixels, 16, 0, 0, 5, true);
    expect([at(both, 16, 0, 0), at(both, 16, 15, 0), at(both, 16, 7, 0)]).toEqual([5, 5, 0]);
  });
});
