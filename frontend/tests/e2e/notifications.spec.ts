// US8: push notifications offered after a bet, then the switches of the profile. The device's
// push side is a stand-in: Playwright's Chromium cannot subscribe to a real push service, and the
// development server has no service worker.
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

/** A device that accepts push: permission, subscription (kept for the tab) and server key. */
async function pushCapableDevice(page: Page): Promise<void> {
  await page.route('**/api/push/vapid-public-key', (route) =>
    route.fulfill({ json: { key: 'BP_-AQID' } }),
  );
  await page.addInitScript(() => {
    const KEY = 'e2e.push';
    const endpoint = `https://fcm.googleapis.com/fcm/send/e2e-${Math.random().toString(36).slice(2)}`;
    const subscription = () => {
      const stored = sessionStorage.getItem(KEY);
      if (!stored) return null;
      return {
        endpoint: stored,
        toJSON: () => ({ endpoint: stored, keys: { p256dh: 'cle-publique', auth: 'secret' } }),
        unsubscribe: async () => {
          sessionStorage.removeItem(KEY);
          return true;
        },
      };
    };
    const pushManager = {
      getSubscription: async () => subscription(),
      subscribe: async () => {
        sessionStorage.setItem(KEY, sessionStorage.getItem(KEY) ?? endpoint);
        return subscription();
      },
    };
    Object.defineProperty(navigator, 'serviceWorker', {
      configurable: true,
      value: { getRegistration: async () => ({ pushManager }) },
    });
    Object.defineProperty(Notification, 'permission', {
      configurable: true,
      get: () => (sessionStorage.getItem(KEY) ? 'granted' : 'default'),
    });
    Notification.requestPermission = async () => 'granted';
  });
}

async function bet(page: Page, orgId: string, pronoId: string): Promise<void> {
  await page.goto(`/o/${orgId}/pronos/${pronoId}`);
  await page.getByRole('button', { name: /Nice/ }).click();
  await page.getByRole('button', { name: /Valider mon prono/ }).click();
  await expect(page.getByText('TON PRONO', { exact: true })).toBeVisible();
}

test('push offered after a bet, then set kind by kind in the settings', async ({
  browser,
}, testInfo) => {
  test.setTimeout(120_000);
  const ines = await newPerson(browser, testInfo, 'Inès');
  await createNewsroom(ines, 'Sophia Office', 'Inès');
  const orgId = orgIdOf(ines);
  const first = await publishProno(ines, orgId, { question: 'Nice ou Monaco samedi ?' });
  const second = await publishProno(ines, orgId, { question: 'Nice ou Lyon dimanche ?' });
  const cami = await newPerson(browser, testInfo, 'Camille', await invitationPath(ines));
  await joinWith(cami, 'Cami');
  await expect(cami.getByRole('heading', { name: 'Bonjour Cami' })).toBeVisible();
  await pushCapableDevice(cami);

  // After her bet, the offer; « Plus tard » sets it aside, also for the next bets.
  await bet(cami, orgId, first.id);
  const offer = cami.getByRole('region', { name: 'SOIS PRÉVENU·E' });
  await expect(offer).toContainText('Reçois le résultat de ce prono');
  await offer.getByRole('button', { name: 'Plus tard' }).click();
  await expect(offer).toBeHidden();
  await bet(cami, orgId, second.id);
  await expect(offer).toBeHidden();

  // In her settings: this device, then the eight switches.
  await cami.goto('/compte#notifications');
  const settings = cami.getByRole('region', { name: 'NOTIFICATIONS' });
  await expect(settings).toContainText('ne sont pas activées sur cet appareil');
  const subscribed = cami.waitForResponse(
    (r) => r.url().endsWith('/api/me/push-subscriptions') && r.request().method() === 'POST',
  );
  await settings.getByRole('button', { name: 'Activer sur cet appareil' }).click();
  const answer = await subscribed;
  expect(answer.status()).toBe(201);
  expect(answer.request().postDataJSON()).toMatchObject({
    endpoint: expect.stringContaining('https://fcm.googleapis.com/fcm/send/e2e-'),
    keys: { p256dh: 'cle-publique', auth: 'secret' },
  });
  await expect(settings).toContainText('Les notifications push arrivent sur cet appareil.');

  const newsByMail = settings.getByRole('switch', { name: 'Nouveau prono par e-mail' });
  await expect(newsByMail).toHaveAttribute('aria-checked', 'true');
  await newsByMail.click();
  await expect(newsByMail).toHaveAttribute('aria-checked', 'false');
  await cami.reload();
  await expect(newsByMail).toHaveAttribute('aria-checked', 'false');
  await expect(settings.getByRole('switch', { name: 'Nouveau prono par push' })).toHaveAttribute(
    'aria-checked',
    'true',
  );

  // Off on this device: the server forgets it.
  const forgotten = cami.waitForResponse(
    (r) => r.url().includes('/api/me/push-subscriptions/') && r.request().method() === 'DELETE',
  );
  await settings.getByRole('button', { name: 'Couper sur cet appareil' }).click();
  expect((await forgotten).status()).toBe(204);
  await expect(settings).toContainText('ne sont pas activées sur cet appareil');
});
