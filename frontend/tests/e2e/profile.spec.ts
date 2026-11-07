// US7: the press card, the card's editor (pixel art, pseudo, frame, things on show) with the card
// redrawn as it goes, buying a colour with coins and a secret code, and another member's card
// from « La rédaction ». Then a new password from the settings (specs/002-keycloak-auth, US3).
import { expect, test } from '@playwright/test';

import {
  backOnSibylle,
  call,
  createNewsroom,
  emailOf,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  notes,
  orgIdOf,
  PASSWORD,
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
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();

  // Her press card: the second to arrive.
  await cami.getByRole('link', { name: 'PROFIL' }).click();
  const card = cami.getByRole('region', { name: 'Carte de presse' });
  await expect(card).toContainText('CARTE DE PRESSE N° 0002');
  await expect(card.getByRole('heading', { name: 'Cami' })).toBeVisible();
  await expect(card).toContainText(/MEMBRE DEPUIS [A-ZÉÛ]+ \d{4}/);

  // She redraws her avatar in 32 × 32, with the mouse and the keyboard; the card follows, and
  // « Annuler » and « Enregistrer » wake up with the first change.
  await card.getByRole('link', { name: 'Personnaliser ma carte' }).click();
  await expect(cami.getByRole('heading', { name: 'Ma carte de presse' })).toBeVisible();
  const preview = cami.getByRole('region', { name: 'CE QUE VOIENT LES AUTRES' });
  const editor = cami.getByRole('region', { name: 'MON PIXEL ART' });
  const save = preview.getByRole('button', { name: 'Enregistrer', exact: true });
  const cancel = preview.getByRole('button', { name: 'Annuler', exact: true });
  await expect(save).toBeDisabled();
  await expect(cancel).toBeDisabled();
  await editor.getByRole('button', { name: '32 × 32' }).click();
  await editor.getByRole('radio', { name: 'Rouge', exact: true }).click();
  const grid = editor.getByRole('application');
  await grid.click({ position: { x: 5, y: 5 } });
  await grid.press('ArrowRight');
  await grid.press('Space');
  await expect(save).toBeEnabled();
  await cami.getByLabel('TON PSEUDO DANS CETTE RÉDACTION').fill('Cami la Bulle');
  await expect(preview.getByRole('heading', { name: 'Cami la Bulle' })).toBeVisible();
  await cami.getByLabel('TON PSEUDO DANS CETTE RÉDACTION').fill('Cami');
  await save.click();
  // The page stays open, with nothing left to save; a note says it is done.
  await expect(notes(cami)).toContainText('Carte enregistrée');
  await expect(save).toBeDisabled();
  await expect(cancel).toBeDisabled();
  // Everyone sees it.
  const members = await call(ines, 'GET', `/orgs/${orgId}/members`);
  const drawn = members.body.find((m: { pseudo: string }) => m.pseudo === 'Cami').avatar;
  expect(drawn.size).toBe(32);
  const pixels = Buffer.from(drawn.pixels, 'base64');
  expect([pixels[0], pixels[1]]).toEqual([13, 13]);

  // Monday brings 500 coins; a colour for 400 coins, and the laurels stay.
  await cami.goto(`/o/${orgId}/profil`);
  sibylle('clock', 'advance', '7d');
  sibylle('coins', 'grant', '--org', orgId);
  const news = cami.getByRole('dialog', { name: 'Tes lauriers en or deviennent des pièces' });
  await news.getByRole('button', { name: 'Fermer' }).click();
  await cami.getByRole('link', { name: 'Ma collection' }).click();
  // 400 coins, or less if the deal of the week fell on it.
  await cami.getByRole('button', { name: /^Acheter Couleur Rouge vif pour \d+ pièces/ }).click();
  await cami.getByRole('button', { name: 'Acheter', exact: true }).click();
  await expect(cami.getByRole('listitem', { name: 'Couleur Rouge vif' })).toContainText('À TOI');
  expect(await laurels(cami, orgId)).toEqual([500, 0]);
  // The balls are not sold.
  await expect(cami.getByText("Les boules ne s'achètent pas", { exact: false })).toBeVisible();
  await expect(cami.getByRole('button', { name: /^Acheter Boule/ })).toHaveCount(0);

  // A secret code: once only.
  const code = `BOUH-${Date.now()}`;
  sibylle('secret-code', 'add', code, 'ball-halloween');
  const secret = cami.getByRole('region', { name: 'Un code secret ?' });
  await secret.getByLabel('TON CODE').fill(code.toLowerCase());
  await secret.getByRole('button', { name: 'Débloquer' }).click();
  await expect(notes(cami)).toContainText("Débloqué : Boule d'Halloween !");
  await secret.getByLabel('TON CODE').fill(code);
  await secret.getByRole('button', { name: 'Débloquer' }).click();
  await expect(notes(cami).getByRole('alert')).toBeVisible();

  // Back on the card: the colour is in the palette; the laurels statement has no purchase.
  await cami.getByRole('link', { name: 'Retour à ma carte de presse' }).click();
  await expect(cami.getByRole('region', { name: 'Couleurs et cadres' })).toContainText(
    'Couleur Rouge vif',
  );
  await expect(cami.getByRole('region', { name: 'Boules collectionnées' })).toContainText(
    "Boule d'Halloween",
  );
  const statement = cami.getByRole('region', { name: 'Mon relevé' });
  await expect(statement).toContainText('SOLDE DE DÉPART');
  await expect(statement).not.toContainText('ACHAT');
  // She shows the ball and the colour on her card, in that order: the card shows them at once.
  // « Annuler » puts back what was saved.
  await cami.getByRole('link', { name: 'Personnaliser ma carte' }).click();
  await expect(cami.getByRole('radio', { name: 'Rouge vif' })).toBeVisible();
  await cami.getByRole('button', { name: 'Couleur Rouge vif' }).click();
  await expect(preview.getByRole('list', { name: 'MIS EN AVANT' })).toBeVisible();
  await cancel.click();
  await expect(preview.getByRole('list', { name: 'MIS EN AVANT' })).toHaveCount(0);
  await expect(cami.getByText('MIS EN AVANT · 0 / 3')).toBeVisible();
  await cami.getByRole('button', { name: "Boule d'Halloween" }).click();
  await cami.getByRole('button', { name: 'Couleur Rouge vif' }).click();
  await expect(cami.getByText('MIS EN AVANT · 2 / 3')).toBeVisible();
  const order = [/Boule d'Halloween/, /Couleur Rouge vif/];
  await expect(
    preview.getByRole('list', { name: 'MIS EN AVANT' }).getByRole('listitem'),
  ).toHaveText(order);
  await save.click();
  await expect(save).toBeDisabled();
  await cami.goto(`/o/${orgId}/profil`);
  const shown = cami.getByRole('list', { name: 'MIS EN AVANT' });
  await expect(shown.getByRole('listitem')).toHaveText(order);

  // Inès finds her in « La rédaction », a tab of its own, with her role, and sees the same card.
  await ines.goto(`/o/${orgId}/profil`);
  await ines
    .getByRole('dialog', { name: 'Tes lauriers en or deviennent des pièces' })
    .getByRole('button', { name: 'Fermer' })
    .click();
  await ines.getByRole('link', { name: /^(LA )?RÉDACTION$/ }).click();
  await expect(ines.getByRole('heading', { name: 'La rédaction', level: 1 })).toBeVisible();
  await expect(ines.getByRole('listitem').filter({ hasText: 'Cami' })).toContainText(
    'LECTEUR·RICE',
  );
  await ines.getByRole('link', { name: 'Cami' }).click();
  await expect(ines.getByRole('region', { name: 'Carte de presse' })).toContainText('Cami');
  await expect(ines.getByRole('list', { name: 'MIS EN AVANT' })).toContainText("Boule d'Halloween");
  await expect(ines.getByRole('region', { name: 'Mon relevé' })).toHaveCount(0);
});

