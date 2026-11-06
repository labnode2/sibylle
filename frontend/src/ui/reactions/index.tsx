// Quick reactions: five 16 × 16 pixel-art emojis drawn from Emile's GIFs (research.md J17). Each
// one becomes a strip of its steps, an SVG image made once; CSS shows its first step, the still
// emoji, and plays the strip while the pointer or the keyboard is on its button, and once after a
// press. « couper les animations » keeps the still emoji.
import type { CSSProperties } from 'react';

import { COLORS, EMOJIS, type Color, type Emoji } from './frames';
import styles from './reactions.module.css';

/** A drawing as one path per colour, made of its runs of one colour in each row. */
function paths(frame: readonly string[]): string {
  const found = new Map<Color, string>();
  frame.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const color = row[x] as Color | '.';
      let width = 1;
      while (row[x + width] === color) width += 1;
      if (color !== '.') {
        found.set(color, `${found.get(color) ?? ''}M${x} ${y}h${width}v1h-${width}z`);
      }
      x += width;
    }
  });
  return [...found].map(([color, d]) => `<path fill="${COLORS[color]}" d="${d}"/>`).join('');
}

/** Each drawing once, then a copy of the right one at each step, side by side. */
function strip({ frames, sequence }: Emoji): string {
  const width = 16 * sequence.length;
  const drawings = frames.map((frame, index) => `<g id="f${index}">${paths(frame)}</g>`);
  const steps = sequence.map((index, step) => `<use href="#f${index}" x="${16 * step}"/>`);
  const svg =
    `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="16" ` +
    `viewBox="0 0 ${width} 16" shape-rendering="crispEdges">` +
    `<defs>${drawings.join('')}</defs>${steps.join('')}</svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

type Kind = keyof typeof EMOJIS;

/** In display order: each strip, its number of steps and how long one play lasts, in ms. */
export const REACTIONS = Object.fromEntries(
  Object.entries(EMOJIS).map(([kind, emoji]: [string, Emoji]) => [
    kind,
    {
      src: strip(emoji),
      steps: emoji.sequence.length,
      duration: emoji.step * emoji.sequence.length,
    },
  ]),
) as Record<Kind, { src: string; steps: number; duration: number }>;

/** The emoji of a reaction, 32 pixels square: still, or playing (see above) and once while
 *  `playing`, then `onPlayed`; it says nothing to screen readers. */
export function ReactionEmoji({
  kind,
  playing = false,
  onPlayed,
}: {
  kind: Kind;
  playing?: boolean;
  onPlayed?: () => void;
}) {
  const { src, steps, duration } = REACTIONS[kind];
  return (
    <span
      className={playing ? `${styles.emoji} ${styles.playing}` : styles.emoji}
      aria-hidden="true"
    >
      <img
        className={styles.strip}
        src={src}
        alt=""
        style={{ '--steps': steps, '--duration': `${duration}ms` } as CSSProperties}
        onAnimationEnd={onPlayed}
      />
    </span>
  );
}
