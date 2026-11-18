// Editing a prono (« Modifier » on its page, FR-035): before the first bet every field changes;
// after it, what the bets were placed on is greyed with why (the type, the choices, the unit, the
// gain, the open-ended date), the closing only moves later, and only what changed is sent. A
// closed prono keeps its closing: a relaunch reopens it. The prono's page lists the edits, each
// field as it was and as it is, the latest first.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import type { LockedField, PronoDetail } from '../../src/features/pronos/api';
import { EditPronoPage } from '../../src/features/pronos/CreatePronoPage';
import { PronoHistory } from '../../src/features/pronos/PronoHistory';

// What the server answers: the prono, and the edit's error if it refuses one.
const server = vi.hoisted(() => ({
  prono: undefined as unknown,
  error: null as unknown,
  edit: vi.fn(),
}));

vi.mock('../../src/features/pronos/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/pronos/api')>()),
  useProno: () => ({ data: server.prono }),
  useSections: () => ({
    data: [
      { id: 'general', name: 'Général', position: 0 },
      { id: 'foot', name: 'Foot', position: 1 },
    ],
  }),
  useEditProno: () => ({ mutate: server.edit, isPending: false, error: server.error }),
  useCreateProno: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useUpload: () => ({ mutate: vi.fn(), isPending: false, error: null }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { max_base_gain: 50, my_membership: { role: 'journalist' } } }),
}));

afterEach(() => {
  cleanup();
  server.edit.mockReset();
  server.error = null;
});

const AFTER_BETS: LockedField[] = [
  'kind',
  'options',
  'open_ended',
  'base_gain',
  'number_unit',
  'opens_at',
];
const LOCKED = 'VERROUILLÉ : DES PARIS ONT DÉJÀ ÉTÉ FAITS';
// Saturday 21 November, 18:00 in Paris.
const CLOSING = '2026-11-21T17:00:00Z';

const option = (label: string) => ({
  id: label,
  label,
  is_correct: null,
  count: 0,
  stake_total: 0,
  share_pct: 0,
});

function prono(over: Record<string, unknown> = {}): PronoDetail {
  return {
    id: 'p1',
    kind: 'choice',
    question: 'Nice ou Monaco samedi ?',
    section: { id: 'general', name: 'Général', position: 0 },
    options: [option('Nice'), option('Nul'), option('Monaco')],
    number_unit: null,
    open_ended: false,
    link_url: null,
    image_id: null,
    image_url: null,
    opens_at: null,
    closes_at: CLOSING,
    result_expected_at: null,
    base_gain: 20,
    state: 'open',
    bet_count: 0,
    can_edit: true,
    locked_fields: [],
    events: [],
    ...over,
  } as unknown as PronoDetail;
}

function page() {
  return (
    <MemoryRouter initialEntries={['/o/org/pronos/p1/modifier']}>
      <Routes>
        <Route path="/o/:orgId/pronos/:pronoId/modifier" element={<EditPronoPage />} />
        <Route path="/o/:orgId/pronos/:pronoId" element={<p>La page du prono</p>} />
      </Routes>
    </MemoryRouter>
  );
}

function open(data: PronoDetail) {
  server.prono = data;
  return render(page());
}

const save = () => screen.getByRole('button', { name: 'Enregistrer les modifications' });
const question = () => screen.getByRole('textbox', { name: 'LA QUESTION' });
const closing = () => screen.getByLabelText('CLÔTURE DES PRONOS');
const kinds = () =>
  ['CHOIX', 'OUI/NON', 'NOMBRE', 'DATE'].map((name) => screen.getByRole('button', { name }));
const gain = () => screen.getByRole('group', { name: 'Gain fixe si juste' });
/** What the form sent, once saved. */
const sent = () => server.edit.mock.calls[0]?.[0] as Record<string, unknown>;

