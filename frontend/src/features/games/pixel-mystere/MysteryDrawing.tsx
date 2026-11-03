// A Pixel mystère drawing as far as it shows: the pixels not shown yet (255) as a grey checker,
// so that they stand apart from the drawing's own transparent background.
import { useEffect, useRef } from 'react';

import { PALETTE } from '../../../ui/palette';
import styles from '../games.module.css';

export const HIDDEN = 255;

function rgb(color: string): number[] {
  return [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16));
}

export function MysteryDrawing({
  size,
  revealed,
  label,
}: {
  size: 16 | 32;
  /** Base64, one byte per pixel: a palette index, or 255 for a pixel not shown yet. */
  revealed: string;
  label: string;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (!element || !context) return;
    const css = getComputedStyle(element);
    const token = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
    const background = rgb(token('--surface', '#ffffff'));
    const hidden = [rgb(token('--grey', '#e3e4eb')), rgb(token('--rule', '#c9cbe4'))];
    const raw = atob(revealed);
    const frame = context.createImageData(size, size);
    for (let i = 0; i < raw.length; i += 1) {
      const index = raw.charCodeAt(i);
      const color = PALETTE[index];
      const shade =
        index === HIDDEN
          ? hidden[((i % size) + Math.floor(i / size)) % 2]!
          : color
            ? rgb(color)
            : background;
      frame.data.set([...shade, 255], i * 4);
    }
    context.putImageData(frame, 0, 0);
  }, [size, revealed]);

  return (
    <canvas
      ref={canvas}
      width={size}
      height={size}
      className={styles.mystery}
      role="img"
      aria-label={label}
    />
  );
}
