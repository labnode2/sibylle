// Types of src/crystal-ball.js.

/** The seasons and holidays that a date can get. */
export type DatedVariant =
  | 'spring' | 'summer' | 'autumn' | 'winter'
  | 'epiphany' | 'candlemas' | 'valentines' | 'april-fools' | 'easter' | 'may-day'
  | 'remembrance' | 'music-day' | 'bastille-day' | 'pink-october' | 'halloween'
  | 'beaujolais' | 'christmas' | 'new-year';

/** fixed: the still ball (favicon); base: the animated ball; vision: the ball shows a portal. */
export type Variant = 'fixed' | 'base' | 'vision' | DatedVariant;

/** 16 rows of 16 colors (#rrggbb), null where the pixel is transparent. */
export type Grid = (string | null)[][];

export const SIZE: 16;
export const FRAME_MS: 120;

export function variants(): Variant[];
/** Frames in one loop: 1 for a still variant. */
export function frameCount(id: Variant): number;
export function info(id: Variant): { name: string; frames: number };
/** Frame f of a variant; f wraps around the loop. */
export function frame(id: Variant, f?: number): Grid;

/** An SVG of one frame (one rect per run of same-colored pixels). */
export function toSVG(grid: Grid): string;
/** Draws one frame on a 16×16 canvas context. */
export function paint(ctx: CanvasRenderingContext2D, grid: Grid): void;
/** RGBA bytes of one frame, each ball pixel scale × scale. */
export function toRGBA(grid: Grid, scale?: number): Uint8Array;

export interface Player {
  /** Plays `loops` more loops (default: the animate option), unless reduced motion is asked. */
  play(loops?: number): void;
  /** Stops and shows the first frame. */
  stop(): void;
  /** Stops without drawing (on unmount). */
  destroy(): void;
}
/** Plays a variant on a canvas: 2 loops by default, then rests on its first frame. */
export function animate(canvas: HTMLCanvasElement, id: Variant, options?: { loops?: number }): Player;

/** Easter Sunday as [month, day]. */
export function easter(year: number): [number, number];
export function holidays(year: number): [DatedVariant, [number, number][]][];
export function season(month: number, day: number): 'spring' | 'summer' | 'autumn' | 'winter';
/** The holiday of a date (local time), or else its season. */
export function variantFor(date: Date): DatedVariant;
