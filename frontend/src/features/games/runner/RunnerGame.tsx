// The ball's race on a canvas, 60 steps a second: the kit's ball jumps (space, up arrow, or a
// touch), obstacles come from the server's seed, faster and faster. The server opens the run and
// checks its score. With « couper les animations », the ball and the ground stay still: only the
// obstacles move, which the game needs.
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { formatNumber } from '../../../i18n';
import { Button } from '../../../ui/components';
import {
  frame,
  frameCount,
  FRAME_MS,
  paint,
  SIZE,
  variantFor,
} from '../../../vendor/crystal-ball/crystal-ball.js';
import { useFinishRun, useStartRun } from '../api';
import styles from '../games.module.css';
import {
  BALL_SIZE,
  BALL_X,
  GROUND,
  HEIGHT,
  newRun,
  scoreOf,
  step,
  STEP,
  WIDTH,
  type RunState,
} from './engine';

type Phase = 'idle' | 'playing' | 'sending' | 'over';
type Result = { score: number; my_best: number; rank: number | null };

// A press just before landing still jumps: it waits up to 6 steps (0.1 s).
const JUMP_BUFFER = 6;

const motionReduced = () => document.documentElement.classList.contains('reduce-motion');

/** The kit's ball, one small canvas per frame, drawn scaled up without smoothing. */
function ballFrames(): HTMLCanvasElement[] {
  const variant = variantFor(new Date());
  const count = motionReduced() ? 1 : frameCount(variant);
  return Array.from({ length: count }, (_, f) => {
    const sprite = document.createElement('canvas');
    sprite.width = SIZE;
    sprite.height = SIZE;
    const context = sprite.getContext('2d');
    if (context) paint(context, frame(variant, f));
    return sprite;
  });
}

type Look = {
  frames: HTMLCanvasElement[];
  still: boolean;
  ink: string;
  surface: string;
  muted: string;
  font: string;
};

/** The theme's colours and the ball, read once per run rather than on every frame. */
function look(element: HTMLCanvasElement): Look {
  const css = getComputedStyle(element);
  const token = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return {
    frames: ballFrames(),
    still: motionReduced(),
    ink: token('--ink', '#15162d'),
    surface: token('--surface', '#ffffff'),
    muted: token('--ink-2', '#4a4d6a'),
    font: `600 14px ${token('--font-mono', 'monospace')}`,
  };
}

function draw(context: CanvasRenderingContext2D, state: RunState, scene: Look) {
  const { frames, still, ink, surface, muted } = scene;
  context.fillStyle = surface;
  context.fillRect(0, 0, WIDTH, HEIGHT);

  // The ground, and its dashes running by (still when animations are cut).
  context.fillStyle = ink;
  context.fillRect(0, GROUND, WIDTH, 2);
  context.fillStyle = muted;
  const offset = still ? 0 : state.distance % 40;
  for (let x = -offset; x < WIDTH; x += 40) context.fillRect(x, GROUND + 8, 12, 2);

  // The obstacles: stacks of ink, with a lighter band.
  for (const o of state.obstacles) {
    context.fillStyle = ink;
    context.fillRect(Math.round(o.x), GROUND - o.height, o.width, o.height);
    context.fillStyle = surface;
    context.fillRect(Math.round(o.x) + 4, GROUND - o.height + 6, o.width - 8, 2);
  }

  const sprite = still
    ? frames[0]
    : frames[Math.floor((state.time * 1000) / FRAME_MS) % frames.length];
  if (sprite) {
    context.imageSmoothingEnabled = false;
    context.drawImage(sprite, BALL_X, GROUND - state.y - BALL_SIZE, BALL_SIZE, BALL_SIZE);
  }

  context.fillStyle = ink;
  context.font = scene.font;
  context.textAlign = 'right';
  context.fillText(String(scoreOf(state)).padStart(5, '0'), WIDTH - 12, 24);
}

