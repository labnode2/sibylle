// A game won, Wordle or Pixel mystère: a burst of confetti and gold laurels flies up from the
// middle of the screen and falls back, unhurried, in two and a half seconds at most, then leaves
// the page. Only the winning answer plays it: never a wrong one, nor a page that opens on a game
// already won. It stands over the page and under the notes, says nothing to screen readers (the
// page says the win in words) and lets every click through. Without animations (« couper les
// animations », prefers-reduced-motion), nothing shows. The pieces are worked out once, the same
// every time.
import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

import laurelUrl from './assets/laurel.png';
import styles from './celebration.module.css';

const motionReduced = () =>
  document.documentElement.classList.contains('reduce-motion') ||
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

/** Numbers from 0 to 1 that look random but come in the same order every time (the « minimal
 *  standard » generator of Park and Miller). */
function series(seed: number): () => number {
  let state = seed;
  return () => {
    state = (state * 16807) % 2147483647;
    return state / 2147483647;
  };
}

const next = series(2026);
const between = (low: number, high: number) => low + next() * (high - low);

const COUNT = 36;
/** How long a piece flies, in ms: a few lengths only, so that the browser has few starts and
 *  ends to follow. All set off together. The longer the flight, the slower the piece goes over
 *  the same way. */
const FLIGHTS = [2000, 2250, 2500] as const;
/** The scraps' sizes in px, width × height: squares and strips. */
const SCRAPS = [
  [9, 9],
  [7, 14],
  [14, 7],
  [11, 11],
  [6, 12],
] as const;

type Piece = { laurel: boolean; duration: number; style: CSSProperties };

/** The pieces, a gold laurel every sixth, spread from left to right, each going its own way. */
const PIECES: Piece[] = Array.from({ length: COUNT }, (_, n) => {
  // From the far left (-1) to the far right (1), evenly, each a little off its place.
  const side = Math.min(1, Math.max(-1, ((n + 0.5) / COUNT) * 2 - 1 + between(-0.08, 0.08)));
  const laurel = n % 6 === 3;
  const [width, height] = SCRAPS[n % SCRAPS.length]!;
  const duration = FLIGHTS[Math.floor(next() * FLIGHTS.length)]!;
  // A laurel rocks from one side to the other; a scrap spins, one way or the other.
  const from = laurel ? between(-20, 20) : between(0, 360);
  const to = laurel ? -from : from + (n % 2 ? 1 : -1) * between(300, 720);
  return {
    laurel,
    duration,
    style: {
      '--x': (side * 48).toFixed(1),
      // The farther out, the lower the flight.
      '--rise': (between(24, 44) * (1 - 0.3 * Math.abs(side))).toFixed(1),
      '--fall': between(55, 75).toFixed(1),
      '--turn-from': `${from.toFixed(0)}deg`,
      '--turn-to': `${to.toFixed(0)}deg`,
      '--duration': `${duration}ms`,
      '--color': `var(--confetti-${(n % 4) + 1})`,
      '--width': `${width}px`,
      '--height': `${height}px`,
    } as CSSProperties,
  };
});

/** How long the burst lasts, to the end of its last piece, in ms. */
export const CELEBRATION_MS = Math.max(...PIECES.map((piece) => piece.duration));

/** The burst, played once as it mounts, then gone from the page. */
export function Celebration() {
  // Without animations, no pieces at all: they would only stand there unseen (see the CSS).
  const [shown, setShown] = useState(() => !motionReduced());

  // A timer, not the pieces' animations, takes it away: without animations, they never end.
  useEffect(() => {
    const timer = window.setTimeout(() => setShown(false), CELEBRATION_MS);
    return () => window.clearTimeout(timer);
  }, []);

  if (!shown) return null;
  return createPortal(
    <div className={styles.celebration} aria-hidden="true">
      {PIECES.map(({ laurel, style }, index) => (
        <span key={index} className={styles.piece} style={style}>
          {laurel ? (
            <img className={`${styles.bit} ${styles.laurel}`} src={laurelUrl} alt="" />
          ) : (
            <span className={`${styles.bit} ${styles.scrap}`} />
          )}
        </span>
      ))}
    </div>,
    document.body,
  );
}

/** A burst for each win: `celebrate()` from the winning answer, and `celebration` to put anywhere
 *  in the page (it shows over everything), nothing until the first win. */
export function useCelebration(): [celebration: ReactNode, celebrate: () => void] {
  const [wins, setWins] = useState(0);
  // A new key at each win: its own burst, from the start.
  const celebrate = useCallback(() => setWins((count) => count + 1), []);
  return [wins > 0 ? <Celebration key={wins} /> : null, celebrate];
}
