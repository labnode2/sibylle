// The pixel art editor (canvas G-Pixel): « Annuler · MON PIXEL ART · Enregistrer » on top, the
// size, a 16 × 16 or 32 × 32 grid, pencil, eraser, fill and eyedropper with the colour in use,
// the base palette and the member's unlocked colours, undo, and the preview at a whole scale.
// It works with a pointer or the keyboard (arrows to move, Space to draw, Ctrl+Z to undo).
// Avatars, the newsroom's logo and Pixel mystère drawings all use it; `screen` fills a page.
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Segmented } from '../../ui/components';
import { BASE_INDICES, PALETTE } from '../../ui/palette';
import { decodePixels, encodePixels, PixelImage, type PixelImageData } from '../../ui/PixelImage';
import { floodFill, paint, resize, type Size } from './grid';
import styles from './pixel-editor.module.css';

type Tool = 'pencil' | 'eraser' | 'fill' | 'picker';
const TOOLS: Tool[] = ['pencil', 'eraser', 'fill', 'picker'];
// The grid is drawn at 320 px, whatever its size.
const GRID_PX = 320;
// The preview, at the largest whole scale under 64 px: 48 px for 16 × 16, 64 px for 32 × 32.
const previewScale = (size: Size) => Math.floor(64 / size);

/** A drawing as the server stores it. */
export type Drawing = { size: Size; palette: 'base-v1'; pixels: string };

export type PixelEditorProps = {
  initial?: PixelImageData | null;
  sizes?: Size[];
  /** Colours beyond the base palette the member may use. */
  unlocked?: number[];
  title: string;
  saveLabel: string;
  onSave: (image: Drawing) => void;
  onCancel?: () => void;
  busy?: boolean;
  error?: string | null;
  /** `screen`: the editor is the whole page (the avatar); `box`: it sits inside a form. */
  layout?: 'box' | 'screen';
};

function blank(size: Size): Uint8Array {
  return new Uint8Array(size * size);
}

