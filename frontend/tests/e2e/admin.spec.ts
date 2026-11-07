// US6: the editor's settings take effect, and they stay closed to the other roles.
import { expect, test } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  notes,
  openSettings,
  orgIdOf,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('the editor runs the newsroom', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const hugo = await newPerson(browser, testInfo, 'Hugo', invitation);
  await joinWith(hugo, 'Hugo');
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();

  // The gain ceiling goes down to 30.
  await openSettings(ines);
  await expect(ines.getByRole('heading', { name: 'Sophia Office', level: 1 })).toBeVisible();
  await expect(ines.getByText('Réglages de la rédaction', { exact: true })).toBeVisible();
  // « Enregistrer les réglages » waits for a change, and sleeps again once it is saved.
  const save = ines.getByRole('button', { name: 'Enregistrer les réglages' });
  await expect(save).toBeDisabled();
  const ceiling = ines.getByRole('group', { name: 'Gain fixe maximum' });
  for (let i = 0; i < 4; i += 1) await ceiling.getByRole('button', { name: 'Moins' }).click();
  await expect(ceiling).toContainText('30');
  await save.click();
  await expect(notes(ines)).toContainText('Réglages enregistrés.');
  await expect(save).toBeDisabled();

  // The logo is saved on its own, once the drawing changed.
  await ines.getByRole('button', { name: 'Modifier le logo' }).click();
  const editor = ines.getByRole('region', { name: 'Modifier le logo' });
  await expect(editor.getByRole('button', { name: 'Enregistrer' })).toBeDisabled();
  await editor.getByRole('button', { name: 'Effacer' }).click();
  await editor.getByRole('button', { name: 'Enregistrer' }).click();
  await expect(notes(ines)).toContainText('Logo enregistré.');
  await expect(save).toBeDisabled();

  // Hugo becomes a journalist and publishes at once, under the new ceiling.
  await ines.getByRole('link', { name: 'MEMBRES', exact: true }).click();
  await ines.getByLabel('Rôle de Hugo').selectOption('journalist');
  await expect(ines.getByLabel('Rôle de Hugo')).toHaveValue('journalist');
  await hugo.goto(`/o/${orgId}/pronos/nouveau`);
  await expect(hugo.getByRole('heading', { name: 'Nouveau prono' })).toBeVisible();
  const tooMuch = await call(hugo, 'POST', `/orgs/${orgId}/pronos`, {
    kind: 'yes_no',
    question: 'Le pot aura-t-il lieu ?',
    section_id: (await call(hugo, 'GET', `/orgs/${orgId}/sections`)).body[0].id,
    base_gain: 40,
    closes_at: new Date(Date.now() + 86_400_000).toISOString(),
  });
  expect(tooMuch.status).toBe(422);
  const prono = await publishProno(hugo, orgId, { question: 'Nice ou Monaco ?', base_gain: 30 });

  // Inès takes 15 laurels from Cami, with a reason: her balance moves, her score does not.
  const camiRow = ines.getByRole('listitem').filter({ hasText: 'Cami' });
  await camiRow.getByRole('button', { name: 'Ajuster les lauriers' }).click();
  await camiRow.getByLabel('LAURIERS À AJOUTER OU À RETIRER').fill('-15');
  // Her green laurels now, and what the adjustment leaves.
  await expect(camiRow).toContainText(
    "AUJOURD'HUI : 100 LAURIERS VERTS · APRÈS : 85 LAURIERS VERTS",
  );
  await camiRow.getByLabel('MOTIF (VISIBLE DANS SON RELEVÉ)').fill('erreur de saisie');
  await camiRow.getByRole('button', { name: 'Ajuster les lauriers de Cami' }).click();
  await expect(notes(ines)).toContainText('Lauriers ajustés : -15.');
  await expect(camiRow).toContainText('85 lauriers verts à miser');
  expect(await laurels(cami, orgId)).toEqual([85, 0]);
  const statement = await call(cami, 'GET', `/orgs/${orgId}/members/me/ledger`);
  expect(statement.body.items[0]).toMatchObject({ kind: 'adjustment', reason: 'erreur de saisie' });

  // A new access code: the old one no longer lets anybody in.
  const oldCode = (await call(ines, 'GET', `/orgs/${orgId}`)).body.access_code;
  await ines.getByRole('button', { name: 'Nouveau code' }).click();
  await expect(ines.getByRole('region', { name: "Le code d'accès" })).not.toContainText(oldCode);
  expect((await call(cami, 'POST', '/join/preview', { code: oldCode })).status).toBe(409);

  // Cami reports the prono; Inès settles it and Cami reads the note.
  const sent = await call(cami, 'POST', `/orgs/${orgId}/pronos/${prono.id}/reports`, {
    kind: 'content',
    message: 'Question en double.',
  });
  expect(sent.status).toBe(201);
  await ines.reload();
  await ines.getByRole('link', { name: /SIGNALEMENTS/ }).click();
  await expect(ines.getByText('Question en double.')).toBeVisible();
  await ines.getByLabel('NOTE POUR SON AUTEUR·RICE (FACULTATIF)').fill('Merci, prono corrigé.');
  await ines.getByRole('button', { name: "Clore : c'est réglé" }).click();
  await expect(ines.getByText('Aucun signalement ouvert.')).toBeVisible();
  await cami.goto(`/o/${orgId}/pronos/${prono.id}`);
  const mine = cami.getByRole('region', { name: 'TES SIGNALEMENTS' });
  await expect(mine).toContainText('Le contenu pose problème : réglé');
  await expect(mine).toContainText('Merci, prono corrigé.');

  // The settings stay closed to the journalist and the reader.
  for (const page of [hugo, cami]) {
    await page.goto(`/o/${orgId}/redaction`);
    await expect(page.getByRole('heading', { name: 'La rédaction' })).toBeAttached();
    await expect(page.getByRole('link', { name: /Réglages de la rédaction/ })).toHaveCount(0);
    await page.goto(`/o/${orgId}/reglages`);
    await expect(
      page.getByText('Ces réglages sont réservés à la rédaction en chef.'),
    ).toBeVisible();
  }
});

test('the editor deletes the newsroom', async ({ browser }, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Gazette éphémère', 'Inès');
  const orgId = orgIdOf(ines);
  await openSettings(ines);
  await ines.getByRole('link', { name: 'PARAMÈTRES', exact: true }).click();
  await ines.getByRole('button', { name: 'Supprimer la rédaction' }).click();
  // Confirmed by the newsroom's name, whatever its case.
  const yes = ines.getByRole('button', { name: 'Oui, supprimer la rédaction' });
  await expect(yes).toBeDisabled();
  await ines.getByLabel('NOM DE LA RÉDACTION').fill('gazette éphémère');
  await yes.click();
  await expect(notes(ines)).toContainText('Rédaction supprimée.');
  await expect(ines.getByRole('heading', { name: 'Bienvenue sur Sibylle' })).toBeVisible();
  expect((await call(ines, 'GET', `/orgs/${orgId}`)).status).toBe(404);
});
