// Quickstart V9: five runs of the ball's race from la une, a sixth refused, then Monday pays the
// week to the balance only (US9); a Pixel mystère drawn in the editor, guessed in order, and
// ended both ways: everyone found, or every pixel shown (US10); the editor planning the games
// week by week, members seeing and playing only those (US12).
import { expect, test, type Page } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  laurels,
  newPerson,
  openSettings,
  orgIdOf,
  resetClock,
  sibylle,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('five runs a week, the best one counts, Monday pays', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);

  const games = ines.getByRole('region', { name: 'Jeux de la semaine' });
  await expect(games).toContainText('PAS ENCORE DE RECORD · 5 ESSAIS SUR 5');
  await games.getByRole('link', { name: /Course de la boule/ }).click();
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

test('Pixel mystère: drawn, guessed in order, ended both ways', async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const people: Page[] = [];
  for (const [name, pseudo] of [
    ['Camille', 'Cami'],
    ['Léo', 'Léo'],
    ['Manon', 'Manon'],
  ] as const) {
    const page = await newPerson(browser, testInfo, name, invitation);
    await joinWith(page, pseudo);
    await expect(page.getByRole('heading', { name: /^La une de / })).toBeVisible();
    people.push(page);
  }
  const [camiPage, leoPage, manonPage] = people as [Page, Page, Page];

  // Inès draws in the editor and chooses the word.
  await ines.goto(`/o/${orgId}/jeux/pixel`);
  await expect(ines.getByText('Pas de Pixel mystère en cours.')).toBeVisible();
  await ines.getByRole('button', { name: 'Dessiner un Pixel mystère' }).click();
  await ines.getByLabel('LE MOT À DEVINER').fill('Café');
  const editor = ines.getByRole('region', { name: 'Ton dessin' });
  await editor.getByRole('radio', { name: 'Rouge', exact: true }).click();
  await editor.getByRole('application').click({ position: { x: 40, y: 40 } });
  await editor.getByRole('button', { name: 'Déposer' }).click();
  await expect(ines.getByText('Ton dessin est lancé')).toBeVisible();
  await expect(ines.getByText('LE MOT : Café')).toBeVisible();

  // Cami, from la une: a wrong guess, then the word without its accent.
  const box = camiPage.getByRole('region', { name: 'Jeux de la semaine' });
  await camiPage.reload();
  await expect(box).toContainText('UN MOT DE 4 LETTRES · LANCÉ PAR LA RÉDACTION');
  await box.getByRole('link', { name: /Pixel mystère/ }).click();
  await expect(camiPage.getByRole('heading', { name: 'Pixel mystère' })).toBeVisible();
  await expect(camiPage.getByRole('img', { name: /37 pixels dévoilés sur 256/ })).toBeVisible();
  await camiPage.getByLabel('TA PROPOSITION').fill('thé');
  await camiPage.getByRole('button', { name: 'Proposer' }).click();
  await expect(
    camiPage.getByText("« thé » : ce n'est pas ça. Il te reste 2 essais aujourd'hui."),
  ).toBeVisible();
  const [balance] = await laurels(camiPage, orgId);
  await camiPage.getByLabel('TA PROPOSITION').fill('cafe');
  await camiPage.getByRole('button', { name: 'Proposer' }).click();
  await expect(
    camiPage.getByText('Bravo ! Tu trouves en premier et gagnes 10 lauriers.'),
  ).toBeVisible();
  await expect(camiPage.getByText('LE MOT : Café')).toBeVisible();
  expect((await laurels(camiPage, orgId))[0]).toBe(balance + 10);

  // Léo second; Manon spends her three guesses, the fourth waits for tomorrow.
  const second = await call(leoPage, 'POST', `/orgs/${orgId}/games/pixel/guesses`, {
    word: 'CAFÉ',
  });
  expect(second.body).toMatchObject({ correct: true, rank: 2, laurels: 7 });
  for (const word of ['thé', 'lait', 'sucre']) {
    await call(manonPage, 'POST', `/orgs/${orgId}/games/pixel/guesses`, { word });
  }
  const fourth = await call(manonPage, 'POST', `/orgs/${orgId}/games/pixel/guesses`, {
    word: 'café',
  });
  expect(fourth.status).toBe(409);
  const finders = camiPage.getByRole('region', { name: 'ONT TROUVÉ' });
  await expect(finders).toContainText('Cami');
  await expect(finders).toContainText('Léo');

  // Tomorrow Manon finds too: everyone but Inès did, the game ends for all.
  sibylle('clock', 'advance', '1d');
  const third = await call(manonPage, 'POST', `/orgs/${orgId}/games/pixel/guesses`, {
    word: 'cafe',
  });
  expect(third.body).toMatchObject({ correct: true, rank: 3, laurels: 5 });
  await ines.reload();
  await expect(ines.getByText(/^Partie terminée/)).toBeVisible();
  const finished = await call(leoPage, 'GET', `/orgs/${orgId}/games/pixel`);
  expect(finished.body).toMatchObject({ state: 'finished', word: 'Café' });

  // A second drawing waits for the next morning, then ends once every pixel shows.
  const blue = Buffer.from(new Uint8Array(256).fill(4)).toString('base64');
  const posted = await call(ines, 'POST', `/orgs/${orgId}/games/pixel/puzzles`, {
    word: 'Boule',
    drawing: { size: 16, palette: 'base-v1', pixels: blue },
  });
  expect(posted.status).toBe(201);
  expect(posted.body.state).toBe('queued');
  sibylle('clock', 'advance', '2d');
  expect(sibylle('games', 'reveal-pixel', '--org', orgId)).toContain('reveal_pixel_puzzles: 1');
  expect((await call(camiPage, 'GET', `/orgs/${orgId}/games/pixel`)).body).toMatchObject({
    state: 'active',
    letters: 5,
    word: null,
  });
  sibylle('clock', 'advance', '7d');
  sibylle('games', 'reveal-pixel', '--org', orgId);
  await camiPage.goto(`/o/${orgId}`);
  await expect(box).toContainText('LE MOT ÉTAIT « Boule »');
});

