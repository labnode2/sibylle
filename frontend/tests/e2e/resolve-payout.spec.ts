// Quickstart V3 and V4: designating a result and being paid, the early-bird bonus, a correction,
// a cancellation, relaunching a prono nobody bet on, and a new bet on an open-ended date.
import { expect, test, type Page } from '@playwright/test';

import {
  advanceClock,
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  orgIdOf,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

const DAY = 86_400_000;

/** A date as the API and a date field write it, `days` from today in Paris. */
function dayFromNow(days: number): string {
  return new Date(Date.now() + days * DAY).toLocaleDateString('en-CA', {
    timeZone: 'Europe/Paris',
  });
}

function option(prono: { options: { id: string; label: string }[] }, label: string): string {
  return prono.options.find((o) => o.label === label)!.id;
}

async function bet(page: Page, orgId: string, pronoId: string, body: object): Promise<void> {
  const answer = await call(page, 'POST', `/orgs/${orgId}/pronos/${pronoId}/bets`, body);
  expect(answer.status, JSON.stringify(answer.body)).toBe(201);
}

test('the spec example, then a correction and a cancellation', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const cancelled = await publishProno(ines, orgId, { question: 'Qui gagne le concours ?' });

  // Four members stake 10: Cami alone on the right answer, and first (early bird).
  const players: Record<string, Page> = {};
  for (const [name, pseudo] of [
    ['Camille', 'Cami'],
    ['Léo', 'Léo'],
    ['Manon', 'Manon'],
    ['Zoé', 'Zoé'],
  ] as const) {
    const page = await newPerson(browser, testInfo, name, invitation);
    await joinWith(page, pseudo);
    await expect(page.getByRole('heading', { name: `Bonjour ${pseudo}` })).toBeVisible();
    players[pseudo] = page;
  }
  await bet(players.Cami!, orgId, prono.id, { option_id: option(prono, 'Nice'), stake: 10 });
  for (const pseudo of ['Léo', 'Manon', 'Zoé']) {
    await bet(players[pseudo]!, orgId, prono.id, { option_id: option(prono, 'Monaco'), stake: 10 });
  }
  await bet(players.Cami!, orgId, cancelled.id, { option_id: option(cancelled, 'Nul'), stake: 30 });

  const cami = players.Cami!;
  await cami.goto(`/o/${orgId}/pronos/${prono.id}`);
  await ines.goto(`/o/${orgId}/pronos/${prono.id}`);
  advanceClock('4d');

  // Inès ticks Nice and publishes: the special edition reaches Cami without reloading.
  const answers = ines.getByRole('group', { name: 'LA OU LES BONNES RÉPONSES' });
  await answers.getByRole('button', { name: /Nice/ }).click();
  await expect(ines.getByText('1 personne avait vu juste')).toBeVisible();
  await ines.getByRole('button', { name: 'Publier le résultat' }).click();
  await expect(ines.getByText('Édition spéciale')).toBeVisible();

  const mine = cami.getByRole('region', { name: 'Ton résultat' });
  await expect(mine).toContainText('GAGNÉ', { timeout: 5_000 });
  await expect(mine).toContainText('+64');
  await expect(mine).toContainText('20 DE BASE + 4 LÈVE-TÔT + 40 DE CAGNOTTE');
  expect(await laurels(cami, orgId)).toEqual([100 - 10 - 30 + 64, 54]);
  expect(await laurels(players.Léo!, orgId)).toEqual([90, -10]);

  // Inès corrects to Monaco: the first payouts are reversed, the pot still shares 40.
  await ines.getByRole('button', { name: 'Corriger le résultat' }).click();
  await answers.getByRole('button', { name: /Nice/ }).click();
  await answers.getByRole('button', { name: /Monaco/ }).click();
  await expect(ines.getByText('3 personnes avaient vu juste')).toBeVisible();
  await ines.getByRole('button', { name: 'Corriger le résultat' }).click();
  await ines.getByRole('button', { name: 'Confirmer' }).click();
  await expect(ines.getByText('CORRIGÉE', { exact: false })).toBeVisible();
  await expect(mine).toContainText('PERDU', { timeout: 5_000 });

  const detail = await call(ines, 'GET', `/orgs/${orgId}/pronos/${prono.id}`);
  const winners = detail.body.special_edition.winners as { pot_share: number }[];
  expect(winners).toHaveLength(3);
  expect(winners.reduce((sum, w) => sum + w.pot_share, 0)).toBe(40);
  expect(await laurels(cami, orgId)).toEqual([60, -10]);

  // Inès cancels the other prono: Cami's 30 come back.
  await ines.goto(`/o/${orgId}/pronos/${cancelled.id}`);
  await ines.getByRole('button', { name: 'Annuler le prono' }).click();
  await ines.getByLabel('MOTIF (FACULTATIF)').fill('Concours reporté');
  await ines.getByRole('button', { name: "Confirmer l'annulation" }).click();
  await expect(ines.getByText('Prono annulé : toutes les mises ont été rendues.')).toBeVisible();
  expect(await laurels(cami, orgId)).toEqual([90, -10]);
});

