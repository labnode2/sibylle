// « Annuler le résultat »: beside « Corriger le résultat », for the editor on a resolved prono,
// after a confirmation that can be taken back, with an optional reason. The prono's page then says
// the result was taken back, and the members' history names the gains taken back.
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { LedgerList } from '../../src/features/profile/LedgerList';
import type { PronoDetail, PronoEvent } from '../../src/features/pronos/api';
import { DesignatePanel } from '../../src/features/results/DesignatePanel';
import { cancelledResult, ResultCancelled } from '../../src/features/results/ResultCancelled';

const server = vi.hoisted(() => ({
  cancelResult: vi.fn(),
  // The other actions of the panel, never sent here.
  other: vi.fn(),
  ledger: [] as unknown[],
}));

vi.mock('../../src/features/results/api', async (importOriginal) => {
  const action = (mutate: () => void) => () => ({ mutate, isPending: false, error: null });
  return {
    ...(await importOriginal<typeof import('../../src/features/results/api')>()),
    useResolve: action(server.other),
    useCorrect: action(server.other),
    useRelaunch: action(server.other),
    useCancel: action(server.other),
    useCancelResult: action(server.cancelResult),
  };
});
vi.mock('../../src/features/profile/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/profile/api')>()),
  useLedger: () => ({ data: { pages: [{ items: server.ledger }] }, hasNextPage: false }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function prono(over: Partial<PronoDetail> = {}): PronoDetail {
  return {
    id: 'p1',
    question: 'Nice ou Monaco samedi ?',
    kind: 'choice',
    state: 'resolved',
    open_ended: false,
    bet_count: 3,
    pot: 40,
    base_gain: 20,
    options: [],
    events: [],
    ...over,
  } as PronoDetail;
}

const ask = () => screen.queryByRole('button', { name: 'Annuler le résultat' });
const confirmation = () => screen.queryByRole('form', { name: 'Annuler le résultat' });

describe('cancelling the result', () => {
  it('sits beside the correction and asks first, then sends the reason', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono()} role="editor" />);
    expect(screen.getByRole('button', { name: 'Corriger le résultat' })).toBeInTheDocument();
    expect(confirmation()).toBeNull();

    await user.click(ask()!);
    const asking = confirmation();
    expect(asking).not.toBeNull();
    expect(asking).toHaveTextContent(
      "Les gains versés seront repris et le prono attendra un nouveau résultat : les pronostics et leurs mises restent en jeu. Confirmer l'annulation du résultat ?",
    );
    expect(server.cancelResult).not.toHaveBeenCalled();

    await user.type(within(asking!).getByLabelText('MOTIF (FACULTATIF)'), '  Score mal saisi ');
    await user.click(
      within(asking!).getByRole('button', { name: "Confirmer l'annulation du résultat" }),
    );
    expect(server.cancelResult).toHaveBeenCalledOnce();
    expect(server.cancelResult).toHaveBeenCalledWith({ reason: 'Score mal saisi' });
    expect(server.other).not.toHaveBeenCalled();
  });

  it('sends no reason when none is given', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono()} role="editor" />);
    await user.click(ask()!);
    await user.click(screen.getByRole('button', { name: "Confirmer l'annulation du résultat" }));
    expect(server.cancelResult).toHaveBeenCalledExactlyOnceWith({ reason: null });
  });

  it('changes nothing when the confirmation is taken back', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono()} role="editor" />);
    await user.click(ask()!);
    await user.click(within(confirmation()!).getByRole('button', { name: 'Retour' }));
    expect(confirmation()).toBeNull();
    expect(ask()).toBeInTheDocument();
    expect(server.cancelResult).not.toHaveBeenCalled();
  });

  it('is offered to the editor on a resolved prono only', () => {
    const cases: [PronoDetail, 'reader' | 'journalist' | 'editor'][] = [
      [prono(), 'journalist'],
      [prono(), 'reader'],
      [prono({ state: 'closed' }), 'editor'],
      [prono({ state: 'cancelled' }), 'editor'],
    ];
    for (const [shown, role] of cases) {
      const { unmount } = render(<DesignatePanel orgId="org" prono={shown} role={role} />);
      expect(ask()).toBeNull();
      unmount();
    }
  });
});

const event = (kind: string, data: Record<string, unknown> = {}): PronoEvent => ({
  kind,
  at: '2026-11-18T10:00:00Z',
  data,
  by: null,
});

describe('a prono whose result was cancelled', () => {
  it('says so on its page while it waits for a new result, with the reason', () => {
    const waiting = prono({
      state: 'closed',
      events: [event('resolved'), event('result_cancelled', { reason: 'Score mal saisi' })],
    });
    const taken = cancelledResult(waiting);
    expect(taken).not.toBeNull();
    render(<ResultCancelled event={taken!} />);
    expect(screen.getByText(/^Résultat annulé/)).toHaveTextContent(
      "Résultat annulé : les gains sont repris, les pronostics et leurs mises restent en jeu jusqu'au nouveau résultat. Motif : « Score mal saisi »",
    );
  });

  it('says nothing more once resolved again or moved on', () => {
    const taken = event('result_cancelled', { reason: null });
    expect(cancelledResult(prono({ state: 'open', events: [taken] }))).toBe(taken);
    expect(cancelledResult(prono({ events: [taken, event('resolved')] }))).toBeNull();
    expect(
      cancelledResult(prono({ state: 'open', events: [taken, event('relaunched')] })),
    ).toBeNull();
    expect(cancelledResult(prono({ state: 'cancelled', events: [taken] }))).toBeNull();
    render(<ResultCancelled event={taken} />);
    expect(screen.getByText(/^Résultat annulé/)).not.toHaveTextContent('Motif');
  });

  it('names the gains taken back in the history', () => {
    const entry = (id: number, settlement_kind: string | null, amount: number) => ({
      id,
      kind: 'reversal',
      amount,
      score_delta: amount,
      reason: null,
      settlement_kind,
      prono: { id: 'p1', question: 'Nice ou Monaco samedi ?', deleted: false },
      created_at: '2026-11-18T10:00:00Z',
    });
    server.ledger = [entry(2, 'result_cancellation', -40), entry(1, 'correction', -20)];
    render(
      <MemoryRouter>
        <LedgerList orgId="org" />
      </MemoryRouter>,
    );
    expect(screen.getByText(/^RÉSULTAT ANNULÉ · /)).toBeInTheDocument();
    expect(screen.getByText(/^CORRECTION · /)).toBeInTheDocument();
  });
});
