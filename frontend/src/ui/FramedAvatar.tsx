// An avatar in the frame its member chose in the collection (`frame-ink`, `frame-indigo`,
// `frame-double`, `frame-dotted`, `frame-vine`, `frame-flowers`, `frame-gold`), or none, and
// with the animation they chose around it (`animation-sun`, `animation-shine`,
// `animation-sparkles`, `animation-flowers`), or none. Without animations (.reduce-motion,
// prefers-reduced-motion), the animation stands still.
import type { CSSProperties } from 'react';

import { PixelImage, type PixelImageData } from './PixelImage';
import styles from './framed.module.css';

const FRAMES: Record<string, string | undefined> = {
  'frame-ink': styles.ink,
  'frame-indigo': styles.indigo,
  'frame-double': styles.double,
  'frame-dotted': styles.dotted,
  'frame-vine': styles.vine,
  'frame-flowers': styles.floral,
  'frame-gold': styles.gold,
};

const ANIMATIONS: Record<string, string | undefined> = {
  'animation-sun': styles.sun,
  'animation-shine': styles.shine,
  'animation-sparkles': styles.sparkles,
  'animation-flowers': styles.blossom,
};

/** The things drawn around the avatar by some animations, four each, each moving in turn: the
 *  sparks of `animation-sparkles`, the flowers of `animation-flowers`. */
const PARTICLES: Record<string, string | undefined> = {
  'animation-sparkles': styles.spark,
  'animation-flowers': styles.bloom,
};
const PARTICLE_COUNT = 4;

export function FramedAvatar({
  image,
  frame,
  animation,
  size,
  label,
}: {
  image: PixelImageData;
  frame?: string | null;
  animation?: string | null;
  size: number;
  label?: string;
}) {
  const frameStyle = frame ? FRAMES[frame] : undefined;
  const animationStyle = animation ? ANIMATIONS[animation] : undefined;
  const pixels = <PixelImage image={image} size={size} label={label} />;
  // The drawn frames' pixels: 1 px around small avatars, 2 px around the press card's.
  const scale = { '--frame-px': size >= 96 ? '2px' : '1px' } as CSSProperties;
  const framed = frameStyle ? (
    <span className={`${styles.frame} ${frameStyle}`} style={scale}>
      {pixels}
    </span>
  ) : (
    pixels
  );
  const particle = animation ? PARTICLES[animation] : undefined;
  if (!animationStyle) return framed;
  return (
    <span className={`${styles.animated} ${animationStyle}`}>
      {framed}
      {particle &&
        Array.from({ length: PARTICLE_COUNT }, (_, index) => (
          <span key={index} className={particle} data-n={index} aria-hidden="true" />
        ))}
    </span>
  );
}
