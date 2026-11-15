// The bell in the menu: a red dot while something is unread, on the phone's tab bar and on the
// computer's navigation; its label tells how many.
import { cleanup, render, screen, within } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { AppShell } from '../../src/app/AppShell';

// The masthead's crystal ball draws on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));

afterEach(cleanup);

function show(unread: number) {
  const router = createMemoryRouter(
    [{ path: '/o/:orgId', element: <AppShell unread={unread} />, children: [{ index: true }] }],
    { initialEntries: ['/o/org'] },
  );
  render(<RouterProvider router={router} />);
}

// Both navigations are in the page (CSS shows one of them): the phone's tab bar is the last.
const bells = (name: RegExp) => screen.getAllByRole('link', { name });

describe('notification bell', () => {
  it('shows the dot and the count in its label, on both navigations', () => {
    show(3);
    const links = bells(/Notifications : 3 non lues/);
    expect(links).toHaveLength(2);
    for (const link of links) {
      expect(within(link).getByTestId('unread-dot')).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/o/org/notifications');
    }
  });

  it('has no dot when nothing is unread', () => {
    show(0);
    const links = bells(/Notifications : aucune non lue/);
    expect(links).toHaveLength(2);
    expect(screen.queryByTestId('unread-dot')).toBeNull();
  });
});
