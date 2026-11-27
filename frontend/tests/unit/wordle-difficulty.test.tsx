// The word's difficulty on the Wordle page, before and after the game: « Difficulté : 4/6 » and
// six squares, four of them filled; nothing for a word of the lists written by hand, which has no
// level. Under the game, the credit of Lexique, where the words come from.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { WordleStatus } from '../../src/features/games/api';
import { WordlePage } from '../../src/features/games/wordle/WordlePage';

const game: { current: WordleStatus } = { current: undefined as unknown as WordleStatus };
vi.mock('../../src/features/games/api', () => ({
  useWordle: () => ({ data: game.current }),
  useWordleGuess: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, error: null }),
}));

afterEach(cleanup);

const playing: WordleStatus = {
  day: '2026-11-28',
  state: 'playing',
  level: 4,
  tries: [{ word: 'livre', marks: ['absent', 'correct', 'absent', 'absent', 'present'] }],
  tries_left: 5,
  hint: null,
  laurels: null,
  solution: null,
};

function show(state: WordleStatus) {
  game.current = state;
  render(
    <MemoryRouter initialEntries={['/o/org/jeux/wordle']}>
      <Routes>
        <Route path="/o/:orgId/jeux/wordle" element={<WordlePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** How many squares the difficulty draws, and how many of them are filled. */
function squares(meter: HTMLElement) {
  const all = [...(meter.querySelector('span')?.children ?? [])];
  return [all.length, all.filter((square) => /squareOn/.test(square.className)).length];
}

describe('WordlePage', () => {
  it('shows the difficulty of the word while the game goes on', () => {
    show(playing);
    const meter = screen.getByRole('img', { name: 'Difficulté du mot : 4 sur 6' });
    expect(meter).toHaveTextContent(/^Difficulté : 4\/6$/);
    expect(squares(meter)).toEqual([6, 4]);
    // Above the grid.
    const grid = screen.getByRole('grid', { name: 'Grille du Wordle' });
    expect(meter.compareDocumentPosition(grid) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('still shows it once the game is over', () => {
    show({ ...playing, state: 'won', level: 6, laurels: 5, solution: 'ville' });
    expect(squares(screen.getByRole('img', { name: 'Difficulté du mot : 6 sur 6' }))).toEqual([
      6, 6,
    ]);
    show({ ...playing, state: 'lost', level: 1, tries_left: 0, solution: 'ville' });
    expect(squares(screen.getByRole('img', { name: 'Difficulté du mot : 1 sur 6' }))).toEqual([
      6, 1,
    ]);
  });

  it('shows no difficulty for a word without a level', () => {
    show({ ...playing, level: null });
    expect(screen.queryByRole('img', { name: /Difficulté/ })).toBeNull();
    expect(screen.queryByText(/Difficulté/)).toBeNull();
  });

  it('credits Lexique, with a link to its site', () => {
    show({ ...playing, level: null });
    const link = screen.getByRole('link', { name: 'Lexique 3.83' });
    expect(link).toHaveAttribute('href', 'http://www.lexique.org');
    expect(link.closest('p')).toHaveTextContent(
      /^Mots : Lexique 3\.83 \(New, Pallier et al\.\), licence CC BY-SA 4\.0$/,
    );
  });
});
