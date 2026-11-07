// An avatar in the frame its member chose in the collection (`frame-ink`, `frame-indigo`,
// `frame-double`, `frame-dotted`, `frame-gold`), or none, and with the animation they chose
// around it (`animation-sun`, `animation-shine`, `animation-sparkles`), or none. Without
// animations (.reduce-motion, prefers-reduced-motion), the animation stands still.
import { PixelImage, type PixelImageData } from './PixelImage';
import styles from './framed.module.css';

const FRAMES: Record<string, string | undefined> = {
  'frame-ink': styles.ink,
  'frame-indigo': styles.indigo,
  'frame-double': styles.double,
  'frame-dotted': styles.dotted,
  'frame-gold': styles.gold,
};

const ANIMATIONS: Record<string, string | undefined> = {
  'animation-sun': styles.sun,
  'animation-shine': styles.shine,
  'animation-sparkles': styles.sparkles,
};

/** The four sparks of `animation-sparkles`, around the avatar, each twinkling in turn. */
const SPARKS = 4;

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
  const framed = frameStyle ? (
    <span className={`${styles.frame} ${frameStyle}`}>{pixels}</span>
  ) : (
    pixels
  );
  if (!animationStyle) return framed;
  return (
    <span className={`${styles.animated} ${animationStyle}`}>
      {framed}
      {animation === 'animation-sparkles' &&
        Array.from({ length: SPARKS }, (_, index) => (
          <span key={index} className={styles.spark} data-spark={index} aria-hidden="true" />
        ))}
    </span>
  );
}
