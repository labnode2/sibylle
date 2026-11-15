// « Les jeux de la semaine » on la une: a Pixel mystère found shows as the newsroom sees it,
// masked and without its word, with a « RÉSOLU » tag; its author sees it masked too.
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
      tries: [],
      tries_left: 6,
      laurels: null,
      solution: null,
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
      ends_at: null,
      started_at: null,
      gain_ends_at: null,
      gain_now: null,
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
  it('shows a drawing found masked, with its tag and without its word', () => {
    show(pixel({ found_by_me: true }));
    expect(screen.getByText('RÉSOLU')).toBeVisible();
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

  it('shows what finding the word would pay now, to the minute', () => {
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
      expect(screen.getByRole('link', { name: /Pixel mystère/ })).toHaveTextContent(
        'TROUVE MAINTENANT : +26',
      );
      act(() => {
        vi.advanceTimersByTime(84 * 3_600_000);
      });
      expect(screen.getByRole('link', { name: /Pixel mystère/ })).toHaveTextContent(
        'TROUVE MAINTENANT : +3',
      );
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows no gain to whoever cannot play', () => {
    show(pixel({ mine: true, gain_now: null }));
    expect(screen.queryByText(/TROUVE MAINTENANT/)).toBeNull();
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
