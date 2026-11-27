// The last chance of a word of level 4 or more, missed six times: a seventh row to type in and,
// above the keyboard, the word's letters in alphabetical order. Neither shows before the sixth try
// is missed, nor for a game lost at the sixth try; once the seventh try is played, its row stays
// but the hint goes. Found at the seventh try, a win without laurels, shared as « 6+1/6 ».
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
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

const ABSENT = ['absent', 'absent', 'absent', 'absent', 'absent'] as const;
const CORRECT = ['correct', 'correct', 'correct', 'correct', 'correct'] as const;
const HINT = 'Dernière chance : les lettres du mot sont A I M N T';

/** As many tries missed on « matin ». */
function missed(count: number): WordleStatus['tries'] {
  return Array.from({ length: count }, () => ({ word: 'boule', marks: [...ABSENT] }));
}

// Five tries missed on a word of level 5: the sixth to come, as for any word.
const sixthTry: WordleStatus = {
  day: '2026-11-28',
  state: 'playing',
  level: 5,
  tries: missed(5),
  tries_left: 1,
  hint: null,
  laurels: null,
  solution: null,
};
// The sixth missed too: the game goes on, with the hint.
const lastChance: WordleStatus = { ...sixthTry, tries: missed(6), hint: 'A I M N T' };

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

const rows = () => screen.getAllByRole('row');
const letters = (row: HTMLElement) =>
  within(row)
    .getAllByRole('gridcell')
    .map((cell) => cell.textContent);
const hint = () => screen.queryByText(/les lettres du mot/);

describe('WordlePage', () => {
  it('has six rows and no hint until the sixth try is missed', () => {
    show(sixthTry);
    expect(rows()).toHaveLength(6);
    expect(screen.getByRole('status')).toHaveTextContent(/^Dernier essai\.$/);
    expect(hint()).toBeNull();
  });

  it('gives a seventh row and the letters of the word above the keyboard at the last chance', () => {
    show(lastChance);
    expect(rows()).toHaveLength(7);
    expect(letters(rows()[6]!)).toEqual(['', '', '', '', '']);
    // The seventh row is the one typed in.
    fireEvent.click(screen.getByRole('button', { name: 'M' }));
    fireEvent.click(screen.getByRole('button', { name: 'A' }));
    expect(letters(rows()[6]!)).toEqual(['M', 'A', '', '', '']);

    // Said to screen readers too, as the line that follows each try.
    const status = screen.getByRole('status');
    expect(status.textContent).toBe(HINT);
    const keyboard = screen.getByRole('button', { name: 'Entrée' });
    expect(
      status.compareDocumentPosition(keyboard) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    // The letters together, on one line.
    expect(within(status).getByText('A I M N T').className).toMatch(/hint/);
  });

  it('keeps the seventh row once played, without the hint', () => {
    const seventh: WordleStatus['tries'][number] = {
      word: 'motif',
      marks: ['correct', 'absent', 'correct', 'correct', 'absent'],
    };
    show({
      ...lastChance,
      state: 'lost',
      tries: [...missed(6), seventh],
      tries_left: 0,
      hint: null,
      solution: 'matin',
    });
    expect(rows()).toHaveLength(7);
    expect(letters(rows()[6]!)).toEqual(['M', 'O', 'T', 'I', 'F']);
    expect(screen.getByRole('status')).toHaveTextContent(/^Perdu\. Le mot était « MATIN »\.$/);
    expect(hint()).toBeNull();
    expect(screen.queryByRole('button', { name: 'Entrée' })).toBeNull();
  });

  it('has no seventh row nor hint for a word lost at the sixth try', () => {
    show({
      ...sixthTry,
      level: 3,
      state: 'lost',
      tries: missed(6),
      tries_left: 0,
      solution: 'matin',
    });
    expect(rows()).toHaveLength(6);
    expect(hint()).toBeNull();
  });

  it('says a word found at the last chance pays no laurels, and shares it as 6+1', () => {
    show({
      ...lastChance,
      state: 'won',
      tries: [...missed(6), { word: 'matin', marks: [...CORRECT] }],
      tries_left: 0,
      hint: null,
      laurels: 0,
      solution: 'matin',
    });
    expect(rows()).toHaveLength(7);
    expect(screen.getByRole('status')).toHaveTextContent(
      /^Trouvé à la dernière chance : pas de lauriers cette fois\.$/,
    );
    expect(hint()).toBeNull();
    const share = screen.getByRole('region', { name: 'PARTAGE TON RÉSULTAT' });
    expect(share.querySelector('pre')?.textContent?.split('\n')[0]).toBe(
      'Wordle Sibylle #14 6+1/6',
    );
  });
});
