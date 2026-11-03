// Quickstart V10, points 1 to 3 (US11): export one's data, the last editor names another before
// leaving, and a deleted account can no longer sign in while its bets stay under « Ancien membre ».
import { readFile } from 'node:fs/promises';

import { expect, test } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  newPerson,
  orgIdOf,
  PASSWORD,
  pot,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('export, the last editor, then deleting an account', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  const nice = prono.options.find((o: { label: string }) => o.label === 'Nice').id;
  const bet = await call(cami, 'POST', `/orgs/${orgId}/pronos/${prono.id}/bets`, {
    option_id: nice,
    stake: 10,
  });
  expect(bet.status).toBe(201);

  // 1. Her data, as a file: account, newsroom, bet.
  await cami.getByRole('link', { name: 'PROFIL' }).first().click();
  await cami.getByRole('link', { name: 'Préférences' }).click();
  await expect(cami.getByRole('heading', { name: 'Mes réglages' })).toBeVisible();
  const download = cami.waitForEvent('download');
  await cami.getByRole('button', { name: 'Télécharger mes données' }).click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/^sibylle-mes-donnees-\d{4}-\d{2}-\d{2}\.json$/);
  const data = JSON.parse(await readFile((await file.path())!, 'utf-8'));
  expect(data.account.first_name).toBe('Camille');
  expect(data.newsrooms[0].newsroom.title).toBe('Sophia Office');
  expect(data.newsrooms[0].bets[0]).toMatchObject({
    question: 'Nice ou Monaco samedi ?',
    answer: 'Nice',
    stake: 10,
  });
  const email: string = data.account.email;

  // 3. Inès is the only editor: neither leaving nor deleting her account before naming another.
  await ines.goto('/compte');
  await ines.getByRole('button', { name: 'Quitter Sophia Office' }).click();
  await ines.getByRole('button', { name: 'Oui, quitter' }).click();
  const lastEditor = 'Tu es la seule rédaction en chef de Sophia Office';
  await expect(ines.getByRole('alert').filter({ hasText: lastEditor })).toBeVisible();
  await ines.getByRole('button', { name: 'Annuler' }).first().click();
  await ines.getByRole('button', { name: 'Supprimer mon compte' }).click();
  await ines.getByRole('button', { name: 'Oui, supprimer mon compte' }).click();
  await expect(ines.getByRole('alert').filter({ hasText: lastEditor })).toBeVisible();
  await expect(
    ines.getByRole('link', { name: 'Gérer les membres de Sophia Office' }).first(),
  ).toBeVisible();
  expect((await call(ines, 'GET', '/me')).status).toBe(200);

  // 2. Cami deletes hers: signed out, and no way back in.
  await cami.getByRole('button', { name: 'Supprimer mon compte' }).click();
  await cami.getByRole('button', { name: 'Oui, supprimer mon compte' }).click();
  await expect(cami).toHaveURL(/\/connexion\?compte=supprime$/);
  await expect(cami.getByText('Ton compte est supprimé.')).toBeVisible();
  await cami.getByLabel('E-MAIL').fill(email);
  await cami.getByLabel('MOT DE PASSE').fill(PASSWORD);
  await cami.getByRole('button', { name: 'Se connecter' }).click();
  await expect(cami.getByText('E-mail ou mot de passe incorrect.')).toBeVisible();

  // Her bet still counts, under « Ancien membre ».
  await ines.goto(`/o/${orgId}/pronos/${prono.id}`);
  const people = ines.getByRole('region', { name: 'Les pronostiqueurs' });
  await expect(people).toContainText('Ancien membre');
  await expect(people).not.toContainText('Cami');
  await expect(pot(ines, 10)).toBeVisible();
});
