// The welcome pop-up of the first newsroom (on a phone, a sheet from the bottom; on a computer, a
// card in the middle): the game in six steps, closed for good, opened again by « Tuto » on la une
// and on « La rédaction », beside « Charte », the newsroom's charter (card #27).
import { expect, test } from '@playwright/test';

import { call, newPerson } from './helpers';

test('the first newsroom explains the game once, then on demand', async ({ browser }, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès', '/', { welcome: true });
  await ines.getByRole('link', { name: 'Créer une rédaction' }).click();
  await ines.getByLabel('NOM DE LA RÉDACTION').fill('Sophia Office');
  await ines.getByLabel('TON PSEUDO DANS CETTE RÉDACTION').fill('Inès');
  await ines.getByRole('button', { name: 'Créer la rédaction' }).click();

  // The first visit to la une compiles its modules when the dev server has just started.
  const welcome = ines.getByRole('dialog');
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!', {
    timeout: 15_000,
  });
  await expect(welcome.getByText('ÉTAPE 1 SUR 6')).toBeVisible();
  for (let step = 1; step < 6; step += 1) {
    await welcome.getByRole('button', { name: 'Suivant' }).click();
  }
  await expect(welcome).toHaveAccessibleName('À toi de lancer la rédaction');
  await welcome.getByRole('button', { name: "C'est parti\u00a0!" }).click();
  await expect(welcome).toBeHidden();
  expect((await call(ines, 'GET', '/me')).body.welcomed).toBe(true);

  // It does not come back...
  await ines.reload();
  await expect(ines.getByRole('heading', { name: 'La une de Sophia Office' })).toBeVisible();
  await expect(welcome).toBeHidden();

  // ...unless asked for: « Tuto » on la une, beside « Charte », the newsroom's charter with its
  // lines as written...
  const tuto = ines.getByRole('button', { name: 'Tuto : revoir les bases du jeu' });
  await tuto.click();
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!');
  await welcome.getByRole('button', { name: 'Passer' }).click();
  await expect(welcome).toBeHidden();
  await ines.getByRole('button', { name: 'Charte : relire la charte de la rédaction' }).click();
  await expect(welcome).toHaveAccessibleName('La charte de la rédaction');
  const charter = welcome.getByText(/^Sibylle se joue entre collègues/);
  await expect(charter).toContainText("En rejoignant la rédaction, je m'engage à :");
  await expect(charter).toHaveCSS('white-space', 'pre-line');
  await welcome.getByRole('button', { name: 'Fermer' }).click();
  await expect(welcome).toBeHidden();

  // ...and the same on « La rédaction ».
  await ines.getByRole('link', { name: /^(LA )?RÉDACTION(,|$)/ }).click();
  await expect(
    ines.getByRole('button', { name: 'Charte : relire la charte de la rédaction' }),
  ).toBeVisible();
  await tuto.click();
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!');
  await welcome.getByRole('button', { name: 'Passer' }).click();
  await expect(welcome).toBeHidden();
});
