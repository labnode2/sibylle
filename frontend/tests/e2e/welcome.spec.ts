// The welcome pop-up of the first newsroom (on a phone, a sheet from the bottom; on a computer, a
// card in the middle): the game in five steps, closed for good, opened again by « Tuto » on la une,
// a pixel-art book at the other end of the newsroom card's line (card #27). « Charte », the
// parchment in the newsroom's card on « La rédaction », opens the newsroom's charter.
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
  await expect(welcome.getByText('ÉTAPE 1 SUR 5')).toBeVisible();
  for (let step = 1; step < 5; step += 1) {
    await welcome.getByRole('button', { name: 'Suivant' }).click();
  }
  await expect(welcome).toHaveAccessibleName('À toi de lancer la rédaction');
  await welcome.getByRole('button', { name: "C'est parti\u00a0!" }).click();
  await expect(welcome).toBeHidden();
  // Closing it saves `welcomed` in the background: the request may still be on its way.
  await expect.poll(async () => (await call(ines, 'GET', '/me')).body.welcomed).toBe(true);

  // It does not come back...
  await ines.reload();
  await expect(ines.getByRole('heading', { name: 'La une de Sophia Office' })).toBeVisible();
  await expect(welcome).toBeHidden();

  // ...unless asked for: « Tuto », the book, on la une, at the other end of the newsroom card's
  // line: left of the navigation on a computer, right of the card on a phone...
  const tuto = ines.getByRole('button', { name: 'Tuto : revoir les bases du jeu' });
  const charte = ines.getByRole('button', { name: 'Charte : relire la charte de la rédaction' });
  await expect(tuto).toBeVisible();
  await expect(charte).toHaveCount(0);
  const card = ines.getByRole('button', { name: /Changer de rédaction/ });
  const [book, newsroom] = await Promise.all([tuto.boundingBox(), card.boundingBox()]);
  const middle = (box: { y: number; height: number }) => box.y + box.height / 2;
  expect(Math.abs(middle(book!) - middle(newsroom!))).toBeLessThan(8);
  if (testInfo.project.name === 'desktop') expect(book!.x + book!.width).toBeLessThan(newsroom!.x);
  else expect(book!.x).toBeGreaterThan(newsroom!.x + newsroom!.width);
  await tuto.click();
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!');
  await welcome.getByRole('button', { name: 'Passer' }).click();
  await expect(welcome).toBeHidden();

  // ...and « Charte », the parchment, on « La rédaction »: the newsroom's charter with its lines
  // as written.
  await ines.getByRole('link', { name: /^(LA )?RÉDACTION(,|$)/ }).click();
  await expect(ines.getByRole('heading', { name: 'La rédaction', level: 1 })).toBeVisible();
  await expect(tuto).toHaveCount(0);
  await charte.click();
  await expect(welcome).toHaveAccessibleName('La charte de la rédaction');
  const charter = welcome.getByText(/^Sibylle se joue entre collègues/);
  await expect(charter).toContainText("En rejoignant la rédaction, je m'engage à :");
  await expect(charter).toHaveCSS('white-space', 'pre-line');
  await welcome.getByRole('button', { name: 'Fermer' }).click();
  await expect(welcome).toBeHidden();
});
