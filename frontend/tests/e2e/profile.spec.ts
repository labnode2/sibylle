// US7: the press card, the pixel editor, buying a colour with coins and a secret code.
import { expect, test } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  orgIdOf,
  resetClock,
  sibylle,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('a press card, an avatar drawn by hand and a collection', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  // A generous newsroom: 500 laurels to start, so 500 coins on the first Monday.
  expect((await call(ines, 'PATCH', `/orgs/${orgId}`, { starting_balance: 500 })).status).toBe(200);
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();

  // Her press card: the second to arrive.
  await cami.getByRole('link', { name: 'PROFIL' }).click();
  const card = cami.getByRole('region', { name: 'Carte de presse' });
  await expect(card).toContainText('CARTE DE PRESSE N° 0002');
  await expect(card.getByRole('heading', { name: 'Cami' })).toBeVisible();
  await expect(card).toContainText(/MEMBRE DEPUIS [A-ZÉÛ]+ \d{4}/);

  // She redraws her avatar in 32 × 32, with the mouse and the keyboard.
  await cami.getByRole('button', { name: 'Redessiner mon avatar' }).click();
  const editor = cami.getByRole('region', { name: 'Mon avatar' });
  await editor.getByRole('button', { name: '32 × 32' }).click();
  await editor.getByRole('radio', { name: 'Couleur 13' }).click();
  const grid = editor.getByRole('application');
  await grid.click({ position: { x: 5, y: 5 } });
  await grid.press('ArrowRight');
  await grid.press('Space');
  await editor.getByRole('button', { name: 'Enregistrer mon avatar' }).click();
  await expect(editor).toHaveCount(0);
  // Everyone sees it.
  const members = await call(ines, 'GET', `/orgs/${orgId}/members`);
  const drawn = members.body.find((m: { pseudo: string }) => m.pseudo === 'Cami').avatar;
  expect(drawn.size).toBe(32);
  const pixels = Buffer.from(drawn.pixels, 'base64');
  expect([pixels[0], pixels[1]]).toEqual([13, 13]);

  // Monday brings 500 coins; a colour for 400 coins, and the laurels stay.
  sibylle('clock', 'advance', '7d');
  sibylle('coins', 'grant', '--org', orgId);
  const news = cami.getByRole('dialog', { name: 'Tes lauriers en or deviennent des pièces' });
  await news.getByRole('button', { name: 'Fermer' }).click();
  await cami.getByRole('link', { name: 'Ma collection' }).click();
  await cami.getByRole('button', { name: 'Acheter Couleur Rouge vif pour 400 pièces' }).click();
  await cami.getByRole('button', { name: 'Acheter', exact: true }).click();
  await expect(cami.getByRole('listitem', { name: 'Couleur Rouge vif' })).toContainText('À TOI');
  expect(await laurels(cami, orgId)).toEqual([500, 0]);
  await expect(
    cami.getByRole('button', { name: "Acheter Boule d'hiver pour 800 pièces" }),
  ).toBeDisabled();

  // A secret code: once only.
  const code = `BOUH-${Date.now()}`;
  sibylle('secret-code', 'add', code, 'ball-halloween');
  const secret = cami.getByRole('region', { name: 'Un code secret ?' });
  await secret.getByLabel('TON CODE').fill(code.toLowerCase());
  await secret.getByRole('button', { name: 'Débloquer' }).click();
  await expect(secret).toContainText("Débloqué : Boule d'Halloween !");
  await secret.getByLabel('TON CODE').fill(code);
  await secret.getByRole('button', { name: 'Débloquer' }).click();
  await expect(secret.getByRole('alert')).toBeVisible();

  // Back on the card: the colour is in the palette; the laurels statement has no purchase.
  await cami.getByRole('link', { name: 'Retour à ma carte de presse' }).click();
  const collection = cami.getByRole('region', { name: 'La collection' });
  await expect(collection).toContainText('Couleur Rouge vif');
  await expect(collection).toContainText("Boule d'Halloween");
  const statement = cami.getByRole('region', { name: 'MON RELEVÉ' });
  await expect(statement).toContainText('SOLDE DE DÉPART');
  await expect(statement).not.toContainText('ACHAT');
  await cami.getByRole('button', { name: 'Redessiner mon avatar' }).click();
  await expect(cami.getByRole('radio', { name: 'Couleur 41' })).toBeVisible();
});
