// Quick reactions: five 16 × 16 pixel-art emojis drawn from Emile's GIFs (research.md J17). Each
// one becomes a strip of its steps, an SVG image made once (ui/pixelStrip.ts); CSS shows its first
// step, the still emoji, and plays the strip while the pointer or the keyboard is on its button,
// and once after a press. « couper les animations » keeps the still emoji.
import type { CSSProperties } from 'react';

import { strip, type Strip } from '../pixelStrip';
import { COLORS, EMOJIS, type Emoji } from './frames';
import styles from './reactions.module.css';

type Kind = keyof typeof EMOJIS;

/** In display order: each strip, its number of steps and how long one play lasts, in ms. */
export const REACTIONS = Object.fromEntries(
  Object.entries(EMOJIS).map(([kind, emoji]: [string, Emoji]) => [kind, strip(emoji, COLORS)]),
) as Record<Kind, Strip>;

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
