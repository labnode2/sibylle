// The stake (card #23): every bet stakes at least one laurel and at most the balance. The stake is
// typed to the laurel in the stepper's field, or moved by 5 with « − » and « + »; the pot shown on
// a phone and on a computer follows it as it is typed, and only a whole number within the bounds
// goes to the server. Below one laurel, the page says why no bet is possible. Each answer shows its
// share of the laurels staked, with how many people played it.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import type { PronoDetail } from '../../src/features/pronos/api';
import { PronoPage } from '../../src/features/pronos/PronoPage';
import { DesignatePanel } from '../../src/features/results/DesignatePanel';
import { Stepper } from '../../src/ui/components';
import { toast } from '../../src/ui/Toaster';

// What the server holds: the prono, the member's balance, and the bets sent.
const server = vi.hoisted(() => ({
  prono: undefined as unknown,
  balance: 100,
  // A bet is taken unless a test says otherwise.
  bet: vi.fn((_: unknown, options?: { onSuccess?: () => void }) => options?.onSuccess?.()),
  // The server's answer to the last bet, when it refused it.
  error: null as unknown,
}));

vi.mock('../../src/features/pronos/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/pronos/api')>()),
  useProno: () => ({ data: server.prono, error: null }),
  usePlaceBet: () => ({ mutate: server.bet, isPending: false, error: server.error }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({
    data: {
      title: 'La Gazette',
      my_membership: { id: 'me', role: 'reader', balance: server.balance },
    },
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
vi.mock('../../src/ui/Toaster', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/ui/Toaster')>()),
  toast: { success: vi.fn(), error: vi.fn() },
}));

beforeEach(() => {
  server.balance = 100;
  server.prono = prono();
  server.error = null;
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const option = (id: string, label: string, count: number, stake: number, pct: number) => ({
  id,
  label,
  is_correct: null,
  count,
  stake_total: stake,
  share_pct: pct,
});

/** « Nice ou Monaco samedi ? », open, with a pot of 40: one person staked 30 on Nice, three
 *  staked 10 in all on Monaco. */
function prono(over: Record<string, unknown> = {}): PronoDetail {
  return {
    id: 'p1',
    number: 7,
    kind: 'choice',
    question: 'Nice ou Monaco samedi ?',
    section: { id: 'sport', name: 'Sport', position: 0 },
    created_by: { id: 'hugo', pseudo: 'Hugo', avatar: null },
    options: [option('nice', 'Nice', 1, 30, 75), option('monaco', 'Monaco', 3, 10, 25)],
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
    bet_count: 4,
    pot: 40,
    message_count: 0,
    bets: [],
    my_bet: null,
    can_rebet: false,
    can_edit: false,
    can_delete: false,
    locked_fields: [],
    events: [],
    my_reports: [],
    reactions: {},
    my_reactions: [],
    ...over,
  } as unknown as PronoDetail;
}

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

const field = () => screen.getByRole('textbox', { name: 'Ta mise' });
const less = () => screen.getByRole('button', { name: 'Moins' });
const more = () => screen.getByRole('button', { name: 'Plus' });
const submit = () => screen.getByRole('button', { name: /Valider mon prono/ });
/** The pot as a phone shows it under the stake, and as a computer shows it in large. */
const pots = (laurels: number) => [
  screen.getByText(`Cagnotte : ${laurels} lauriers, partagés entre les gagnants`),
  screen.getByText(`${laurels} lauriers`),
];

/** The stake's stepper alone, as the prono page sets it: from 1 to the balance, by 5. */
function StakeStepper({ max, heard }: { max: number; heard?: (value: number) => void }) {
  const [value, setValue] = useState(1);
  return (
    <Stepper
      label="Ta mise"
      value={value}
      onChange={(next) => {
        heard?.(next);
        setValue(next);
      }}
      min={1}
      max={max}
      step={5}
      typed
    />
  );
}

describe('the stake stepper', () => {
  it('is a field where the exact stake is typed, between « − » and « + »', async () => {
    const user = userEvent.setup();
    const heard = vi.fn();
    render(<StakeStepper max={100} heard={heard} />);
    expect(screen.getByRole('group', { name: 'Ta mise' })).toBeInTheDocument();
    expect(field()).toHaveValue('1');
    expect(field()).toHaveAttribute('inputmode', 'numeric');

    await user.clear(field());
    await user.type(field(), '42');
    expect(field()).toHaveValue('42');
    expect(heard).toHaveBeenLastCalledWith(42);
    // The buttons go on from the typed stake, to the round numbers around it.
    await user.click(more());
    expect(field()).toHaveValue('45');
    await user.click(less());
    await user.click(less());
    expect(field()).toHaveValue('35');
  });

  it('moves by 5 with the buttons, from 1 up to the balance and back', async () => {
    const user = userEvent.setup();
    render(<StakeStepper max={23} />);
    expect(less()).toBeDisabled();
    const seen = [];
    for (let i = 0; i < 5; i += 1) {
      await user.click(more());
      seen.push((field() as HTMLInputElement).value);
    }
    expect(seen).toEqual(['5', '10', '15', '20', '23']);
    expect(more()).toBeDisabled();
    // What the buttons set is heard by screen readers.
    expect(screen.getByText('23', { selector: '[aria-live="polite"]' })).toBeInTheDocument();
    seen.length = 0;
    for (let i = 0; i < 5; i += 1) {
      await user.click(less());
      seen.push((field() as HTMLInputElement).value);
    }
    expect(seen).toEqual(['20', '15', '10', '5', '1']);
    expect(less()).toBeDisabled();
  });

  it('keeps a typed stake within 1 and the balance, shown once the field is left', async () => {
    const user = userEvent.setup();
    const heard = vi.fn();
    render(<StakeStepper max={100} heard={heard} />);

    await user.clear(field());
    await user.type(field(), '250');
    expect(heard).toHaveBeenLastCalledWith(100);
    await user.tab();
    expect(field()).toHaveValue('100');
    expect(more()).toBeDisabled();

    await user.clear(field());
    await user.type(field(), '0');
    expect(heard).toHaveBeenLastCalledWith(1);
    await user.type(field(), '{Enter}');
    expect(field()).toHaveValue('1');
    expect(less()).toBeDisabled();
  });

  it('takes digits only, and an emptied field keeps the stake it had', async () => {
    const user = userEvent.setup();
    const heard = vi.fn();
    render(<StakeStepper max={100} heard={heard} />);

    await user.clear(field());
    await user.type(field(), '2,5 lauriers');
    expect(field()).toHaveValue('25');
    expect(heard).toHaveBeenLastCalledWith(25);
    expect(heard.mock.calls.every(([value]) => Number.isInteger(value))).toBe(true);

    heard.mockClear();
    await user.clear(field());
    expect(field()).toHaveValue('');
    expect(heard).not.toHaveBeenCalled();
    await user.tab();
    expect(field()).toHaveValue('25');
  });
});

describe('betting on a prono', () => {
  it('starts at one laurel, and the pot shown follows the stake as it is typed', async () => {
    const user = userEvent.setup();
    openPage();
    expect(field()).toHaveValue('1');
    expect(submit()).toHaveTextContent('MISE 1');
    expect(screen.getByText('TA MISE · 100 LAURIERS VERTS À MISER')).toBeInTheDocument();
    for (const shown of pots(41)) expect(shown).toBeInTheDocument();

    await user.clear(field());
    await user.type(field(), '25');
    // Still in the field: the pot on a phone and on a computer has followed.
    expect(field()).toHaveFocus();
    for (const shown of pots(65)) expect(shown).toBeInTheDocument();
    expect(submit()).toHaveTextContent('MISE 25');

    await user.click(more());
    expect(field()).toHaveValue('30');
    for (const shown of pots(70)) expect(shown).toBeInTheDocument();
  });

  it('sends a whole stake within one laurel and the balance', async () => {
    const user = userEvent.setup();
    openPage();
    await user.click(screen.getByRole('button', { name: /^Nice/ }));
    await user.clear(field());
    await user.type(field(), '250');
    await user.click(submit());
    expect(server.bet).toHaveBeenCalledOnce();
    expect(server.bet.mock.calls[0]![0]).toEqual({ option_id: 'nice', stake: 100 });
    expect(toast.success).toHaveBeenCalledWith('Pari enregistré : 100 lauriers misés.');
    // Back to one laurel for the next bet.
    expect(field()).toHaveValue('1');

    // A field emptied or set to 0 still sends a stake of one laurel at least.
    await user.clear(field());
    await user.click(submit());
    await user.clear(field());
    await user.type(field(), '0');
    await user.click(submit());
    expect(server.bet.mock.calls.slice(1).map(([body]) => body)).toEqual([
      { option_id: 'nice', stake: 1 },
      { option_id: 'nice', stake: 1 },
    ]);
  });

  it('says why no bet is possible below one laurel, instead of a dead button', () => {
    for (const [balance, shown] of [
      [0, '0'],
      [-10, '-10'],
    ] as const) {
      server.balance = balance;
      openPage();
      expect(
        screen.getByText(
          `Pour parier, il faut miser au moins 1 laurier vert : ton solde est de ${shown}. Tu en regagnes avec tes pronos justes et les jeux de la semaine, et chaque nouvelle saison te rend ton solde de départ.`,
          { normalizer: (text) => text.replace(/−/g, '-') },
        ),
      ).toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /Valider mon prono/ })).toBeNull();
      expect(screen.queryByRole('textbox', { name: 'Ta mise' })).toBeNull();
      expect(screen.getByRole('button', { name: /^Nice/ })).toBeDisabled();
      cleanup();
    }
  });

  it('says in French why the server refused a stake below one laurel', () => {
    // E.g. a page opened before the minimum stake, which sent a bet without a stake.
    server.error = new ApiError(422, {
      error: {
        code: 'validation_error',
        message: 'Vérifie les champs signalés.',
        fields: { stake: 'too_low' },
      },
    });
    openPage();
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Mise trop basse : il faut miser au moins 1 laurier vert.',
    );
  });

  it('with one laurel left, stakes it', async () => {
    const user = userEvent.setup();
    server.balance = 1;
    openPage();
    expect(field()).toHaveValue('1');
    expect(less()).toBeDisabled();
    expect(more()).toBeDisabled();
    await user.click(screen.getByRole('button', { name: /^Monaco/ }));
    await user.click(submit());
    expect(server.bet.mock.calls[0]![0]).toEqual({ option_id: 'monaco', stake: 1 });
  });

  it('asks a new date of an open-ended prono with a stake of one laurel at least', async () => {
    const user = userEvent.setup();
    server.prono = prono({
      kind: 'date',
      options: [],
      open_ended: true,
      closes_at: null,
      my_bet: { answer: '2026-11-19', stake: 0, option_id: null, date_value: '2026-11-19' },
      can_rebet: true,
    });
    openPage();
    // The earlier bet, placed before the minimum, still shows without a stake.
    expect(screen.getByText('sans mise')).toBeInTheDocument();
    await user.type(screen.getByLabelText('TA DATE'), '2026-12-24');
    await user.click(screen.getByRole('button', { name: /Rejouer une date/ }));
    expect(server.bet.mock.calls[0]![0]).toEqual({ date_value: '2026-12-24', stake: 1 });
  });
});