describe('editing a prono before the first bet', () => {
  it('changes everything and sends only what changed', async () => {
    const user = userEvent.setup();
    open(prono());
    expect(screen.getByRole('heading', { name: 'Modifier le prono' })).toBeInTheDocument();
    expect(screen.queryByRole('note')).toBeNull();
    expect(save()).toBeDisabled();
    for (const button of kinds()) expect(button).toBeEnabled();
    expect(screen.getByRole('textbox', { name: 'Choix 1' })).toBeEnabled();
    for (const button of within(gain()).getAllByRole('button')) expect(button).toBeEnabled();
    expect(closing()).not.toHaveAttribute('min');

    await user.click(screen.getByRole('button', { name: 'OUI/NON' }));
    await user.clear(question());
    await user.type(question(), 'Nice gagne ?');
    await user.click(within(gain()).getByRole('button', { name: 'Plus' }));
    await user.click(save());
    expect(sent()).toEqual({
      kind: 'yes_no',
      question: 'Nice gagne ?',
      options: [],
      base_gain: 25,
    });

    // Saved: back to the prono's page.
    const [, { onSuccess }] = server.edit.mock.calls[0] as [unknown, { onSuccess: () => void }];
    act(() => onSuccess());
    expect(screen.getByText('La page du prono')).toBeInTheDocument();
  });

  it('leads back to the prono once it no longer changes', () => {
    open(prono({ state: 'resolved', bet_count: 2, can_edit: false }));
    expect(screen.getByText('La page du prono')).toBeInTheDocument();
  });
});

describe('editing a prono after the first bet', () => {
  it('greys what was bet on, says why, and sends the rest', async () => {
    const user = userEvent.setup();
    open(prono({ bet_count: 2, locked_fields: AFTER_BETS }));
    expect(screen.getByRole('note')).toHaveTextContent(
      "Déjà 2 paris sur ce prono : pour garder le sens des paris, le type, les choix, l'unité et le gain fixe ne changent plus",
    );

    // The type, the choices and the gain: greyed, each with why.
    for (const button of kinds()) expect(button).toBeDisabled();
    expect(screen.getAllByRole('group', { name: 'TYPE' }).at(-1)).toHaveAccessibleDescription(
      LOCKED,
    );
    const choices = screen.getByRole('group', { name: 'LES CHOIX · 3' });
    expect(choices).toHaveAccessibleDescription(LOCKED);
    for (const input of within(choices).getAllByRole('textbox')) expect(input).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Ajouter un choix' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^Retirer le choix/ })).toBeNull();
    for (const button of within(gain()).getAllByRole('button')) expect(button).toBeDisabled();
    expect(gain()).toHaveAccessibleDescription(LOCKED);
    // The prono is open: nothing to say about its opening any more.
    expect(screen.queryByRole('switch', { name: /Ouvrir les pronos plus tard/ })).toBeNull();

    // The wording, the section, the link and the dates still change; the closing only later.
    expect(question()).toBeEnabled();
    expect(screen.getByRole('textbox', { name: "LIEN VERS L'ARTICLE (FACULTATIF)" })).toBeEnabled();
    expect(closing()).toBeEnabled();
    expect(closing()).toHaveAttribute('min', '2026-11-21T18:00');
    expect(closing()).toHaveAccessibleDescription(
      'SEULEMENT PLUS TARD : DES PARIS ONT DÉJÀ ÉTÉ FAITS',
    );

    await user.clear(question());
    await user.type(question(), 'Nice ou Monaco dimanche ?');
    await user.click(screen.getByRole('button', { name: 'FOOT' }));
    fireEvent.change(closing(), { target: { value: '2026-11-22T18:00' } });
    await user.click(save());
    expect(sent()).toEqual({
      question: 'Nice ou Monaco dimanche ?',
      section_id: 'foot',
      closes_at: '2026-11-22T17:00:00.000Z',
    });
  });

  it('greys the unit of a number and the open end of a date', () => {
    open(
      prono({
        kind: 'number',
        options: [],
        number_unit: 'buts',
        bet_count: 1,
        locked_fields: AFTER_BETS,
      }),
    );
    const unit = screen.getByRole('textbox', { name: 'UNITÉ (FACULTATIF)' });
    expect(unit).toBeDisabled();
    expect(unit).toHaveValue('buts');
    expect(unit).toHaveAccessibleDescription(LOCKED);
    cleanup();

    open(
      prono({
        kind: 'date',
        options: [],
        open_ended: true,
        closes_at: null,
        bet_count: 1,
        locked_fields: AFTER_BETS,
      }),
    );
    const openEnded = screen.getByRole('switch', { name: /Sans date de clôture/ });
    expect(openEnded).toBeDisabled();
    expect(openEnded).toBeChecked();
    expect(openEnded).toHaveTextContent(LOCKED);
    expect(screen.queryByLabelText('CLÔTURE DES PRONOS')).toBeNull();
  });

  it('keeps the closing of a closed prono: a relaunch reopens it', () => {
    open(
      prono({
        state: 'closed',
        closes_at: '2026-11-14T17:00:00Z',
        bet_count: 1,
        locked_fields: [...AFTER_BETS, 'closes_at'],
      }),
    );
    expect(screen.getByRole('note')).toHaveTextContent(
      'Pour rouvrir les paris avec une nouvelle clôture, relance le prono depuis sa page.',
    );
    expect(closing()).toBeDisabled();
    expect(closing()).toHaveValue('2026-11-14T18:00');
    expect(closing()).toHaveAccessibleDescription(
      'VERROUILLÉ : LES PRONOS SONT CLOS, UNE RELANCE LES ROUVRE',
    );
    expect(question()).toBeEnabled();
  });

  it('shows a field locked meanwhile as the server has it, and leaves it out', async () => {
    const user = userEvent.setup();
    const { rerender } = open(prono());
    await user.click(screen.getByRole('button', { name: 'OUI/NON' }));
    await user.clear(question());
    await user.type(question(), 'Nice gagne samedi ?');
    // Someone bets while the form is open: the type locks, as it was.
    server.prono = prono({ bet_count: 1, locked_fields: AFTER_BETS });
    rerender(page());
    expect(screen.getByRole('button', { name: 'CHOIX' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: 'CHOIX' })).toBeDisabled();
    await user.click(save());
    expect(sent()).toEqual({ question: 'Nice gagne samedi ?' });
  });

  it('says why the server refused a field', () => {
    server.error = new ApiError(422, {
      error: {
        code: 'validation_error',
        message: 'Certains champs sont invalides.',
        fields: { closes_at: 'not_later' },
      },
    });
    open(prono({ bet_count: 2, locked_fields: AFTER_BETS }));
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Des paris ont déjà été faits : la clôture peut seulement être repoussée.',
    );
  });
});

