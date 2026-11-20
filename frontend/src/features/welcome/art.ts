// « Tuto » and « Charte » as pixel art that plays in a loop, like a GIF (card #27, research.md
// J19): an open book that turns a page, and the newsroom's charter, a scroll that rolls up to its
// middle, opens again and gets its red seal. Drawings of 16 × 16 in the format of
// ui/pixelStrip.ts, one letter per pixel; the first step of each is its still image. Both last
// the same and take turns: the book turns a page while the scroll rests, and the other way round.
import { strip, type Drawing } from '../../ui/pixelStrip';

/** The colours of the drawings, one letter each. */
export const COLORS = {
  K: '#15162d', // ink: outlines
  T: '#ffffff', // page
  S: '#d9dbff', // page in the shade, the gutter
  L: '#8f94ff', // lines of the book
  B: '#4a50d0', // cover
  b: '#2a2f7a', // cover in the shade
  R: '#e8452c', // ribbon, seal
  D: '#a8281a', // ribbon, seal in the shade
  p: '#f7a493', // shine on the seal
  P: '#fbe9c3', // parchment
  Q: '#e8c98a', // parchment in the shade
  l: '#b08a4a', // lines of the charter
  Y: '#f2c230', // gold
  y: '#c99a18', // gold in the shade
} as const;

type Rows = readonly string[];

/** `top` drawn over `under`; its '.' let `under` show. */
const over = (under: Rows, top: Rows): Rows =>
  under.map((row, y) =>
    [...row].map((pixel, x) => (top[y]![x] === '.' ? pixel : top[y]![x])).join(''),
  );

const mirrored = (rows: Rows): Rows => rows.map((row) => [...row].reverse().join(''));

/** `count` steps of the same drawing. */
const hold = (frame: number, count: number): number[] => Array<number>(count).fill(frame);

// The book open on two pages, as they are before a page is turned (A) and after (B).
const BOOK_A = [
  '................',
  '................',
  '..KKKK....KKKK..',
  '.KTTTTKKKKTTTTK.',
  'KTTTTTTSSTTTTTTK',
  'KTLLLLTSSTLLLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTLLLTTSSTLLLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTLLLLTSSTTLLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTTTTTTSSTTTTTTK',
  'KKTTTTKKKKTTTTKK',
  'BBKKKKBBBBKKKKBB',
  'bBBBBBBRDBBBBBBb',
  '.bbbbbbRDbbbbbb.',
];
const BOOK_B = [
  '................',
  '................',
  '..KKKK....KKKK..',
  '.KTTTTKKKKTTTTK.',
  'KTTTTTTSSTTTTTTK',
  'KTLLLTTSSTLLLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTLLLLTSSTTTLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTLLTTTSSTLLLLTK',
  'KTTTTTTSSTTTTTTK',
  'KTTTTTTSSTTTTTTK',
  'KKTTTTKKKKTTTTKK',
  'BBKKKKBBBBKKKKBB',
  'bBBBBBBRDBBBBBBb',
  '.bbbbbbRDbbbbbb.',
];
// The page that turns, half way up on the right, then standing over the gutter; half way down
// on the left, it is the first one mirrored.
const HALF_UP = [
  '...........KK...',
  '..........KTK...',
  '.........KTSK...',
  '........KTTSK...',
  '........STTSK...',
  '........STTSK...',
  '........STTSK...',
  '........STTSK...',
  '........STTSK...',
  '........STTSK...',
  '........STTKK...',
  '........SKK.....',
  '................',
  '................',
  '................',
  '................',
];
const STANDING = [
  '......KKKK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KTSK......',
  '......KKKK......',
  '................',
  '................',
  '................',
  '................',
];

/** A page turning from `from` to `to`: it goes over the left page of `from` and shows, under
 *  it, the right page of `to`. */
function turning(from: Rows, to: Rows): Rows[] {
  const under = from.map((row, y) => row.slice(0, 8) + to[y]!.slice(8));
  return [HALF_UP, STANDING, mirrored(HALF_UP)].map((page) => over(under, page));
}

export const BOOK: Drawing = {
  // 0 and 1: A and B; 2 to 4: from A to B; 5 to 7: from B to A.
  frames: [BOOK_A, BOOK_B, ...turning(BOOK_A, BOOK_B), ...turning(BOOK_B, BOOK_A)],
  sequence: [0, 2, 3, 4, ...hold(1, 16), 5, 6, 7, ...hold(0, 17)],
  step: 120,
};

// The scroll: a roll at each end, gold at its tips, and the sheet between them, sealed, before
// its seal, and as the seal is pressed on.
// prettier-ignore
const ROLL = [
  '.KKKKKKKKKKKKKK.',
  'KYKPPPPPPPPPPKYK',
  'KyKQQQQQQQQQQKyK',
  '.KKKKKKKKKKKKKK.',
];
const SEALED = [
  '..KPPPPPPPPPPK..',
  '..KPllllllllPK..',
  '..KPPPPPPPPPPK..',
  '..KPllllPRRRPK..',
  '..KPPPPPRpRRRK..',
  '..KPlllPRRRRRK..',
  '..KPPPPPRRRRDK..',
  '..KPPPPPPDDDPK..',
];
const UNSEALED = [
  '..KPPPPPPPPPPK..',
  '..KPllllllllPK..',
  '..KPPPPPPPPPPK..',
  '..KPllllPPPPPK..',
  '..KPPPPPPPPPPK..',
  '..KPlllPPPPPPK..',
  '..KPPPPPPPPPPK..',
  '..KPPPPPPPPPPK..',
];
const PRESSED = [
  '..KPPPPPPPPPPK..',
  '..KPllllllllPK..',
  '..KPPPPPPPPPPK..',
  '..KPllllPPPPPK..',
  '..KPPPPPRRRRPK..',
  '..KPlllRRpRRRK..',
  '..KPPPPRRRRRDK..',
  '..KPPPPPDDDDPK..',
];

/** The scroll open on the `rows` middle rows of its sheet (8: all of it), in the middle of the
 *  drawing. */
function scroll(sheet: Rows, rows: number): Rows {
  const margin = Array<string>((8 - rows) / 2).fill('.'.repeat(16));
  return [...margin, ...ROLL, ...sheet.slice((8 - rows) / 2, (8 + rows) / 2), ...ROLL, ...margin];
}

export const SCROLL: Drawing = {
  // 0: sealed; 1 to 3: rolling up; 4: rolled up; 5 to 8: opening, without its seal; 9: the
  // seal pressed on.
  frames: [
    scroll(SEALED, 8),
    scroll(SEALED, 6),
    scroll(SEALED, 4),
    scroll(SEALED, 2),
    scroll(SEALED, 0),
    scroll(UNSEALED, 2),
    scroll(UNSEALED, 4),
    scroll(UNSEALED, 6),
    scroll(UNSEALED, 8),
    scroll(PRESSED, 8),
  ],
  sequence: [...hold(0, 8), 1, 2, 3, 4, 4, 5, 6, 7, 8, 8, 9, ...hold(0, 21)],
  step: 120,
};

/** The strips to play: « Tuto », the book; « Charte », the scroll. */
export const ART = {
  tuto: strip(BOOK, COLORS),
  charter: strip(SCROLL, COLORS),
};
