import { execFileSync } from 'node:child_process';

import { expect, type Browser, type Locator, type Page, type TestInfo } from '@playwright/test';

// A password for throwaway test accounts of the local Keycloak only.
export const PASSWORD = 'lauriers-de-test';

let counter = 0;

/** An e-mail no other run has used. Keycloak wants its local part in ASCII: « Inès » signs up as
 *  ines-…. */
export function uniqueEmail(name: string, testInfo: TestInfo): string {
  counter += 1;
  const ascii = name.normalize('NFD').replace(/\p{Diacritic}/gu, '');
  return `${ascii}-${testInfo.project.name}-${Date.now()}-${counter}@e2e.sibylle.test`;
}

const emails = new WeakMap<Page, string>();

/** The address a page of `newPerson` signed up with. */
export function emailOf(page: Page): string {
  return emails.get(page)!;
}

// The local Keycloak (`make keycloak`) and its admin, admin / admin (keycloak/dev.sh): what an
// administrator does in its console.
const KEYCLOAK = process.env.KEYCLOAK_URL ?? 'http://localhost:8280';

/** A call to the admin API of the realm `sibylle`, as the local Keycloak's admin. */
export async function keycloakAdmin(method: string, path: string): Promise<Response> {
  const signedIn = await fetch(`${KEYCLOAK}/realms/master/protocol/openid-connect/token`, {
    method: 'POST',
    body: new URLSearchParams({
      grant_type: 'password',
      client_id: 'admin-cli',
      username: 'admin',
      password: 'admin',
    }),
  });
  const { access_token: token } = (await signedIn.json()) as { access_token: string };
  return fetch(`${KEYCLOAK}/admin/realms/sibylle${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** The id of the account `email` in Keycloak's realm. */
export async function keycloakUserId(email: string): Promise<string> {
  const query = new URLSearchParams({ email, exact: 'true' });
  const users = (await (await keycloakAdmin('GET', `/users?${query}`)).json()) as { id: string }[];
  return users[0]!.id;
}

// Mailpit (`make db`), where the local Keycloak sends its e-mails.
const MAILPIT = process.env.MAILPIT_URL ?? 'http://localhost:8025';

/** The link to Keycloak of the newest e-mail sent to `to` with `subject`, once Mailpit holds
 *  `count` of them. */
export async function keycloakLinkInMail(to: string, subject: string, count = 1): Promise<string> {
  let link = '';
  await expect
    .poll(
      async () => {
        const query = new URLSearchParams({ query: `to:"${to}" subject:"${subject}"` });
        const found = (await (await fetch(`${MAILPIT}/api/v1/search?${query}`)).json()) as {
          messages: { ID: string }[];
        };
        if (found.messages.length < count) return false;
        const newest = (await (
          await fetch(`${MAILPIT}/api/v1/message/${found.messages[0]!.ID}`)
        ).json()) as { Text: string };
        link = newest.Text.match(/https?:\/\/\S+\/login-actions\/\S+/)?.[0] ?? '';
        return link !== '';
      },
      { message: `${count} e-mail(s) « ${subject} » to ${to}`, timeout: 15_000 },
    )
    .toBe(true);
  return link;
}

/** Back on Sibylle from Keycloak's pages, past the server's way back (/api/auth/callback). */
export async function backOnSibylle(page: Page, testInfo: TestInfo): Promise<void> {
  const app = new URL(testInfo.project.use.baseURL!).origin;
  await page.waitForURL((url) => url.origin === app && !url.pathname.startsWith('/api/'));
}

/** A fresh browser context (its own cookies), signed up as a new account on the sign-up page of
 *  the local Keycloak (`make keycloak`), and back on `startAt`, signed in. A page behind a
 *  session sends the visitor to Keycloak's sign-in page, which leads to the sign-up. */
export async function newPerson(
  browser: Browser,
  testInfo: TestInfo,
  firstName: string,
  startAt = '/',
): Promise<Page> {
  const context = await browser.newContext({ ...testInfo.project.use });
  const page = await context.newPage();
  await page.goto(startAt);
  await page.getByRole('link', { name: 'Créer un compte' }).click();
  const email = uniqueEmail(firstName.toLowerCase(), testInfo);
  emails.set(page, email);
  await signUpOnKeycloak(page, testInfo, firstName, email);
  return page;
}

/** Fills Keycloak's « Créer un compte » page, on screen, and comes back on Sibylle. */
export async function signUpOnKeycloak(
  page: Page,
  testInfo: TestInfo,
  firstName: string,
  email: string,
): Promise<void> {
  await expect(page.getByRole('heading', { name: 'Créer un compte' })).toBeVisible();
  await page.getByLabel('Prénom').fill(firstName);
  await page.getByLabel('Nom', { exact: true }).fill('Test');
  await page.getByLabel('E-mail').fill(email);
  await page.getByLabel('Mot de passe').fill(PASSWORD);
  await page.getByRole('button', { name: 'Créer mon compte' }).click();
  await backOnSibylle(page, testInfo);
}

export async function createNewsroom(page: Page, title: string, pseudo: string): Promise<void> {
  await expect(page.getByRole('heading', { name: 'Bienvenue sur Sibylle' })).toBeVisible();
  await page.getByRole('link', { name: 'Créer une rédaction' }).click();
  await page.getByLabel('NOM DE LA RÉDACTION').fill(title);
  await page.getByLabel('TON PSEUDO DANS CETTE RÉDACTION').fill(pseudo);
  await page.getByRole('button', { name: 'Créer la rédaction' }).click();
  // The first visit to la une compiles its modules when the dev server has just started.
  await expect(page.getByRole('heading', { name: `La une de ${title}` })).toBeVisible({
    timeout: 15_000,
  });
}

/** A prono's pot as shown: « Cagnotte : 20 lauriers… » on a phone, « 20 lauriers » in large on
 *  a computer. */
export function pot(page: Page, laurels: number): Locator {
  return page.getByText(new RegExp(`^(Cagnotte : )?${laurels} lauriers`)).filter({ visible: true });
}

/** The notes at the top right that say how an action went (ui/Toaster). */
export function notes(page: Page): Locator {
  return page.getByRole('region', { name: 'Infos', exact: true });
}

/** The newsroom's settings: the editor reaches them from « La rédaction ». */
export async function openSettings(page: Page): Promise<void> {
  await page.getByRole('link', { name: /^(LA )?RÉDACTION$/ }).click();
  await page.getByRole('link', { name: 'Réglages de la rédaction', exact: true }).click();
}

export async function joinWith(page: Page, pseudo: string): Promise<void> {
  const field = page.getByLabel('TON PSEUDO DANS CETTE RÉDACTION');
  await field.fill(pseudo);
  const charter = page.getByRole('checkbox', { name: /accepte la charte/ });
  if (!(await charter.isChecked())) await charter.check();
  await page.getByRole('button', { name: 'Rejoindre la rédaction' }).click();
}

/** Runs `sibylle …` on the API's side, with the simulated clock. */
export function sibylle(...args: string[]): string {
  return execFileSync('uv', ['run', '--directory', '../backend', 'sibylle', ...args], {
    env: { ...process.env, SIBYLLE_CLOCK: 'fake' },
    encoding: 'utf-8',
  });
}

/** Puts the simulated clock back on the real time. */
export function resetClock(): void {
  sibylle('clock', 'set', new Date().toISOString().replace('Z', '+00:00'));
}

/** Moves the simulated clock and lets the worker open and close the pronos. */
export function advanceClock(duration: string): void {
  sibylle('clock', 'advance', duration);
  sibylle('jobs', 'run', 'advance_pronos');
}

// Answers are read loosely in tests: the contract tests check their shape.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Json = any;

export type ApiAnswer = { status: number; body: Json };

/** Calls the API from the page itself, with its session, the way the interface would. */
export async function call(
  page: Page,
  method: 'GET' | 'POST' | 'PATCH',
  url: string,
  body?: object,
): Promise<ApiAnswer> {
  return page.evaluate(
    async ({ method, url, body }) => {
      const response = await fetch(url, {
        method,
        headers: {
          ...(body ? { 'Content-Type': 'application/json' } : {}),
          // The CSRF check wants it on every request that changes something.
          ...(method === 'GET' ? {} : { 'X-Sibylle': '1' }),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
      return { status: response.status, body: (await response.json()) as unknown };
    },
    { method, url: `/api${url}`, body },
  );
}

/** The newsroom id of a page under /o/:orgId. */
export function orgIdOf(page: Page): string {
  return new URL(page.url()).pathname.split('/')[2]!;
}

/** Creates an invitation link from the editor's members page and returns its path; the page
 * goes back to la une. */
export async function invitationPath(page: Page): Promise<string> {
  const orgId = orgIdOf(page);
  await page.goto(`/o/${orgId}/reglages/membres`);
  await page.getByRole('button', { name: 'Créer le lien' }).click();
  const path = new URL(await page.getByLabel('LIEN À PARTAGER').inputValue()).pathname;
  await page.goto(`/o/${orgId}`);
  return path;
}

/** Publishes a prono through the API, closing in three days unless `fields` say otherwise. */
export async function publishProno(page: Page, orgId: string, fields: object): Promise<Json> {
  const sections = await call(page, 'GET', `/orgs/${orgId}/sections`);
  const answer = await call(page, 'POST', `/orgs/${orgId}/pronos`, {
    kind: 'choice',
    options: ['Nice', 'Nul', 'Monaco'],
    base_gain: 20,
    section_id: sections.body[0].id,
    closes_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    ...fields,
  });
  expect(answer.status, JSON.stringify(answer.body)).toBe(201);
  return answer.body;
}

/** The member's balance and season score in the newsroom. */
export async function laurels(page: Page, orgId: string): Promise<[number, number]> {
  const org = await call(page, 'GET', `/orgs/${orgId}`);
  return [org.body.my_membership.balance, org.body.my_membership.season_score];
}
