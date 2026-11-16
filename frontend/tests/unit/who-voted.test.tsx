// « Qui a voté quoi »: the avatars of the members next to the distribution line they chose; a bet
// replaced by a later one is not listed. The mouse over an avatar opens the member's press card,
// which a click closes; on a touch screen a tap opens it and another one closes it.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import type { PronoDetail } from '../../src/features/pronos/api';
import { Voters, votersFor } from '../../src/features/pronos/WhoVoted';

// The avatars draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

const { usePressCard } = vi.hoisted(() => ({ usePressCard: vi.fn() }));
vi.mock('../../src/features/profile/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/profile/api')>()),
  usePressCard,
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { title: 'La Gazette' } }),
}));

afterEach(cleanup);

const avatar = { size: 16, palette: 'x', pixels: '' };

/** The press card the server sends for a member (the members' ids are their pseudos here). */
function pressCard(pseudo: string) {
  return {
    id: pseudo,
    pseudo,
    avatar,
    frame: null,
    animation: null,
    role: 'journalist',
    joined_at: '2026-09-01T10:00:00Z',
    card_number: '0042',
    stats: {
      laurels: 120,
      pronos_played: 8,
      settled: 6,
      wins: 3,
      success_rate: 50,
      streak: 0,
      best_streak: 0,
    },
    trophies: [],
    collection: [],
    showcase: [],
  };
}

beforeEach(() => {
  usePressCard.mockReset();
  usePressCard.mockImplementation((_orgId: string, memberId: string) => ({
    data: pressCard(memberId),
    isError: false,
    error: null,
  }));
});

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
  const pressCardShown = () => screen.queryByRole('region', { name: 'Carte de presse' });

  function show() {
    render(<Voters orgId="org" bets={[bet('1', 'Cami', {}), bet('2', 'Hugo', {})] as never} />);
    return {
      cami: screen.getByRole('button', { name: 'Cami' }),
      hugo: screen.getByRole('button', { name: 'Hugo' }),
    };
  }

  it('opens the press card of the member under the mouse, and a click closes it', async () => {
    const user = userEvent.setup();
    const { cami, hugo } = show();
    expect(hugo).toBeVisible();
    expect(cami).toHaveAttribute('aria-expanded', 'false');
    expect(pressCardShown()).toBeNull();
    // Nothing is asked of the server before a card is opened.
    expect(usePressCard).not.toHaveBeenCalled();

    await user.hover(cami);
    expect(cami).toHaveAttribute('aria-expanded', 'true');
    const card = pressCardShown()!;
    expect(within(card).getByRole('heading', { name: 'Cami' })).toBeVisible();
    expect(within(card).getByText('CARTE DE PRESSE N° 0042')).toBeVisible();
    expect(usePressCard).toHaveBeenCalledWith('org', 'Cami');

    // The click closes the card and stays on the prono: the avatar leads nowhere else.
    await user.click(cami);
    expect(cami).toHaveAttribute('aria-expanded', 'false');
    expect(pressCardShown()).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('keeps the card while the pointer is over it, and a click on the card closes it', () => {
    const { cami } = show();
    // A browser's pointer events say where the pointer goes (relatedTarget), which React reads to
    // tell a move onto the card from a leave; user-event's do not, hence fireEvent here.
    fireEvent.pointerOver(cami, { pointerType: 'mouse' });
    const card = pressCardShown()!;
    fireEvent.pointerOut(cami, { pointerType: 'mouse', relatedTarget: card });
    fireEvent.pointerOver(card, { pointerType: 'mouse', relatedTarget: cami });
    expect(cami).toHaveAttribute('aria-expanded', 'true');
    expect(pressCardShown()).not.toBeNull();
    fireEvent.click(card);
    expect(cami).toHaveAttribute('aria-expanded', 'false');
    expect(pressCardShown()).toBeNull();
  });

  it('closes the card when the mouse leaves the avatar', async () => {
    const user = userEvent.setup();
    const { cami } = show();
    await user.hover(cami);
    expect(pressCardShown()).not.toBeNull();
    await user.unhover(cami);
    expect(cami).toHaveAttribute('aria-expanded', 'false');
    expect(pressCardShown()).toBeNull();
  });

  it('opens and closes the card with a tap on a touch screen', async () => {
    const user = userEvent.setup();
    const { cami, hugo } = show();
    await user.pointer({ keys: '[TouchA]', target: cami });
    expect(cami).toHaveAttribute('aria-expanded', 'true');
    expect(pressCardShown()).not.toBeNull();
    await user.pointer({ keys: '[TouchA]', target: cami });
    expect(pressCardShown()).toBeNull();

    // A tap elsewhere closes it too.
    await user.pointer({ keys: '[TouchA]', target: cami });
    await user.pointer({ keys: '[TouchA]', target: hugo });
    expect(cami).toHaveAttribute('aria-expanded', 'false');
    expect(hugo).toHaveAttribute('aria-expanded', 'true');
  });

  it('opens with the keyboard; Escape or the focus moving on closes it', async () => {
    const user = userEvent.setup();
    const { cami, hugo } = show();
    await user.tab();
    expect(cami).toHaveFocus();
    await user.keyboard('{Enter}');
    expect(pressCardShown()).not.toBeNull();
    await user.keyboard('{Escape}');
    expect(pressCardShown()).toBeNull();

    await user.keyboard('{Enter}');
    expect(pressCardShown()).not.toBeNull();
    await user.tab();
    expect(hugo).toHaveFocus();
    expect(pressCardShown()).toBeNull();
  });

  it('opens over the avatar when the screen ends under the card, if it fits there', async () => {
    // jsdom lays nothing out: here the card is told where it would be, under the avatar or over
    // it, on jsdom's screen of 768 px.
    const places = { under: [700, 924], over: [460, 692] };
    const layout = vi
      .spyOn(HTMLElement.prototype, 'getBoundingClientRect')
      .mockImplementation(function (this: HTMLElement) {
        const [top = 0, bottom = 0] = this.hasAttribute('data-above') ? places.over : places.under;
        return {
          x: 100,
          y: top,
          left: 100,
          right: 420,
          top,
          bottom,
          width: 320,
          height: bottom - top,
        } as DOMRect;
      });
    try {
      const user = userEvent.setup();
      const { cami } = show();
      await user.hover(cami);
      expect(pressCardShown()?.parentElement).toHaveAttribute('data-above');

      // No room over it either: the card stays under the avatar.
      await user.unhover(cami);
      places.over = [-20, 212];
      await user.hover(cami);
      expect(pressCardShown()?.parentElement).not.toHaveAttribute('data-above');
    } finally {
      layout.mockRestore();
    }
  });

  it('says so when the member left the newsroom', async () => {
    usePressCard.mockReturnValue({
      data: undefined,
      isError: true,
      error: new ApiError(404, { error: { code: 'not_found', message: 'Introuvable.' } }),
    });
    const user = userEvent.setup();
    const { cami } = show();
    await user.hover(cami);
    expect(screen.getByText('Cami ne fait plus partie de la rédaction.')).toBeVisible();
  });
});
