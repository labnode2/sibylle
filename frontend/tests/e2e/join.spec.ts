// Quickstart V1 (points 1, 2, 4 and 5): sign up, create a newsroom, invite with a 2-place link,
// join, and never see another member's private data.
import { expect, test, type Page } from '@playwright/test';

import { createNewsroom, joinWith, newPerson, notes, openSettings } from './helpers';

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
  // The invitations live with the members, in the newsroom's settings.
  await openSettings(ines);
  await ines.getByRole('link', { name: 'MEMBRES', exact: true }).click();

  // The settings pages have several steppers: this one is the link's number of places.
  const places = ines.getByRole('group', { name: 'Nombre de places' });
  for (let count = 10; count > 2; count -= 1) {
    await places.getByRole('button', { name: 'Moins' }).click();
  }
  await expect(places).toContainText('2 places');
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
  await expect(notes(cami).getByRole('alert')).toContainText('déjà pris');
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  // The starting balance, all of it to stake.
  await expect(cami.getByRole('main').getByText('100 lauriers verts à miser')).toBeAttached();

  // Third person takes the last place; the fourth is turned away.
  const leo = await newPerson(browser, testInfo, 'Léo', path);
  await joinWith(leo, 'Léo');
  await expect(leo.getByRole('heading', { name: /^La une de / })).toBeVisible();

  const manon = await newPerson(browser, testInfo, 'Manon', path);
  await expect(manon.getByRole('alert')).toContainText("Cette invitation n'est plus valable");

  expect(leaks).toEqual([]);
});

test('the newsroom card opens a menu to change newsroom or join another, and the welcome page lists them', async ({
  browser,
}, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  // The card is in the navigation on a computer, on la une on a phone: the one on screen.
  const card = (title: string) =>
    ines.getByRole('button', { name: new RegExp(`^${title}.*Changer de rédaction$`) }).filter({
      visible: true,
    });
  const menu = ines.getByRole('list', { name: 'Mes rédactions' });

  // It opens where it is; its last option joins or creates another newsroom.
  await card('Sophia Office').click();
  await expect(card('Sophia Office')).toHaveAttribute('aria-expanded', 'true');
  await expect(menu.getByRole('link')).toHaveCount(1);
  await expect(menu.getByRole('link')).toHaveAccessibleName('Sophia Office');
  await ines.getByRole('link', { name: 'Rejoindre ou créer une rédaction' }).click();

  // The welcome page lists her newsrooms under « Créer une rédaction », and its gear opens the
  // settings, which lead back to it.
  const mine = ines.getByRole('navigation', { name: 'Mes rédactions' });
  await expect(mine.getByRole('link')).toHaveCount(1);
  await expect(mine.getByRole('link')).toHaveAccessibleName('Sophia Office');
  await ines.getByRole('link', { name: 'Mes réglages' }).click();
  await expect(ines.getByRole('heading', { name: 'Mes réglages' })).toBeVisible();
  await ines.getByRole('link', { name: "Retour à l'accueil" }).click();
  await createNewsroom(ines, 'Le Petit Écho', 'Inès');

  // Both newsrooms, the current one marked; Escape closes the menu.
  await card('Le Petit Écho').click();
  await expect(menu.getByRole('link')).toHaveCount(2);
  await expect(menu.getByRole('link').first()).toHaveAccessibleName('Sophia Office');
  await expect(menu.getByRole('link').last()).toHaveAccessibleName('Le Petit Écho');
  await expect(menu.getByRole('link', { name: 'Le Petit Écho' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await ines.keyboard.press('Escape');
  await expect(menu).toBeHidden();
  await expect(card('Le Petit Écho')).toBeFocused();

  // Back to the first one.
  await card('Le Petit Écho').click();
  await menu.getByRole('link', { name: 'Sophia Office' }).click();
  await expect(ines.getByRole('heading', { name: 'La une de Sophia Office' })).toBeVisible();
  await expect(menu).toBeHidden();

  // Her profile ends with « Déconnexion », which asks first.
  await ines.getByRole('link', { name: /^(MON )?PROFIL$/ }).click();
  await ines.getByRole('button', { name: 'Déconnexion' }).click();
  const leaving = ines.getByRole('dialog', { name: 'Te déconnecter ?' });
  await leaving.getByRole('button', { name: 'Annuler' }).click();
  await expect(leaving).toBeHidden();
  await expect(ines).toHaveURL(/\/profil$/);
  await ines.getByRole('button', { name: 'Déconnexion' }).click();
  await leaving.getByRole('button', { name: 'Me déconnecter' }).click();
  await expect(ines).toHaveURL(/\/connexion$/);
});
