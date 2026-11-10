// SC-005 (T148): over a full journey through the app, the browser sends no request to a domain
// other than the app's own: no font, image, script, style or analytics from elsewhere. The only
// other address it may reach is the sign-in server, the operator's own Keycloak (auth.<domaine>
// in production, the local one here), whose pages are checked the same way.
import { expect, test, type Browser, type Page, type TestInfo } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  orgIdOf,
  publishProno,
  resetClock,
  signUpOnKeycloak,
  uniqueEmail,
} from './helpers';

const KEYCLOAK = new URL(process.env.KEYCLOAK_URL ?? 'http://localhost:8280').host;

/** A page in a fresh browser context whose every request, from its pages, frames and service
 *  worker, and every WebSocket, adds its address to `requested`. */
async function recordedPage(
  browser: Browser,
  testInfo: TestInfo,
  requested: Set<string>,
): Promise<Page> {
  const context = await browser.newContext({ ...testInfo.project.use });
  context.on('request', (request) => requested.add(request.url()));
  context.on('page', (page) => page.on('websocket', (socket) => requested.add(socket.url())));
  return context.newPage();
}

/** `newPerson`, with the requests of Keycloak's sign-up pages recorded too. */
async function newPerson(
  browser: Browser,
  testInfo: TestInfo,
  requested: Set<string>,
  firstName: string,
  startAt = '/',
): Promise<Page> {
  const page = await recordedPage(browser, testInfo, requested);
  await page.goto(startAt);
  await page.getByRole('link', { name: 'Créer un compte' }).click();
  await signUpOnKeycloak(page, testInfo, firstName, uniqueEmail(firstName.toLowerCase(), testInfo));
  return page;
}

/** The host of an address, or none for the data: and blob: ones, which go nowhere. */
function hostOf(url: string): string | null {
  return url.startsWith('data:') || url.startsWith('blob:') ? null : new URL(url).host;
}

/** Opens `path` and waits until the page has asked for all it needs. */
async function visit(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.waitForLoadState('networkidle');
}

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('no request leaves the app', async ({ browser }, testInfo) => {
  test.setTimeout(180_000);
  const app = new URL(testInfo.project.use.baseURL!).host;
  const requested = new Set<string>();

  // A visitor first: the sign-in pages, without an account.
  const visitor = await recordedPage(browser, testInfo, requested);
  for (const path of ['/connexion', '/inscription', '/mot-de-passe/oubli', '/au-revoir']) {
    await visit(visitor, path);
  }

  // An editor signs up on Keycloak's pages, creates a newsroom and publishes a prono with a link
  // to another site: the link is shown, nothing is fetched from it.
  const ines = await newPerson(browser, testInfo, requested, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const prono = await publishProno(ines, orgId, {
    question: 'Nice ou Monaco samedi ?',
    link_url: 'https://example.com/match',
  });

  // A member joins by an invitation and bets.
  const cami = await newPerson(browser, testInfo, requested, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  const nice = prono.options.find((o: { label: string }) => o.label === 'Nice').id;
  const bet = await call(cami, 'POST', `/orgs/${orgId}/pronos/${prono.id}/bets`, {
    option_id: nice,
    stake: 10,
  });
  expect(bet.status).toBe(201);

  // Every page of the newsroom, for a member and for the editor.
  const pages = [
    `/o/${orgId}`,
    `/o/${orgId}/pronos`,
    `/o/${orgId}/pronos/${prono.id}`,
    `/o/${orgId}/classement`,
    `/o/${orgId}/profil`,
    `/o/${orgId}/profil/carte`,
    `/o/${orgId}/redaction`,
    `/o/${orgId}/collection`,
    `/o/${orgId}/jeux/course`,
    `/o/${orgId}/jeux/pixel`,
    '/compte',
    '/bienvenue',
  ];
  for (const path of pages) await visit(cami, path);
  for (const path of [
    ...pages,
    `/o/${orgId}/pronos/nouveau`,
    `/o/${orgId}/reglages/membres`,
    `/o/${orgId}/reglages/jeux`,
    `/o/${orgId}/reglages/signalements`,
    `/o/${orgId}/reglages/parametres`,
  ]) {
    await visit(ines, path);
  }

  // A press card made public, seen without an account.
  expect(
    (await call(ines, 'PATCH', `/orgs/${orgId}/members/me`, { card_public: true })).status,
  ).toBe(200);
  await visit(ines, `/o/${orgId}/profil`);
  const link = ines.getByRole('region', { name: 'Profil public' }).getByLabel('LIEN PUBLIC');
  await visit(visitor, new URL(await link.inputValue()).pathname);
  await expect(visitor.getByRole('region', { name: 'Carte de presse' })).toBeVisible();

  // The journey went through the app and Keycloak, its live updates included, and nowhere else.
  const hosts = new Set([...requested].map(hostOf));
  expect(hosts).toContain(app);
  expect(hosts).toContain(KEYCLOAK);
  expect([...requested].some((url) => url.startsWith('ws'))).toBe(true);
  const elsewhere = [...requested].filter((url) => {
    const host = hostOf(url);
    return host !== null && host !== app && host !== KEYCLOAK;
  });
  expect(elsewhere).toEqual([]);
});
