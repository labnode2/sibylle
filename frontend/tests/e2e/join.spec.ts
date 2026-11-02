// Quickstart V1 (points 1, 2, 4 and 5): sign up, create a newsroom, invite with a 2-place link,
// join, and never see another member's private data.
import { expect, test, type Page } from '@playwright/test';

import { createNewsroom, joinWith, newPerson } from './helpers';

const PRIVATE_KEYS = ['first_name', 'last_name', 'email', 'password_hash'];

/** Fails the test if a response other than the account's own carries private data. */
function watchPrivacy(page: Page, leaks: string[]) {
  page.on('response', async (response) => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/') || url.pathname === '/api/me') return;
    if (url.pathname.startsWith('/api/auth/')) return;
    // The editor's own invitations show the address they typed for a nominative invitation.
    if (url.pathname.endsWith('/invitations')) return;
    const type = response.headers()['content-type'] ?? '';
    if (!type.includes('application/json')) return;
    const body = await response.text().catch(() => '');
    for (const key of PRIVATE_KEYS) {
      if (body.includes(`"${key}"`)) leaks.push(`${url.pathname}: ${key}`);
    }
  });
}

test('invite with a link and join a newsroom', async ({ browser }, testInfo) => {
  const leaks: string[] = [];

  const ines = await newPerson(browser, testInfo, 'Inès');
  watchPrivacy(ines, leaks);
  await createNewsroom(ines, 'Sophia Office', 'Inès');

  for (let places = 10; places > 2; places -= 1) {
    await ines.getByRole('button', { name: 'Moins' }).click();
  }
  await expect(ines.getByRole('group', { name: 'Nombre de places' })).toContainText('2 places');
  await ines.getByRole('button', { name: 'Créer le lien' }).click();
  const link = await ines.getByLabel('LIEN À PARTAGER').inputValue();
  expect(link).toMatch(/\/rejoindre\/[A-Za-z0-9_-]{40,}$/);
  const path = new URL(link).pathname;

  // Second person: the pseudo « inès » is taken whatever its case, then « Cami » works.
  const cami = await newPerson(browser, testInfo, 'Camille', path);
  watchPrivacy(cami, leaks);
  await expect(cami.getByText("INVITATION D'INÈS")).toBeVisible();
  await expect(cami.getByText('1 MEMBRE · 2 PLACES RESTANTES')).toBeVisible();
  await joinWith(cami, 'inès');
  await expect(cami.getByRole('alert')).toContainText('déjà pris');
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();
  await expect(cami.getByRole('main').getByText('100', { exact: true })).toBeVisible();

  // Third person takes the last place; the fourth is turned away.
  const leo = await newPerson(browser, testInfo, 'Léo', path);
  await joinWith(leo, 'Léo');
  await expect(leo.getByRole('heading', { name: 'Bonjour Léo' })).toBeVisible();

  const manon = await newPerson(browser, testInfo, 'Manon', path);
  await expect(manon.getByRole('alert')).toContainText("Cette invitation n'est plus valable");

  expect(leaks).toEqual([]);
});