describe("a prono's edits", () => {
  const hugo = { id: 'hugo', pseudo: 'Hugo' };
  const ines = { id: 'ines', pseudo: 'Inès' };

  it('lists each change, as it was and as it is, the latest first', () => {
    render(
      <PronoHistory
        prono={prono({
          events: [
            { kind: 'created', at: '2026-11-17T09:00:00Z', data: {}, by: hugo },
            {
              kind: 'edited',
              at: '2026-11-18T13:05:00Z',
              data: {
                changes: [
                  {
                    field: 'question',
                    before: 'Nice ou Monaco samedi ?',
                    after: 'Nice ou Monaco dimanche ?',
                  },
                  { field: 'section', before: 'Général', after: 'Foot' },
                  {
                    field: 'closes_at',
                    before: '2026-11-21T17:00:00+00:00',
                    after: '2026-11-22T17:00:00+00:00',
                  },
                  { field: 'image', before: null, after: 'affiche' },
                ],
              },
              by: hugo,
            },
            {
              kind: 'edited',
              at: '2026-11-19T08:00:00Z',
              data: {
                changes: [
                  { field: 'result_expected_at', before: null, after: '2026-11-23T10:00:00+00:00' },
                ],
              },
              by: ines,
            },
          ],
        })}
      />,
    );
    const history = screen.getByRole('region', { name: 'Les modifications' });
    const [latest, first] = within(history).getAllByRole('listitem');
    expect(latest).toHaveTextContent('JEU. 19 NOV.');
    expect(latest).toHaveTextContent('PAR INÈS');
    expect(within(latest!).getByRole('deletion')).toHaveTextContent('Avant : aucune');
    expect(within(latest!).getByRole('insertion')).toHaveTextContent(/Après : lundi 23 novembre/);

    expect(first).toHaveTextContent('PAR HUGO');
    const terms = within(first!)
      .getAllByRole('term')
      .map((term) => term.textContent);
    expect(terms).toEqual(['QUESTION', 'RUBRIQUE', 'CLÔTURE', 'IMAGE']);
    const [wasAsked, wasFiled, wasClosing] = within(first!).getAllByRole('deletion');
    const [asked, filed, closingNow] = within(first!).getAllByRole('insertion');
    expect(wasAsked).toHaveTextContent('Nice ou Monaco samedi ?');
    expect(asked).toHaveTextContent('Nice ou Monaco dimanche ?');
    expect([wasFiled?.textContent, filed?.textContent]).toEqual([
      'Avant : Général',
      'Après : Foot',
    ]);
    expect(wasClosing).toHaveTextContent(/samedi 21 novembre/);
    expect(closingNow).toHaveTextContent(/dimanche 22 novembre/);
    expect(first).toHaveTextContent('ajoutée');
  });

  it('says nothing for a prono never edited', () => {
    const { container } = render(
      <PronoHistory
        prono={prono({ events: [{ kind: 'created', at: CLOSING, data: {}, by: hugo }] })}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});
