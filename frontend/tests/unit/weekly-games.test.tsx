// « Les jeux de la semaine » on la une: a Pixel mystère found shows as the newsroom sees it,
// masked and without its word, with a blue « RÉSOLU » tag; its author sees it masked too. Whoever
// can still find it reads what finding it now would pay right after its time left, with a gold
// laurel.
import { act, cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { Games } from '../../src/features/games/api';
import { WeeklyGames } from '../../src/features/games/WeeklyGames';

const games: { current: Games } = { current: undefined as unknown as Games };
vi.mock('../../src/features/games/api', () => ({ useGames: () => ({ data: games.current }) }));
// The crystal ball and the drawing draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/features/games/pixel-mystere/MysteryDrawing', () => ({
  MysteryDrawing: ({ revealed }: { revealed: string }) => (
    <span data-testid="drawing" data-revealed={revealed} />
  ),
}));

afterEach(cleanup);

// Two pixels of 16 × 16 shown, the rest hidden (255).
const MASKED = btoa(String.fromCharCode(13, 13, ...Array<number>(254).fill(255)));

function pixel(overrides: Partial<NonNullable<Games['pixel']>>): Games {
  return {
    scheduled: ['pixel'],
    runner: null,
    wordle: {
      day: '2026-11-16',
      state: 'playing',
      level: null,
      tries: [],
      tries_left: 6,
      hint: null,
      laurels: null,
      streak_bonus: null,
      solution: null,
      streak: { current: 0, joker: false },
      ranking: [],
    },
    pixel: {
      puzzle_id: '00000000-0000-0000-0000-000000000001',
      size: 16,
      revealed: MASKED,
      revealed_count: 2,
      letters: 4,
      guesses_left_today: 0,
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
      ...overrides,
    },
  };
}

function show(state: Games) {
  games.current = state;
  render(
    <MemoryRouter>
      <WeeklyGames orgId="org" />
    </MemoryRouter>,
  );
}

describe('WeeklyGames', () => {
  it('shows a drawing found masked, with its blue tag and without its word', () => {
    show(pixel({ found_by_me: true }));
    const tag = screen.getByText('RÉSOLU');
    expect(tag).toBeVisible();
    expect(tag.className).toMatch(/chipIndigo/);
    expect(tag.className).not.toMatch(/chipInk/);
    expect(screen.getByTestId('drawing')).toHaveAttribute('data-revealed', MASKED);
    expect(screen.getByRole('link', { name: /Pixel mystère/ })).toHaveTextContent(
      'UN MOT DE 4 LETTRES',
    );
    expect(screen.queryByText(/LE MOT/)).toBeNull();
  });

  it('shows its author the drawing masked, without a tag', () => {
    show(pixel({ mine: true }));
    expect(screen.getByTestId('drawing')).toHaveAttribute('data-revealed', MASKED);
    expect(screen.queryByText('RÉSOLU')).toBeNull();
  });

  it('has no tag for whoever has not found yet', () => {
    show(pixel({ guesses_left_today: 3 }));
    expect(screen.queryByText('RÉSOLU')).toBeNull();
  });

  it('shows what finding the word would pay now after its time left, to the minute', () => {
    const start = new Date('2026-11-02T09:00:00Z').getTime();
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
    vi.setSystemTime(start + 84 * 3_600_000); // half of the week
    try {
      show(
        pixel({
          started_at: new Date(start).toISOString(),
          gain_ends_at: new Date(start + 168 * 3_600_000).toISOString(),
          ends_at: new Date(start + 168 * 3_600_000).toISOString(),
          gain_now: 26,
        }),
      );
      const link = screen.getByRole('link', { name: /Pixel mystère/ });
      // « +26 » and a gold laurel, named for screen readers, on the line after the time left.
      expect(link).toHaveTextContent(
        'UN MOT DE 4 LETTRES · FIN DANS 3 J 12 H · +26 lauriers si tu trouves maintenant',
      );
      expect(link.querySelector('img')).toHaveAttribute(
        'src',
        expect.stringMatching(/\/laurel\.png$/),
      );
      expect(link).not.toHaveTextContent('TROUVE MAINTENANT');
      act(() => {
        vi.advanceTimersByTime(84 * 3_600_000);
      });
      expect(link).toHaveTextContent('· +3 lauriers si tu trouves maintenant');
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows no gain to whoever cannot play', () => {
    show(pixel({ mine: true, gain_now: null }));
    const link = screen.getByRole('link', { name: /Pixel mystère/ });
    expect(link).not.toHaveTextContent('si tu trouves maintenant');
    expect(link).not.toHaveTextContent('+');
    expect(link.querySelector('img')).toBeNull();
  });

  it('always shows Wordle, even in a week without games, and says if it was played', () => {
    const base = pixel({});
    show({ ...base, scheduled: [], pixel: null });
    expect(screen.getByRole('link', { name: /Wordle/ })).toHaveTextContent('UN MOT PAR JOUR');
    cleanup();
    show({ ...base, wordle: { ...base.wordle, state: 'won', laurels: 4 } });
    expect(screen.getByRole('link', { name: /Wordle/ })).toHaveTextContent('TROUVÉ AUJOURD');
  });
});
