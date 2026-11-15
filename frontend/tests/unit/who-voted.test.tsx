// « Qui a voté quoi » on a prono's page: the members under the option (or number) they chose, with
// their stake; a bet replaced by a later one is not listed.
import { cleanup, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { PronoDetail } from '../../src/features/pronos/api';
import { WhoVoted } from '../../src/features/pronos/WhoVoted';

// The avatars draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

afterEach(cleanup);

const avatar = { size: 16, palette: 'x', pixels: '' };
const member = (id: string, pseudo: string) => ({ id, pseudo, avatar });

function bet(id: string, who: string, over: Record<string, unknown>) {
  return {
    id,
    member: member(who, who),
    option_id: null,
    number_value: null,
    date_value: null,
    answer: '',
    stake: 0,
    rank: 1,
    placed_at: '2026-11-01T10:00:00Z',
    superseded: false,
    outcome: 'pending',
    payout: 0,
    ...over,
  };
}

function show(prono: Record<string, unknown>) {
  render(
    <MemoryRouter>
      <WhoVoted orgId="org" prono={prono as unknown as PronoDetail} />
    </MemoryRouter>,
  );
}

describe('WhoVoted', () => {
  it('lists the members under the option they chose, with their stake', () => {
    show({
      kind: 'choice',
      options: [
        { id: 'a', label: 'Nice' },
        { id: 'b', label: 'Monaco' },
        { id: 'c', label: 'Nul' },
      ],
      bets: [
        bet('1', 'Cami', { option_id: 'a', answer: 'Nice', stake: 20 }),
        bet('2', 'Hugo', { option_id: 'b', answer: 'Monaco' }),
        bet('3', 'Leo', { option_id: 'a', answer: 'Nice', superseded: true }),
      ],
    });
    const nice = screen.getByRole('group', { name: 'Nice' });
    expect(within(nice).getByText('Cami')).toBeVisible();
    expect(within(nice).getByText(/20/)).toBeVisible();
    expect(within(nice).queryByText('Leo')).toBeNull();
    expect(within(screen.getByRole('group', { name: 'Monaco' })).getByText('Hugo')).toBeVisible();
    // An option nobody chose is not listed.
    expect(screen.queryByRole('group', { name: 'Nul' })).toBeNull();
  });

  it('groups a number prono by the value played', () => {
    show({
      kind: 'number',
      options: [],
      bets: [
        bet('1', 'Cami', { number_value: '3', answer: '3 buts' }),
        bet('2', 'Hugo', { number_value: '3', answer: '3 buts' }),
        bet('3', 'Leo', { number_value: '5', answer: '5 buts' }),
      ],
    });
    const three = screen.getByRole('group', { name: '3 buts' });
    expect(within(three).getAllByRole('listitem')).toHaveLength(2);
    expect(within(screen.getByRole('group', { name: '5 buts' })).getByText('Leo')).toBeVisible();
  });
});
