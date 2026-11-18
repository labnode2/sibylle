// My coins, the shop beside them and my avatar. My coins explain themselves again, on hover, on
// focus or pinned by a tap, and lead nowhere. On a phone, the shop right of them on la une's top
// line opens the collection, which leads back to la une; a computer has no shop. On a computer,
// my avatar and pseudo open my account's menu: « Profil », « Collection », « Réglages »,
// « Déconnexion ».
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { Org } from '../../src/api/types';
import { OrgLayout } from '../../src/app/OrgLayout';
import { CollectionPage } from '../../src/features/collection/CollectionPage';
import { UnePage } from '../../src/features/une/UnePage';

// The crystal balls and the pixel images draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));
vi.mock('../../src/features/install/InstallButton', () => ({ InstallButton: () => null }));
// No server here: the newsroom, an empty catalog, and nothing else loaded.
vi.mock('../../src/api/realtime', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/api/realtime')>()),
  useTopic: () => undefined,
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: ORG }),
}));
vi.mock('../../src/features/auth/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/auth/api')>()),
  useMe: () => ({ data: undefined }),
  useWelcomed: () => ({ mutate: vi.fn() }),
}));
vi.mock('../../src/features/admin/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/admin/api')>()),
  useReports: () => ({ data: [] }),
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
vi.mock('../../src/features/une/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/une/api')>()),
  useFrontPage: () => ({ data: undefined }),
}));
vi.mock('../../src/features/games/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/games/api')>()),
  useGames: () => ({ data: undefined }),
}));
vi.mock('../../src/features/profile/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/profile/api')>()),
  useCatalog: () => ({ data: [] }),
}));

const ORG = {
  id: 'org',
  title: 'Sophia Office',
  edition_number: 305,
  my_membership: {
    id: 'cami',
    pseudo: 'Cami',
    avatar: { size: 16, pixels: '' },
    role: 'journalist',
    balance: 120,
    gold: 150,
    coins: 40,
  },
} as unknown as Org;

beforeAll(() => {
  // jsdom has the element, not its modal methods: « Déconnexion » asks in a modal dialog.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
});

afterEach(cleanup);

