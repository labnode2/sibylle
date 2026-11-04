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

export type Cell = [number, number];

/** Every cell from `from` to `to`, both included, each touching the one before (Bresenham): a
 *  stroke has no gap, however fast the pointer went. */
export function line(from: Cell, to: Cell): Cell[] {
  let [x, y] = from;
  const [x1, y1] = to;
  const dx = Math.abs(x1 - x);
  const dy = -Math.abs(y1 - y);
  const sx = x < x1 ? 1 : -1;
  const sy = y < y1 ? 1 : -1;
  let error = dx + dy;
  const cells: Cell[] = [[x, y]];
  while (x !== x1 || y !== y1) {
    const twice = 2 * error;
    if (twice >= dy) {
      error += dy;
      x += sx;
    }
    if (twice <= dx) {
      error += dx;
      y += sy;
    }
    cells.push([x, y]);
  }
  return cells;
}

/** The cell across the vertical axis of the drawing. */
export const mirrored = ([x, y]: Cell, size: Size): Cell => [size - 1 - x, y];

/** A stroke from `from` to `to` in `color` (0 rubs out), and its reflection with `mirror`. */
export function stroke(
  pixels: Uint8Array,
  size: Size,
  from: Cell,
  to: Cell,
  color: number,
  mirror: boolean,
): Uint8Array {
  const cells = line(from, to);
  const all = mirror ? [...cells, ...cells.map((cell) => mirrored(cell, size))] : cells;
  if (all.every(([x, y]) => pixels[y * size + x] === color)) return pixels;
  const result = pixels.slice();
  for (const [x, y] of all) result[y * size + x] = color;
  return result;
}

/** A fill from (x, y), and from its reflection with `mirror`. */
export function fill(
  pixels: Uint8Array,
  size: Size,
  x: number,
  y: number,
  color: number,
  mirror: boolean,
): Uint8Array {
  const once = floodFill(pixels, size, x, y, color);
  if (!mirror) return once;
  const [mx, my] = mirrored([x, y], size);
  return floodFill(once, size, mx, my, color);
}
