// The kit's React component (crystal-ball-kit/examples/react/CrystalBall.tsx), wired to the
// vendored module and to the app's own "couper les animations" setting.
import { useEffect, useRef } from 'react';
import {
  animate,
  variantFor,
  type Player,
  type Variant,
} from '../vendor/crystal-ball/crystal-ball.js';

type Props = {
  /** A variant; by default today's season or holiday. */
  variant?: Variant;
  /** CSS size in px: keep it a multiple of 16 so the pixels stay crisp. */
  size?: number;
  /** Loops played on mount and on hover. */
  loops?: number;
  /** Accessible name; without it the ball is decorative. */
  label?: string;
};

const motionReduced = () => document.documentElement.classList.contains('reduce-motion');

export function CrystalBall({ variant, size = 16, loops = 2, label }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const player = useRef<Player | null>(null);
  const id = variant ?? variantFor(new Date());

  useEffect(() => {
    if (!canvas.current) return;
    player.current = animate(canvas.current, id, { loops: motionReduced() ? 0 : loops });
    return () => player.current?.destroy();
  }, [id, loops]);

  return (
    <canvas
      ref={canvas}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      width={16}
      height={16}
      style={{ width: size, height: size, imageRendering: 'pixelated' }}
      onMouseEnter={() => {
        if (!motionReduced()) player.current?.play();
      }}
    />
  );
}
