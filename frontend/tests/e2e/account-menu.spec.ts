// Card #18: my coins open the collection in one click, from the computer's date bar and from
// la une's top line on a phone, and still explain themselves on hover. On a computer, my avatar
// and pseudo open my account's menu: « Profil », « Collection », « Réglages », « Déconnexion ».
import { expect, test } from '@playwright/test';

import { createNewsroom, newPerson, orgIdOf } from './helpers';

test('my coins open the collection, my avatar my account’s menu', async ({ browser }, testInfo) => {
  test.setTimeout(90_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const main = ines.getByRole('main');

  // On la une: my coins beside my laurels, which explain what they are on hover.
  const coins = ines.getByRole('link', { name: /^\d+ pièces?, ma collection$/ });
  await expect(coins).toHaveAttribute('href', `/o/${orgId}/collection`);
  await expect(coins).toHaveAccessibleDescription(/^Pièces : pour acheter des couleurs/);
  const hint = ines.getByRole('tooltip').filter({ hasText: /^Pièces : / });
  await expect(hint).toBeHidden();
  if (testInfo.project.name === 'desktop') {
    await coins.hover();
    await expect(hint).toBeVisible();
  }
  // A click opens the collection, whose way back leads to la une.
  await coins.click();
  await expect(main.getByRole('heading', { name: 'La collection' })).toBeVisible();
  await expect(ines).toHaveURL(new RegExp(`/o/${orgId}/collection$`));
  await expect(main.getByRole('link', { name: 'Retour à ma carte de presse' })).toHaveAttribute(
    'href',
    `/o/${orgId}`,
  );
  // No chest anywhere.
  await expect(ines.getByRole('link', { name: 'Ma collection', exact: true })).toHaveCount(0);

  // On a phone, the profile has its tab at the bottom; the menu is the computer's.
  const account = ines.getByRole('button', { name: 'INÈS, mon compte' });
  if (testInfo.project.name !== 'desktop') {
    await expect(account).toBeHidden();
    return;
  }

  const menu = ines.getByRole('list', { name: 'Mon compte' });
  await ines.goto(`/o/${orgId}/pronos`);
  await account.click();
  await expect(account).toHaveAttribute('aria-expanded', 'true');
  await expect(menu.getByRole('listitem')).toHaveText([
    'Profil',
    'Collection',
    'Réglages',
    'Déconnexion',
  ]);
  // « Collection »: the collection, and back to the pronos.
  await menu.getByRole('link', { name: 'Collection' }).click();
  await expect(main.getByRole('heading', { name: 'La collection' })).toBeVisible();
  await expect(menu).toHaveCount(0);
  await main.getByRole('link', { name: 'Retour à ma carte de presse' }).click();
  await expect(ines).toHaveURL(new RegExp(`/o/${orgId}/pronos$`));

  // « Profil »: my press card.
  await account.click();
  await menu.getByRole('link', { name: 'Profil' }).click();
  await expect(ines).toHaveURL(new RegExp(`/o/${orgId}/profil$`));
  await expect(main.getByRole('region', { name: 'Carte de presse' })).toBeVisible();

  // « Réglages »: my settings, which lead back to my press card.
  await account.click();
  await menu.getByRole('link', { name: 'Réglages' }).click();
  await expect(ines.getByRole('heading', { name: 'Mes réglages' })).toBeVisible();
  await ines.getByRole('link', { name: 'Retour à mon profil' }).click();
  await expect(ines).toHaveURL(new RegExp(`/o/${orgId}/profil$`));

  // Escape closes the menu, back on its button.
  await account.click();
  await expect(menu).toBeVisible();
  await ines.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(account).toBeFocused();

  // « Déconnexion » asks first; « Annuler » keeps me signed in.
  await account.click();
  await menu.getByRole('button', { name: 'Déconnexion' }).click();
  const ask = ines.getByRole('dialog', { name: 'Te déconnecter ?' });
  await expect(ask).toBeVisible();
  await ask.getByRole('button', { name: 'Annuler' }).click();
  await expect(ask).toBeHidden();
  await expect(account).toBeFocused();
  await account.click();
  await menu.getByRole('button', { name: 'Déconnexion' }).click();
  await ask.getByRole('button', { name: 'Me déconnecter' }).click();
  // Signed out of Keycloak too: its sign-in page asks for the password again.
  await expect(ines.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  await expect(ines.getByLabel('Mot de passe', { exact: true })).toBeEmpty();
});
