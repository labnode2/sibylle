// Palette "base-v1" of the pixel images (avatars, newsroom logos, Pixel mystère drawings).
// Index 0 is transparent. Must match backend/src/sibylle/domain/pixels.py.

// 1–32: drawn from the Gazette avatars of the canvas, open to everyone.
const BASE = [
  '#1d1b2b',
  '#3c2a24',
  '#3a3d45',
  '#5c3a2e',
  '#2a2f7a',
  '#71442b',
  '#22804a',
  '#a8432a',
  '#885837',
  '#3a3ea9',
  '#33a25f',
  '#987333',
  '#d44647',
  '#c56938',
  '#4a50d0',
  '#c99a18',
  '#d39a6a',
  '#e2b54a',
  '#f2c230',
  '#fb8194',
  '#e2a48e',
  '#ffb066',
  '#c6f06a',
  '#9be3b4',
  '#8fb0ff',
  '#f3c9a5',
  '#ffe28a',
  '#f5d0b0',
  '#c9cbff',
  '#d9dbff',
  '#ffd0e4',
  '#f4f6fb',
];

// 33–48: the vivid PICO-8 colours, unlocked with laurels.
const UNLOCKABLE = [
  '#000000',
  '#1d2b53',
  '#7e2553',
  '#008751',
  '#ab5236',
  '#5f574f',
  '#c2c3c7',
  '#fff1e8',
  '#ff004d',
  '#ffa300',
  '#ffec27',
  '#00e436',
  '#29adff',
  '#83769c',
  '#ff77a8',
  '#ffccaa',
];

// 49–52: rare colours of the crystal ball, unlocked by secret codes.
const RARE = ['#6e74ff', '#8f94ff', '#6267e8', '#8a6a12'];

export const PALETTE: readonly (string | null)[] = [null, ...BASE, ...UNLOCKABLE, ...RARE];
export const BASE_INDICES = BASE.map((_, i) => i + 1);
