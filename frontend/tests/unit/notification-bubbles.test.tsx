// The notifications waiting for me lead from the menus to the prono: a bubble on the newsroom in
// the lists of newsrooms, beside « Pronos » on the phone's tab bar and on the computer's
// navigation, then on the list's filters and sections, then on the prono itself (past « Voir
// plus » while it is further down). No tab of their own; screen readers hear how many are unread.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { createMemoryRouter, MemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { Me, Org } from '../../src/api/types';
import { AppShell } from '../../src/app/AppShell';
import type { UnreadNotifications } from '../../src/features/notifications/api';
import { NewsroomSwitcher } from '../../src/features/orgs/NewsroomPage';
import { StartPage } from '../../src/features/orgs/OrgPages';
import { PronoListPage } from '../../src/features/pronos/PronoListPage';
import type { PronoSummary } from '../../src/features/pronos/api';

// The masthead's crystal ball and the pixel images draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

const unread: { current: UnreadNotifications | undefined } = { current: undefined };
vi.mock('../../src/features/notifications/api', () => ({
  useUnread: () => ({ data: unread.current }),
  useBubbleEvents: () => undefined,
}));
const me: { current: Me | undefined } = { current: undefined };
vi.mock('../../src/features/auth/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/auth/api')>()),
  useMe: () => ({ data: me.current }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { my_membership: { role: 'reader' } } }),
}));

const SPORT = { id: 'sport', name: 'Sport' };
const ECO = { id: 'eco', name: 'Économie' };

function prono(
  id: string,
  state: PronoSummary['state'],
  question: string,
  section = SPORT,
): PronoSummary {
  return {
    id,
    state,
    question,
    section,
    opens_at: null,
    closes_at: '2026-11-20T18:00:00Z',
    bet_count: 3,
    message_count: 0,
    pot: 30,
  } as PronoSummary;
}

const PRONOS = [
  prono('nice', 'open', 'Nice ou Monaco samedi ?'),
  prono('pot', 'open', 'Le pot aura-t-il lieu ?', ECO),
  prono('neige', 'resolved', 'Neige à Noël ?'),
];
// The list's sections, and whether more pages wait below the one shown.
const list = { sections: [SPORT], more: false };
vi.mock('../../src/features/pronos/api', () => ({
  usePronoList: (_orgId: string, states: string[], section?: string) => ({
    isPending: false,
    hasNextPage: list.more,
    data: {
      pages: [
        {
          items: PRONOS.filter(
            (p) => states.includes(p.state) && (!section || p.section.id === section),
          ),
        },
      ],
    },
  }),
  useSections: () => ({ data: list.sections }),
}));

