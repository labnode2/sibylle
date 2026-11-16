// Opening a prono reads its notifications: its bubbles leave the menus at once, the server is
// told, the newsroom's bubble in the lists of newsrooms follows, and a prono with nothing waiting
// asks nothing.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { useMe } from '../../src/features/auth/api';
import {
  useReadProno,
  useUnread,
  type UnreadNotifications,
} from '../../src/features/notifications/api';

const server = vi.hoisted(() => ({
  unread: undefined as unknown,
  GET: vi.fn(),
  POST: vi.fn(),
}));
const asked = (path: string) => server.GET.mock.calls.filter(([called]) => called === path).length;
vi.mock('../../src/api/client', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/api/client')>()),
  api: { GET: server.GET, POST: server.POST },
}));

const ok = (data?: unknown) => Promise.resolve({ data, response: { ok: true, status: 200 } });

beforeEach(() => {
  server.unread = {
    total: 3,
    pronos: [
      { prono_id: 'nice', state: 'open', section_id: 'sport', unread: 2 },
      { prono_id: 'pot', state: 'open', section_id: 'sport', unread: 1 },
    ],
  } satisfies UnreadNotifications;
  server.GET.mockImplementation((path: string) =>
    ok(path === '/api/me' ? { memberships: [] } : server.unread),
  );
  server.POST.mockImplementation((_path: string, init: { body: { prono_id: string } }) => {
    const before = server.unread as UnreadNotifications;
    const pronos = before.pronos.filter((p) => p.prono_id !== init.body.prono_id);
    server.unread = { total: pronos.reduce((sum, p) => sum + p.unread, 0), pronos };
    return ok();
  });
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

function Prono({ id }: { id: string }) {
  useReadProno('org', id);
  useMe();
  const unread = useUnread('org');
  return <p>{unread.data ? `total ${unread.data.total}` : 'loading'}</p>;
}

function open(id: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <Prono id={id} />
    </QueryClientProvider>,
  );
}

describe('opening a prono', () => {
  it('reads its notifications and takes its bubbles away', async () => {
    open('nice');
    await waitFor(() => expect(screen.getByText('total 1')).toBeInTheDocument());
    expect(server.POST).toHaveBeenCalledOnce();
    expect(server.POST).toHaveBeenCalledWith('/api/orgs/{org_id}/notifications/read', {
      params: { path: { org_id: 'org' } },
      body: { prono_id: 'nice' },
    });
    // The count comes back from the server once it is told, and so do the newsrooms' own.
    const unread = '/api/orgs/{org_id}/notifications/unread';
    await waitFor(() => expect(asked(unread)).toBe(2));
    await waitFor(() => expect(asked('/api/me')).toBe(2));
    expect(screen.getByText('total 1')).toBeInTheDocument();
  });

  it('asks nothing for a prono without notifications', async () => {
    open('neige');
    await waitFor(() => expect(screen.getByText('total 3')).toBeInTheDocument());
    expect(server.POST).not.toHaveBeenCalled();
    expect(asked('/api/me')).toBe(1);
  });
});
