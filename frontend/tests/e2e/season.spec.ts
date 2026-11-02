// Quickstart V5: the six rankings, a live refresh after a result, and the end of the autumn
// season (simulated clock on 21 December 2026 at 00:00:30, Paris time).
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
  sibylle,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

function option(prono: { options: { id: string; label: string }[] }, label: string): string {
  return prono.options.find((o) => o.label === label)!.id;
}

/** The ranking as shown: "rank pseudo value", with "(toi)" on the member's own line. */
async function board(page: Page): Promise<string[]> {
  return page
    .getByRole('table')
    .locator('tbody tr')
    .evaluateAll((rows) =>
      rows.map((row) => {
        const [rank, member, value] = Array.from(row.children) as HTMLElement[];
        const shown = value!.querySelector('span > span') ?? value!;
        const me = row.getAttribute('aria-current') === 'true' ? ' (toi)' : '';
        return `${rank!.textContent} ${member!.querySelector('a')!.textContent}${me} ${shown.textContent}`;
      }),
    );
}

async function bet(page: Page, orgId: string, pronoId: string, body: object): Promise<void> {
  const answer = await call(page, 'POST', `/orgs/${orgId}/pronos/${pronoId}/bets`, body);
  expect(answer.status, JSON.stringify(answer.body)).toBe(201);
}

async function resolve(page: Page, orgId: string, prono: { id: string }, answer: string) {
  const result = await call(page, 'POST', `/orgs/${orgId}/pronos/${prono.id}/resolve`, {
    correct_option_ids: [answer],
  });
  expect(result.status, JSON.stringify(result.body)).toBe(200);
}

test('rankings, a live refresh and the end of the season', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const players: Record<string, Page> = {};
  for (const [name, pseudo] of [
    ['Camille', 'Cami'],
    ['Léo', 'Léo'],
  ] as const) {
    const page = await newPerson(browser, testInfo, name, invitation);
    await joinWith(page, pseudo);
    await expect(page.getByRole('heading', { name: `Bonjour ${pseudo}` })).toBeVisible();
    players[pseudo] = page;
  }
  const cami = players.Cami!;
  const leo = players.Léo!;

  // Cami bets first and wins: 20 base + 4 early bird + the pot of 20, minus her stake.
  const first = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  await bet(cami, orgId, first.id, { option_id: option(first, 'Nice'), stake: 10 });
  await bet(leo, orgId, first.id, { option_id: option(first, 'Monaco'), stake: 10 });
  advanceClock('4d');
  await resolve(ines, orgId, first, option(first, 'Nice'));

  // The leaderboard is a tab of the newsroom.
  await cami.goto(`/o/${orgId}`);
  // One link in the desktop bar, one in the mobile tab bar; the other one is hidden.
  await cami.getByRole('link', { name: 'CLASSEMENT' }).click();
  await expect(cami.getByRole('heading', { name: 'Classement' })).toBeVisible();
  await expect(cami.getByText(/^SAISON D'AUTOMNE 2026 · JUSQU'AU 20 DÉCEMBRE$/)).toBeVisible();
  await expect.poll(() => board(cami)).toEqual(['1 Cami (toi) 34', '2 Inès 0', '3 Léo -10']);

  const metric = cami.getByRole('group', { name: 'Classer par' });
  const period = cami.getByRole('group', { name: 'Période' });
  await metric.getByRole('button', { name: 'PRONOS GAGNÉS' }).click();
  await expect
    .poll(() => board(cami))
    .toEqual(['1 Cami (toi) 1 prono', '2 Inès 0 prono', '2 Léo 0 prono']);
  for (const name of ['MOIS', 'DEPUIS TOUJOURS', 'SAISON']) {
    await period.getByRole('button', { name }).click();
    await expect(period.getByRole('button', { name })).toHaveAttribute('aria-pressed', 'true');
    await expect
      .poll(() => board(cami))
      .toEqual(['1 Cami (toi) 1 prono', '2 Inès 0 prono', '2 Léo 0 prono']);
  }
  await expect(
    cami.getByRole('table', { name: /PRONOS GAGNÉS · SAISON D'AUTOMNE 2026/ }),
  ).toBeVisible();
  await metric.getByRole('button', { name: 'LAURIERS' }).click();

  // Léo watches the ranking while his win is published: it moves without reloading.
  await leo.goto(`/o/${orgId}/classement`);
  await expect.poll(() => board(leo)).toEqual(['1 Cami 34', '2 Inès 0', '3 Léo (toi) -10']);
  // The simulated clock is already 4 days ahead: close a week from now.
  const second = await publishProno(ines, orgId, {
    question: 'Le pot aura-t-il lieu ?',
    closes_at: new Date(Date.now() + 7 * 86_400_000).toISOString(),
  });
  await bet(leo, orgId, second.id, { option_id: option(second, 'Nice'), stake: 0 });
  advanceClock('4d');
  await resolve(ines, orgId, second, option(second, 'Nice'));
  await expect.poll(() => board(leo)).toEqual(['1 Cami 34', '2 Léo (toi) 14', '3 Inès 0']);

  // Sessions last 30 days from their last use: stop on the way, where each one slides forward,
  // so that the jump to the end of the season does not sign anybody out.
  sibylle('clock', 'set', '2026-12-01T12:00:00+01:00');
  for (const page of [ines, cami, leo])
    expect((await call(page, 'GET', `/orgs/${orgId}`)).status).toBe(200);

  // The end of autumn: engraved scores, everyone back to the starting balance.
  sibylle('clock', 'set', '2026-12-21T00:00:30+01:00');
  expect(sibylle('seasons', 'close', '--org', orgId)).toContain('close_finished_seasons: 1');
  // Run again (a restarted worker): nothing is paid twice.
  expect(sibylle('seasons', 'close', '--org', orgId)).toContain('close_finished_seasons: 0');

  await expect(cami.getByText(/^SAISON D'HIVER 2026 · JUSQU'AU 20 MARS$/)).toBeVisible();
  await expect.poll(() => board(cami)).toEqual(['1 Cami (toi) 0', '1 Inès 0', '1 Léo 0']);
  expect(await laurels(cami, orgId)).toEqual([100, 0]);
  expect(await laurels(leo, orgId)).toEqual([100, 0]);
  await period.getByRole('button', { name: 'DEPUIS TOUJOURS' }).click();
  await expect.poll(() => board(cami)).toEqual(['1 Cami (toi) 34', '2 Léo 14', '3 Inès 0']);
});
