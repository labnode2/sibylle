// The pixel art editor (canvas G-Pixel): « Annuler · MON PIXEL ART · Enregistrer » on top, the
// size, a 16 × 16 or 32 × 32 grid, pencil, eraser, fill and eyedropper with the colour in use,
// the mirror that draws both halves of a face at once, the grid lines, undo, redo and clear, the
// base palette and the member's unlocked colours, and the preview at a whole scale. Strokes have
// no gap however fast the pointer goes; a right click (or Alt + click) takes a pixel's colour.
// It works with the keyboard too: arrows to move, Space to draw, letters for the tools.
// Avatars, the newsroom's logo and Pixel mystère drawings all use it; `screen` fills a page.
// Without `onSave` it has no bar: the page around it saves, and `onChange` follows the drawing.
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
import { fill, resize, stroke, type Cell, type Size } from './grid';
import { EDITOR_ICONS, type EditorIcon } from './icons';
import styles from './pixel-editor.module.css';

type Tool = 'pencil' | 'eraser' | 'fill' | 'picker';
const TOOLS: Tool[] = ['pencil', 'eraser', 'fill', 'picker'];
// Letters that pick a tool from the grid (C, G, R, P: their French names).
const TOOL_KEYS: Record<string, Tool> = { c: 'pencil', g: 'eraser', r: 'fill', p: 'picker' };
// The canvas is drawn at 640 px and shown smaller, so that its lines stay crisp.
const GRID_PX = 640;
const HISTORY = 50;
// The preview, at the largest whole scale under 64 px: 48 px for 16 × 16, 64 px for 32 × 32.
const previewScale = (size: Size) => Math.floor(64 / size);

/** A drawing as the server stores it. */
export type Drawing = { size: Size; palette: 'base-v1'; pixels: string };

export type PixelEditorProps = {
  initial?: PixelImageData | null;
  sizes?: Size[];
  /** The colours given for free: the whole base palette, or an avatar's free colours. */
  base?: readonly number[];
  /** Colours beyond `base` the member may use. */
  unlocked?: number[];
  title: string;
  saveLabel?: string;
  onSave?: (image: Drawing) => void;
  /** Each change of the drawing, for a page that shows it as it goes. */
  onChange?: (image: Drawing) => void;
  onCancel?: () => void;
  /** The save button waits until the drawing differs from `initial`. */
  requireChange?: boolean;
  busy?: boolean;
  error?: string | null;
  /** `screen`: the editor is the whole page (the avatar); `box`: it sits inside a form. */
  layout?: 'box' | 'screen';
};

function blank(size: Size): Uint8Array {
  return new Uint8Array(size * size);
}

/** A 12 × 12 pixel icon in the text colour. */
function Glyph({ name }: { name: EditorIcon }) {
  return (
    <svg width={24} height={24} viewBox="0 0 12 12" shapeRendering="crispEdges" aria-hidden="true">
      <path fill="currentColor" d={EDITOR_ICONS[name]} />
    </svg>
  );
}