export function RunnerGame({ orgId, attemptsLeft }: { orgId: string; attemptsLeft: number }) {
  const { t } = useTranslation('games');
  const canvas = useRef<HTMLCanvasElement>(null);
  const jump = useRef<() => void>(() => undefined);
  const start = useStartRun(orgId);
  const finish = useFinishRun(orgId);
  const [phase, setPhase] = useState<Phase>('idle');
  const [run, setRun] = useState<{ id: string; seed: number } | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [score, setScore] = useState(0);

  // Sharp on any screen: the canvas has as many pixels as the screen shows.
  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (!element || !context) return;
    const ratio = window.devicePixelRatio || 1;
    element.width = WIDTH * ratio;
    element.height = HEIGHT * ratio;
    context.scale(ratio, ratio);
    draw(context, newRun(0), { ...look(element), still: true });
  }, []);

  useEffect(() => {
    const element = canvas.current;
    const context = element?.getContext('2d');
    if (phase !== 'playing' || !run || !element || !context) return;
    const looks = look(element);
    let state = newRun(run.seed);
    let buffer = 0;
    let last = performance.now();
    let pending = 0;
    let handle = 0;

    jump.current = () => {
      buffer = JUMP_BUFFER;
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.code === 'Space' || event.code === 'ArrowUp') {
        event.preventDefault();
        jump.current();
      }
    };
    window.addEventListener('keydown', onKey);

    const tick = (now: number) => {
      // A hidden tab stops the frames; the game waits instead of jumping ahead.
      pending += Math.min(0.1, (now - last) / 1000);
      last = now;
      while (pending >= STEP && !state.over) {
        pending -= STEP;
        const grounded = state.y === 0;
        state = step(state, buffer > 0);
        buffer = buffer > 0 && grounded ? 0 : Math.max(0, buffer - 1);
      }
      draw(context, state, looks);
      if (!state.over) {
        handle = requestAnimationFrame(tick);
        return;
      }
      const final = scoreOf(state);
      setScore(final);
      setPhase('sending');
      finish.mutate(
        { runId: run.id, score: final, durationMs: Math.round(state.time * 1000) },
        {
          onSuccess: (answer) => setResult(answer),
          onSettled: () => setPhase('over'),
        },
      );
    };
    handle = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(handle);
      window.removeEventListener('keydown', onKey);
      jump.current = () => undefined;
    };
    // `finish` changes identity on each render; the run's loop must not restart for that.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, run]);

  const play = () => {
    setResult(null);
    finish.reset();
    start.mutate(undefined, {
      onSuccess: (opened) => {
        setRun({ id: opened.run_id, seed: opened.seed });
        setPhase('playing');
      },
    });
  };

  const canStart = (phase === 'idle' || phase === 'over') && attemptsLeft > 0;
  return (
    <div className={styles.game}>
      <div
        className={styles.track}
        onPointerDown={(event) => {
          if (phase !== 'playing') return;
          event.preventDefault();
          jump.current();
        }}
      >
        <canvas ref={canvas} className={styles.canvas} role="img" aria-label={t('runner.canvas')} />
      </div>
      <p className={styles.note}>{t('runner.controls')}</p>
      <div role="status" className={styles.result}>
        {phase === 'over' && (
          <>
            <p>{t('runner.result', { score: formatNumber(score) })}</p>
            {result &&
              (result.rank === 1 ? (
                <p>{t('runner.bestFirst', { best: formatNumber(result.my_best) })}</p>
              ) : result.rank ? (
                <p>{t('runner.best', { best: formatNumber(result.my_best), rank: result.rank })}</p>
              ) : null)}
          </>
        )}
        {start.isPending && <p>{t('runner.starting')}</p>}
      </div>
      {canStart && (
        <Button onClick={play} disabled={start.isPending}>
          {phase === 'over' ? t('runner.again') : t('runner.start')}
        </Button>
      )}
    </div>
  );
}
