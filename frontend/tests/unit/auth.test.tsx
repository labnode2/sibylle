// The ways to Keycloak's pages (specs/002-keycloak-auth/contracts/auth.md, « Pages de
// l'interface »): a page behind a session, /connexion and /inscription go to the server's
// /api/auth/login with the page to come back to; an error of the way back explains and offers to
// start again.
import { cleanup, render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import { PreferencesProvider } from '../../src/app/preferences';
import {
  GoodbyePage,
  LoginPage,
  SignInUnavailablePage,
  SignupPage,
} from '../../src/features/auth/AuthPages';
import { RequireAuth } from '../../src/features/auth/RequireAuth';
import { browser } from '../../src/features/auth/signIn';

const me = vi.hoisted(() => ({ current: {} as Record<string, unknown> }));
vi.mock('../../src/features/auth/api', () => ({ useMe: () => me.current }));

let go: MockInstance<(url: string) => void>;

beforeEach(() => {
  go = vi.spyOn(browser, 'go').mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function open(path: string, routes: ReactNode) {
  render(
    <PreferencesProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>{routes}</Routes>
      </MemoryRouter>
    </PreferencesProvider>,
  );
}

const publicPages = (
  <>
    <Route path="/connexion" element={<LoginPage />} />
    <Route path="/inscription" element={<SignupPage />} />
    <Route path="/connexion-indisponible" element={<SignInUnavailablePage />} />
    <Route path="/au-revoir" element={<GoodbyePage />} />
  </>
);

describe('RequireAuth', () => {
  const protectedPage = (
    <Route element={<RequireAuth />}>
      <Route path="/o/:orgId/pronos" element={<p>Les pronos</p>} />
    </Route>
  );

  it('sends a visitor without a session to sign in, and back to the page afterwards', () => {
    me.current = { isPending: false, error: new ApiError(401, undefined), data: undefined };
    open('/o/42/pronos?vue=ouverts', protectedPage);
    expect(go).toHaveBeenCalledWith('/api/auth/login?suite=%2Fo%2F42%2Fpronos%3Fvue%3Douverts');
    expect(screen.queryByText('Les pronos')).toBeNull();
  });

  it('shows the page to a signed-in account', () => {
    me.current = {
      isPending: false,
      error: null,
      data: { theme: 'light', reduce_motion: false },
    };
    open('/o/42/pronos', protectedPage);
    expect(screen.getByText('Les pronos')).toBeInTheDocument();
    expect(go).not.toHaveBeenCalled();
  });
});

describe('the sign-in pages', () => {
  it('/connexion goes to Keycloak through the server, keeping the page to come back to', () => {
    open('/connexion?suite=%2Frejoindre%2Fabc', publicPages);
    expect(go).toHaveBeenCalledWith('/api/auth/login?suite=%2Frejoindre%2Fabc');
  });

  it('/inscription asks for the sign-up page', () => {
    open('/inscription?suite=%2Frejoindre%2Fabc', publicPages);
    expect(go).toHaveBeenCalledWith('/api/auth/login?action=signup&suite=%2Frejoindre%2Fabc');
  });

  it('never comes back outside Sibylle', () => {
    open('/connexion?suite=%2F%2Fexemple.org', publicPages);
    expect(go).toHaveBeenCalledWith('/api/auth/login?suite=%2F');
  });

  it('explains a sign-in that did not go through, and offers to start again', () => {
    open('/connexion?erreur=expired&suite=%2Fcompte', publicPages);
    expect(go).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: "La connexion n'a pas abouti" })).toBeVisible();
    expect(screen.getByText(/a pris trop de temps/)).toBeVisible();
    expect(screen.getByRole('link', { name: 'Recommencer' })).toHaveAttribute(
      'href',
      '/api/auth/login?suite=%2Fcompte',
    );
  });

  it('says when an address belongs to another account', () => {
    open('/connexion?erreur=email_taken', publicPages);
    expect(screen.getByText(/appartient déjà à un autre compte/)).toBeVisible();
  });

  it('says when the sign-in service does not answer', () => {
    open('/connexion-indisponible?suite=%2Fcompte', publicPages);
    expect(go).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Connexion indisponible' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Réessayer' })).toHaveAttribute(
      'href',
      '/api/auth/login?suite=%2Fcompte',
    );
  });

  it('says goodbye once the account is deleted, and offers to start again', () => {
    open('/au-revoir', publicPages);
    expect(go).not.toHaveBeenCalled();
    expect(screen.getByRole('heading', { name: 'Ton compte est supprimé' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Créer un nouveau compte' })).toHaveAttribute(
      'href',
      '/inscription',
    );
  });
});
