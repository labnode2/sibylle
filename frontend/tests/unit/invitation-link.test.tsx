// An invitation link (card #26), with its token (/rejoindre/:token) or its code
// (/rejoindre?code=…), through the app's own routes. Without a session, it does not leave for
// Keycloak's sign-in page at once: it offers « Créer un compte » and « Se connecter », which both
// come back to the whole link, and asks the server nothing but who is there. Signed in, the link
// shows the newsroom and the profile to fill in, or the way in for a member. The other pages behind
// a session still go straight to Keycloak's sign-in page.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { createMemoryRouter, RouterProvider } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';

import '../../src/i18n';
import { PreferencesProvider } from '../../src/app/preferences';
import { routes } from '../../src/app/router';
import { browser } from '../../src/features/auth/signIn';

// The crystal balls and the pixel images draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

/** The server: whether the browser has a session, whether the account is already in the
 *  invitation's newsroom, and every request it was sent (method, path and body). */
const server = vi.hoisted(() => ({
  signedIn: false,
  alreadyMember: false,
  requests: [] as string[],
}));

vi.mock('../../src/api/client', async (importOriginal) => {
  const image = { size: 16, palette: 'base-v1', pixels: '0'.repeat(256) };
  const answers: Record<string, () => unknown> = {
    'GET /api/me': () => ({
      id: 'me',
      theme: 'light',
      reduce_motion: false,
      welcomed: true,
      memberships: [],
    }),
    'GET /api/content': () => ({
      avatars: [{ key: 'chouette', name: 'Chouette', image }],
      logos: [],
      backgrounds: ['mer'],
      charter: '',
    }),
    'POST /api/join/preview': () => ({
      org: { id: 'org-1', title: 'Sophia Office', logo: image, background_key: 'mer' },
      member_count: 3,
      places_left: 7,
      invited_by_pseudo: 'Inès',
      role: 'reader',
      charter: 'On ne parie pas sur les collègues.',
      already_member: server.alreadyMember,
    }),
  };
  const send =
    (method: string) =>
    (path: string, init?: { body?: unknown }): Promise<unknown> => {
      server.requests.push(
        init?.body === undefined
          ? `${method} ${path}`
          : `${method} ${path} ${JSON.stringify(init.body)}`,
      );
      if (!server.signedIn) {
        return Promise.resolve({
          error: { error: { code: 'unauthenticated', message: 'Connexion requise' } },
          response: { ok: false, status: 401 },
        });
      }
      const answer = answers[`${method} ${path}`];
      // Anything else waits for a server that never answers here.
      if (!answer) return new Promise(() => undefined);
      return Promise.resolve({ data: answer(), response: { ok: true, status: 200 } });
    };
  return {
    ...(await importOriginal<typeof import('../../src/api/client')>()),
    api: {
      GET: send('GET'),
      POST: send('POST'),
      PUT: send('PUT'),
      PATCH: send('PATCH'),
      DELETE: send('DELETE'),
    },
  };
});

const INVITED = 'Tu es invité·e à rejoindre une rédaction de Sibylle';
const PSEUDO = 'TON PSEUDO DANS CETTE RÉDACTION';

let go: MockInstance<(url: string) => void>;

