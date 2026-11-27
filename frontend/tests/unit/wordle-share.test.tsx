// Sharing a finished Wordle by copy and paste: the word's number, the tries it took (« 6+1 » when
// found at the last chance, « X » when lost) and a row of coloured squares per try, without a
// letter; only once the game is over.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import i18n from '../../src/i18n';
import type { WordleStatus } from '../../src/features/games/api';
import { shareText, wordleNumber } from '../../src/features/games/wordle/share';
import { WordlePage } from '../../src/features/games/wordle/WordlePage';

const game: { current: WordleStatus } = { current: undefined as unknown as WordleStatus };
vi.mock('../../src/features/games/api', () => ({
  useWordle: () => ({ data: game.current }),
  useWordleGuess: () => ({ mutate: vi.fn(), reset: vi.fn(), isPending: false, error: null }),
}));

const writeText = vi.fn<(text: string) => Promise<void>>();

beforeEach(() => {
  writeText.mockReset().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
});

afterEach(() => {
  cleanup();
  Reflect.deleteProperty(navigator, 'clipboard');
});

const t = i18n.getFixedT('fr', 'games');

const won: WordleStatus = {
  day: '2026-11-16',
  state: 'won',
  level: null,
  tries: [
    { word: 'livre', marks: ['absent', 'correct', 'absent', 'absent', 'present'] },
    { word: 'ville', marks: ['present', 'correct', 'absent', 'correct', 'correct'] },
    { word: 'mille', marks: ['absent', 'correct', 'correct', 'correct', 'correct'] },
    { word: 'bille', marks: ['correct', 'correct', 'correct', 'correct', 'correct'] },
  ],
  tries_left: 2,
  hint: null,
  laurels: 3,
  solution: 'bille',
};

const lost: WordleStatus = {
  day: '2026-11-17',
  state: 'lost',
  level: null,
  tries: Array.from({ length: 6 }, () => ({
    word: 'livre',
    marks: ['absent', 'absent', 'absent', 'absent', 'absent'],
  })),
  tries_left: 0,
  hint: null,
  laurels: null,
  solution: 'bille',
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

describe('wordleNumber', () => {
  it('counts the days from the first word, 15 November 2026', () => {
    expect(wordleNumber('2026-11-15')).toBe(1);
    expect(wordleNumber('2026-11-16')).toBe(2);
    expect(wordleNumber('2027-01-01')).toBe(48);
    // Over a change of time, still one a day.
    expect(wordleNumber('2027-03-29')).toBe(135);
  });
});

describe('shareText', () => {
  it('gives the number, the tries and the colours, not a letter', () => {
    expect(shareText(t, won)).toBe(
      ['Wordle Sibylle #2 4/6', '', '⬛🟩⬛⬛🟨', '🟨🟩⬛🟩🟩', '⬛🟩🟩🟩🟩', '🟩🟩🟩🟩🟩'].join(
        '\n',
      ),
    );
    for (const { word } of won.tries) expect(shareText(t, won)).not.toContain(word);
  });

  it('scores a lost game « X »', () => {
    const text = shareText(t, lost);
    expect(text.split('\n')[0]).toBe('Wordle Sibylle #3 X/6');
    expect(text.split('\n').slice(2)).toEqual(Array<string>(6).fill('⬛⬛⬛⬛⬛'));
  });

  it('scores a word found at the last chance « 6+1 », its seventh row with the others', () => {
    const found: WordleStatus = {
      ...lost,
      state: 'won',
      level: 5,
      tries: [
        ...lost.tries,
        { word: 'bille', marks: ['correct', 'correct', 'correct', 'correct', 'correct'] },
      ],
      laurels: 0,
    };
    expect(shareText(t, found)).toBe(
      ['Wordle Sibylle #3 6+1/6', '', ...Array<string>(6).fill('⬛⬛⬛⬛⬛'), '🟩🟩🟩🟩🟩'].join(
        '\n',
      ),
    );
    // Missed there too, it is lost.
    const missed: WordleStatus = {
      ...lost,
      level: 5,
      tries: [
        ...lost.tries,
        { word: 'balle', marks: ['correct', 'absent', 'correct', 'correct', 'correct'] },
      ],
    };
    const lines = shareText(t, missed).split('\n');
    expect(lines[0]).toBe('Wordle Sibylle #3 X/6');
    expect(lines.slice(2)).toEqual([...Array<string>(6).fill('⬛⬛⬛⬛⬛'), '🟩⬛🟩🟩🟩']);
  });
});

describe('WordlePage', () => {
  it('copies the result of a finished game, shown as it will be pasted', async () => {
    show(won);
    const share = screen.getByRole('region', { name: 'PARTAGE TON RÉSULTAT' });
    expect(share.querySelector('pre')?.textContent).toBe(shareText(t, won));
    await act(async () => {
      fireEvent.click(within(share).getByRole('button', { name: 'Copier le résultat' }));
    });
    expect(writeText).toHaveBeenCalledWith(shareText(t, won));
  });

  it('shares a lost game too', () => {
    show(lost);
    const share = screen.getByRole('region', { name: 'PARTAGE TON RÉSULTAT' });
    expect(share).toHaveTextContent('Wordle Sibylle #3 X/6');
  });

  it('has nothing to share while the game goes on', () => {
    show({ ...won, state: 'playing', tries: won.tries.slice(0, 2), laurels: null, solution: null });
    expect(screen.queryByRole('region', { name: 'PARTAGE TON RÉSULTAT' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Copier le résultat' })).toBeNull();
  });
});
