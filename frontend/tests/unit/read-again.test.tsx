// « Tuto » and « Charte » (card #27): the game's bases and the newsroom's charter, to read again
// at any time. « Tuto », the open book, is on la une: at the end of the newsroom card's line on a
// phone, at the left of the navigation on a computer. « Charte », the parchment, is on « La
// rédaction », in the newsroom's card, right of its name; « Revoir les bases du jeu » is gone.
// Each is a still pixel-art image (art.ts), without a word under it. « Tuto » opens the welcome
// with the newsroom and the member's role; « Charte » the charter, its line breaks kept; no
// « Charte » without a charter.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { OrgLayout } from '../../src/app/OrgLayout';
import { NewsroomPage } from '../../src/features/orgs/NewsroomPage';
import type { FrontPage } from '../../src/features/une/api';
import { UnePage } from '../../src/features/une/UnePage';
import { ART } from '../../src/features/welcome/art';

const CHARTER =
  'On joue pour le plaisir.\nEn rejoignant la rédaction, je m’engage à :\n- respecter les autres ;\n- signaler un résultat erroné.\n\nLa rédaction en chef modère.';
const TUTO = 'Tuto : revoir les bases du jeu';
const CHARTE = 'Charte : relire la charte de la rédaction';

const state = vi.hoisted(() => ({
  charter: '',
  role: 'reader' as 'reader' | 'journalist' | 'editor',
  note: null as string | null,
}));

vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({
    data: {
      id: 'org',
      title: 'La Gazette',
      logo: null,
      background_key: 'mer',
      charter: state.charter,
      access_code: null,
      member_count: 1,
      edition_number: 305,
      my_membership: {
        id: 'me',
        pseudo: 'Inès',
        avatar: null,
        role: state.role,
        balance: 100,
        gold: 100,
        coins: 0,
      },
    },
  }),
}));
vi.mock('../../src/features/une/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/une/api')>()),
  useFrontPage: () => ({
    data: {
      headline: null,
      open: [],
      open_count: 0,
      to_designate: null,
      latest_results: [],
      leaderboard_top: [],
      leaderboard_period: 'all_time',
      editor_note: state.note,
    } satisfies FrontPage,
  }),
}));
vi.mock('../../src/features/admin/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/admin/api')>()),
  useMembers: () => ({
    data: [
      {
        id: 'me',
        pseudo: 'Inès',
        avatar: null,
        frame: null,
        animation: null,
        role: state.role,
        joined_at: '2026-11-01T09:00:00Z',
        streak: 0,
        balance: 100,
      },
    ],
  }),
  useReports: () => ({ data: [] }),
}));
// Welcomed already: the welcome only opens when asked for.
vi.mock('../../src/features/auth/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/auth/api')>()),
  useMe: () => ({ data: { memberships: [], welcomed: true } }),
  useWelcomed: () => ({ mutate: vi.fn() }),
}));
// A week without games, and neither the proposals to review nor the install button.
vi.mock('../../src/features/games/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/games/api')>()),
  useGames: () => ({ data: { scheduled: [] } }),
}));
vi.mock('../../src/features/pronos/ProposalsPanel', () => ({ ProposalsPanel: () => null }));
vi.mock('../../src/features/install/InstallButton', () => ({ InstallButton: () => null }));
// The frame's own loads: no server here.
vi.mock('../../src/api/realtime', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/api/realtime')>()),
  useTopic: () => undefined,
}));
vi.mock('../../src/features/coins/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/coins/api')>()),
  useWeeklyCoins: () => ({ isPending: true, data: undefined }),
}));
vi.mock('../../src/features/notifications/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/notifications/api')>()),
  useUnread: () => ({ data: undefined }),
  useBubbleEvents: () => undefined,
}));
// The crystal ball and the pixel images draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

beforeAll(() => {
  // jsdom has the element, not its modal methods.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
});

beforeEach(() => {
  state.charter = CHARTER;
  state.role = 'reader';
  state.note = null;
});

afterEach(cleanup);

/** The page alone, as a phone shows it; `frame` adds the computer's navigation around it (jsdom
 *  shows both, CSS choosing between them). */
