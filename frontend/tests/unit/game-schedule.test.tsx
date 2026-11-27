// Wordle's level in « Jeux », the editor's planning of the games: Facile, Normal or Difficile,
// each with the words it gives; a choice is saved at once and counts from tomorrow's word.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { GameSchedulePage } from '../../src/features/admin/GameSchedulePage';
import type { GameSchedule } from '../../src/features/games/api';

// Mutations that do nothing; the level's, kept to look at what the page asked.
const { idle, state } = vi.hoisted(() => {
  const idle = () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false });
  const state: { schedule: GameSchedule; level: ReturnType<typeof idle> } = {
    schedule: undefined as unknown as GameSchedule,
    level: idle(),
  };
  return { idle, state };
});
vi.mock('../../src/features/games/api', () => ({
  GAMES: ['runner', 'pixel'],
  WORDLE_LEVELS: [1, 2, 3],
  useGameSchedule: () => ({ data: state.schedule }),
  useSetOrdinaryWeek: idle,
  usePlanWeek: idle,
  useUnplanWeek: idle,
  useSetWordleLevel: () => state.level,
}));

const week = (week_start: string) => ({ week_start, games: ['runner', 'pixel'], planned: false });

beforeEach(() => {
  state.schedule = {
    default: ['runner', 'pixel'],
    weeks: [week('2026-11-23'), week('2026-11-30'), week('2026-12-07'), week('2026-12-14')],
    wordle_level: 2,
  } as GameSchedule;
  state.level = idle();
});

afterEach(cleanup);

function show() {
  render(
    <MemoryRouter initialEntries={['/o/org/reglages/jeux']}>
      <Routes>
        <Route path="/o/:orgId/reglages/jeux" element={<GameSchedulePage />} />
      </Routes>
    </MemoryRouter>,
  );
  return within(screen.getByRole('region', { name: 'Wordle' }));
}

describe('GameSchedulePage', () => {
  it("shows the newsroom's Wordle level, each with the words it gives", () => {
    const wordle = show();
    const levels = within(wordle.getByRole('group', { name: 'NIVEAU DES MOTS' }));
    expect(levels.getAllByRole('radio')).toHaveLength(3);
    expect(levels.getByRole('radio', { name: 'Facile' })).not.toBeChecked();
    expect(levels.getByRole('radio', { name: 'Normal' })).toBeChecked();
    expect(levels.getByRole('radio', { name: 'Difficile' })).not.toBeChecked();
    expect(levels.getByRole('radio', { name: 'Facile' })).toHaveAccessibleDescription(
      'Les mots les plus courants.',
    );
    expect(levels.getByRole('radio', { name: 'Difficile' })).toHaveAccessibleDescription(
      "Tous les mots, jusqu'aux plus rares.",
    );
    expect(wordle.getByText(/vaut à partir du mot de demain/)).toBeVisible();
  });

  it('saves the level chosen', () => {
    const wordle = show();
    fireEvent.click(wordle.getByRole('radio', { name: 'Difficile' }));
    expect(state.level.reset).toHaveBeenCalled();
    expect(state.level.mutate).toHaveBeenCalledWith(3);
    fireEvent.click(wordle.getByRole('radio', { name: 'Facile' }));
    expect(state.level.mutate).toHaveBeenLastCalledWith(1);
  });

  it('shows the level the server sends back', () => {
    state.schedule = { ...state.schedule, wordle_level: 1 };
    const wordle = show();
    expect(wordle.getByRole('radio', { name: 'Facile' })).toBeChecked();
    expect(wordle.getByRole('radio', { name: 'Normal' })).not.toBeChecked();
  });

  it('waits while a change is being saved', () => {
    state.level = { ...idle(), isPending: true };
    const wordle = show();
    for (const radio of wordle.getAllByRole('radio')) expect(radio).toBeDisabled();
  });
});
