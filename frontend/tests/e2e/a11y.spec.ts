// T147, principle VI: the main pages of the app, la une, a prono, the leaderboard, the press card,
// the newsroom's settings and the account's preferences, have no WCAG 2.2 A or AA violation that
// axe-core can find, in the light and the dark theme, on a phone (390 px) and on a computer
// (1 280 px), and reflow without scrolling sideways (1.4.10), which axe-core does not check. So
// does the choice an invitation link offers without a session (card #26).
import AxeBuilder from '@axe-core/playwright';
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

const WCAG_22_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

/** The width each project is checked at: a common phone, a common computer. */
const WIDTHS: Record<string, { width: number; height: number }> = {
  mobile: { width: 390, height: 844 },
  desktop: { width: 1280, height: 800 },
};

/** What axe-core finds on the page (or in the part of it `include` selects), one line per rule
 *  broken, with the elements that break it. */
async function violations(page: Page, include?: string): Promise<string[]> {
  const axe = new AxeBuilder({ page }).withTags(WCAG_22_AA);
  if (include) axe.include(include);
  const { violations } = await axe.analyze();
  return violations.map(
    (violation) =>
      `${violation.id} (${violation.impact}): ${violation.nodes
        .map((node) => node.target.join(' '))
        .join(', ')}`,
  );
}

/** What runs wider than the screen, which axe-core does not check: the page reflows at 390 px
 *  without scrolling sideways (1.4.10). */
async function overflow(page: Page): Promise<string[]> {
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  return sideways > 0 ? [`reflow: the page scrolls ${sideways} px sideways`] : [];
}

/** Opens `path` and waits until it has loaded what it shows and its entrance has played. */
async function visit(page: Page, path: string): Promise<void> {
  await page.goto(path);
  await page.waitForLoadState('networkidle');
  await expect(page.getByRole('main').first()).toBeVisible();
  await page.waitForTimeout(500);
}

test.beforeEach(resetClock);
test.afterEach(resetClock);

test('the main pages meet WCAG 2.2 AA in both themes', async ({ browser }, testInfo) => {
  test.setTimeout(240_000);
  const viewport = WIDTHS[testInfo.project.name]!;

  // An editor publishes a prono; a member joins and bets on it, so that the pages show a pot,
  // a bet and a leaderboard of two.
  const ines = await newPerson(browser, testInfo, 'Inès');
  await ines.setViewportSize(viewport);
  await createNewsroom(ines, 'Gazette de Nice', 'Inès');
  const orgId = orgIdOf(ines);
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  const nice = prono.options.find((o: { label: string }) => o.label === 'Nice').id;
  const bet = await call(cami, 'POST', `/orgs/${orgId}/pronos/${prono.id}/bets`, {
    option_id: nice,
    stake: 10,
  });
  expect(bet.status).toBe(201);
  await cami.context().close();

  const pages = [
    `/o/${orgId}`,
    `/o/${orgId}/pronos/${prono.id}`,
    `/o/${orgId}/classement`,
    `/o/${orgId}/profil`,
    `/o/${orgId}/reglages`,
    `/o/${orgId}/reglages/membres`,
    `/o/${orgId}/reglages/parametres`,
    '/compte',
  ];

  const found: Record<string, string[]> = {};
  for (const theme of ['light', 'dark'] as const) {
    expect((await call(ines, 'PATCH', '/me', { theme })).status).toBe(200);
    for (const path of pages) {
      await visit(ines, path);
      await expect(ines.locator('html')).toHaveAttribute('data-theme', theme);
      const broken = [...(await violations(ines)), ...(await overflow(ines))];
      if (broken.length > 0) found[`${theme} ${viewport.width}px ${path}`] = broken;
    }
    // On a computer, my account's menu, open under my avatar on la une. Open, it covers the
    // newsroom's card below (a click there closes it first): the menu itself is checked.
    if (testInfo.project.name === 'desktop') {
      await visit(ines, `/o/${orgId}`);
      await ines.getByRole('button', { name: 'INÈS, mon compte' }).click();
      await expect(ines.getByRole('list', { name: 'Mon compte' })).toBeVisible();
      const broken = await violations(ines, 'ul[aria-label="Mon compte"]');
      if (broken.length > 0) found[`${theme} ${viewport.width}px account menu`] = broken;
    }
  }
  expect(found).toEqual({});
});

test("an invitation link's choice, without a session, meets WCAG 2.2 AA in both themes", async ({
  page,
}, testInfo) => {
  const viewport = WIDTHS[testInfo.project.name]!;
  await page.setViewportSize(viewport);
  // The choice reads nothing of the invitation: any token shows it.
  const path = '/rejoindre/une-invitation';
  const found: Record<string, string[]> = {};
  for (const theme of ['light', 'dark'] as const) {
    // Without an account, the theme is the one last chosen on this device (light by default).
    if (theme === 'dark') {
      await page.evaluate(() =>
        localStorage.setItem(
          'sibylle.preferences.v2',
          JSON.stringify({ theme: 'dark', reduceMotion: false }),
        ),
      );
    }
    await visit(page, path);
    await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
    await expect(page.getByRole('link', { name: 'Se connecter' })).toBeVisible();
    const broken = [...(await violations(page)), ...(await overflow(page))];
    if (broken.length > 0) found[`${theme} ${viewport.width}px ${path}`] = broken;
  }
  expect(found).toEqual({});
});
