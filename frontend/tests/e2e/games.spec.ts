// Quickstart V9 (US9): five runs of the ball's race from la une, a sixth refused, then Monday
// pays the week to the balance only. Pixel mystère joins with US10.
import { expect, test } from '@playwright/test';

import { call, createNewsroom, laurels, newPerson, orgIdOf, resetClock, sibylle } from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('five runs a week, the best one counts, Monday pays', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);

  const games = ines.getByRole('region', { name: 'LES JEUX DE LA SEMAINE' });
  await expect(games).toContainText('PAS ENCORE DE RECORD · 5 ESSAIS SUR 5');
  await games.getByRole('link', { name: 'Jouer' }).click();
  await expect(ines.getByRole('heading', { name: 'Course de la boule' })).toBeVisible();

  // Nobody jumps: each run ends on the first obstacle, after a couple of seconds.
  for (let left = 4; left >= 0; left -= 1) {
    const finished = ines.waitForResponse((r) => r.url().endsWith('/finish'));
    await ines.getByRole('button', { name: /Lancer une partie|Rejouer/ }).click();
    expect((await finished).status()).toBe(200);
    await expect(ines.getByRole('status').filter({ hasText: 'Score :' })).toBeVisible();
    await expect(ines.getByText(`${left} essai`)).toBeVisible();
  }
  await expect(
    ines.getByText(/Tes 5 essais de la semaine sont joués\. Nouveaux essais lundi/),
  ).toBeVisible();
  await expect(ines.getByRole('button', { name: 'Rejouer' })).toHaveCount(0);
  const sixth = await call(ines, 'POST', `/orgs/${orgId}/games/runner/runs`);
  expect(sixth.status).toBe(409);
  expect(sixth.body.error.code).toBe('attempts_exhausted');

  const week = ines.getByRole('region', { name: 'CLASSEMENT DE LA SEMAINE' });
  await expect(week).toContainText('Inès');

  // The next week: the race pays its first, to the balance only.
  const [balance, score] = await laurels(ines, orgId);
  sibylle('clock', 'advance', '7d');
  expect(sibylle('games', 'pay-runner', '--org', orgId)).toContain('pay_runner_week: 1');
  expect(await laurels(ines, orgId)).toEqual([balance + 10, score]);
  await ines.goto(`/o/${orgId}`);
  await expect(games).toContainText('PAS ENCORE DE RECORD · 5 ESSAIS SUR 5');
});