describe('the shares of a prono', () => {
  it('are those of the laurels staked, with the number of people beside them', () => {
    openPage();
    expect(screen.getByRole('button', { name: /^Nice/ })).toHaveTextContent(
      'Nice75 % DES LAURIERS · 1 PERSONNE',
    );
    expect(screen.getByRole('button', { name: /^Monaco/ })).toHaveTextContent(
      'Monaco25 % DES LAURIERS · 3 PERSONNES',
    );
  });

  it('split the numbers and dates in laurels too', () => {
    server.prono = prono({
      kind: 'number',
      options: [],
      distribution: [
        { label: '3', count: 1, stake_total: 30, share_pct: 75 },
        { label: '5', count: 2, stake_total: 10, share_pct: 25 },
      ],
    });
    openPage();
    const split = screen.getByRole('region', { name: 'RÉPARTITION DES PRONOS' });
    expect(within(split).getByText('75 % DES LAURIERS').parentElement).toHaveTextContent(
      '75 % DES LAURIERS · 1 PERSONNE',
    );
    expect(within(split).getByText('25 % DES LAURIERS').parentElement).toHaveTextContent(
      '25 % DES LAURIERS · 2 PERSONNES',
    );
  });

  it('show in laurels where a journalist designates the result', () => {
    render(
      <DesignatePanel orgId="org" prono={prono({ state: 'closed', bets: [] })} role="journalist" />,
      {
        wrapper: ({ children }) => (
          <QueryClientProvider client={new QueryClient()}>{children}</QueryClientProvider>
        ),
      },
    );
    const answers = screen.getByRole('group', { name: 'LA OU LES BONNES RÉPONSES' });
    expect(within(answers).getByRole('button', { name: /^Nice/ })).toHaveTextContent(
      'Nice75 % DES LAURIERS · 1 PERSONNE',
    );
  });
});
