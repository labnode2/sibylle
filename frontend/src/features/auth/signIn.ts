// The way to Keycloak's pages (specs/002-keycloak-auth/contracts/auth.md): a whole-page
// navigation to the server's /api/auth/login, which sends the browser on to Keycloak and, once
// signed in, back to `suite`. The interface never sees a password nor a token.

export type SignInAction = 'login' | 'signup' | 'password' | 'forgot';

/** The server's way to Keycloak's page for `action`, coming back to `next`, a page of Sibylle
 *  (`forgot` comes back through an ordinary sign-in). */
export function signInUrl(action: SignInAction, next = '/'): string {
  const params = new URLSearchParams();
  if (action !== 'login') params.set('action', action);
  if (action !== 'forgot') params.set('suite', next);
  return `/api/auth/login?${params.toString()}`;
}

/** A page of Sibylle to come back to, as the server checks it: a path of the app, never `//…`,
 *  nor a backslash or a control character a browser could read as another site, nor the API. */
export function isAppPath(path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//') || path.startsWith('/api/')) return false;
  for (const char of path) {
    const code = char.charCodeAt(0);
    if (char === '\\' || code < 0x20 || code === 0x7f) return false;
  }
  return true;
}

/** Leaves the app for a whole page (the server, then Keycloak); tests replace `go`. */
export const browser = {
  go(url: string): void {
    window.location.assign(url);
  },
};
