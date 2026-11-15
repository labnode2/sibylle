// « Qui a voté quoi »: the avatars of the members next to the distribution line they chose; a bet
// replaced by a later one is not listed.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PronoDetail } from '../../src/features/pronos/api';
import { Voters, votersFor } from '../../src/features/pronos/WhoVoted';

// The avatars draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

afterEach(cleanup);

const avatar = { size: 16, palette: 'x', pixels: '' };

function bet(id: string, who: string, over: Record<string, unknown>) {
  return {
    id,
    member: { id: who, pseudo: who, avatar },
    option_id: null,
    number_value: null,
    date_value: null,
    answer: '',
    stake: 0,
    superseded: false,
    ...over,
  };
}

const as = (prono: Record<string, unknown>) => prono as unknown as PronoDetail;
const names = (prono: PronoDetail, index: number) =>
  votersFor(prono, index).map((b) => b.member.pseudo);

describe('votersFor', () => {
  it('lists the members under the option they chose, not replaced bets', () => {
    const prono = as({
      kind: 'choice',
      distribution: [{ label: 'Nice' }, { label: 'Monaco' }],
      bets: [
        bet('1', 'Cami', { answer: 'Nice' }),
        bet('2', 'Hugo', { answer: 'Monaco' }),
        bet('3', 'Leo', { answer: 'Nice', superseded: true }),
      ],
    });
    expect(names(prono, 0)).toEqual(['Cami']);
    expect(names(prono, 1)).toEqual(['Hugo']);
  });

  it('matches a date prono by the date played', () => {
    const prono = as({
      kind: 'date',
      distribution: [{ label: '2026-11-17' }, { label: '2026-11-25' }],
      bets: [
        bet('1', 'Loulou', { date_value: '2026-11-17' }),
        bet('2', 'Emile', { date_value: '2026-11-25' }),
      ],
    });
    expect(names(prono, 0)).toEqual(['Loulou']);
    expect(names(prono, 1)).toEqual(['Emile']);
  });

  it('matches a number prono by value and by grouped range', () => {
    const bets = [
      bet('1', 'Cami', { number_value: '3.00' }),
      bet('2', 'Leo', { number_value: '10' }),
    ];
    const single = as({ kind: 'number', distribution: [{ label: '3' }, { label: '10' }], bets });
    expect(names(single, 0)).toEqual(['Cami']);
    const ranged = as({
      kind: 'number',
      distribution: [{ label: '3 – 6.5' }, { label: '6.5 – 10' }],
      bets,
    });
    expect(names(ranged, 0)).toEqual(['Cami']);
    expect(names(ranged, 1)).toEqual(['Leo']);
  });
});

describe('Voters', () => {
  it('shows one avatar link per member', () => {
    render(
      <MemoryRouter>
        <Voters orgId="org" bets={[bet('1', 'Cami', {}), bet('2', 'Hugo', {})] as never} />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link', { name: 'Cami' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Hugo' })).toBeVisible();
  });
});