test('relaunch a prono nobody bet on, and bet again on an open-ended date', async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);

  // Closed without a single bet: it can only be relaunched or cancelled.
  const empty = await publishProno(ines, orgId, { question: 'Le pot de départ aura-t-il lieu ?' });
  const someday = await publishProno(ines, orgId, {
    kind: 'date',
    options: [],
    question: 'Quand la machine à café sera-t-elle réparée ?',
    open_ended: true,
    closes_at: null,
  });
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();
  await bet(cami, orgId, someday.id, { date_value: dayFromNow(1), stake: 10 });

  advanceClock('4d');
  await ines.goto(`/o/${orgId}/pronos/${empty.id}`);
  await expect(ines.getByText("Personne n'a joué", { exact: false })).toBeVisible();
  await ines.getByRole('button', { name: "L'événement n'a pas eu lieu : relancer" }).click();
  await ines.getByLabel('MOTIF (FACULTATIF)').fill('Pot reporté');
  await ines.getByRole('button', { name: 'Relancer le prono' }).click();
  await expect(ines.getByRole('timer')).toBeVisible();
  const relaunched = await call(ines, 'GET', `/orgs/${orgId}/pronos/${empty.id}`);
  expect([relaunched.body.state, relaunched.body.relaunch_count]).toEqual(['open', 1]);

  // Cami's date has passed: she bets a new one; the first stake stays in the pot.
  await cami.goto(`/o/${orgId}/pronos/${someday.id}`);
  await cami.getByLabel('TA DATE').fill(dayFromNow(7));
  await cami.getByRole('button', { name: 'Plus' }).click();
  const rebetButton = cami.getByRole('button', { name: /Rejouer une date/ });
  await rebetButton.click();
  // "TON PRONO" already shows the passed bet; the form goes away once the new one is saved.
  await expect(rebetButton).toBeHidden();
  await expect(cami.getByText('TON PRONO', { exact: true })).toBeVisible();
  const rebet = await call(cami, 'GET', `/orgs/${orgId}/pronos/${someday.id}`);
  expect(rebet.body.pot).toBe(20);

  // The real date is designated: Cami's active bet wins, her first stake counts as lost.
  await ines.goto(`/o/${orgId}/pronos/${someday.id}`);
  await ines.getByLabel('LA DATE RÉELLE').fill(dayFromNow(7));
  await ines.getByRole('button', { name: 'Publier le résultat' }).click();
  await expect(ines.getByText('Édition spéciale')).toBeVisible();
  // 100 − 10 − 10, then 20 base + 4 early bird + the pot of 20; score 24 + (20 − 10) − 10.
  expect(await laurels(cami, orgId)).toEqual([124, 24]);
});
