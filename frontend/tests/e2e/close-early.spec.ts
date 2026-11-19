// Card #25: the newsroom closes a prono's bets before their planned time (« Clore les paris
// maintenant »), after a confirmation. The bettor sees it close without reloading, la une lists it
// at once among the results to designate, and its result is given right away, days before the
// expected result date.
import { expect, test, type Page } from '@playwright/test';

import {
  call,
  createNewsroom,
  invitationPath,
  joinWith,
  newPerson,
  notes,
  orgIdOf,
  publishProno,
  resetClock,
} from './helpers';

test.beforeEach(resetClock);
test.afterEach(resetClock);

const DAY = 86_400_000;

/** Opens a page and waits until the server confirms it follows the topic live. */
async function openFollowing(page: Page, path: string, topic: string): Promise<void> {
  // The dev server opens its own socket too: wait for the app's.
  const following = page
    .waitForEvent('websocket', (socket) => socket.url().endsWith('/api/ws'))
    .then((socket) =>
      socket.waitForEvent('framereceived', {
        predicate: (frame) =>
          String(frame.payload).includes('"subscribed"') && String(frame.payload).includes(topic),
      }),
    );
  await page.goto(path);
  await following;
}

test('close the bets early, then give the result at once', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const prono = await publishProno(ines, orgId, {
    question: 'Qui gagne le baby-foot ?',
    closes_at: new Date(Date.now() + 3 * DAY).toISOString(),
    result_expected_at: new Date(Date.now() + 4 * DAY).toISOString(),
  });
  const nice = (prono.options as { id: string; label: string }[]).find(
    (option) => option.label === 'Nice',
  )!.id;
  const bets = `/orgs/${orgId}/pronos/${prono.id}/bets`;

  // Cami bets, and keeps the prono open on her screen.
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
  expect((await call(cami, 'POST', bets, { option_id: nice, stake: 10 })).status).toBe(201);
  await openFollowing(cami, `/o/${orgId}/pronos/${prono.id}`, `prono:${prono.id}`);
  await expect(cami.getByRole('timer')).toBeVisible();

  // Inès goes from la une to the prono: the bets stop once she confirms.
  await ines.goto(`/o/${orgId}`);
  await ines
    .getByRole('article', { name: 'À la une' })
    .getByRole('link', { name: 'Qui gagne le baby-foot ?' })
    .click();
  await ines.getByRole('button', { name: 'Clore les paris maintenant' }).click();
  const asking = ines.getByRole('form', { name: 'Clore les paris maintenant' });
  await expect(asking).toContainText('Plus personne ne pourra parier : la clôture prévue ');
  await asking.getByRole('button', { name: 'Confirmer la clôture' }).click();
  await expect(notes(ines)).toContainText('Paris clos : plus personne ne peut parier.');
  // Its result can be designated at once.
  await expect(ines.getByText('CLOS · EN ATTENTE DE TON VERDICT')).toBeVisible();
  await expect(ines.getByRole('button', { name: 'Clore les paris maintenant' })).toHaveCount(0);

  // Cami's screen follows without reloading: no more countdown, and no more bets.
  await expect(cami.getByText(/^Les pronos ont été clos plus tôt que prévu, /)).toBeVisible({
    timeout: 5_000,
  });
  await expect(cami.getByRole('timer')).toHaveCount(0);
  const late = await call(cami, 'POST', bets, { option_id: nice, stake: 5 });
  expect([late.status, late.body.error.code]).toEqual([409, 'invalid_state']);

  // Back on la une, the prono waits among the results to designate.
  await ines.goBack();
  const toDesignate = ines.getByRole('region', { name: 'À désigner' });
  await toDesignate.getByRole('link', { name: /Qui gagne le baby-foot/ }).click();

  // The result comes days before the expected date: Cami is paid straight away.
  const answers = ines.getByRole('group', { name: 'LA OU LES BONNES RÉPONSES' });
  await answers.getByRole('button', { name: /Nice/ }).click();
  await ines.getByRole('button', { name: 'Publier le résultat' }).click();
  await expect(ines.getByText('Édition spéciale')).toBeVisible();
  await expect(cami.getByRole('region', { name: 'Ton résultat' })).toContainText('GAGNÉ', {
    timeout: 5_000,
  });
  const detail = await call(ines, 'GET', `/orgs/${orgId}/pronos/${prono.id}`);
  expect(detail.body.state).toBe('resolved');
  expect(Date.parse(detail.body.result_expected_at)).toBeGreaterThan(Date.now() + 3 * DAY);
});