function visit(path: string) {
  const router = createMemoryRouter(
    [
      {
        path: '/o/:orgId',
        element: <OrgLayout />,
        children: [
          { index: true, element: <UnePage /> },
          { path: 'pronos', element: <p>Les pronos</p> },
          { path: 'profil', element: <p>Ma carte de presse</p> },
          { path: 'collection', element: <CollectionPage /> },
        ],
      },
      { path: '/compte', element: <p>Mes réglages</p> },
    ],
    { initialEntries: [path] },
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const { container } = render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  // Both top lines are in the page, CSS shows one of them: the computer's date bar comes with
  // the frame, the phone's with la une.
  const desktop = container.querySelector<HTMLElement>('.only-desktop')!;
  const phone = screen
    .queryAllByText(/^N° 305 · /)
    .map((date) => date.parentElement!)
    .find((line) => line.classList.contains('only-mobile'));
  return { router, desktop: within(desktop), phone: phone && within(phone) };
}

const coinsName = { name: /40 pièces$/ } as const;
const coinsHint =
  'Pièces : pour acheter des couleurs, des cadres et des animations dans la collection. ' +
  'Les dépenser ne touche ni tes lauriers ni ton classement.';
const shopName = { name: 'Ma collection' } as const;

/** Where the collection's two ways back lead: « PROFIL » above it, the link at its foot. */
function waysBack() {
  const page = within(screen.getByRole('main'));
  return [
    page.getByRole('link', { name: 'PROFIL' }),
    page.getByRole('link', { name: 'Retour à ma carte de presse' }),
  ].map((link) => link.getAttribute('href'));
}

/** The word of explanation a trigger is described by. */
function tipOf(trigger: HTMLElement) {
  return document.getElementById(trigger.getAttribute('aria-describedby')!)!;
}

describe('my coins', () => {
  it('explain themselves again on the computer’s date bar, and lead nowhere', async () => {
    const user = userEvent.setup();
    const { desktop } = visit('/o/org/pronos');
    expect(
      desktop.queryAllByRole('link').filter((link) => /pièce/.test(link.textContent!)),
    ).toEqual([]);
    const coins = desktop.getByRole('button', coinsName);
    expect(coins).toHaveTextContent(/^40/);
    expect(coins).toHaveAccessibleDescription(coinsHint);
    const tip = tipOf(coins);
    expect(tip).toHaveRole('tooltip');
    expect(tip).not.toBeVisible();
    await user.hover(coins);
    expect(tip).toBeVisible();
    await user.unhover(coins);
    expect(tip).not.toBeVisible();
    act(() => coins.focus());
    expect(tip).toBeVisible();
    await user.keyboard('{Escape}');
    expect(tip).not.toBeVisible();
    act(() => coins.blur());
    // A click pins it, as it does for the laurels beside them.
    await user.click(coins);
    expect(coins).toHaveAttribute('aria-expanded', 'true');
    expect(tip).toBeVisible();
  });

  it('explain themselves again on la une’s top line, on a phone: a tap pins the word', async () => {
    const user = userEvent.setup();
    const { router, phone } = visit('/o/org');
    expect(phone).toBeDefined();
    const coins = phone!.getByRole('button', coinsName);
    expect(coins).toHaveAttribute('aria-expanded', 'false');
    await user.click(coins);
    expect(router.state.location.pathname).toBe('/o/org');
    expect(coins).toHaveAttribute('aria-expanded', 'true');
    expect(tipOf(coins)).toBeVisible();
    expect(tipOf(coins)).toHaveTextContent(coinsHint);
    // A tap elsewhere puts it away.
    await user.click(phone!.getByText(/^N° 305 · /));
    expect(coins).toHaveAttribute('aria-expanded', 'false');
    expect(tipOf(coins)).not.toBeVisible();
  });
});

describe('the shop of the collection', () => {
  it('stands right of my coins on la une’s top line, on a phone', () => {
    const { phone } = visit('/o/org');
    const shop = phone!.getByRole('link', shopName);
    expect(shop).toHaveAttribute('href', '/o/org/collection');
    expect(shop).toHaveAttribute('title', 'Ma collection');
    // A drawing, with no word to read.
    expect(shop).toHaveTextContent('');
    expect(shop.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    // Right after my three counters, whose last are the coins, and last in the line.
    const counters = within(shop.previousElementSibling as HTMLElement).getAllByRole('button');
    expect(counters).toHaveLength(3);
    expect(counters.at(-1)).toBe(phone!.getByRole('button', coinsName));
    expect(shop.nextElementSibling).toBeNull();
  });

  it('opens the collection in a tap, whose way back leads to la une', async () => {
    const user = userEvent.setup();
    const { router, phone } = visit('/o/org');
    await user.click(phone!.getByRole('link', shopName));
    expect(router.state.location.pathname).toBe('/o/org/collection');
    expect(router.state.location.state).toEqual({ from: '/o/org' });
    expect(await screen.findByRole('heading', { name: 'La collection' })).toBeInTheDocument();
    expect(waysBack()).toEqual(['/o/org', '/o/org']);
  });

  it('is not on the computer’s date bar, nor on the other pages', () => {
    const { desktop } = visit('/o/org');
    expect(desktop.queryByRole('link', shopName)).toBeNull();
    cleanup();
    visit('/o/org/pronos');
    expect(screen.queryByRole('link', shopName)).toBeNull();
  });
});

describe('the menu of my avatar, on a computer', () => {
  function openMenu(path: string) {
    const user = userEvent.setup();
    const visited = visit(path);
    const button = visited.desktop.getByRole('button', { name: 'CAMI, mon compte' });
    return { user, button, ...visited };
  }

  it('opens under my avatar and pseudo, with my account’s four entries', async () => {
    const { user, button, desktop } = openMenu('/o/org/pronos');
    // My pseudo is a button now, no longer a link to the profile.
    expect(button).toHaveTextContent('CAMI');
    expect(desktop.queryByRole('link', { name: /CAMI/ })).toBeNull();
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(desktop.queryByRole('list', { name: 'Mon compte' })).toBeNull();

    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
    const list = desktop.getByRole('list', { name: 'Mon compte' });
    expect(list.parentElement).toHaveAttribute('id', button.getAttribute('aria-controls'));
    const menu = within(list);
    expect(menu.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Profil',
      'Collection',
      'Réglages',
      'Déconnexion',
    ]);
    expect(menu.getByRole('link', { name: 'Profil' })).toHaveAttribute('href', '/o/org/profil');
    expect(menu.getByRole('link', { name: 'Collection' })).toHaveAttribute(
      'href',
      '/o/org/collection',
    );
    expect(menu.getByRole('link', { name: 'Réglages' })).toHaveAttribute('href', '/compte');
    expect(menu.getByRole('button', { name: 'Déconnexion' })).toBeInTheDocument();
  });

  it('« Profil » opens my press card, and the menu closes', async () => {
    const { user, button, router, desktop } = openMenu('/o/org/pronos');
    await user.click(button);
    await user.click(desktop.getByRole('link', { name: 'Profil' }));
    expect(router.state.location.pathname).toBe('/o/org/profil');
    expect(await screen.findByText('Ma carte de presse')).toBeInTheDocument();
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(desktop.queryByRole('list', { name: 'Mon compte' })).toBeNull();
    // On the press card, « Profil » is the page open.
    await user.click(button);
    expect(desktop.getByRole('link', { name: 'Profil' })).toHaveAttribute('aria-current', 'page');
  });

  it('« Collection » opens the collection, whose way back leads to the page I came from', async () => {
    const { user, button, router, desktop } = openMenu('/o/org/pronos');
    await user.click(button);
    await user.click(desktop.getByRole('link', { name: 'Collection' }));
    expect(router.state.location.pathname).toBe('/o/org/collection');
    expect(await screen.findByRole('heading', { name: 'La collection' })).toBeInTheDocument();
    expect(waysBack()).toEqual(['/o/org/pronos', '/o/org/pronos']);
    // Opened again there, it keeps that way back.
    await user.click(button);
    const again = desktop.getByRole('link', { name: 'Collection' });
    expect(again).toHaveAttribute('aria-current', 'page');
    await user.click(again);
    expect(router.state.location.state).toEqual({ from: '/o/org/pronos' });
  });

  it('« Réglages » opens my settings, which lead back to the page I came from', async () => {
    const { user, button, router, desktop } = openMenu('/o/org/pronos');
    await user.click(button);
    await user.click(desktop.getByRole('link', { name: 'Réglages' }));
    expect(router.state.location.pathname).toBe('/compte');
    expect(router.state.location.state).toEqual({ from: '/o/org/pronos' });
  });

  it('« Déconnexion » closes the menu and asks first', async () => {
    const { user, button, desktop } = openMenu('/o/org/pronos');
    await user.click(button);
    await user.click(desktop.getByRole('button', { name: 'Déconnexion' }));
    expect(button).toHaveAttribute('aria-expanded', 'false');
    // The focus waits on my avatar, where the dialog gives it back.
    expect(button).toHaveFocus();
    const ask = screen.getByRole('dialog', { name: 'Te déconnecter ?' });
    expect(ask).toHaveAttribute('open');
    await user.click(within(ask).getByRole('button', { name: 'Annuler' }));
    expect(ask).not.toHaveAttribute('open');
  });

  it('closes with Escape, back on its button, and with a click elsewhere', async () => {
    const { user, button, desktop } = openMenu('/o/org/pronos');
    await user.click(button);
    await user.keyboard('{Escape}');
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(button).toHaveFocus();
    await user.click(button);
    await user.click(desktop.getByText(/^N° 305 · /));
    expect(button).toHaveAttribute('aria-expanded', 'false');
    expect(desktop.queryByRole('list', { name: 'Mon compte' })).toBeNull();
    // Its button closes it too.
    await user.click(button);
    await user.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });
});
