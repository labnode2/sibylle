// Quickstart of specs/002-keycloak-auth: signing in again on Keycloak's page leads back to the page
// asked for, and the way back never leaves Sibylle (US1); signing out signs out of Keycloak too
// (US4); Keycloak's pages, in the Gazette theme, are accessible (principle VI).
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

import {
  backOnSibylle,
  createNewsroom,
  emailOf,
  keycloakAdmin,
  keycloakUserId,
  newPerson,
  PASSWORD,
} from './helpers';

const WCAG_22_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

/** The page has no WCAG 2.2 A or AA violation axe-core can find. */
async function expectAccessible(page: Page): Promise<void> {
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_22_AA).analyze();
  const found = violations.map(
    (violation) =>
      `${violation.id} (${violation.impact}): ${violation.nodes.map((node) => node.target.join(' ')).join(', ')}`,
  );
  expect(found, page.url()).toEqual([]);
}

test('signing in again leads back to the page asked for, and never elsewhere', async ({
  browser,
}, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès');
  const welcome = ines.getByRole('heading', { name: 'Bienvenue sur Sibylle' });
  await expect(welcome).toBeVisible();

  // Still signed in to Keycloak: the way there comes straight back, and only to Sibylle.
  await ines.goto('/api/auth/login?suite=//exemple.org');
  await backOnSibylle(ines, testInfo);
  await expect(welcome).toBeVisible();

  // Signed out, of Keycloak too: a page behind a session leads to Keycloak's sign-in page, which
  // asks for the password again, then back to that page.
  await ines.goto('/compte');
  await ines.getByRole('button', { name: 'Me déconnecter' }).click();
  await ines
    .getByRole('dialog', { name: 'Te déconnecter ?' })
    .getByRole('button', { name: 'Me déconnecter' })
    .click();
  await expect(ines.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  await ines.goto('/compte');
  await expect(ines.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  expect(new URL(ines.url()).port).toBe('8280');
  await expect(ines.getByLabel('Mot de passe')).toBeEmpty();
  await ines.getByLabel('E-mail').fill(emailOf(ines));
  await ines.getByLabel('Mot de passe').fill(PASSWORD);
  await ines.getByRole('button', { name: 'Se connecter' }).click();
  await backOnSibylle(ines, testInfo);
  await expect(ines).toHaveURL(/\/compte$/);
  await expect(ines.getByRole('heading', { name: 'Mes réglages' })).toBeVisible();
});

test('a session an administrator closes in Keycloak ends in Sibylle at once, its WebSocket too', async ({
  browser,
}, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès');
  // La une follows the newsroom: its WebSocket is open.
  await createNewsroom(ines, 'Sophia Office', 'Inès');

  // The console's Sessions → « Sign out »: Keycloak tells Sibylle (a back-channel logout), which
  // closes the WebSocket with 4401; the page goes to Keycloak's sign-in page.
  const user = await keycloakUserId(emailOf(ines));
  expect((await keycloakAdmin('POST', `/users/${user}/logout`)).status).toBe(204);
  await expect(ines.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  expect(new URL(ines.url()).port).toBe('8280');
});

test("Keycloak's sign-in, sign-up and forgotten password pages are accessible", async ({
  page,
}) => {
  await page.goto('/connexion');
  await expect(page.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('link', { name: 'Créer un compte' }).click();
  await expect(page.getByRole('heading', { name: 'Créer un compte' })).toBeVisible();
  await expectAccessible(page);

  await page.getByRole('link', { name: "J'ai déjà un compte" }).click();
  await page.getByRole('link', { name: 'Mot de passe oublié ?' }).click();
  await expect(page.getByRole('heading', { name: 'Mot de passe oublié' })).toBeVisible();
  await expectAccessible(page);
});
