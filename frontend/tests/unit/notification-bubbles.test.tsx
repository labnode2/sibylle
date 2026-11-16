// The notifications waiting for me lead from the menus to the prono: a bubble beside « Pronos »
// on the phone's tab bar and on the computer's navigation, then on the list's filters, then on
// the prono itself. No tab of their own; screen readers hear how many are unread.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { AppShell } from '../../src/app/AppShell';
import type { UnreadNotifications } from '../../src/features/notifications/api';
import { PronoListPage } from '../../src/features/pronos/PronoListPage';
import type { PronoSummary } from '../../src/features/pronos/api';

// The masthead's crystal ball draws on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));

const unread: { current: UnreadNotifications | undefined } = { current: undefined };
vi.mock('../../src/features/notifications/api', () => ({
  useUnread: () => ({ data: unread.current }),
}));
vi.mock('../../src/features/orgs/api', () => ({
  useOrg: () => ({ data: { my_membership: { role: 'reader' } } }),
}));

function prono(id: string, state: PronoSummary['state'], question: string): PronoSummary {
  return {
    id,
    state,
    question,
    section: { id: 's', name: 'Sport' },
    opens_at: null,
    closes_at: '2026-11-20T18:00:00Z',
    bet_count: 3,
    message_count: 0,
    pot: 30,
  } as PronoSummary;
}

const PRONOS = [
  prono('nice', 'open', 'Nice ou Monaco samedi ?'),
  prono('pot', 'open', 'Le pot aura-t-il lieu ?'),
  prono('neige', 'resolved', 'Neige à Noël ?'),
];
vi.mock('../../src/features/pronos/api', () => ({
  usePronoList: (_orgId: string, states: string[]) => ({
    isPending: false,
    hasNextPage: false,
    data: { pages: [{ items: PRONOS.filter((p) => states.includes(p.state)) }] },
  }),
  useSections: () => ({ data: [{ id: 's', name: 'Sport' }] }),
}));

afterEach(() => {
  cleanup();
  unread.current = undefined;
});

function showShell(count: number) {
  const router = createMemoryRouter(
    [{ path: '/o/:orgId', element: <AppShell unread={count} />, children: [{ index: true }] }],
    { initialEntries: ['/o/org'] },
  );
  const { container } = render(<RouterProvider router={router} />);
  // Both navigations are in the page, CSS shows one of them.
  return {
    desktop: within(container.querySelector<HTMLElement>('.only-desktop')!),
    mobile: within(container.querySelector<HTMLElement>('.only-mobile')!),
  };
}

describe('the bubble beside « Pronos »', () => {
  it('counts the notifications waiting, on the phone and on the computer', () => {
    const { desktop, mobile } = showShell(3);
    for (const [nav, name] of [
      [mobile, 'PRONOS'],
      [desktop, 'LES PRONOS'],
    ] as const) {
      const link = nav.getByRole('link', { name: `${name}, 3 notifications non lues` });
      expect(link).toHaveAttribute('href', '/o/org/pronos');
      expect(within(link).getByText('3')).toBeInTheDocument();
    }
  });

  it('is absent when nothing waits', () => {
    const { desktop, mobile } = showShell(0);
    expect(mobile.getByRole('link', { name: 'PRONOS' })).toBeInTheDocument();
    expect(desktop.getByRole('link', { name: 'LES PRONOS' })).toBeInTheDocument();
    expect(screen.queryByText(/non lue/)).toBeNull();
  });

  it('says one notification in the singular', () => {
    const { mobile } = showShell(1);
    expect(
      mobile.getByRole('link', { name: 'PRONOS, 1 notification non lue' }),
    ).toBeInTheDocument();
  });

  it('has no tab of its own', () => {
    const { desktop, mobile } = showShell(2);
    for (const nav of [desktop, mobile]) {
      const links = nav.getAllByRole('link').filter((link) => link.closest('nav'));
      expect(links.map((link) => link.getAttribute('href'))).toEqual([
        '/o/org',
        '/o/org/pronos',
        '/o/org/redaction',
        '/o/org/profil',
      ]);
    }
  });
});

describe('the bubbles of the pronos list', () => {
  function showList() {
    render(
      <MemoryRouter>
        <PronoListPage />
      </MemoryRouter>,
    );
  }

  it('show under which filter, then on which prono, the notifications wait', () => {
    unread.current = {
      total: 3,
      pronos: [
        { prono_id: 'nice', state: 'open', unread: 2 },
        { prono_id: 'neige', state: 'resolved', unread: 1 },
      ],
    };
    showList();
    expect(
      screen.getByRole('button', { name: 'OUVERTS, 2 notifications non lues' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'CLOS' })).toBeInTheDocument();
    const resolved = screen.getByRole('button', { name: 'RÉSOLUS, 1 notification non lue' });

    // The open pronos: the bubble is on the one notified only.
    const nice = screen.getByRole('link', { name: /Nice ou Monaco samedi/ });
    expect(nice).toHaveAccessibleName(expect.stringContaining('2 notifications non lues'));
    expect(within(nice).getByText('2')).toBeInTheDocument();
    const pot = screen.getByRole('link', { name: /Le pot aura-t-il lieu/ });
    expect(pot).not.toHaveAccessibleName(expect.stringContaining('non lue'));

    fireEvent.click(resolved);
    const neige = screen.getByRole('link', { name: /Neige à Noël/ });
    expect(neige).toHaveAccessibleName(expect.stringContaining('1 notification non lue'));
  });

  it('are absent when nothing waits', () => {
    unread.current = { total: 0, pronos: [] };
    showList();
    expect(screen.getByRole('button', { name: 'OUVERTS' })).toBeInTheDocument();
    expect(screen.queryByText(/non lue/)).toBeNull();
  });
});