// US3 of specs/002-keycloak-auth: « Changer mon mot de passe » leads to Keycloak's page, which signs
// the other devices out (a back-channel logout, US4), then back to the settings.
test('a new password from the settings signs the other devices out', async ({
  browser,
}, testInfo) => {
  const NEW_PASSWORD = 'nouvelles-boules-de-cristal';
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const une = `/o/${orgIdOf(ines)}`;

  // The same account on a phone, on la une: its WebSocket is open.
  const phone = await (await browser.newContext({ ...testInfo.project.use })).newPage();
  await phone.goto(une);
  await phone.getByLabel('E-mail').fill(emailOf(ines));
  await phone.getByLabel('Mot de passe').fill(PASSWORD);
  await phone.getByRole('button', { name: 'Se connecter' }).click();
  await backOnSibylle(phone, testInfo);
  await expect(phone.getByRole('heading', { name: 'La une de Sophia Office' })).toBeVisible();

  await ines.goto('/compte');
  await ines.getByRole('link', { name: 'Changer mon mot de passe' }).click();
  await expect(ines.getByRole('heading', { name: 'Nouveau mot de passe' })).toBeVisible();
  const signOutOthers = ines.getByRole('checkbox', { name: 'Déconnecter mes autres appareils' });
  await expect(signOutOthers).toBeChecked();
  // The page's region is named like its field: the field, by its name.
  await ines.locator('input[name="password-new"]').fill(NEW_PASSWORD);
  await ines.getByRole('button', { name: 'Changer de mot de passe' }).click();
  await backOnSibylle(ines, testInfo);
  await expect(ines).toHaveURL(/\/compte$/);
  await expect(ines.getByRole('heading', { name: 'Mes réglages' })).toBeVisible();

  // The phone is signed out at once: Keycloak's sign-in page, where the new password works.
  await expect(phone.getByRole('heading', { name: 'Connexion' })).toBeVisible();
  await phone.getByLabel('E-mail').fill(emailOf(ines));
  await phone.getByLabel('Mot de passe').fill(NEW_PASSWORD);
  await phone.getByRole('button', { name: 'Se connecter' }).click();
  await backOnSibylle(phone, testInfo);
  await expect(phone.getByRole('heading', { name: 'La une de Sophia Office' })).toBeVisible();
});
