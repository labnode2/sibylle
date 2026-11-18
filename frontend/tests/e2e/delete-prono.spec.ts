// Deleting a cancelled prono (card #20): the editor cancels it, then « Supprimer le prono » asks
// for a confirmation that can be taken back. The prono leaves the list, the page of a member who
// had it open says it cannot be found, and the refund stays in her history, without a link.
import { expect, test } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  notes,
  orgIdOf,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('the editor deletes a cancelled prono', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const doomed = await publishProno(ines, orgId, { question: 'Qui gagne le concours ?' });
  await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });

  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  const nul = doomed.options.find((o: { label: string }) => o.label === 'Nul').id;
  const bet = await call(cami, 'POST', `/orgs/${orgId}/pronos/${doomed.id}/bets`, {
    option_id: nul,
    stake: 30,
  });
  expect(bet.status, JSON.stringify(bet.body)).toBe(201);
  await cami.goto(`/o/${orgId}/pronos/${doomed.id}`);
  await expect(cami.getByRole('heading', { name: 'Qui gagne le concours ?' })).toBeVisible();

  // Only a cancelled prono can be deleted: nothing to delete while it is open.
  await ines.goto(`/o/${orgId}/pronos/${doomed.id}`);
  await expect(ines.getByRole('heading', { name: 'Qui gagne le concours ?' })).toBeVisible();
  await expect(ines.getByRole('button', { name: 'Supprimer le prono' })).toHaveCount(0);
  await ines.getByRole('button', { name: 'Annuler le prono' }).click();
  await ines.getByRole('button', { name: "Confirmer l'annulation" }).click();
  await expect(ines.getByText('Prono annulé : toutes les mises ont été rendues.')).toBeVisible();

  // Asked, taken back, then asked again and confirmed.
  await ines.getByRole('button', { name: 'Supprimer le prono' }).click();
  const confirmation = ines.getByRole('group', { name: 'Supprimer le prono' });
  await expect(confirmation).toContainText('Le prono disparaîtra des listes');
  await confirmation.getByRole('button', { name: 'Retour' }).click();
  await expect(confirmation).toHaveCount(0);
  await ines.getByRole('button', { name: 'Supprimer le prono' }).click();
  await confirmation.getByRole('button', { name: 'Confirmer la suppression' }).click();

  // On to the list, where it is gone, even among the results.
  await expect(ines).toHaveURL(new RegExp(`/o/${orgId}/pronos$`));
  await expect(notes(ines)).toContainText('Prono supprimé.');
  await expect(ines.getByText('Nice ou Monaco samedi ?')).toBeVisible();
  await ines.getByRole('button', { name: /^RÉSOLUS/ }).click();
  await expect(ines.getByText("Aucun prono ici pour l'instant.")).toBeVisible();
  await expect(ines.getByText('Qui gagne le concours ?')).toHaveCount(0);

  // Cami's open page hears of it without a reload; the address now leads to « introuvable ».
  const gone = cami.getByText('Ce prono est introuvable : il a peut-être été supprimé.');
  await expect(gone).toBeVisible();
  await cami.reload();
  await expect(gone).toBeVisible();

  // Her 30 laurels came back, and the refund stays in her history, without a link.
  expect(await laurels(cami, orgId)).toEqual([100, 0]);
  await cami.goto(`/o/${orgId}/profil`);
  const history = cami.getByRole('region', { name: 'Mon relevé' });
  await expect(history.getByText('Qui gagne le concours ? (prono supprimé)').first()).toBeVisible();
  await expect(history.getByRole('link', { name: /Qui gagne le concours/ })).toHaveCount(0);
});
