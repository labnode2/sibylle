// The chain of wins and the ranking of the day on the Wordle page. The ranking shows before and
// after one's own game: whoever finished, with their rank (none for those who lost), avatar,
// pseudo and tries (« 3/6 », « 6+1/6 » at the last chance, « perdu »), and the flame of their
// chain from two wins in a row; never a letter. The member's own chain and its joker show from two
// wins in a row too; a win says what the tries paid, and what the chain's bonus added.
import { cleanup, render, screen, within } from '@testing-library/react';
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
// The avatars draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

afterEach(cleanup);

type Row = WordleStatus['ranking'][number];

const CORRECT = ['correct', 'correct', 'correct', 'correct', 'correct'] as const;
const ABSENT = ['absent', 'absent', 'absent', 'absent', 'absent'] as const;

function row(
  pseudo: string,
  rank: number | null,
  tries: number,
  streak: number,
  is_me = false,
): Row {
  return {
    member: {
      id: `00000000-0000-0000-0000-${pseudo.padStart(12, '0')}`,
      pseudo,
      avatar: { size: 16, palette: 'base-v1', pixels: '' },
      role: 'reader',
      joined_at: '2026-11-01T09:00:00Z',
    },
    rank,
    state: rank === null ? 'lost' : 'won',
    tries,
    streak,
    is_me,
  };
}

// Not played yet: the chain of last evening, and the ranking of those who finished.
const before: WordleStatus = {
  day: '2026-11-28',
  state: 'playing',
  level: 4,
  tries: [],
  tries_left: 6,
  hint: null,
  laurels: null,
  streak_bonus: null,
  solution: null,
  streak: { current: 5, joker: true },
  ranking: [
    row('Leo', 1, 2, 4),
    row('Ines', 2, 3, 2),
    row('Paul', 3, 7, 1),
    row('Hugo', null, 7, 0),
  ],
};

/** Found at that try, on the server's reply: what it paid and the chain it makes. */
function won(count: number, laurels: number, bonus: number, chain: number): WordleStatus {
  const missed = Array.from({ length: count - 1 }, () => ({ word: 'boule', marks: [...ABSENT] }));
  return {
    ...before,
    state: 'won',
    tries: [...missed, { word: 'matin', marks: [...CORRECT] }],
    tries_left: 6 - count,
    laurels,
    streak_bonus: bonus,
    solution: 'matin',
    streak: { current: chain, joker: true },
  };
}

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

const ranking = () => screen.getByRole('region', { name: 'CLASSEMENT DU JOUR' });
const lines = () => within(ranking()).getAllByRole('listitem');
const flames = (line: HTMLElement) => within(line).queryAllByTitle(/^Chaîne de \d+ victoires$/);
const shown = (line: HTMLElement) =>
  [...line.querySelectorAll('[aria-hidden="true"]')].map((part) => part.textContent);
const chain = () => screen.queryByText(/^Chaîne de \d+ victoires/, { selector: 'p' });

describe('WordlePage', () => {
  it('shows the ranking of the day before playing, with the flame from two wins in a row', () => {
    show(before);
    const [leo, ines, paul, hugo] = lines();
    // Rank, pseudo, and the tries: « 6+1/6 » at the last chance, « perdu » with no rank.
    expect(leo).toHaveTextContent(/^1Leo/);
    expect(shown(leo!)).toContain('2/6');
    expect(paul).toHaveTextContent(/^3Paul/);
    expect(shown(paul!)).toContain('6+1/6');
    expect(hugo).toHaveTextContent(/^Hugoperdu$/);
    // Said in words to screen readers.
    expect(within(ines!).getByText('trouvé en 3 essais')).toHaveClass('visually-hidden');
    expect(within(paul!).getByText('trouvé à la dernière chance')).toHaveClass('visually-hidden');
    // The flame and the chain from 2; nothing at 1 or 0.
    expect(flames(leo!).map((flame) => flame.textContent)).toEqual(['4Chaîne de 4 victoires']);
    expect(flames(ines!)).toHaveLength(1);
    expect(flames(paul!)).toEqual([]);
    expect(flames(hugo!)).toEqual([]);
    // Not a letter of anyone's tries.
    expect(ranking()).not.toHaveTextContent(/matin|boule/i);
    // Nobody is marked as me: I have not finished.
    expect(lines().filter((line) => line.getAttribute('aria-current'))).toEqual([]);
  });

  it('marks my own line once my game is over', () => {
    show({ ...won(3, 6, 1, 3), ranking: [row('Leo', 1, 2, 4), row('Moi', 2, 3, 3, true)] });
    const mine = lines().filter((line) => line.getAttribute('aria-current') === 'true');
    expect(mine).toHaveLength(1);
    expect(mine[0]).toHaveTextContent(/^2Moi/);
  });

  it('says when nobody finished yet', () => {
    show({ ...before, ranking: [] });
    expect(within(ranking()).queryAllByRole('listitem')).toEqual([]);
    expect(ranking()).toHaveTextContent("Personne n'a encore fini la partie du jour.");
    // Under it, the rules of the chain: below the game, not in the intro above it.
    expect(ranking()).toHaveTextContent(/sauf une fois par palier \(3, 9, 27…\) : le joker/);
  });

  it("gives the chain's bonus in the message of a win", () => {
    show(won(3, 6, 1, 3));
    expect(screen.getByRole('status')).toHaveTextContent(
      /^Trouvé en 3 essais : \+6 lauriers, \+1 pour ta chaîne de 3 victoires\.$/,
    );
    cleanup();
    show(won(1, 32, 2, 9));
    expect(screen.getByRole('status')).toHaveTextContent(
      /^Trouvé en 1 essai : \+32 lauriers, \+2 pour ta chaîne de 9 victoires\.$/,
    );
  });

  it('gives the gain alone when the chain pays no bonus yet', () => {
    show(won(2, 8, 0, 2));
    expect(screen.getByRole('status')).toHaveTextContent(/^Trouvé en 2 essais : \+8 lauriers\.$/);
    cleanup();
    show(won(6, 1, 0, 1));
    expect(screen.getByRole('status')).toHaveTextContent(/^Trouvé en 6 essais : \+1 laurier\.$/);
  });

  it('shows my chain and its joker from two wins in a row', () => {
    show(before);
    expect(chain()).toHaveTextContent(/^Chaîne de 5 victoires, joker disponible$/);
    cleanup();
    show({ ...before, streak: { current: 5, joker: false } });
    expect(chain()).toHaveTextContent(/^Chaîne de 5 victoires, joker utilisé$/);
    cleanup();
    show({ ...before, streak: { current: 2, joker: false } });
    expect(chain()).toHaveTextContent(/^Chaîne de 2 victoires : bonus et joker dès la 3ᵉ$/);
    cleanup();
    show({ ...before, streak: { current: 1, joker: false } });
    expect(chain()).toBeNull();
  });
});