export function PixelEditor({
  initial,
  sizes = [16, 32],
  base = BASE_INDICES,
  unlocked = [],
  title,
  saveLabel = '',
  onSave,
  onChange,
  onCancel,
  requireChange = false,
  busy,
  error,
  layout = 'box',
}: PixelEditorProps) {
  const { t } = useTranslation('pixel');
  const [size, setSize] = useState<Size>(initial?.size ?? sizes[0]!);
  const [pixels, setPixels] = useState(() => (initial ? decodePixels(initial) : blank(size)));
  // The drawing it started from, encoded as the editor encodes, to tell whether it changed.
  const [start] = useState(() => ({ size, pixels: encodePixels(pixels) }));
  // Drawings before (undo) and after (redo) the one on screen.
  const [past, setPast] = useState<Uint8Array[]>([]);
  const [future, setFuture] = useState<Uint8Array[]>([]);
  const [color, setColor] = useState(1);
  const [tool, setTool] = useState<Tool>('pencil');
  const [mirror, setMirror] = useState(false);
  const [lines, setLines] = useState(true);
  const [cursor, setCursor] = useState({ x: 0, y: 0 });
  // The cell a screen reader hears of: the keyboard's moves only, not the mouse's hovering.
  const [spoken, setSpoken] = useState({ x: 0, y: 0 });
  const canvas = useRef<HTMLCanvasElement>(null);
  // The last cell of the stroke under way, to join it to the next one.
  const last = useRef<Cell | null>(null);
  const colors = [...base, ...unlocked.filter((i) => !base.includes(i))];
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
    if (lines) {
      context.strokeStyle = 'rgba(128, 128, 160, 0.35)';
      context.lineWidth = 2;
      for (let k = 1; k < size; k += 1) {
        context.beginPath();
        context.moveTo(k * cell, 0);
        context.lineTo(k * cell, GRID_PX);
        context.moveTo(0, k * cell);
        context.lineTo(GRID_PX, k * cell);
        context.stroke();
      }
    }
    if (mirror) {
      context.save();
      context.strokeStyle = '#4a50d0';
      context.lineWidth = 3;
      context.setLineDash([12, 8]);
      context.beginPath();
      context.moveTo(GRID_PX / 2, 0);
      context.lineTo(GRID_PX / 2, GRID_PX);
      context.stroke();
      context.restore();
    }
    context.strokeStyle = '#4a50d0';
    context.lineWidth = 4;
    context.strokeRect(cursor.x * cell + 2, cursor.y * cell + 2, cell - 4, cell - 4);
  }, [pixels, size, cell, cursor, lines, mirror]);

  useEffect(() => {
    onChange?.({ size, palette: 'base-v1', pixels: encodePixels(pixels) });
  }, [onChange, pixels, size]);

  /** Keeps the drawing on screen for undo, before it changes. */
  const remember = () => {
    setPast((before) => [...before.slice(1 - HISTORY), pixels]);
    setFuture([]);
  };

  const restore = (drawing: Uint8Array) => {
    setSize(Math.sqrt(drawing.length) as Size);
    setPixels(drawing);
  };

  const undo = () => {
    const previous = past.at(-1);
    if (!previous) return;
    setPast(past.slice(0, -1));
    setFuture([pixels, ...future]);
    restore(previous);
  };

  const redo = () => {
    const next = future[0];
    if (!next) return;
    setFuture(future.slice(1));
    setPast([...past, pixels]);
    restore(next);
  };

  const clear = () => {
    if (pixels.every((index) => index === 0)) return;
    remember();
    setPixels(blank(size));
  };

  /** Takes the colour of a pixel; a transparent one is no colour to take. */
  const take = (x: number, y: number) => {
    const index = pixels[y * size + x] ?? 0;
    if (index) setColor(index);
  };

  // The eyedropper takes the colour under it, then hands back the pencil.
  const pick = (x: number, y: number) => {
    take(x, y);
    setTool('pencil');
  };

  /** A press on (x, y): the start of a stroke, a fill, or a colour taken. */
  const press = (x: number, y: number) => {
    if (tool === 'picker') {
      pick(x, y);
      return;
    }
    remember();
    if (tool === 'fill') {
      setPixels((current) => fill(current, size, x, y, color, mirror));
      return;
    }
    const ink = tool === 'eraser' ? 0 : color;
    setPixels((current) => stroke(current, size, [x, y], [x, y], ink, mirror));
  };

  const cellAt = (event: ReactPointerEvent<HTMLCanvasElement>): Cell => {
    const box = event.currentTarget.getBoundingClientRect();
    const x = Math.floor(((event.clientX - box.left) / box.width) * size);
    const y = Math.floor(((event.clientY - box.top) / box.height) * size);
    return [Math.min(size - 1, Math.max(0, x)), Math.min(size - 1, Math.max(0, y))];
  };

  const onPointerDown = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const [x, y] = cellAt(event);
    setCursor({ x, y });
    // A right click or Alt + click takes the colour, whatever the tool.
    if (event.button === 2 || event.altKey) {
      take(x, y);
      if (tool === 'eraser' || tool === 'picker') setTool('pencil');
      return;
    }
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    press(x, y);
    last.current = tool === 'pencil' || tool === 'eraser' ? [x, y] : null;
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLCanvasElement>) => {
    const [x, y] = cellAt(event);
    setCursor((current) => (current.x === x && current.y === y ? current : { x, y }));
    const from = last.current;
    if (!from || (from[0] === x && from[1] === y)) return;
    const ink = tool === 'eraser' ? 0 : color;
    setPixels((current) => stroke(current, size, from, [x, y], ink, mirror));
    last.current = [x, y];
  };

  const endStroke = () => {
    last.current = null;
  };

  const onKeyDown = (event: KeyboardEvent<HTMLCanvasElement>) => {
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    const move = moves[event.key];
    const command = event.ctrlKey || event.metaKey;
    const key = event.key.toLowerCase();
    if (move) {
      event.preventDefault();
      const next = {
        x: Math.min(size - 1, Math.max(0, cursor.x + move[0])),
        y: Math.min(size - 1, Math.max(0, cursor.y + move[1])),
      };
      setCursor(next);
      setSpoken(next);
    } else if (event.key === ' ' || event.key === 'Enter') {
      event.preventDefault();
      press(cursor.x, cursor.y);
    } else if (command && (key === 'y' || (key === 'z' && event.shiftKey))) {
      event.preventDefault();
      redo();
    } else if (command && key === 'z') {
      event.preventDefault();
      undo();
    } else if (!command && !event.altKey && TOOL_KEYS[key]) {
      setTool(TOOL_KEYS[key]);
    } else if (!command && !event.altKey && key === 'm') {
      setMirror((on) => !on);
    }
  };

  const changeSize = (next: Size) => {
    if (next === size) return;
    remember();
    setPixels((current) => resize(current, size, next));
    setCursor({ x: 0, y: 0 });
    setSpoken({ x: 0, y: 0 });
    setSize(next);
  };

  const image: Drawing = { size, palette: 'base-v1', pixels: encodePixels(pixels) };
  const colorName = (index: number) =>
    t(`colors.${index}`, { defaultValue: t('color', { index }) });
  const scale = previewScale(size);
  const empty = pixels.every((index) => index === 0);
  const changed = image.size !== start.size || image.pixels !== start.pixels;

  return (
    <section
      className={`${styles.editor} ${layout === 'screen' ? styles.screen : ''}`}
      aria-label={title}
    >
      {onSave && (
        <header className={styles.bar}>
          {onCancel ? (
            <button type="button" className={styles.cancel} onClick={onCancel} disabled={busy}>
              {t('cancel')}
            </button>
          ) : (
            <span />
          )}
          <h2 className={styles.title}>{title}</h2>
          <Button
            className={styles.save}
            onClick={() => onSave(image)}
            disabled={busy || (requireChange && !changed)}
          >
            {saveLabel}
          </Button>
        </header>
      )}
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
          onPointerUp={endStroke}
          onPointerCancel={endStroke}
          onLostPointerCapture={endStroke}
          onContextMenu={(event) => event.preventDefault()}
          onKeyDown={onKeyDown}
        />
        <div className={styles.side}>
          <div className={styles.toolRow}>
            <div className={styles.tools} role="radiogroup" aria-label={t('tools')}>
              {TOOLS.map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={tool === value}
                  className={styles.tool}
                  title={t(`toolHint.${value}`)}
                  onClick={() => setTool(value)}
                >
                  <Glyph name={value} />
                  <span>{t(`tool.${value}`)}</span>
                </button>
              ))}
            </div>
            <span
              className={styles.current}
              role="img"
              aria-label={t('current', { name: colorName(color) })}
              style={{ background: PALETTE[color] ?? 'transparent' }}
            />
          </div>
          <div className={styles.actions} role="group" aria-label={t('actions')}>
            <button
              type="button"
              className={styles.tool}
              aria-pressed={mirror}
              title={t('mirrorHint')}
              onClick={() => setMirror((on) => !on)}
            >
              <Glyph name="mirror" />
              <span>{t('mirror')}</span>
            </button>
            <button
              type="button"
              className={styles.tool}
              aria-pressed={lines}
              onClick={() => setLines((on) => !on)}
            >
              <Glyph name="lines" />
              <span>{t('lines')}</span>
            </button>
            <button
              type="button"
              className={styles.tool}
              disabled={past.length === 0}
              onClick={undo}
            >
              <Glyph name="undo" />
              <span>{t('undo')}</span>
            </button>
            <button
              type="button"
              className={styles.tool}
              disabled={future.length === 0}
              onClick={redo}
            >
              <Glyph name="redo" />
              <span>{t('redo')}</span>
            </button>
            <button type="button" className={styles.tool} disabled={empty} onClick={clear}>
              <Glyph name="clear" />
              <span>{t('clear')}</span>
            </button>
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
          </div>
        </div>
      </div>
      <p id="pixel-editor-help" className={styles.help}>
        {t('help')}
      </p>
      <p className="visually-hidden" aria-live="polite">
        {t('cursor', { x: spoken.x + 1, y: spoken.y + 1 })}
      </p>
      {error && (
        <p role="alert" className={styles.alert}>
          {error}
        </p>
      )}
    </section>
  );
}
