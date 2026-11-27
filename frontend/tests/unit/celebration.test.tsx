// The burst of a game won: confetti and gold laurels over the page for two to three seconds, then
// gone. It plays after the answer that wins, in Wordle (the word found) as in Pixel mystère (the
// right word); never after a wrong answer, nor when a page opens on a game already won. It says
// nothing to screen readers, and without animations nothing shows.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { components } from '../../src/api/schema';
import type { PixelStatus, WordleStatus } from '../../src/features/games/api';
import { PixelMysterePage } from '../../src/features/games/pixel-mystere/PixelMysterePage';
import { WordlePage } from '../../src/features/games/wordle/WordlePage';
import { CELEBRATION_MS, useCelebration } from '../../src/ui/Celebration';
import styles from '../../src/ui/celebration.module.css';

type PixelAnswer = components['schemas']['PixelGuessOut'];
type Callbacks<T> = { onSuccess?: (reply: T) => void };

// What the server holds, and what it answers to the next try.
const wordle = {
  game: undefined as unknown as WordleStatus,
  reply: undefined as unknown as WordleStatus,
};
const pixel = {
  status: undefined as unknown as PixelStatus,
  answer: undefined as unknown as PixelAnswer,
};

vi.mock('../../src/features/games/api', () => ({
  useWordle: () => ({ data: wordle.game }),
  // The answer to a try is the whole game, which the page shows from then on.
  useWordleGuess: () => ({
    mutate: (_word: string, options?: Callbacks<WordleStatus>) => {
      wordle.game = wordle.reply;
      options?.onSuccess?.(wordle.reply);
    },
    reset: () => {},
    isPending: false,
    error: null,
  }),
  useGames: () => ({ data: { scheduled: ['pixel'] } }),
  usePixel: () => ({ data: pixel.status }),
  // The drawing itself comes back a moment later (see `openPixel`).
  useGuess: () => ({
    mutate: (_word: string, options?: Callbacks<PixelAnswer>) => {
      options?.onSuccess?.(pixel.answer);
    },
    isPending: false,
    error: null,
  }),
  usePixelQueue: () => ({ data: [] }),
  usePostPuzzle: () => ({ mutate: () => {}, reset: () => {}, isPending: false, error: null }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { my_membership: { role: 'reader', unlocked_colors: [] } } }),
}));
// The drawing and the avatars draw on a canvas, which jsdom does not have.
vi.mock('../../src/features/games/pixel-mystere/MysteryDrawing', () => ({
  MysteryDrawing: () => null,
}));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  document.documentElement.classList.remove('reduce-motion');
  // @ts-expect-error jsdom has no matchMedia: only some tests give it one.
  delete window.matchMedia;
});

const bursts = () => document.querySelectorAll(`.${styles.celebration}`);
const burst = () => document.querySelector(`.${styles.celebration}`);

function Game() {
  const [celebration, celebrate] = useCelebration();
  return (
    <>
      <button type="button" onClick={celebrate}>
        Gagner
      </button>
      {celebration}
    </>
  );
}

const win = () => fireEvent.click(screen.getByRole('button', { name: 'Gagner' }));
const wait = (ms: number) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

describe('Celebration', () => {
  it('plays once over the page, silent to screen readers, then leaves it', () => {
    vi.useFakeTimers();
    render(<Game />);
    expect(burst()).toBeNull();
    win();
    // On the page itself, outside whatever holds it: confetti and six gold laurels.
    expect(burst()?.parentElement).toBe(document.body);
    expect(burst()).toHaveAttribute('aria-hidden', 'true');
    expect(burst()?.children).toHaveLength(36);
    expect(burst()?.querySelectorAll('img')).toHaveLength(6);
    wait(CELEBRATION_MS - 1);
    expect(burst()).not.toBeNull();
    wait(1);
    expect(burst()).toBeNull();
  });

  it('lasts two to three seconds', () => {
    expect(CELEBRATION_MS).toBeGreaterThanOrEqual(2000);
    expect(CELEBRATION_MS).toBeLessThanOrEqual(3000);
  });

  it('starts again for a new win, one burst at a time', () => {
    vi.useFakeTimers();
    render(<Game />);
    win();
    wait(1000);
    win();
    expect(bursts()).toHaveLength(1);
    wait(CELEBRATION_MS - 1);
    expect(burst()).not.toBeNull();
    wait(1);
    expect(burst()).toBeNull();
  });

  it('shows nothing once « couper les animations » is chosen', () => {
    document.documentElement.classList.add('reduce-motion');
    render(<Game />);
    win();
    expect(burst()).toBeNull();
  });

  it('shows nothing when the system asks for less motion', () => {
    window.matchMedia = vi.fn(
      (query: string) =>
        ({ matches: query === '(prefers-reduced-motion: reduce)' }) as MediaQueryList,
    );
    render(<Game />);
    win();
    expect(burst()).toBeNull();
  });
});

const CORRECT = ['correct', 'correct', 'correct', 'correct', 'correct'] as const;
const ABSENT = ['absent', 'absent', 'absent', 'absent', 'absent'] as const;

