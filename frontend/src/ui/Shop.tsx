// The collection's shop: a little shop of 17 × 17 pixels, its awning striped red and white over a
// window and a door, drawn like the flame (ui/Flame.tsx) from rows of letters. It stands beside
// my coins on la une's top line, on a phone, where it opens the collection.

const COLORS = {
  o: '#1d1b2b', // outline
  R: '#d44647', // awning, red
  r: '#a8323a', // its shade, and the step
  W: '#f4f6fb', // awning, white
  w: '#c9cbff', // its shade
  Y: '#ffb066', // wall
  y: '#e2914f', // its shade
  B: '#8fb0ff', // window
  b: '#d9dbff', // its glint
  D: '#4a50d0', // door
  k: '#ffe28a', // its knob
} as const;
type Color = keyof typeof COLORS;

const SHOP = [
  '.ooooooooooooooo.',
  'oRRRWWWRRRWWWRRRo',
  'oRRRWWWRRRWWWRRRo',
  'orrrwwwrrrwwwrrro',
  'ooRooWooRooWooRoo',
  '.ooyyoyyoyyoyyoo.',
  '.oYYYYYYYYYYYYYo.',
  '.oYoooooYoooooYo.',
  '.oYobBBoYoDDDoYo.',
  '.oYoBbBoYoDDDoYo.',
  '.oYoBBboYoDDkoYo.',
  '.oYoooooYoDDDoYo.',
  '.oYYYYYYYoDDDoYo.',
  '.oyyyyyyyoDDDoyo.',
  'ooooooooooooooooo',
  'orrrrrrrrrrrrrrro',
  'ooooooooooooooooo',
];

const SIZE = SHOP.length;

/** Each colour as one path: a rectangle for each run of it in a row. */
const PATHS = (Object.keys(COLORS) as Color[]).map((color) => ({
  color,
  d: SHOP.flatMap((row, y) =>
    [...row.matchAll(new RegExp(`${color}+`, 'g'))].map(
      ({ index, 0: run }) => `M${index} ${y}h${run.length}v1h-${run.length}z`,
    ),
  ).join(''),
}));

/** The shop alone, one pixel of the screen for each of its own, like the coins beside it; it
 *  says nothing to screen readers. */
export function Shop() {
  return (
    <svg
      width={SIZE}
      height={SIZE}
      viewBox={`0 0 ${SIZE} ${SIZE}`}
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {PATHS.map(({ color, d }) => (
        <path key={color} fill={COLORS[color]} d={d} />
      ))}
    </svg>
  );
}
