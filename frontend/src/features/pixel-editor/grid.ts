// The pixel editor's drawing rules, kept apart from the screen: a drawing is a square grid of
// palette indices, 0 being transparent.

export type Size = 16 | 32;

/** Colours a whole area of the same colour, starting from (x, y), with `color`. */
export function floodFill(
  pixels: Uint8Array,
  size: Size,
  x: number,
  y: number,
  color: number,
): Uint8Array {
  const result = pixels.slice();
  const target = pixels[y * size + x];
  if (target === undefined || target === color) return result;
  const stack: [number, number][] = [[x, y]];
  while (stack.length > 0) {
    const [cx, cy] = stack.pop()!;
    if (cx < 0 || cy < 0 || cx >= size || cy >= size) continue;
    const i = cy * size + cx;
    if (result[i] !== target) continue;
    result[i] = color;
    stack.push([cx + 1, cy], [cx - 1, cy], [cx, cy + 1], [cx, cy - 1]);
  }
  return result;
}

/** One pixel set to `color`. */
export function paint(
  pixels: Uint8Array,
  size: Size,
  x: number,
  y: number,
  color: number,
): Uint8Array {
  const i = y * size + x;
  if (pixels[i] === color) return pixels;
  const result = pixels.slice();
  result[i] = color;
  return result;
}

/** The drawing at another size: each pixel doubled going up, the top-left of each 2 × 2
 * block kept going down. */
export function resize(pixels: Uint8Array, from: Size, to: Size): Uint8Array {
  if (from === to) return pixels.slice();
  const result = new Uint8Array(to * to);
  const ratio = from / to;
  for (let y = 0; y < to; y += 1) {
    for (let x = 0; x < to; x += 1) {
      result[y * to + x] = pixels[Math.floor(y * ratio) * from + Math.floor(x * ratio)]!;
    }
  }
  return result;
}
