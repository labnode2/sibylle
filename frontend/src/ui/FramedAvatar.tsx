// An avatar in the frame its member chose in the collection (`frame-ink`, `frame-indigo`,
// `frame-double`, `frame-dotted`), or none.
import { PixelImage, type PixelImageData } from './PixelImage';
import styles from './framed.module.css';

const FRAMES: Record<string, string | undefined> = {
  'frame-ink': styles.ink,
  'frame-indigo': styles.indigo,
  'frame-double': styles.double,
  'frame-dotted': styles.dotted,
};

export function FramedAvatar({
  image,
  frame,
  size,
  label,
}: {
  image: PixelImageData;
  frame?: string | null;
  size: number;
  label?: string;
}) {
  const style = frame ? FRAMES[frame] : undefined;
  if (!style) return <PixelImage image={image} size={size} label={label} />;
  return (
    <span className={`${styles.frame} ${style}`}>
      <PixelImage image={image} size={size} label={label} />
    </span>
  );
}