const playing: WordleStatus = {
  day: '2026-11-16',
  state: 'playing',
  level: null,
  tries: [{ word: 'livre', marks: ['absent', 'correct', 'absent', 'absent', 'present'] }],
  tries_left: 5,
  laurels: null,
  solution: null,
};
const won: WordleStatus = {
  ...playing,
  state: 'won',
  level: null,
  tries: [...playing.tries, { word: 'bille', marks: [...CORRECT] }],
  tries_left: 4,
  laurels: 5,
  solution: 'bille',
};

function openWordle(game: WordleStatus, reply: WordleStatus = game) {
  wordle.game = game;
  wordle.reply = reply;
  render(
    <MemoryRouter initialEntries={['/o/org/jeux/wordle']}>
      <Routes>
        <Route path="/o/:orgId/jeux/wordle" element={<WordlePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

/** Types a word on the on-screen keyboard, then sends it. */
function tryWord(word: string) {
  for (const letter of word) {
    fireEvent.click(screen.getByRole('button', { name: letter.toUpperCase() }));
  }
  fireEvent.click(screen.getByRole('button', { name: 'Entrée' }));
}

describe('WordlePage', () => {
  it('plays the burst when a try finds the word', () => {
    openWordle(playing, won);
    expect(burst()).toBeNull();
    tryWord('bille');
    expect(screen.getByText('Trouvé en 2 essais : +5 lauriers.')).toBeVisible();
    expect(burst()).not.toBeNull();
  });

  it('plays nothing after a wrong try, the last one either', () => {
    const missed: WordleStatus = {
      ...playing,
      tries: [...playing.tries, { word: 'ville', marks: [...ABSENT] }],
      tries_left: 4,
    };
    openWordle(playing, missed);
    tryWord('ville');
    expect(screen.getByText('4 essais restants.')).toBeVisible();
    expect(burst()).toBeNull();

    cleanup();
    const lastTry: WordleStatus = {
      ...playing,
      tries: Array.from({ length: 5 }, () => playing.tries[0]!),
      tries_left: 1,
    };
    const lost: WordleStatus = {
      ...lastTry,
      state: 'lost',
      level: null,
      tries: [...lastTry.tries, { word: 'ville', marks: [...ABSENT] }],
      tries_left: 0,
      solution: 'bille',
    };
    openWordle(lastTry, lost);
    tryWord('ville');
    expect(screen.getByText('Perdu. Le mot était « BILLE ».')).toBeVisible();
    expect(burst()).toBeNull();
  });

  it('plays nothing when the page opens on a game already won', () => {
    openWordle(won);
    expect(screen.getByText('Trouvé en 2 essais : +5 lauriers.')).toBeVisible();
    expect(burst()).toBeNull();
  });
});

const active: PixelStatus = {
  puzzle_id: '00000000-0000-0000-0000-000000000001',
  size: 16,
  revealed: '',
  revealed_count: 12,
  letters: 4,
  guesses_left_today: 3,
  finds: [],
  found_by_me: false,
  mine: false,
  state: 'active',
  word: null,
  words: null,
  ends_at: null,
  started_at: null,
  gain_ends_at: null,
  gain_now: null,
  author_earned: null,
};
const found: PixelStatus = {
  ...active,
  guesses_left_today: 2,
  found_by_me: true,
  word: 'Café',
  words: ['Café'],
};

/** The page on a drawing, the answer to the next guess, and `refresh`: the drawing as the server
 *  sends it again after the guess. */
function openPixel(status: PixelStatus, answer?: PixelAnswer) {
  pixel.status = status;
  pixel.answer = answer as PixelAnswer;
  const page = () => (
    <MemoryRouter initialEntries={['/o/org/jeux/pixel']}>
      <Routes>
        <Route path="/o/:orgId/jeux/pixel" element={<PixelMysterePage />} />
      </Routes>
    </MemoryRouter>
  );
  const { rerender } = render(page());
  return {
    refresh(next: PixelStatus) {
      pixel.status = next;
      rerender(page());
    },
  };
}

function guessWord(word: string) {
  fireEvent.change(screen.getByLabelText('TA PROPOSITION'), { target: { value: word } });
  fireEvent.click(screen.getByRole('button', { name: 'Proposer' }));
}

describe('PixelMysterePage', () => {
  it('plays the burst when the right word is found, and keeps it once the form goes', () => {
    const page = openPixel(active, { correct: true, rank: 1, laurels: 50, guesses_left_today: 2 });
    expect(burst()).toBeNull();
    guessWord('cafe');
    expect(burst()).not.toBeNull();
    page.refresh(found);
    expect(screen.getByText('Tu as trouvé !')).toBeVisible();
    expect(screen.queryByLabelText('TA PROPOSITION')).toBeNull();
    expect(burst()).not.toBeNull();
  });

  it('plays nothing after a wrong word', () => {
    const page = openPixel(active, {
      correct: false,
      rank: null,
      laurels: null,
      guesses_left_today: 2,
    });
    guessWord('thé');
    page.refresh({ ...active, guesses_left_today: 2 });
    expect(screen.getByText("Il te reste 2 essais aujourd'hui.")).toBeVisible();
    expect(burst()).toBeNull();
  });

  it('plays nothing when the page opens on a word already found', () => {
    openPixel(found);
    expect(screen.getByText('Tu as trouvé !')).toBeVisible();
    expect(burst()).toBeNull();
  });
});
