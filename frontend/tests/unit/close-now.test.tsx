// « Clore les paris maintenant » (card #25): on an open prono that has a closing, the newsroom
// stops the bets before their planned time, after a confirmation that can be taken back. The
// prono's page then tells the members it was closed earlier than planned, and the journalist
// designates its result at once, without waiting for the expected result date.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { PronoDetail, PronoEvent } from '../../src/features/pronos/api';
import { PronoPage } from '../../src/features/pronos/PronoPage';
import { DesignatePanel } from '../../src/features/results/DesignatePanel';

type Role = 'reader' | 'journalist' | 'editor';

const server = vi.hoisted(() => ({
  closeNow: vi.fn(),
  // The other actions of the panel, never sent here.
  other: vi.fn(),
  prono: undefined as unknown,
  role: 'reader' as string,
}));

vi.mock('../../src/features/results/api', async (importOriginal) => {
  const action = (mutate: () => void) => () => ({ mutate, isPending: false, error: null });
  return {
    ...(await importOriginal<typeof import('../../src/features/results/api')>()),
    useCloseNow: action(server.closeNow),
    useResolve: action(server.other),
    useCorrect: action(server.other),
    useRelaunch: action(server.other),
    useCancel: action(server.other),
    useCancelResult: action(server.other),
  };
});
vi.mock('../../src/features/pronos/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/pronos/api')>()),
  useProno: () => ({ data: server.prono, error: null }),
  usePlaceBet: () => ({ mutate: vi.fn(), isPending: false, error: null }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({
    data: { title: 'La Gazette', my_membership: { id: 'me', role: server.role, balance: 100 } },
  }),
}));
vi.mock('../../src/features/notifications/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/notifications/api')>()),
  useReadProno: () => undefined,
}));
vi.mock('../../src/features/notifications/PushPrompt', () => ({ PushPrompt: () => null }));
// The rest of the page (discussion, reactions…) waits for a server that never answers here.
vi.mock('../../src/api/client', async (importOriginal) => {
  const never = () => new Promise(() => undefined);
  return {
    ...(await importOriginal<typeof import('../../src/api/client')>()),
    api: { GET: never, POST: never, PUT: never, PATCH: never, DELETE: never },
  };
});
vi.mock('../../src/api/realtime', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/api/realtime')>()),
  useTopic: () => undefined,
}));

beforeEach(() => {
  server.role = 'reader';
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const event = (kind: string, data: Record<string, unknown> = {}): PronoEvent => ({
  kind,
  at: '2026-11-19T21:30:00Z',
  data,
  by: null,
});

/** « Nice ou Monaco samedi ? », open until Saturday 18:00 (Paris), three bets in. */
function prono(over: Record<string, unknown> = {}): PronoDetail {
  return {
    id: 'p1',
    number: 7,
    kind: 'choice',
    question: 'Nice ou Monaco samedi ?',
    section: { id: 'sport', name: 'Sport', position: 0 },
    created_by: { id: 'hugo', pseudo: 'Hugo', avatar: null },
    options: [
      { id: 'nice', label: 'Nice', is_correct: null, count: 2, stake_total: 30, share_pct: 75 },
      { id: 'monaco', label: 'Monaco', is_correct: null, count: 1, stake_total: 10, share_pct: 25 },
    ],
    distribution: [],
    number_unit: null,
    open_ended: false,
    link_url: null,
    image_url: null,
    opens_at: null,
    closes_at: '2026-11-21T17:00:00Z',
    result_expected_at: null,
    base_gain: 20,
    state: 'open',
    bet_count: 3,
    pot: 40,
    relaunch_count: 0,
    message_count: 0,
    bets: [],
    my_bet: null,
    can_rebet: false,
    can_edit: false,
    can_delete: false,
    locked_fields: [],
    events: [event('created')],
    my_reports: [],
    reactions: {},
    my_reactions: [],
    ...over,
  } as unknown as PronoDetail;
}

const ask = () => screen.queryByRole('button', { name: 'Clore les paris maintenant' });
const confirmation = () => screen.queryByRole('form', { name: 'Clore les paris maintenant' });

describe('closing the bets now', () => {
  it('is offered to the newsroom on an open prono, under what it does', () => {
    for (const role of ['journalist', 'editor'] as const) {
      const { unmount } = render(<DesignatePanel orgId="org" prono={prono()} role={role} />);
      expect(ask()).toBeInTheDocument();
      expect(
        screen.getByText("LES PARIS S'ARRÊTENT AVANT LA CLÔTURE PRÉVUE, PRONOSTICS CONSERVÉS"),
      ).toBeInTheDocument();
      expect(confirmation()).toBeNull();
      unmount();
    }
  });

  it('is not offered to readers, on an open-ended date or on a prono that is not open', () => {
    const cases: [PronoDetail, Role][] = [
      [prono(), 'reader'],
      [prono({ kind: 'date', options: [], open_ended: true, closes_at: null }), 'journalist'],
      [prono({ state: 'scheduled', opens_at: '2026-11-20T08:00:00Z' }), 'editor'],
      [prono({ state: 'closed' }), 'journalist'],
      [prono({ state: 'resolved' }), 'editor'],
      [prono({ state: 'cancelled' }), 'editor'],
    ];
    for (const [shown, role] of cases) {
      const { unmount } = render(<DesignatePanel orgId="org" prono={shown} role={role} />);
      expect(ask()).toBeNull();
      unmount();
    }
  });

  it('asks first, with the planned closing, then closes', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono()} role="journalist" />);
    await user.click(ask()!);
    const asking = confirmation();
    expect(asking).not.toBeNull();
    expect(asking).toHaveTextContent(
      'Plus personne ne pourra parier : la clôture prévue samedi 21 novembre à 18:00 est avancée à maintenant. Tu pourras désigner le résultat tout de suite. Confirmer la clôture ?',
    );
    expect(server.closeNow).not.toHaveBeenCalled();

    await user.click(within(asking!).getByRole('button', { name: 'Confirmer la clôture' }));
    expect(server.closeNow).toHaveBeenCalledOnce();
    expect(server.other).not.toHaveBeenCalled();
  });

  it('says what comes next when nobody bet', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono({ bet_count: 0, pot: 0 })} role="editor" />);
    await user.click(ask()!);
    expect(confirmation()).toHaveTextContent(
      "Plus personne ne pourra parier : la clôture prévue samedi 21 novembre à 18:00 est avancée à maintenant. Personne n'a joué : tu pourras ensuite le relancer ou l'annuler. Confirmer la clôture ?",
    );
  });

  it('changes nothing when the confirmation is taken back', async () => {
    const user = userEvent.setup();
    render(<DesignatePanel orgId="org" prono={prono()} role="editor" />);
    await user.click(ask()!);
    await user.click(within(confirmation()!).getByRole('button', { name: 'Retour' }));
    expect(confirmation()).toBeNull();
    expect(ask()).toBeInTheDocument();
    expect(server.closeNow).not.toHaveBeenCalled();
  });
});

function openPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/o/org/pronos/p1']}>
        <Routes>
          <Route path="/o/:orgId/pronos/:pronoId" element={<PronoPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Closed by Hugo on Thursday at 22:30 (Paris), two days before its planned closing; its result
 *  is expected on Sunday at 12:00. */
function closedEarly(over: Record<string, unknown> = {}): PronoDetail {
  return prono({
    state: 'closed',
    closes_at: '2026-11-19T21:30:00Z',
    result_expected_at: '2026-11-22T11:00:00Z',
    events: [
      event('created'),
      event('closed', {
        previous_closes_at: '2026-11-21T17:00:00+00:00',
        closes_at: '2026-11-19T21:30:00+00:00',
      }),
    ],
    ...over,
  });
}

describe('a prono closed early', () => {
  it('tells the members the bets closed earlier than planned, and when', () => {
    server.prono = closedEarly();
    openPage();
    expect(
      screen.getByText(
        'Les pronos ont été clos plus tôt que prévu, jeudi 19 novembre à 22:30. Résultat attendu dimanche 22 novembre à 12:00.',
      ),
    ).toBeInTheDocument();
    expect(ask()).toBeNull();
    expect(screen.queryByRole('button', { name: 'Valider mon prono' })).toBeNull();
  });

  it('says so without an expected result date too', () => {
    server.prono = closedEarly({ result_expected_at: null });
    openPage();
    expect(
      screen.getByText(
        'Les pronos ont été clos plus tôt que prévu, jeudi 19 novembre à 22:30. Le résultat arrive bientôt.',
      ),
    ).toBeInTheDocument();
  });

  it('says what it always said once closed at its time', () => {
    server.prono = prono({
      state: 'closed',
      result_expected_at: '2026-11-22T11:00:00Z',
      events: [event('created'), event('closed')],
    });
    openPage();
    expect(
      screen.getByText('Les pronos sont clos. Résultat attendu dimanche 22 novembre à 12:00.'),
    ).toBeInTheDocument();
  });

  it('is closed at its time again after a relaunch', () => {
    server.prono = closedEarly({
      closes_at: '2026-11-25T17:00:00Z',
      events: [
        ...closedEarly().events,
        event('relaunched', { closes_at: '2026-11-25T17:00:00+00:00' }),
        event('closed'),
      ],
    });
    openPage();
    expect(screen.getByText(/^Les pronos sont clos\./)).toBeInTheDocument();
  });

  it('offers the journalist its result at once, before the expected date', async () => {
    const user = userEvent.setup();
    server.role = 'journalist';
    server.prono = closedEarly({ result_expected_at: '2099-01-01T11:00:00Z' });
    openPage();
    const panel = screen.getByRole('region', { name: 'Désigner le résultat' });
    expect(within(panel).getByText('CLOS · EN ATTENTE DE TON VERDICT')).toBeInTheDocument();
    await user.click(within(panel).getByRole('button', { name: /^Nice/ }));
    await user.click(within(panel).getByRole('button', { name: 'Publier le résultat' }));
    expect(server.other).toHaveBeenCalledOnce();
    expect(server.other).toHaveBeenCalledWith({ correct_option_ids: ['nice'] }, expect.anything());
  });
});
