// Quickstart V2: two browsers on the same prono. A bet shows up at the other's in less than 2 s
// without reloading, a second bet and a stake above the balance are refused, and the prono
// closes once the simulated clock passes its closing time. Also measures SC-001: from opening the
// invitation link to the first bet in less than 2 minutes.
import { expect, test, type Page } from '@playwright/test';

import {
  advanceClock,
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  newPerson,
  resetClock,
} from './helpers';

/** The prono's answers, read from the page's session. */
async function optionIds(page: Page, orgId: string, pronoId: string): Promise<string[]> {
  const prono = await call(page, 'GET', `/orgs/${orgId}/pronos/${pronoId}`);
  return (prono.body.options as { id: string }[]).map((option) => option.id);
}

/** Posts a bet from the page itself, the way the interface would. */
async function postBet(page: Page, orgId: string, pronoId: string, body: object) {
  return call(page, 'POST', `/orgs/${orgId}/pronos/${pronoId}/bets`, body);
}

// Back to the real time: an earlier run may have moved the simulated clock forward.
test.beforeEach(resetClock);
test.afterEach(resetClock);

test('a bet shows up live, then the prono closes', async ({ browser }, testInfo) => {
  // Inès runs the newsroom and publishes a prono.
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = new URL(ines.url()).pathname.split('/')[2]!;
  const invitation = await invitationPath(ines);

  await ines.goto(`/o/${orgId}/pronos/nouveau`);
  await ines.getByLabel('LA QUESTION').fill('Qui gagnera le derby de dimanche ?');
  await ines.getByLabel('Réponse 1').fill('OM');
  await ines.getByLabel('Réponse 2').fill('OGC Nice');
  await ines.getByRole('button', { name: 'Publier le prono' }).click();
  await expect(ines.getByRole('heading', { name: 'Qui gagnera le derby' })).toBeVisible();
  const pronoPath = new URL(ines.url()).pathname;
  const pronoId = pronoPath.split('/').at(-1)!;
  await expect(ines.getByText("Personne n'a encore joué")).toBeVisible();

  // The stake cannot go above the balance in the interface, nor through the API.
  const plus = ines.getByRole('button', { name: 'Plus' });
  for (let i = 0; i < 10; i += 1) await plus.click();
  await expect(ines.getByRole('group', { name: 'Ta mise' })).toContainText('100');
  await expect(plus).toBeDisabled();
  const [om] = await optionIds(ines, orgId, pronoId);
  const tooMuch = await postBet(ines, orgId, pronoId, { option_id: om, stake: 1000 });
  expect(tooMuch.status).toBe(409);
  expect(tooMuch.body).toMatchObject({ error: { code: 'insufficient_balance' } });
  for (let i = 0; i < 10; i += 1) await ines.getByRole('button', { name: 'Moins' }).click();

  // Cami opens the invitation, joins and bets: SC-001 starts when the link opens.
  const started = Date.now();
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();
  await cami.getByRole('link', { name: 'PRONOS' }).first().click();
  await cami.getByRole('link', { name: /Qui gagnera le derby/ }).click();
  await cami.getByRole('button', { name: /OGC Nice/ }).click();
  await cami.getByRole('button', { name: 'Plus' }).click();
  await cami.getByRole('button', { name: 'Plus' }).click();
  await expect(cami.getByText('Cagnotte : 20 lauriers')).toBeVisible();
  await cami.getByRole('button', { name: /Valider mon prono/ }).click();
  await expect(cami.getByText('TON PRONO', { exact: true })).toBeVisible();
  const betAt = Date.now();
  expect(betAt - started).toBeLessThan(120_000);
  testInfo.annotations.push({ type: 'SC-001', description: `${betAt - started} ms` });

  // Inès sees it without reloading, in less than 2 s.
  const people = ines.getByRole('region', { name: 'QUI A JOUÉ QUOI' });
  await expect(people.getByText('Cami')).toBeVisible({ timeout: 2_000 });
  await expect(people).toContainText('OGC Nice');
  await expect(ines.getByText('Cagnotte : 20 lauriers')).toBeVisible();

  // Cami's choice is final, and her balance went down.
  await expect(cami.getByRole('button', { name: /Valider mon prono/ })).toHaveCount(0);
  const again = await postBet(cami, orgId, pronoId, { option_id: om, stake: 0 });
  expect(again.status).toBe(409);
  expect(again.body).toMatchObject({ error: { code: 'already_bet' } });

  // Past the closing time, the worker closes the prono and both pages follow.
  advanceClock('2d');
  await expect(ines.getByText('Les pronos sont clos', { exact: false })).toBeVisible({
    timeout: 5_000,
  });
  await expect(ines.getByRole('button', { name: /Valider mon prono/ })).toHaveCount(0);
  await expect(cami.getByText('CLOS', { exact: true }).first()).toBeVisible();
});
