import { describe, expect, it } from 'vitest';

import { floodFill, paint, resize } from '../../src/features/pixel-editor/grid';
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
