// « Ma collection » in one click: a chest right after my avatar and pseudo in the computer's date
// bar, and right of my laurels on la une's top line on a phone (no avatar up there). It opens the
// collection, whose way back then leads to the page I came from.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

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
          { path: 'collection', element: <CollectionPage /> },
        ],
      },
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

const chest = { name: 'Ma collection' } as const;

/** Where the collection's two ways back lead: « PROFIL » above it, the link at its foot. */
function waysBack() {
  const page = within(screen.getByRole('main'));
  return [
    page.getByRole('link', { name: 'PROFIL' }),
    page.getByRole('link', { name: 'Retour à ma carte de presse' }),
  ].map((link) => link.getAttribute('href'));
}

describe('the chest of « Ma collection »', () => {
  it('follows my avatar and pseudo in the computer’s date bar', () => {
    const { desktop } = visit('/o/org/pronos');
    const profile = desktop.getByRole('link', { name: 'CAMI' });
    expect(profile).toHaveAttribute('href', '/o/org/profil');
    const link = desktop.getByRole('link', chest);
    expect(link).toHaveAttribute('href', '/o/org/collection');
    expect(link).toHaveAttribute('title', 'Ma collection');
    expect(profile.nextElementSibling).toBe(link);
    // An icon alone: its name is its label, nothing written beside it.
    expect(link).toHaveTextContent(/^$/);
    expect(link.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
  });

  it('stands right of my laurels on la une’s top line, on a phone', () => {
    const { phone } = visit('/o/org');
    expect(phone).toBeDefined();
    const link = phone!.getByRole('link', chest);
    expect(link).toHaveAttribute('href', '/o/org/collection');
    expect(link).toHaveAttribute('title', 'Ma collection');
    const laurels = phone!.getByText('120 lauriers verts à miser');
    expect(laurels.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(link.nextElementSibling).toBeNull();
  });

  it('is only on la une among the phone’s pages', () => {
    const { phone } = visit('/o/org/pronos');
    expect(phone).toBeUndefined();
    // The computer's date bar has one; the phone's other pages reach it through the profile.
    expect(screen.getAllByRole('link', chest)).toHaveLength(1);
  });

  it('opens the collection, whose way back leads to the page it came from', async () => {
    const user = userEvent.setup();
    const { router, desktop } = visit('/o/org/pronos');
    await user.click(desktop.getByRole('link', chest));
    expect(router.state.location.pathname).toBe('/o/org/collection');
    expect(await screen.findByRole('heading', { name: 'La collection' })).toBeInTheDocument();
    expect(waysBack()).toEqual(['/o/org/pronos', '/o/org/pronos']);
  });

  it('leads back to la une when opened from it on a phone', async () => {
    const user = userEvent.setup();
    const { phone } = visit('/o/org');
    await user.click(phone!.getByRole('link', chest));
    expect(await screen.findByRole('heading', { name: 'La collection' })).toBeInTheDocument();
    expect(waysBack()).toEqual(['/o/org', '/o/org']);
  });

  it('keeps that way back when clicked again on the collection, marked as the page open', async () => {
    const user = userEvent.setup();
    const { router, desktop } = visit('/o/org/pronos');
    await user.click(desktop.getByRole('link', chest));
    await screen.findByRole('heading', { name: 'La collection' });
    const link = desktop.getByRole('link', chest);
    expect(link).toHaveAttribute('aria-current', 'page');
    await user.click(link);
    expect(router.state.location.state).toEqual({ from: '/o/org/pronos' });
    expect(waysBack()).toEqual(['/o/org/pronos', '/o/org/pronos']);
  });
});
