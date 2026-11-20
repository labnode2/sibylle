// Pixel art as SVG images made once (`data:`): nothing to download, and sharp at every size. A
// drawing is rows of letters, one per pixel ('.' is transparent), each letter a colour.
// The quick reactions (ui/reactions) move in steps: 16 rows of 16 letters per drawing, `sequence`
// gives the drawing of each step, all of them `step` ms long, and its first step is the still
// image. Each one becomes a strip of its steps, that CSS slides by one step at a time behind a
// window of one step. The « Tuto » and « Charte » images (features/welcome/art.ts) are still: one
// drawing each, of any size.

export type Drawing = {
  frames: readonly (readonly string[])[];
  sequence: readonly number[];
  step: number;
};

export type Colors = Readonly<Record<string, string>>;

/** A strip to play: its image, its number of steps and how long one play lasts, in ms. */
export type Strip = { src: string; steps: number; duration: number };

/** A drawing as one path per colour, made of its runs of one colour in each row. */
function paths(frame: readonly string[], colors: Colors): string {
  const found = new Map<string, string>();
  frame.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const color = row[x]!;
      let width = 1;
      while (row[x + width] === color) width += 1;
      if (color !== '.') {
        found.set(color, `${found.get(color) ?? ''}M${x} ${y}h${width}v1h-${width}z`);
      }
      x += width;
    }
  });
  return [...found].map(([color, d]) => `<path fill="${colors[color]}" d="${d}"/>`).join('');
}

/** Each drawing once, then a copy of the right one at each step, side by side. */
export function strip({ frames, sequence, step }: Drawing, colors: Colors): Strip {
  const width = 16 * sequence.length;
  const drawings = frames.map((frame, index) => `<g id="f${index}">${paths(frame, colors)}</g>`);
  const steps = sequence.map((index, at) => `<use href="#f${index}" x="${16 * at}"/>`);
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="16" ` +
    `viewBox="0 0 ${width} 16" shape-rendering="crispEdges">` +
    `<defs>${drawings.join('')}</defs>${steps.join('')}</svg>`;
  return {
    src: `data:image/svg+xml,${encodeURIComponent(svg)}`,
    steps: sequence.length,
    duration: step * sequence.length,
  };
}

/** A still drawing, as large as its rows: the source of its image. */
export function picture(rows: readonly string[], colors: Colors): string {
  const width = rows[0]?.length ?? 0;
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${rows.length}" ` +
    `viewBox="0 0 ${width} ${rows.length}" shape-rendering="crispEdges">` +
    `${paths(rows, colors)}</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}
