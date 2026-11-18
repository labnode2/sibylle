// Editing a prono (FR-035): « Modifier » on its page leads to the publishing form. Before the first
// bet everything changes; after it, the type, the choices and the gain are greyed with why, the
// question is reworded and the closing postponed, and the server refuses the rest. Every member
// reads the edits on the prono's page, as they were and as they are; a reader has no « Modifier ».
import { expect, test } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  newPerson,
  orgIdOf,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);

/** The same time of day, one day later, in a datetime-local field's words. */
function dayLater(value: string): string {
  const day = new Date(`${value.slice(0, 10)}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() + 1);
  return `${day.toISOString().slice(0, 10)}${value.slice(10)}`;
}

test('a prono is reworded after the first bets, and everyone reads what changed', async ({
  browser,
}, testInfo) => {
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const pronoPath = `/o/${orgId}/pronos/${prono.id}`;

  // Before any bet, everything changes.
  await ines.goto(pronoPath);
  await ines.getByRole('link', { name: 'Modifier' }).click();
  await expect(ines.getByRole('heading', { name: 'Modifier le prono' })).toBeVisible();
  await expect(ines.getByRole('button', { name: 'OUI/NON' })).toBeEnabled();
  await expect(ines.getByRole('button', { name: 'Enregistrer les modifications' })).toBeDisabled();
  await ines.getByLabel('LA QUESTION').fill('Nice ou Monaco samedi soir ?');
  await ines.getByRole('button', { name: 'Enregistrer les modifications' }).click();
  await expect(ines.getByRole('heading', { name: 'Nice ou Monaco samedi soir ?' })).toBeVisible();
  await expect(ines).toHaveURL(new RegExp(`${pronoPath}$`));

  // Cami joins and bets.
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await cami.goto(pronoPath);
  await cami.getByRole('button', { name: /Nice/ }).first().click();
  await cami.getByRole('button', { name: /Valider mon prono/ }).click();
  await expect(cami.getByText('TON PRONO', { exact: true })).toBeVisible();
  await expect(cami.getByRole('link', { name: 'Modifier' })).toHaveCount(0);

  // After it, what was bet on is greyed; the question and the closing still change.
  await ines.reload();
  await ines.getByRole('link', { name: 'Modifier' }).click();
  await expect(ines.getByRole('note')).toContainText('Déjà 1 pari sur ce prono');
  for (const kind of ['CHOIX', 'OUI/NON', 'NOMBRE', 'DATE']) {
    await expect(ines.getByRole('button', { name: kind, exact: true })).toBeDisabled();
  }
  await expect(ines.getByRole('textbox', { name: 'Choix 1' })).toBeDisabled();
  await expect(ines.getByRole('button', { name: 'Ajouter un choix' })).toHaveCount(0);
  await expect(
    ines.getByRole('group', { name: 'Gain fixe si juste' }).getByRole('button', { name: 'Plus' }),
  ).toBeDisabled();
  await expect(ines.getByText('VERROUILLÉ : DES PARIS ONT DÉJÀ ÉTÉ FAITS').first()).toBeVisible();
  const closing = ines.getByLabel('CLÔTURE DES PRONOS');
  const closesAt = await closing.inputValue();
  await expect(closing).toHaveAttribute('min', closesAt);
  await ines.getByLabel('LA QUESTION').fill('Nice ou Monaco dimanche ?');
  await closing.fill(dayLater(closesAt));
  await ines.getByRole('button', { name: 'Enregistrer les modifications' }).click();
  await expect(ines.getByRole('heading', { name: 'Nice ou Monaco dimanche ?' })).toBeVisible();

  // The server refuses what the form greys.
  const refused = await call(ines, 'PATCH', `/orgs/${orgId}/pronos/${prono.id}`, {
    kind: 'yes_no',
    options: [],
  });
  expect(refused.status).toBe(422);
  expect(refused.body.error.fields).toMatchObject({ kind: 'locked_after_bets' });

  // Cami reads both edits, the latest first, and her bet stands.
  await cami.reload();
  await expect(cami.getByRole('heading', { name: 'Nice ou Monaco dimanche ?' })).toBeVisible();
  const history = cami.getByRole('region', { name: 'Les modifications' });
  const edits = history.getByRole('listitem');
  await expect(edits).toHaveCount(2);
  await expect(edits.first()).toContainText('PAR INÈS');
  await expect(edits.first().getByRole('deletion').first()).toContainText(
    'Nice ou Monaco samedi soir ?',
  );
  await expect(edits.first().getByRole('insertion').first()).toContainText(
    'Nice ou Monaco dimanche ?',
  );
  await expect(edits.first()).toContainText('CLÔTURE');
  await expect(edits.last()).toContainText('Nice ou Monaco samedi ?');
  await expect(cami.getByText('TON PRONO', { exact: true })).toBeVisible();
});
