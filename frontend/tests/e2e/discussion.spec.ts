// US14: the discussion under a prono, live from one screen to the other, with likes; each one
// deletes their own messages and the editor removes the others'; la une counts them.
import { expect, test, type Page } from '@playwright/test';

import {
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

const HINT = "Monaco n'a pas gagné à Nice depuis 2019.";

const discussion = (page: Page) => page.getByRole('region', { name: 'La discussion' });
const message = (page: Page, text: string) =>
  discussion(page).getByRole('listitem').filter({ hasText: text });

async function write(page: Page, text: string): Promise<void> {
  await discussion(page).getByLabel('TON MESSAGE').fill(text);
  await discussion(page).getByRole('button', { name: 'Publier' }).click();
  await expect(message(page, text)).toBeVisible();
}

test('members discuss a prono live, like and delete messages', async ({ browser }, testInfo) => {
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
  const prono = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const page = `/o/${orgId}/pronos/${prono.id}`;

  // Both look at the prono; Cami's message reaches Léo without reloading.
  await cami.goto(page);
  await leo.goto(page);
  await expect(discussion(leo)).toContainText('Pas encore de message');
  await write(cami, HINT);
  await expect(message(leo, HINT)).toContainText('Cami');

  // Léo likes it: Cami sees who did.
  await message(leo, HINT)
    .getByRole('button', { name: /^J'aime/ })
    .click();
  await expect(message(leo, HINT).getByRole('button', { name: /^J'aime/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(message(cami, HINT)).toContainText('Aimé par Léo');

  // La une counts the messages.
  await write(leo, 'Hors sujet : qui a pris mon agrafeuse ?');
  await ines.goto(`/o/${orgId}`);
  await expect(ines.getByText(/· 2 MESSAGES/).first()).toBeVisible();

  // The editor removes Léo's message; Léo cannot remove Cami's.
  await expect(message(leo, HINT).getByRole('button', { name: /Supprimer|Retirer/ })).toHaveCount(
    0,
  );
  await ines.goto(page);
  const offTopic = message(ines, 'agrafeuse');
  await offTopic.getByRole('button', { name: 'Retirer' }).click();
  await expect(offTopic).toContainText('Retirer ce message de la discussion ?');
  await offTopic.getByRole('button', { name: 'Retirer' }).click();
  await expect(message(cami, 'agrafeuse')).toHaveCount(0);

  // Cami deletes her own.
  const mine = message(cami, HINT);
  await mine.getByRole('button', { name: 'Supprimer' }).click();
  await mine.getByRole('button', { name: 'Supprimer' }).click();
  await expect(discussion(leo)).toContainText('Pas encore de message');
});
