// Deleting a cancelled prono (« Supprimer le prono » on its page): only for whoever the server
// allows (`can_delete`, the editor), after a confirmation that can be taken back; once deleted, the
// page goes on to the list. A deleted prono's page says it cannot be found, and the members'
// history keeps its refunds without a link to it.
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import { LedgerList } from '../../src/features/profile/LedgerList';
import type { PronoDetail } from '../../src/features/pronos/api';
import { DeleteProno } from '../../src/features/pronos/DeleteProno';
import { PronoPage } from '../../src/features/pronos/PronoPage';

const server = vi.hoisted(() => ({
  prono: { data: undefined, error: null } as { data: unknown; error: unknown },
  // The deletion: it succeeds unless a test says otherwise.
  remove: vi.fn((_: unknown, options?: { onSuccess?: () => void }) => options?.onSuccess?.()),
  ledger: [] as unknown[],
}));

vi.mock('../../src/features/pronos/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/pronos/api')>()),
  useProno: () => server.prono,
  usePlaceBet: () => ({ mutate: vi.fn(), isPending: false, error: null }),
  useDeleteProno: () => ({ mutate: server.remove, isPending: false }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { title: 'La Gazette', my_membership: { id: 'm1', role: 'editor' } } }),
}));
vi.mock('../../src/features/notifications/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/notifications/api')>()),
  useReadProno: () => undefined,
}));
vi.mock('../../src/features/profile/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/profile/api')>()),
  useLedger: () => ({ data: { pages: [{ items: server.ledger }] }, hasNextPage: false }),
}));

afterEach(() => {
  cleanup();
  server.remove.mockClear();
});

function prono(over: Partial<PronoDetail> = {}): PronoDetail {
  return {
    id: 'p1',
    question: 'Nice ou Monaco samedi ?',
    state: 'cancelled',
    can_delete: true,
    ...over,
  } as PronoDetail;
}

function at(path: string, element: React.ReactNode) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/o/:orgId/pronos/:pronoId" element={element} />
        <Route path="/o/:orgId/pronos" element={<p>La liste des pronos</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

const ask = () => screen.getByRole('button', { name: 'Supprimer le prono' });
const confirmation = () => screen.queryByRole('group', { name: 'Supprimer le prono' });

describe('deleting a cancelled prono', () => {
  it('asks first, then deletes it and goes on to the list', async () => {
    const user = userEvent.setup();
    at('/o/org/pronos/p1', <DeleteProno orgId="org" prono={prono()} />);
    expect(confirmation()).toBeNull();

    await user.click(ask());
    const asking = confirmation();
    expect(asking).not.toBeNull();
    expect(asking).toHaveTextContent(
      "Le prono disparaîtra des listes pour toute la rédaction. Les mises rendues restent dans l'historique de chacun·e. Confirmer la suppression ?",
    );
    expect(server.remove).not.toHaveBeenCalled();

    await user.click(within(asking!).getByRole('button', { name: 'Confirmer la suppression' }));
    expect(server.remove).toHaveBeenCalledOnce();
    expect(await screen.findByText('La liste des pronos')).toBeInTheDocument();
  });

  it('changes nothing when the confirmation is taken back', async () => {
    const user = userEvent.setup();
    at('/o/org/pronos/p1', <DeleteProno orgId="org" prono={prono()} />);
    await user.click(ask());
    await user.click(screen.getByRole('button', { name: 'Retour' }));
    expect(confirmation()).toBeNull();
    expect(ask()).toBeInTheDocument();
    expect(server.remove).not.toHaveBeenCalled();
  });

  it('stays on the page when the server refuses', async () => {
    const user = userEvent.setup();
    server.remove.mockImplementationOnce(() => undefined);
    at('/o/org/pronos/p1', <DeleteProno orgId="org" prono={prono()} />);
    await user.click(ask());
    await user.click(screen.getByRole('button', { name: 'Confirmer la suppression' }));
    expect(server.remove).toHaveBeenCalledOnce();
    expect(screen.queryByText('La liste des pronos')).toBeNull();
  });

  it('is offered only where the server allows it', () => {
    // Another state, or a journalist or a reader: `can_delete` is false.
    at('/o/org/pronos/p1', <DeleteProno orgId="org" prono={prono({ can_delete: false })} />);
    expect(screen.queryByRole('button', { name: 'Supprimer le prono' })).toBeNull();
  });
});

describe('a deleted prono', () => {
  it('has a page that says it cannot be found, with the way to the list', async () => {
    const user = userEvent.setup();
    server.prono = {
      data: undefined,
      error: new ApiError(404, { error: { code: 'not_found', message: 'Introuvable.' } }),
    };
    at('/o/org/pronos/p1', <PronoPage />);
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Ce prono est introuvable : il a peut-être été supprimé.',
    );
    expect(screen.queryByText('Chargement…')).toBeNull();
    await user.click(screen.getByRole('link', { name: 'Voir les pronos' }));
    expect(await screen.findByText('La liste des pronos')).toBeInTheDocument();
  });

  it('keeps its refunds in the history, without a link to it', () => {
    server.ledger = [
      {
        id: 3,
        kind: 'refund',
        amount: 30,
        score_delta: 0,
        reason: null,
        prono: { id: 'p1', question: 'Nice ou Monaco samedi ?', deleted: true },
        created_at: '2026-11-18T10:00:00Z',
      },
      {
        id: 2,
        kind: 'stake',
        amount: -10,
        score_delta: 0,
        reason: null,
        prono: { id: 'p2', question: 'Le pot aura-t-il lieu ?', deleted: false },
        created_at: '2026-11-18T09:00:00Z',
      },
    ];
    render(
      <MemoryRouter>
        <LedgerList orgId="org" />
      </MemoryRouter>,
    );
    expect(screen.getByText('Nice ou Monaco samedi ? (prono supprimé)')).toBeInTheDocument();
    expect(screen.getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual([
      '/o/org/pronos/p2',
    ]);
  });
});
