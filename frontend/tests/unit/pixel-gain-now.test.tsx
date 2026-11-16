// Pixel mystère: what finding the word now would pay shows in a gold box on the game page, big
// and counting down to the minute; nothing for whoever cannot win.
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { PixelStatus } from '../../src/features/games/api';
import { GainNow } from '../../src/features/games/pixel-mystere/GainNow';

afterEach(cleanup);

const START = new Date('2026-11-02T09:00:00Z').getTime();
const WEEK = 168 * 3_600_000;

function status(overrides: Partial<PixelStatus>): PixelStatus {
  return {
    puzzle_id: '00000000-0000-0000-0000-000000000001',
    size: 16,
    revealed: '',
    revealed_count: 0,
    letters: 4,
    guesses_left_today: 3,
    finds: [],
    found_by_me: false,
    mine: false,
    state: 'active',
    word: null,
    words: null,
    ends_at: new Date(START + WEEK).toISOString(),
    started_at: new Date(START).toISOString(),
    gain_ends_at: new Date(START + WEEK).toISOString(),
    gain_now: 50,
    author_earned: null,
    ...overrides,
  };
}

describe('GainNow', () => {
  it('shows the laurels to win now, big, and counts them down', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] });
    vi.setSystemTime(START);
    try {
      render(<GainNow status={status({})} />);
      const box = screen.getByRole('status', { name: 'TROUVE MAINTENANT : +50' });
      expect(box).toHaveTextContent('SI TU TROUVES MAINTENANT');
      expect(box).toHaveTextContent('+50 LAURIERS');
      act(() => {
        vi.advanceTimersByTime(WEEK / 2);
      });
      expect(screen.getByRole('status')).toHaveTextContent('+26 LAURIERS');
      act(() => {
        vi.advanceTimersByTime(WEEK / 2);
      });
      expect(screen.getByRole('status')).toHaveTextContent('+3 LAURIERS');
    } finally {
      vi.useRealTimers();
    }
  });

  it('shows nothing to the author, to a finder, or once the drawing ended', () => {
    render(<GainNow status={status({ mine: true, gain_now: null })} />);
    render(<GainNow status={status({ found_by_me: true, gain_now: null })} />);
    render(<GainNow status={status({ state: 'finished', gain_now: null })} />);
    expect(screen.queryByRole('status')).toBeNull();
    expect(screen.queryByText(/LAURIERS/)).toBeNull();
  });
});
