// US13: two pronos won in a row light the flame beside the pseudo, in the leaderboard and on the
// press card; a loss puts it out and the record stays.
import { expect, test, type Page } from '@playwright/test';

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
test.afterEach(resetClock);

/** A day from now, as an open-ended date prono takes it. */
const day = (days: number) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 10);

/** An open-ended date prono, settled while open on the day `result` days from now; each
 *  member bets a day too, and the closest one wins. */
async function round(editor: Page, orgId: string, result: number, ...bets: [Page, number][]) {
  const prono = await publishProno(editor, orgId, {
    kind: 'date',
    options: [],
    open_ended: true,
    closes_at: null,
    question: `Quand la machine à café sera-t-elle réparée (${result}) ?`,
  });
  for (const [page, days] of bets) {
    const bet = await call(page, 'POST', `/orgs/${orgId}/pronos/${prono.id}/bets`, {
      date_value: day(days),
      stake: 0,
    });
    expect(bet.status, JSON.stringify(bet.body)).toBe(201);
  }
  const resolved = await call(editor, 'POST', `/orgs/${orgId}/pronos/${prono.id}/resolve`, {
    result_date: day(result),
  });
  expect(resolved.status, JSON.stringify(resolved.body)).toBe(200);
}

test('a chain of wins lights the flame, a loss puts it out', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  const leo = await newPerson(browser, testInfo, 'Léo', invitation);
  await joinWith(leo, 'Léo');
  await expect(leo.getByRole('heading', { name: /^La une de / })).toBeVisible();

  // Cami sees right twice in a row; Léo, never.
  await round(ines, orgId, 5, [cami, 5], [leo, 9]);
  await round(ines, orgId, 6, [cami, 6], [leo, 9]);

  await cami.goto(`/o/${orgId}/classement`);
  const row = (pseudo: string) => cami.locator('tbody tr').filter({ hasText: pseudo });
  await expect(row('Cami').getByTitle("2 pronos gagnés d'affilée")).toBeVisible();
  await expect(row('Léo').getByTitle(/gagnés d'affilée/)).toHaveCount(0);

  await cami.goto(`/o/${orgId}/profil`);
  const card = cami.getByRole('region', { name: 'Carte de presse' });
  await expect(card.getByTitle("2 pronos gagnés d'affilée")).toBeVisible();
  await expect(card).toContainText("RECORD : 2 PRONOS GAGNÉS D'AFFILÉE");

  // A loss puts the flame out; the record stays.
  await round(ines, orgId, 5, [cami, 9], [leo, 5]);
  await cami.reload();
  await expect(card).toContainText("RECORD : 2 PRONOS GAGNÉS D'AFFILÉE");
  await expect(card.getByTitle(/gagnés d'affilée/)).toHaveCount(0);
  await cami.goto(`/o/${orgId}/classement`);
  await expect(row('Léo')).toBeVisible();
  await expect(cami.locator('tbody').getByTitle(/gagnés d'affilée/)).toHaveCount(0);
});
