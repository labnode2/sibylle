// The ball's race, without drawing: a ball that jumps over obstacles drawn from the server's
// seed, faster and faster. Pure, so that it can be tested; RunnerGame draws it and feeds it time.
//
// The score is one point per 10 pixels run, at a speed between 300 and 900 pixels a second: never
// more than 90 points a second, which the server checks (backend/src/sibylle/domain/minigames.py).

export const WIDTH = 600;
export const HEIGHT = 200;
export const GROUND = 168;
export const BALL_X = 56;
export const BALL_SIZE = 32;
// The game moves in steps of a sixtieth of a second, whatever the screen's rate.
export const STEP = 1 / 60;

export const START_SPEED = 300;
export const MAX_SPEED = 900;
const ACCELERATION = 6;
const GRAVITY = 2600;
const JUMP_SPEED = 820;
const PIXELS_PER_POINT = 10;

export type Obstacle = { x: number; width: number; height: number };

export type RunState = {
  /** Seconds played. */
  time: number;
  /** Pixels run. */
  distance: number;
  /** Height of the ball's bottom above the ground, and its upward speed. */
  y: number;
  vy: number;
  obstacles: Obstacle[];
  /** The obstacles' random generator, seeded by the server. */
  random: number;
  over: boolean;
};

/** mulberry32: a small generator, the same on every browser for the same seed. */
function next(state: number): [number, number] {
  const seed = (state + 0x6d2b79f5) | 0;
  let t = seed;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return [((t ^ (t >>> 14)) >>> 0) / 4294967296, seed];
}

export function speedAt(time: number): number {
  return Math.min(MAX_SPEED, START_SPEED + ACCELERATION * time);
}

export function scoreOf(state: RunState): number {
  return Math.floor(state.distance / PIXELS_PER_POINT);
}

export function newRun(seed: number): RunState {
  return { time: 0, distance: 0, y: 0, vy: 0, obstacles: [], random: seed, over: false };
}

const SHAPES: { width: number; height: number }[] = [
  { width: 20, height: 28 },
  { width: 20, height: 40 },
  { width: 28, height: 52 },
  { width: 44, height: 28 },
  { width: 44, height: 40 },
];

/** Adds obstacles ahead, far enough apart to land and jump again at the current speed. */
function spawn(state: RunState, speed: number): RunState {
  const obstacles = [...state.obstacles];
  let random = state.random;
  let last = obstacles.at(-1);
  while (!last || last.x < WIDTH * 2) {
    let roll: number;
    [roll, random] = next(random);
    const shape = SHAPES[Math.floor(roll * SHAPES.length)]!;
    [roll, random] = next(random);
    const shortest = speed * 0.8 + 160;
    const gap = shortest + roll * (speed * 0.9 + 220);
    const x = last ? last.x + last.width + gap : WIDTH + 120;
    last = { x, ...shape };
    obstacles.push(last);
  }
  return { ...state, obstacles, random };
}

function hits(state: RunState): boolean {
  const left = BALL_X + 6;
  const right = BALL_X + BALL_SIZE - 6;
  return state.obstacles.some(
    (o) => right > o.x + 2 && left < o.x + o.width - 2 && state.y < o.height - 2,
  );
}

/** One step of `STEP` seconds; `jump` asks for a jump, taken only from the ground. */
export function step(state: RunState, jump: boolean): RunState {
  if (state.over) return state;
  const speed = speedAt(state.time);
  let { y, vy } = state;
  if (jump && y === 0) vy = JUMP_SPEED;
  vy -= GRAVITY * STEP;
  y = Math.max(0, y + vy * STEP);
  if (y === 0) vy = 0;
  const moved = speed * STEP;
  const obstacles = state.obstacles
    .map((o) => ({ ...o, x: o.x - moved }))
    .filter((o) => o.x + o.width > 0);
  const after = spawn(
    { ...state, time: state.time + STEP, distance: state.distance + moved, y, vy, obstacles },
    speed,
  );
  return hits(after) ? { ...after, over: true } : after;
}
