// A pixel image (avatar, newsroom logo, Pixel mystère drawing) drawn on a canvas at a whole
// multiple of its grid. Format shared with the server: { size, palette, pixels: base64 indices }.
import { useEffect, useRef } from 'react';

import { PALETTE } from './palette';
import styles from './ui.module.css';

export type PixelImageData = { size: 16 | 32; palette: string; pixels: string };

export function decodePixels(data: PixelImageData): Uint8Array {
  const raw = atob(data.pixels);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

export function encodePixels(indices: Uint8Array): string {
  let raw = '';
  for (const index of indices) raw += String.fromCharCode(index);
  return btoa(raw);
}

export function PixelImage({
  image,
  size,
  label,
  avatar = true,
  hidden,
}: {
  image: PixelImageData;
  /** CSS size in px; keep it a whole multiple of the grid (16 or 32). */
  size: number;
  label?: string;
  avatar?: boolean;
  hidden?: Uint8Array;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    const pixels = decodePixels(image);
    const frame = context.createImageData(image.size, image.size);
    pixels.forEach((index, i) => {
      const color = hidden?.[i] ? null : PALETTE[index];
      if (!color) return;
      frame.data[i * 4] = parseInt(color.slice(1, 3), 16);
      frame.data[i * 4 + 1] = parseInt(color.slice(3, 5), 16);
      frame.data[i * 4 + 2] = parseInt(color.slice(5, 7), 16);
      frame.data[i * 4 + 3] = 255;
    });
    context.putImageData(frame, 0, 0);
  }, [image, hidden]);

  return (
    <canvas
      ref={canvas}
      width={image.size}
      height={image.size}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`pixelated ${avatar ? styles.avatar : ''}`}
      style={{ width: size, height: size, display: 'block', flex: 'none' }}
    />
  );
}

export function AvatarStack({
  avatars,
  more = 0,
  size = 24,
}: {
  avatars: PixelImageData[];
  more?: number;
  size?: number;
}) {
  return (
    <span className={styles.avatarStack}>
      {avatars.map((avatar, i) => (
        <PixelImage key={i} image={avatar} size={size} />
      ))}
      {more > 0 && <span className={styles.avatarMore}>+{more}</span>}
    </span>
  );
}
