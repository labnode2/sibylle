// A React component for the kit: copy it next to src/crystal-ball.js (and its .d.ts) in your
// project, and fix the import path.
import { useEffect, useRef } from 'react';
import { animate, variantFor, type Player, type Variant } from '../../src/crystal-ball.js';

type Props = {
  /** A variant; by default today's season or holiday. */
  variant?: Variant;
  /** CSS size in px: keep it a multiple of 16 so the pixels stay crisp. */
  size?: number;
  /** Loops played on mount and on hover. */
  loops?: number;
};

export function CrystalBall({ variant, size = 16, loops = 2 }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const player = useRef<Player | null>(null);
  const id = variant ?? variantFor(new Date());

  useEffect(() => {
    if (!canvas.current) return;
    player.current = animate(canvas.current, id, { loops });
    return () => player.current?.destroy();
  }, [id, loops]);

  return (
    <canvas
      ref={canvas}
      aria-hidden="true"
      width={16}
      height={16}
      style={{ width: size, height: size, imageRendering: 'pixelated' }}
      onMouseEnter={() => player.current?.play()}
    />
  );
}

// In a sidebar brand, for example:
//   <a href="/" className="brand"><CrystalBall /> my-app</a>
// As a loading indicator, playing until the data arrives:
//   <CrystalBall size={64} loops={Infinity} />
// The browser tab keeps the still ball: assets/favicon/favicon.svg.