beforeEach(() => {
  server.signedIn = false;
  server.alreadyMember = false;
  server.requests = [];
  go = vi.spyOn(browser, 'go').mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

/** Opens `path` in the app's routes, with nothing known yet about the browser's session. */
function open(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <PreferencesProvider>
        <RouterProvider router={createMemoryRouter(routes, { initialEntries: [path] })} />
      </PreferencesProvider>
    </QueryClientProvider>,
  );
}

describe('an invitation link without a session', () => {
  it('offers to create an account or to sign in, both coming back to the link', async () => {
    open('/rejoindre/abc123');
    expect(await screen.findByRole('heading', { name: INVITED })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Créer un compte' })).toHaveAttribute(
      'href',
      '/api/auth/login?action=signup&suite=%2Frejoindre%2Fabc123',
    );
    expect(screen.getByRole('link', { name: 'Se connecter' })).toHaveAttribute(
      'href',
      '/api/auth/login?suite=%2Frejoindre%2Fabc123',
    );
    // Nothing leaves for Keycloak on its own, and the server is only asked who is there: the
    // invitation is read once signed in.
    expect(go).not.toHaveBeenCalled();
    expect(server.requests).toEqual(['GET /api/me']);
    expect(screen.queryByLabelText(PSEUDO)).toBeNull();
  });

  it('keeps the access code of a link with a code', async () => {
    open('/rejoindre?code=SOPHIA-7K2');
    expect(await screen.findByRole('heading', { name: INVITED })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Créer un compte' })).toHaveAttribute(
      'href',
      '/api/auth/login?action=signup&suite=%2Frejoindre%3Fcode%3DSOPHIA-7K2',
    );
    expect(screen.getByRole('link', { name: 'Se connecter' })).toHaveAttribute(
      'href',
      '/api/auth/login?suite=%2Frejoindre%3Fcode%3DSOPHIA-7K2',
    );
    expect(go).not.toHaveBeenCalled();
    expect(server.requests).toEqual(['GET /api/me']);
  });

  it('without an invitation in it, signs in for the welcome page', async () => {
    open('/rejoindre');
    await waitFor(() => expect(go).toHaveBeenCalledWith('/api/auth/login?suite=%2Fbienvenue'));
    expect(screen.queryByRole('heading', { name: INVITED })).toBeNull();
  });

  it('leaves the other pages behind a session going straight to the sign-in', async () => {
    open('/o/42/pronos?vue=ouverts');
    await waitFor(() =>
      expect(go).toHaveBeenCalledWith('/api/auth/login?suite=%2Fo%2F42%2Fpronos%3Fvue%3Douverts'),
    );
    expect(screen.queryByRole('heading', { name: INVITED })).toBeNull();
  });
});

describe('an invitation link, signed in', () => {
  beforeEach(() => {
    server.signedIn = true;
  });

  it('shows the newsroom and the profile to fill in, without the choice', async () => {
    open('/rejoindre/abc123');
    expect(await screen.findByLabelText(PSEUDO)).toBeVisible();
    expect(screen.getByRole('heading', { name: 'Sophia Office' })).toBeVisible();
    expect(screen.getByText("INVITATION D'INÈS")).toBeVisible();
    expect(screen.getByRole('radiogroup', { name: 'TON AVATAR' })).toBeVisible();
    expect(
      screen.getByRole('checkbox', { name: "J'accepte la charte de la rédaction" }),
    ).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Rejoindre la rédaction' })).toBeDisabled();
    expect(screen.queryByRole('heading', { name: INVITED })).toBeNull();
    expect(go).not.toHaveBeenCalled();
    expect(server.requests).toContain('POST /api/join/preview {"token":"abc123"}');
  });

  it('with a code, shows it beside the profile to fill in', async () => {
    open('/rejoindre?code=SOPHIA-7K2');
    expect(await screen.findByLabelText(PSEUDO)).toBeVisible();
    expect(screen.getByLabelText("CODE D'ACCÈS")).toHaveValue('SOPHIA-7K2');
    expect(screen.queryByRole('heading', { name: INVITED })).toBeNull();
    expect(server.requests).toContain('POST /api/join/preview {"code":"SOPHIA-7K2"}');
  });

  it('opens the newsroom to one of its members', async () => {
    server.alreadyMember = true;
    open('/rejoindre/abc123');
    expect(await screen.findByText('Tu fais déjà partie de cette rédaction.')).toBeVisible();
    expect(screen.getByRole('link', { name: 'Ouvrir la rédaction' })).toHaveAttribute(
      'href',
      '/o/org-1',
    );
    expect(screen.queryByLabelText(PSEUDO)).toBeNull();
    expect(screen.queryByRole('heading', { name: INVITED })).toBeNull();
  });
});
