// Coins: green laurels to stake, gold laurels in all, and Monday turning gold laurels into coins,
// with its good news shown once.
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
  sibylle,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('Monday turns gold laurels into coins, and says so once', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco ?' });
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();

  // A stake of 30: 70 green laurels left to stake, still 100 gold ones, no coins yet.
  const nice = prono.options.find((o: { label: string }) => o.label === 'Nice').id;
  const bet = await call(cami, 'POST', `/orgs/${orgId}/pronos/${prono.id}/bets`, {
    option_id: nice,
    stake: 30,
  });
  expect(bet.status).toBe(201);
  await cami.reload();
  // The front page's counters (the desktop header has the same ones).
  const page = cami.getByRole('main');
  await expect(page.getByText('70 lauriers verts à miser')).toBeAttached();
  await expect(page.getByText('100 lauriers en or')).toBeAttached();
  await expect(page.getByText('0 pièce', { exact: true })).toBeAttached();

  // Next Monday, while Cami has the app open: the good news shows at once.
  sibylle('clock', 'advance', '7d');
  expect(sibylle('coins', 'grant', '--org', orgId)).toContain('grant_weekly_coins: 2');
  const news = cami.getByRole('dialog', { name: 'Tes lauriers en or deviennent des pièces' });
  await expect(news).toBeVisible();
  await expect(news).toContainText("tes 100 lauriers en or t'ont rapporté 100 pièces");
  await expect(news).toContainText('Tu as maintenant 100 pièces');
  await news.getByRole('button', { name: 'Fermer' }).click();
  await expect(news).toBeHidden();

  // Seen once: it does not come back, and the laurels did not move.
  const weekly = cami.waitForResponse((r) => r.url().endsWith('/coins/weekly'));
  await cami.reload();
  await weekly;
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();
  await expect(cami.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByText('70 lauriers verts à miser')).toBeAttached();
  await expect(page.getByText('100 pièces', { exact: true })).toBeAttached();

  // Inès goes from the news to the collection, priced in coins.
  await ines.reload();
  const hers = ines.getByRole('dialog', { name: 'Tes lauriers en or deviennent des pièces' });
  await hers.getByRole('link', { name: 'Voir la collection' }).click();
  await expect(hers).toBeHidden();
  await expect(ines.getByRole('heading', { name: 'La collection' })).toBeVisible();
  await expect(
    ines.getByRole('button', { name: 'Acheter Couleur Rouge vif pour 400 pièces' }),
  ).toBeDisabled();
  expect((await call(ines, 'GET', `/orgs/${orgId}/coins/weekly`)).body).toBeNull();
});
