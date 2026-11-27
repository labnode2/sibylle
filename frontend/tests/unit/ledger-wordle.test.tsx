// The member's statement names Wordle's lines by their day, rather than by their codes: what the
// day's win paid, and, on a line of its own, the bonus of the chain of wins.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { LedgerEntry } from '../../src/features/profile/api';
import { LedgerList } from '../../src/features/profile/LedgerList';

const entries: { current: LedgerEntry[] } = { current: [] };
vi.mock('../../src/features/profile/api', () => ({
  useLedger: () => ({
    data: { pages: [{ items: entries.current, next_cursor: null }] },
    hasNextPage: false,
  }),
}));

afterEach(cleanup);

function minigame(id: number, reason: string, amount: number): LedgerEntry {
  return {
    id,
    kind: 'minigame',
    amount,
    score_delta: 0,
    reason,
    prono: null,
    settlement_kind: null,
    created_at: '2026-11-16T09:30:00Z',
  };
}

describe('LedgerList', () => {
  it('names the Wordle won and the bonus of its chain by their day', () => {
    entries.current = [
      minigame(2, 'wordle-streak:2026-11-16', 1),
      minigame(1, 'wordle:2026-11-16', 6),
    ];
    render(
      <MemoryRouter>
        <LedgerList orgId="org" />
      </MemoryRouter>,
    );
    const [bonus, gain] = screen.getAllByRole('listitem');
    expect(bonus).toHaveTextContent('Wordle du 16 novembre : bonus de ta chaîne de victoires');
    expect(bonus).toHaveTextContent('+1 LAURIERS VERTS');
    expect(gain).toHaveTextContent(/Wordle du 16 novembre\+6 LAURIERS VERTS$/);
    expect(screen.queryByText(/wordle(-streak)?:/)).toBeNull();
  });
});