function show(path: string, frame = false) {
  const pages: RouteObject[] = [
    { index: true, element: <UnePage /> },
    { path: 'redaction', element: <NewsroomPage /> },
  ];
  const router = createMemoryRouter(
    [{ path: '/o/:orgId', element: frame ? <OrgLayout /> : undefined, children: pages }],
    { initialEntries: [path] },
  );
  render(
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

const tuto = () => screen.getByRole('button', { name: TUTO });
const charter = () => screen.queryByRole('button', { name: CHARTE });

/** The computer's navigation bar: the logo or « Tuto », the tabs, the newsroom's card. */
const navigationBar = () =>
  screen.getByRole('link', { name: 'MON PROFIL' }).closest('nav')!.parentElement!;

/** Its image says nothing; the button's name and a mouse's hint say what it opens. */
function expectPicture(button: HTMLElement, name: string, src: string) {
  expect(button).toHaveTextContent(/^$/);
  expect(button).toHaveAttribute('title', name);
  const image = button.querySelector('img');
  expect(image).toHaveAttribute('src', src);
  expect(image).toHaveAttribute('alt', '');
}

describe('la une', () => {
  it('shows « Tuto », the book, without a word on screen, and no « Charte »', () => {
    show('/o/org');
    expectPicture(tuto(), TUTO, ART.tuto);
    expect(charter()).toBeNull();
  });

  it('ends the newsroom card’s line with it on a phone', () => {
    show('/o/org');
    const line = tuto().parentElement!;
    expect(line).toContainElement(screen.getByRole('button', { name: /Changer de rédaction/ }));
    expect(line.lastElementChild).toBe(tuto());
  });

  it('puts it left of the navigation on a computer', () => {
    show('/o/org', true);
    const bar = navigationBar();
    const book = within(bar).getByRole('button', { name: TUTO });
    expect(bar.firstElementChild).toContainElement(book);
    expectPicture(book, TUTO, ART.tuto);
    expect(within(bar).queryByRole('button', { name: CHARTE })).toBeNull();
  });

  it('no longer puts anything under the editor’s note', () => {
    state.note = 'Bonne semaine à toutes et à tous !';
    show('/o/org', true);
    const aside = screen.getByRole('complementary', { name: 'Le classement et les jeux' });
    const note = within(aside).getByRole('region', { name: 'Le mot de la rédaction en chef' });
    expect(aside.lastElementChild).toBe(note);
    expect(within(aside).queryByRole('button', { name: TUTO })).toBeNull();
    expect(charter()).toBeNull();
  });

  it.each([
    ['on a phone', false],
    ['on a computer', true],
  ])('opens the welcome with the newsroom and my role, %s', (_device, frame) => {
    state.role = 'journalist';
    show('/o/org', frame);
    fireEvent.click(frame ? within(navigationBar()).getByRole('button', { name: TUTO }) : tuto());
    const welcome = screen.getByRole('dialog', { name: 'Bienvenue dans La Gazette\u00a0!' });
    expect(within(welcome).getByText('ÉTAPE 1 SUR 5')).toBeVisible();
    for (let step = 1; step < 5; step += 1) {
      fireEvent.click(within(welcome).getByRole('button', { name: 'Suivant' }));
    }
    expect(within(welcome).getByRole('heading', { name: 'Tu tiens la plume' })).toBeVisible();
    fireEvent.click(within(welcome).getByRole('button', { name: "C'est parti\u00a0!" }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('« La rédaction »', () => {
  it('shows « Charte », the parchment, right of the newsroom’s name, and no « Tuto »', () => {
    show('/o/org/redaction', true);
    expectPicture(charter()!, CHARTE, ART.charter);
    const name = screen.getByText('La Gazette', { selector: 'p' });
    expect(name.parentElement!.nextElementSibling).toBe(charter());
    expect(screen.queryByRole('button', { name: TUTO })).toBeNull();
  });

  it('opens the charter, its line breaks kept', () => {
    show('/o/org/redaction');
    fireEvent.click(charter()!);
    const dialog = screen.getByRole('dialog', { name: 'La charte de la rédaction' });
    expect(within(dialog).getByText('LA GAZETTE')).toBeVisible();
    // The parchment on top, as on the button.
    expect(dialog.querySelector('img')).toHaveAttribute('src', ART.charter);
    // The text as written, each line kept (white-space: pre-line).
    expect(
      within(dialog).getByText(
        (_text, element) => element?.tagName === 'P' && element.textContent === CHARTER,
      ),
    ).toBeVisible();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fermer' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(charter()).toBeInTheDocument();
  });

  it.each(['', ' \n '])('shows no « Charte » without a charter (%j)', (blank) => {
    state.charter = blank;
    show('/o/org/redaction');
    expect(screen.getByText('La Gazette', { selector: 'p' })).toBeVisible();
    expect(charter()).toBeNull();
  });

  it('no longer has the link « Revoir les bases du jeu »', () => {
    show('/o/org/redaction');
    expect(screen.queryByRole('button', { name: 'Revoir les bases du jeu' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Revoir les bases du jeu' })).toBeNull();
  });
});