export function PixelEditor({
  initial,
  sizes = [16, 32],
  unlocked = [],
  title,
  saveLabel,
  onSave,
  onCancel,
  busy,
  error,
  layout = 'box',
}: PixelEditorProps) {
  const { t } = useTranslation('pixel');
  const [size, setSize] = useState<Size>(initial?.size ?? sizes[0]!);
  const [pixels, setPixels] = useState(() => (initial ? decodePixels(initial) : blank(size)));
  const [history, setHistory] = useState<Uint8Array[]>([]);
  const [color, setColor] = useState(1);
  const [tool, setTool] = useState<Tool>('pencil');
  const [cursor, setCursor] = useState({ x: 0, y: 0 });
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const colors = [...BASE_INDICES, ...unlocked.filter((i) => !BASE_INDICES.includes(i))];
  const cell = GRID_PX / size;

  useEffect(() => {
    const context = canvas.current?.getContext('2d');
    if (!context) return;
    context.clearRect(0, 0, GRID_PX, GRID_PX);
    pixels.forEach((index, i) => {
      const hex = PALETTE[index];
      if (!hex) return;
      context.fillStyle = hex;
      context.fillRect((i % size) * cell, Math.floor(i / size) * cell, cell, cell);
    });
    context.strokeStyle = 'rgba(128, 128, 160, 0.35)';
    context.lineWidth = 1;
    for (let k = 1; k < size; k += 1) {
      context.beginPath();
      context.moveTo(k * cell + 0.5, 0);
      context.lineTo(k * cell + 0.5, GRID_PX);
      context.moveTo(0, k * cell + 0.5);
      context.lineTo(GRID_PX, k * cell + 0.5);
      context.stroke();
    }
    context.strokeStyle = '#4a50d0';
    context.lineWidth = 2;
    context.strokeRect(cursor.x * cell + 1, cursor.y * cell + 1, cell - 2, cell - 2);
  }, [pixels, size, cell, cursor]);

  const remember = () => setHistory((past) => [...past.slice(-49), pixels]);

  const apply = (x: number, y: number, current: Uint8Array) => {
    if (tool === 'fill') return floodFill(current, size, x, y, color);
    return paint(current, size, x, y, tool === 'eraser' ? 0 : color);
  };

  // The eyedropper takes the colour under it, then hands back the pencil.
  const pick = (x: number, y: number) => {
    const index = pixels[y * size + x] ?? 0;
    if (index) setColor(index);
    setTool('pencil');
  };

  const undo = () => {
    const previous = history.at(-1);
    if (!previous) return;
    setHistory(history.slice(0, -1));
    setSize(Math.sqrt(previous.length) as Size);
    setPixels(previous);
  };

  const cellAt = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    const x = Math.floor(((event.clientX - box.left) / box.width) * size);
    const y = Math.floor(((event.clientY - box.top) / box.height) * size);
    return { x: Math.min(size - 1, Math.max(0, x)), y: Math.min(size - 1, Math.max(0, y)) };
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    const { x, y } = cellAt(event);
    if (tool === 'picker') {
      setCursor({ x, y });
      pick(x, y);
      return;
    }
    remember();
    drawing.current = tool !== 'fill';
    setCursor({ x, y });
    setPixels((current) => apply(x, y, current));
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current) return;
    const { x, y } = cellAt(event);
    setCursor({ x, y });
    setPixels((current) => apply(x, y, current));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLCanvasElement>) => {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const move = moves[event.key];
    if (move) {
      event.preventDefault();
      setCursor(({ x, y }) => ({
        x: Math.min(size - 1, Math.max(0, x + move[0])),
        y: Math.min(size - 1, Math.max(0, y + move[1])),
      }));
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      if (tool === 'picker') {
        pick(cursor.x, cursor.y);
        return;
      }
      remember();
      setPixels((current) => apply(cursor.x, cursor.y, current));
    } else if (event.key === 'z' && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      undo();
    }
  };

  const changeSize = (next: Size) => {
    if (next === size) return;
    remember();
    setPixels((current) => resize(current, size, next));
    setCursor({ x: 0, y: 0 });
    setSize(next);
  };

  const image: Drawing = { size, palette: 'base-v1', pixels: encodePixels(pixels) };
  const colorName = (index: number) =>
    t(`colors.${index}`, { defaultValue: t('color', { index }) });
  const scale = previewScale(size);

  return (
    <section
      className={`${styles.editor} ${layout === 'screen' ? styles.screen : ''}`}
      aria-label={title}
    >
      <header className={styles.bar}>
        {onCancel ? (
          <button type="button" className={styles.cancel} onClick={onCancel} disabled={busy}>
            {t('cancel')}
          </button>
        ) : (
          <span />
        )}
        <h2 className={styles.title}>{title}</h2>
        <Button className={styles.save} onClick={() => onSave(image)} disabled={busy}>
          {saveLabel}
        </Button>
      </header>
      {sizes.length > 1 && (
        <Segmented
          label={t('size')}
          options={sizes.map((value) => ({
            value: String(value),
            label: t('sizeValue', { size: value }),
          }))}
          value={String(size)}
          onChange={(value) => changeSize(Number(value) as Size)}
        />
      )}

      <div className={styles.workspace}>
        <canvas
          ref={canvas}
          width={GRID_PX}
          height={GRID_PX}
          className={styles.grid}
          tabIndex={0}
          role="application"
          aria-label={t('grid', { size })}
          aria-describedby="pixel-editor-help"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={() => (drawing.current = false)}
          onPointerCancel={() => (drawing.current = false)}
          onKeyDown={onKeyDown}
        />
        <div className={styles.side}>
          <div className={styles.toolRow}>
            <Segmented
              label={t('tools')}
              mode="radio"
              options={TOOLS.map((value) => ({ value, label: t(`tool.${value}`) }))}
              value={tool}
              onChange={setTool}
            />
            <span
              className={styles.current}
              role="img"
              aria-label={t('current', { name: colorName(color) })}
              style={{ background: PALETTE[color] ?? 'transparent' }}
            />
          </div>
          <div className={styles.palette} role="radiogroup" aria-label={t('palette')}>
            {colors.map((index) => (
              <button
                key={index}
                type="button"
                role="radio"
                aria-checked={color === index}
                aria-label={colorName(index)}
                className={styles.swatch}
                style={{ background: PALETTE[index] ?? 'transparent' }}
                onClick={() => {
                  setColor(index);
                  if (tool === 'eraser' || tool === 'picker') setTool('pencil');
                }}
              />
            ))}
          </div>
          <div className={styles.previewRow}>
            <div className={styles.preview} aria-label={t('preview')} role="group">
              <PixelImage image={image} size={size * scale} label={t('previewAt', { scale })} />
            </div>
            <div className={styles.previewText}>
              <span className={styles.previewTitle}>{t('previewTitle')}</span>
              <span className={styles.help}>{t('previewHint', { px: size * scale })}</span>
            </div>
            <Button variant="secondary" onClick={undo} disabled={history.length === 0}>
              {t('undo')}
            </Button>
          </div>
        </div>
      </div>
      <p id="pixel-editor-help" className={styles.help}>
        {t('help')}
      </p>
      <p className="visually-hidden" aria-live="polite">
        {t('cursor', { x: cursor.x + 1, y: cursor.y + 1 })}
      </p>
      {error && (
        <p role="alert" className={styles.alert}>
          {error}
        </p>
      )}
    </section>
  );
}
