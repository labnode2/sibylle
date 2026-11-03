// US5: la une in the spec's order, a reader's proposal published by the editor from la une, and
// a quick reaction that reaches the other screen, then goes away on a second press.
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

test('la une, a proposal and a reaction', async ({ browser }, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const invitation = await invitationPath(ines);
  const cami = await newPerson(browser, testInfo, 'Camille', invitation);
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();

  // The prono closing first is the headline; the other one follows.
  await publishProno(ines, orgId, {
    question: 'Qui gagne le baby-foot ?',
    closes_at: new Date(Date.now() + 3 * DAY).toISOString(),
  });
  const coffee = await publishProno(ines, orgId, {
    question: 'Combien de cafés jeudi ?',
    // Before any "tomorrow at 18:00", whatever the time the test runs.
    closes_at: new Date(Date.now() + DAY / 2).toISOString(),
  });
  await cami.reload();
  const headline = cami.getByRole('article', { name: 'À la une' });
  await expect(headline.getByRole('link', { name: 'Combien de cafés jeudi ?' })).toBeVisible();
  await expect(headline).toContainText('0 PRONO · CAGNOTTE 0');
  await expect(cami.getByRole('link', { name: /Qui gagne le baby-foot/ })).toBeVisible();
  await expect(cami.getByRole('region', { name: 'À désigner' })).toHaveCount(0);

  // Cami proposes a prono; it waits for a journalist.
  await cami.goto(`/o/${orgId}/pronos/nouveau`);
  await expect(cami.getByRole('heading', { name: 'Proposer un prono' })).toBeVisible();
  await cami.getByLabel('LA QUESTION').fill('Le pot de vendredi aura-t-il lieu ?');
  await cami.getByRole('textbox', { name: 'Choix 1' }).fill('Oui, à 18 h');
  await cami.getByRole('textbox', { name: 'Choix 2' }).fill('Non, reporté');
  await cami.getByRole('button', { name: 'Proposer le prono' }).click();
  await expect(
    cami.getByText('En attente : un·e journaliste doit valider', { exact: false }),
  ).toBeVisible();
  const proposalUrl = cami.url();

  // Inès sees it on her front page and publishes it with a gain of 30.
  await ines.goto(`/o/${orgId}`);
  const proposals = ines.getByRole('region', { name: 'PROPOSITIONS À VALIDER' });
  await expect(proposals).toContainText('PROPOSÉ PAR CAMI');
  await proposals.getByRole('button', { name: 'Plus' }).click();
  await proposals.getByRole('button', { name: 'Plus' }).click();
  await proposals.getByRole('button', { name: 'Publier' }).click();
  await expect(proposals).toHaveCount(0);

  await cami.goto(proposalUrl);
  await expect(cami.getByRole('timer')).toBeVisible();
  await expect(cami.getByText('En attente', { exact: false })).toHaveCount(0);

  // A reaction on the headline's page reaches Inès's screen; a second press takes it back.
  await openFollowing(ines, `/o/${orgId}/pronos/${coffee.id}`, `prono:${coffee.id}`);
  await cami.goto(`/o/${orgId}`);
  await cami
    .getByRole('article', { name: 'À la une' })
    .getByRole('link', { name: 'Je pronostique' })
    .click();
  const camiReactions = cami.getByRole('group', { name: 'Réactions' });
  const inesReactions = ines.getByRole('group', { name: 'Réactions' });
  await camiReactions.getByRole('button', { name: 'Bien vu (0)' }).click();
  await expect(camiReactions.getByRole('button', { name: 'Bien vu (1)' })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await expect(inesReactions.getByRole('button', { name: 'Bien vu (1)' })).toHaveAttribute(
    'aria-pressed',
    'false',
  );
  await camiReactions.getByRole('button', { name: 'Bien vu (1)' }).click();
  await expect(inesReactions.getByRole('button', { name: 'Bien vu (0)' })).toBeVisible();
});
