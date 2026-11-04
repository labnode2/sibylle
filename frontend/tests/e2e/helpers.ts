import { execFileSync } from 'node:child_process';

import { expect, type Browser, type Locator, type Page, type TestInfo } from '@playwright/test';

// A password for throwaway test accounts on the local app only.
export const PASSWORD = 'lauriers-de-test';

let counter = 0;

/** An e-mail no other run has used. */
export function uniqueEmail(name: string, testInfo: TestInfo): string {
  counter += 1;
  return `${name}-${testInfo.project.name}-${Date.now()}-${counter}@e2e.sibylle.test`;
}

/** A fresh browser context (its own cookies), signed up as a new account. */
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
  await page.getByLabel('PRÉNOM').fill(firstName);
  await page.getByLabel('NOM', { exact: true }).fill('Test');
  await page.getByLabel('E-MAIL').fill(uniqueEmail(firstName.toLowerCase(), testInfo));
  await page.getByLabel('MOT DE PASSE').fill(PASSWORD);
  await page.getByRole('button', { name: 'Créer mon compte' }).click();
  return page;
}

export async function createNewsroom(page: Page, title: string, pseudo: string): Promise<void> {
  await expect(page.getByRole('heading', { name: 'Bienvenue sur Sibylle' })).toBeVisible();
  await page.getByRole('link', { name: 'Créer une rédaction' }).click();
  await page.getByLabel('NOM DE LA RÉDACTION').fill(title);
  await page.getByLabel('TON PSEUDO DANS CETTE RÉDACTION').fill(pseudo);
  await page.getByRole('button', { name: 'Créer la rédaction' }).click();
  await expect(page.getByRole('heading', { name: `La une de ${title}` })).toBeVisible();
}

/** A prono's pot as shown: « Cagnotte : 20 lauriers… » on a phone, « 20 lauriers » in large on
 *  a computer. */
export function pot(page: Page, laurels: number): Locator {
  return page.getByText(new RegExp(`^(Cagnotte : )?${laurels} lauriers`)).filter({ visible: true });
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