test('the editor plans the games, members see and play only those', async ({
  browser,
}, testInfo) => {
  test.setTimeout(150_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  const box = cami.getByRole('region', { name: 'Jeux de la semaine' });
  await expect(box.getByRole('link', { name: /Course de la boule/ })).toBeVisible();

  // The planning is the editor's only.
  await cami.goto(`/o/${orgId}/reglages/jeux`);
  await expect(cami.getByText('Ces réglages sont réservés à la rédaction en chef.')).toBeVisible();
  expect((await call(cami, 'GET', `/orgs/${orgId}/games/schedule`)).status).toBe(403);

  // Inès takes the race out of this week, after a word on what it cancels.
  await openSettings(ines);
  await ines
    .getByRole('navigation', { name: 'Réglages' })
    .getByRole('link', { name: 'JEUX' })
    .click();
  const weeks = ines.getByRole('region', { name: 'Les quatre semaines' });
  await expect(weeks.getByRole('row')).toHaveCount(5);
  const race = weeks.getByRole('checkbox', { name: 'Course de la boule, cette semaine' });
  await expect(race).toBeChecked();
  await race.click();
  await expect(weeks.getByText(/^Retirer la course de la boule de cette semaine \?/)).toBeVisible();
  await weeks.getByRole('button', { name: 'Retirer' }).click();
  await expect(race).not.toBeChecked();

  // Cami no longer sees it on la une, nor plays it.
  await cami.goto(`/o/${orgId}`);
  await expect(box.getByRole('link', { name: /Pixel mystère/ })).toBeVisible();
  await expect(box.getByRole('link', { name: /Course de la boule/ })).toHaveCount(0);
  await cami.goto(`/o/${orgId}/jeux/course`);
  await expect(
    cami.getByText("La course de la boule n'est pas au programme cette semaine."),
  ).toBeVisible();
  const run = await call(cami, 'POST', `/orgs/${orgId}/games/runner/runs`);
  expect([run.status, run.body.error.code]).toEqual([409, 'game_not_scheduled']);

  // With a drawing in play, taking Pixel mystère out too stops it and gives its word: the week
  // has no game left, and la une no games block.
  const blue = Buffer.from(new Uint8Array(256).fill(4)).toString('base64');
  const posted = await call(ines, 'POST', `/orgs/${orgId}/games/pixel/puzzles`, {
    word: 'Boule',
    drawing: { size: 16, palette: 'base-v1', pixels: blue },
  });
  expect(posted.body.state).toBe('active');
  const pixel = weeks.getByRole('checkbox', { name: 'Pixel mystère, cette semaine' });
  await pixel.click();
  await expect(weeks.getByText(/^Retirer Pixel mystère de cette semaine \?/)).toBeVisible();
  await weeks.getByRole('button', { name: 'Retirer' }).click();
  await expect(pixel).not.toBeChecked();
  await cami.goto(`/o/${orgId}`);
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  await expect(box).toHaveCount(0);
  await cami.goto(`/o/${orgId}/jeux/pixel`);
  await expect(cami.getByText("Pixel mystère n'est pas au programme cette semaine.")).toBeVisible();
  await expect(cami.getByText('LE MOT : Boule')).toBeVisible();

  // An upcoming week planned, then back to an ordinary week.
  const third = weeks.getByRole('row').nth(3);
  await third.getByRole('checkbox', { name: /^Pixel mystère/ }).click();
  await expect(third).toContainText('PROGRAMMÉE');
  await third.getByRole('button', { name: 'Revenir à une semaine ordinaire' }).click();
  await expect(third).toContainText('ORDINAIRE');
  await expect(third.getByRole('checkbox', { name: /^Pixel mystère/ })).toBeChecked();

  // An ordinary week without Pixel mystère holds from next week on; this week keeps its own.
  const ordinary = ines.getByRole('region', { name: 'Une semaine ordinaire' });
  const usualPixel = ordinary.getByRole('checkbox', { name: 'Pixel mystère', exact: true });
  await usualPixel.click();
  await expect(usualPixel).not.toBeChecked();
  const nextPixel = weeks
    .getByRole('row')
    .nth(2)
    .getByRole('checkbox', { name: /^Pixel mystère/ });
  await expect(nextPixel).not.toBeChecked();
  await expect(
    weeks.getByRole('checkbox', { name: 'Course de la boule, cette semaine' }),
  ).not.toBeChecked();
  sibylle('clock', 'advance', '7d');
  await cami.goto(`/o/${orgId}`);
  await expect(box).toContainText('PAS ENCORE DE RECORD · 5 ESSAIS SUR 5');
  await expect(box.getByRole('link', { name: /Pixel mystère/ })).toHaveCount(0);
});
