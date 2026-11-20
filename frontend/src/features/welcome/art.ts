// « Tuto » and « Charte » as still pixel art (card #27, research.md J19): an open book, its red
// ribbon hanging out, and the newsroom's charter, a parchment between two rolls with gold caps,
// signed and sealed in red. Drawings of 32 × 32, one letter per pixel ('.' is transparent),
// each made once into an SVG image (ui/pixelStrip.ts): nothing to download, sharp at every size.
import { picture } from '../../ui/pixelStrip';

/** The colours of the drawings, one letter each. */
export const COLORS = {
  K: '#15162d', // ink: outlines
  T: '#ffffff', // page
  U: '#eceeff', // page, towards the crease
  S: '#d9dbff', // page, by the crease
  L: '#a3a7ff', // lines of the book
  E: '#c9cbe4', // edges of the pages under
  B: '#4a50d0', // cover
  c: '#6d72e8', // cover, lit corner
  b: '#2a2f7a', // cover in the shade
  R: '#e8452c', // ribbon, seal
  D: '#a8281a', // ribbon, seal in the shade
  p: '#f7a493', // shine on the seal
  W: '#fff8e6', // parchment, lit
  P: '#fbe9c3', // parchment
  Q: '#e8c98a', // parchment in the shade
  q: '#b08a4a', // parchment in the deep shade
  l: '#c9a46a', // lines of the charter
  n: '#8a6a3a', // title and signature of the charter
  Y: '#f2c230', // gold
  w: '#fff3b0', // gold, lit
  y: '#c99a18', // gold in the shade
} as const;

/** « Tuto »: the book open on two pages of text, on its blue cover, its ribbon hanging out. */
export const BOOK = [
  '................................',
  '................................',
  '................................',
  '................................',
  '................................',
  '...KKKKK...............KKKKK....',
  '.KKTTTTTKKKK.......KKKKTTTTTKK..',
  'KcKTTTTTTTTTKK...KKTTTTTTTTTKcK.',
  'KBKTTTTTTTTTTUK.KUTTTTTTTTTTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTLLLLLLLLLUSKSULLLLLLLLLTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTLLLLLLLLTUSKSULLLLLLLLTTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTLLLLLTTTTUSKSULLLLLLLLLTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTLLLLLLLLLUSKSULLLLLLLLLTKBK.',
  'KBKTTTTTTTTTTUSKSUTTTTTTTTTTKBK.',
  'KBKTLLLLLLLTTUSKSULLLLLTTTTTKBK.',
  'KBEKKKKKTTTTTUSKSUTTTTTKKKKKEBK.',
  'KBEEEEEEKKKKTUSKSUTKKKKEEEEEEBK.',
  'KBBBBBBBEEEEKKSKSKKEEEEBBBBBBBK.',
  'KbbbbbbbBBBBEEKRDKEBBBBbbbbbbbK.',
  '.KKKKKKKbbbbBBKRDKBbbbbKKKKKKK..',
  '........KKKKbbKRDKbKKKK.........',
  '............KKKRDKK.............',
  '..............KRDK..............',
  '..............KDKK..............',
  '..............KK.K..............',
  '................................',
  '................................',
];

/** « Charte »: the parchment, its title, its lines and a signature, the red seal at its foot. */
export const SCROLL = [
  '................................',
  '................................',
  '................................',
  '....KK.KKKKKKKKKKKKKKKKKK.KK....',
  '...KwYKWWWWWWWWWWWWWWWWWWKwYK...',
  '...KYYKPPPPPPPPPPPPPPPPPPKYYK...',
  '...KYyKQQQQQQQQQQQQQQQQQQKYyK...',
  '...KyyKqqqqqqqqqqqqqqqqqqKyyK...',
  '....KK.KKKKKKKKKKKKKKKKKK.KK....',
  '.......KQQQQQQQQQQQQQQQQK.......',
  '.......KWPPPPPPPPPPPPPPQK.......',
  '.......KWPPnnnnnnnnnnPPQK.......',
  '.......KWPPPPPPPPPPPPPPQK.......',
  '.......KWPPPPPPPPPPPPPPQK.......',
  '.......KWllllllllllllllQK.......',
  '.......KWPPPPPPPPPPPPPPQK.......',
  '.......KWllllllllllllPPQK.......',
  '.......KWPPPPPPPPPPKKKKQK.......',
  '.......KWlllllllPPKRRRRKK.......',
  '.......KWPPPPPPPPKRpDDRRK.......',
  '.......KWPnnPPPnPKRDRRDRK.......',
  '.......KWnPPnPnPnKRDRRDDK.......',
  '.......KWPPPPnPPPKRRDDDDK.......',
  '....KK.KKKKKKKKKKKKRDDDKK.KK....',
  '...KwYKWWWWWWWWWWWWKKKKWWKwYK...',
  '...KYYKPPPPPPPPPPPPPPPPPPKYYK...',
  '...KYyKQQQQQQQQQQQQQQQQQQKYyK...',
  '...KyyKqqqqqqqqqqqqqqqqqqKyyK...',
  '....KK.KKKKKKKKKKKKKKKKKK.KK....',
  '................................',
  '................................',
  '................................',
];

/** The images to show: « Tuto », the book; « Charte », the parchment. */
export const ART = {
  tuto: picture(BOOK, COLORS),
  charter: picture(SCROLL, COLORS),
};
