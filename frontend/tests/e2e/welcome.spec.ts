// The welcome pop-up of the first newsroom (on a phone, a sheet from the bottom; on a computer, a
// card in the middle): the game in five steps, closed for good, opened again by « Tuto » on la une
// and on « La rédaction », beside « Charte », the newsroom's charter (card #27): two pixel-art
// images playing in a loop, in the middle of their column.
import { expect, test, type Locator } from '@playwright/test';

import { call, newPerson } from './helpers';

/** How far « Tuto » and « Charte » sit from the middle of their column, in px. */
function offCentre(tuto: Locator): Promise<number> {
  return tuto.evaluate((button) => {
    const pair = button.parentElement!;
    const column = pair.parentElement!;
    const style = getComputedStyle(column);
    const box = column.getBoundingClientRect();
    const inner = (side: 'Left' | 'Right') =>
      parseFloat(style[`padding${side}`]) + parseFloat(style[`border${side}Width`]);
    const middle = (box.left + inner('Left') + box.right - inner('Right')) / 2;
    const buttons = [...pair.querySelectorAll(':scope > button')].map((b) =>
      b.getBoundingClientRect(),
    );
    const left = Math.min(...buttons.map((b) => b.left));
    const right = Math.max(...buttons.map((b) => b.right));
    return buttons.length === 2 ? Math.abs((left + right) / 2 - middle) : Infinity;
  });
}

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

  // ...unless asked for: « Tuto » on la une, beside « Charte », the newsroom's charter with its
  // lines as written. Both play in a loop, like GIFs, side by side in the middle of the column;
  // with less motion, they keep still...
  const tuto = ines.getByRole('button', { name: 'Tuto : revoir les bases du jeu' });
  const charte = ines.getByRole('button', { name: 'Charte : relire la charte de la rédaction' });
  for (const button of [tuto, charte]) {
    await expect(button.locator('img')).toHaveCSS('animation-iteration-count', 'infinite');
  }
  expect(await offCentre(tuto)).toBeLessThan(1);
  await ines.emulateMedia({ reducedMotion: 'reduce' });
  await expect(tuto.locator('img')).toHaveCSS('animation-name', 'none');
  await expect(charte.locator('img')).toHaveCSS('animation-name', 'none');
  await ines.emulateMedia({ reducedMotion: null });
  await tuto.click();
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!');
  await welcome.getByRole('button', { name: 'Passer' }).click();
  await expect(welcome).toBeHidden();
  await charte.click();
  await expect(welcome).toHaveAccessibleName('La charte de la rédaction');
  // The scroll on top of the charter keeps still while it is read.
  await expect(welcome.locator('img')).toHaveCSS('animation-name', 'none');
  const charter = welcome.getByText(/^Sibylle se joue entre collègues/);
  await expect(charter).toContainText("En rejoignant la rédaction, je m'engage à :");
  await expect(charter).toHaveCSS('white-space', 'pre-line');
  await welcome.getByRole('button', { name: 'Fermer' }).click();
  await expect(welcome).toBeHidden();

  // ...and the same on « La rédaction », once it has replaced la une and its own pair.
  await ines.getByRole('link', { name: /^(LA )?RÉDACTION(,|$)/ }).click();
  await expect(ines.getByRole('heading', { name: 'La rédaction', level: 1 })).toBeVisible();
  await expect(charte).toBeVisible();
  expect(await offCentre(tuto)).toBeLessThan(1);
  await tuto.click();
  await expect(welcome).toHaveAccessibleName('Bienvenue dans Sophia Office\u00a0!');
  await welcome.getByRole('button', { name: 'Passer' }).click();
  await expect(welcome).toBeHidden();
});
