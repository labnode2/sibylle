// The chain of wins (US13, research.md J8): a flame of 8 × 10 pixels in three frames that CSS
// shows in turn, so that « couper les animations » leaves the first one standing still; and
// the chain itself, the flame and its number, from two wins in a row.
import { useTranslation } from 'react-i18next';

import styles from './flame.module.css';

/** A single win is not a chain yet (backend `SHOWN_FROM`). */
export const STREAK_SHOWN_FROM = 2;

const COLORS = { R: '#e8452c', O: '#ff9f1c', Y: '#ffd23f', W: '#fff3b0' } as const;
type Color = keyof typeof COLORS;

// The tongue leans right, then left, then stands up with a spark; the heart stays.
const FRAMES = [
  [
    '....R...',
    '....RR..',
    '...RRR..',
    '..RRORR.',
    '.RROOR..',
    '.ROOYOR.',
    'RROYYOR.',
    'ROYYWYOR',
    'ROYWWYOR',
    '.RROORR.',
  ],
  [
    '...R....',
    '..RR....',
    '..RRR...',
    '.RRORR..',
    '..ROORR.',
    '.ROYOOR.',
    '.ROYYORR',
    'ROYWYYOR',
    'ROYWWYOR',
    '.RROORR.',
  ],
  [
    '......R.',
    '...RR...',
    '...RRR..',
    '..RROR..',
    '.RROORR.',
    '.ROOYOR.',
    'RROYYORR',
    'ROYYWYOR',
    'ROYWWYOR',
    '.RROORR.',
  ],
];

type Run = { x: number; y: number; width: number; color: Color };

/** Each row as runs of one colour, to keep the drawing small. */
function runs(frame: string[]): Run[] {
  const found: Run[] = [];
  frame.forEach((row, y) => {
    let x = 0;
    while (x < row.length) {
      const color = row[x] as Color | '.';
      let width = 1;
      while (row[x + width] === color) width += 1;
      if (color !== '.') found.push({ x, y, width, color });
      x += width;
    }
  });
  return found;
}

const DRAWN = FRAMES.map(runs);

/** The flame alone, `size` pixels wide; it says nothing to screen readers. */
export function Flame({ size = 16 }: { size?: number }) {
  return (
    <svg
      className={styles.flame}
      width={size}
      height={(size * 10) / 8}
      viewBox="0 0 8 10"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {DRAWN.map((frame, index) => (
        <g key={index} className={styles.frame}>
          {frame.map((run) => (
            <rect
              key={`${run.x}-${run.y}`}
              x={run.x}
              y={run.y}
              width={run.width}
              height={1}
              fill={COLORS[run.color]}
            />
          ))}
        </g>
      ))}
    </svg>
  );
}

/** « 🔥 3 »: the member's chain of wins, from two in a row; nothing below. */
export function Streak({
  value,
  size = 12,
  className,
}: {
  value: number;
  size?: number;
  className?: string;
}) {
  const { t } = useTranslation();
  if (value < STREAK_SHOWN_FROM) return null;
  const label = t('streak', { count: value });
  return (
    <span className={className ? `${styles.streak} ${className}` : styles.streak} title={label}>
      <Flame size={size} />
      <span aria-hidden="true">{value}</span>
      <span className="visually-hidden">{label}</span>
    </span>
  );
}