afterEach(() => {
  cleanup();
  unread.current = undefined;
  me.current = undefined;
  list.sections = [SPORT];
  list.more = false;
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
        { prono_id: 'nice', state: 'open', section_id: 'sport', unread: 2 },
        { prono_id: 'neige', state: 'resolved', section_id: 'sport', unread: 1 },
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
    list.sections = [SPORT, ECO];
    list.more = true;
    unread.current = { total: 0, pronos: [] };
    showList();
    expect(screen.getByRole('button', { name: 'OUVERTS' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Sport' })).toHaveTextContent(/^Sport$/);
    expect(screen.getByRole('button', { name: 'Voir plus' })).toBeInTheDocument();
    expect(screen.queryByText(/non lue/)).toBeNull();
  });

  it('show on which section of the chosen filter they wait', () => {
    list.sections = [SPORT, ECO];
    unread.current = {
      total: 3,
      pronos: [
        { prono_id: 'nice', state: 'open', section_id: 'sport', unread: 2 },
        { prono_id: 'neige', state: 'resolved', section_id: 'eco', unread: 1 },
      ],
    };
    showList();
    const sport = screen.getByRole('option', { name: 'Sport, 2 notifications non lues' });
    expect(sport).toHaveTextContent('Sport (2)');
    expect(screen.getByRole('option', { name: 'Économie' })).toHaveTextContent(/^Économie$/);

    // Économie chosen under « Ouverts »: its prono has nothing, Sport still says where to go.
    fireEvent.change(screen.getByRole('combobox', { name: 'Rubrique' }), {
      target: { value: 'eco' },
    });
    expect(screen.getByRole('link', { name: /Le pot aura-t-il lieu/ })).not.toHaveAccessibleName(
      expect.stringContaining('non lue'),
    );
    expect(screen.queryByRole('link', { name: /Nice ou Monaco/ })).toBeNull();
    expect(sport).toHaveTextContent('Sport (2)');

    fireEvent.click(screen.getByRole('button', { name: 'RÉSOLUS, 1 notification non lue' }));
    expect(
      screen.getByRole('option', { name: 'Économie, 1 notification non lue' }),
    ).toHaveTextContent('Économie (1)');
    expect(screen.getByRole('option', { name: 'Sport' })).toHaveTextContent(/^Sport$/);
  });

  it('lead past « Voir plus » to the pronos further down the list', () => {
    list.more = true;
    unread.current = {
      total: 3,
      pronos: [
        { prono_id: 'nice', state: 'open', section_id: 'sport', unread: 1 },
        { prono_id: 'plus-bas', state: 'open', section_id: 'sport', unread: 2 },
        { prono_id: 'neige', state: 'resolved', section_id: 'sport', unread: 1 },
      ],
    };
    showList();
    expect(
      screen.getByRole('button', { name: 'Voir plus, 2 notifications non lues' }),
    ).toBeInTheDocument();
    // Under « Résolus », the one waiting is already shown.
    fireEvent.click(screen.getByRole('button', { name: 'RÉSOLUS, 1 notification non lue' }));
    expect(screen.getByRole('button', { name: 'Voir plus' })).toBeInTheDocument();
  });
});

describe('the bubble of each newsroom', () => {
  const card = (id: string, title: string) => ({
    id,
    title,
    background_key: 'mer',
    logo: { size: 16, palette: 'default', pixels: '' },
  });

  /** My newsrooms and what waits in each: the bubbles of their menus added up. */
  function newsrooms(...entries: [string, string, number][]) {
    me.current = {
      memberships: entries.map(([id, title, waiting]) => ({
        org: card(id, title),
        waiting,
        sole_editor: false,
      })),
    } as unknown as Me;
  }

  function showSwitcher() {
    const here = { ...card('sophia', 'Sophia Office'), member_count: 3 } as unknown as Org;
    render(
      <MemoryRouter>
        <NewsroomSwitcher org={here} />
      </MemoryRouter>,
    );
    return screen.getByRole('button', { name: /^Sophia Office/ });
  }

  it('adds up the menus of each newsroom in the menu of newsrooms', () => {
    newsrooms(
      ['sophia', 'Sophia Office', 2],
      ['antibes', 'Antibes Matin', 3],
      ['nice', 'Nice Matin', 0],
    );
    const button = showSwitcher();
    // On the card itself, the other newsrooms: this one's menus show its own.
    expect(button).toHaveAccessibleName(
      expect.stringContaining('3 notifications dans tes autres rédactions'),
    );
    expect(within(button).getByText('3')).toBeInTheDocument();

    fireEvent.click(button);
    const menu = within(screen.getByRole('list', { name: 'Mes rédactions' }));
    const sophia = menu.getByRole('link', { name: 'Sophia Office, 2 notifications' });
    expect(sophia).toHaveAttribute('aria-current', 'true');
    expect(menu.getByRole('link', { name: 'Antibes Matin, 3 notifications' })).toHaveAttribute(
      'href',
      '/o/antibes',
    );
    expect(menu.getByRole('link', { name: 'Nice Matin' })).toBeInTheDocument();
  });

  it('says one notification in the singular, and nothing when nothing waits', () => {
    newsrooms(['sophia', 'Sophia Office', 0], ['antibes', 'Antibes Matin', 1]);
    const button = showSwitcher();
    expect(button).toHaveAccessibleName(
      expect.stringContaining('1 notification dans tes autres rédactions'),
    );
    cleanup();

    newsrooms(['sophia', 'Sophia Office', 0], ['antibes', 'Antibes Matin', 0]);
    fireEvent.click(showSwitcher());
    expect(screen.queryByText(/notification/)).toBeNull();
    expect(screen.getByRole('link', { name: 'Antibes Matin' })).toBeInTheDocument();
  });

  it('shows on the welcome page too', () => {
    newsrooms(['sophia', 'Sophia Office', 2], ['nice', 'Nice Matin', 0]);
    render(
      <MemoryRouter>
        <StartPage />
      </MemoryRouter>,
    );
    const list = within(screen.getByRole('navigation', { name: 'Mes rédactions' }));
    expect(list.getByRole('link', { name: 'Sophia Office, 2 notifications' })).toHaveAttribute(
      'href',
      '/o/sophia',
    );
    expect(list.getByRole('link', { name: 'Nice Matin' })).toBeInTheDocument();
  });
});
