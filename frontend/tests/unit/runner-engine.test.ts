import { describe, expect, it } from 'vitest';

import {
  BALL_X,
  MAX_SPEED,
  newRun,
  scoreOf,
  speedAt,
  START_SPEED,
  step,
  STEP,
  type RunState,
} from '../../src/features/games/runner/engine';

function run(state: RunState, seconds: number, jump: (s: RunState) => boolean = () => false) {
  let current = state;
  for (let i = 0; i < Math.round(seconds / STEP) && !current.over; i += 1) {
    current = step(current, jump(current));
  }
  return current;
}

/** Without obstacles, to measure the pace alone. */
const clear = (state: RunState): RunState => ({ ...state, obstacles: [] });

describe('the ball’s race', () => {
  it('draws the same obstacles from the same seed', () => {
    const a = step(newRun(42), false);
    const b = step(newRun(42), false);
    expect(a.obstacles).toEqual(b.obstacles);
    expect(step(newRun(7), false).obstacles).not.toEqual(a.obstacles);
  });

  it('speeds up from 300 to 900 pixels a second, never more', () => {
    expect(speedAt(0)).toBe(START_SPEED);
    expect(speedAt(50)).toBeGreaterThan(START_SPEED);
    expect(speedAt(1_000)).toBe(MAX_SPEED);
  });

  it('never scores more than 90 points a second, the bound the server checks', () => {
    let state = newRun(1);
    for (let i = 0; i < 200 / STEP; i += 1) state = step(clear(state), false);
    expect(state.over).toBe(false);
    expect(scoreOf(state)).toBeLessThanOrEqual(90 * 200);
    expect(scoreOf(state)).toBeGreaterThan(30 * 200);
  });

  it('jumps from the ground and comes back down', () => {
    const jumped = step(clear(newRun(1)), true);
    expect(jumped.y).toBeGreaterThan(0);
    expect(step(jumped, true).vy).toBeLessThan(jumped.vy); // no jump in the air
    expect(run(jumped, 1).y).toBe(0);
  });

  it('ends on an obstacle, and a jump clears it', () => {
    const block = { x: BALL_X + 40, width: 20, height: 40 };
    const crash = run({ ...newRun(1), obstacles: [block] }, 1);
    expect(crash.over).toBe(true);
    const frozen = step(crash, true);
    expect(frozen).toBe(crash);

    const early = { ...block, x: BALL_X + 120 };
    const jumpAt = (s: RunState) => s.obstacles[0] === undefined || s.obstacles[0].x < BALL_X + 70;
    const cleared = run({ ...newRun(1), obstacles: [early] }, 0.6, jumpAt);
    expect(cleared.over).toBe(false);
  });
});
