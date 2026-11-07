// US8: push notifications offered after a bet, then the switches of the profile. The device's
// push side is a stand-in: Playwright's Chromium cannot subscribe to a real push service, and the
// development server has no service worker.
import { expect, test, type Page } from '@playwright/test';

import {
  backOnSibylle,
  call,
  createNewsroom,
  emailOf,
  invitationPath,
  joinWith,
  keycloakLinkInMail,
  newPerson,
  notes,
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

/** The app opened from its icon, once installed from Chrome on a phone (or on a computer). */
async function installedApp(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const matchMedia = window.matchMedia.bind(window);
    window.matchMedia = (query: string) => {
      const list = matchMedia(query);
      if (query.includes('display-mode: standalone'))
        Object.defineProperty(list, 'matches', { value: true });
      return list;
    };
  });
}

test('the installed app offers push when it opens, once per device', async ({
  browser,
}, testInfo) => {
  test.setTimeout(90_000);
  const lea = await newPerson(browser, testInfo, 'Léa');
  await createNewsroom(lea, 'Antibes Matin', 'Léa');
  const une = lea.getByRole('heading', { name: 'La une de Antibes Matin' });
  const offer = lea.getByRole('dialog', { name: 'Activer les notifications ?' });
  const answered = () => lea.evaluate(() => localStorage.getItem('sibylle.push-dialog.done'));
  // In a browser's tab: no pop-up.
  await expect(offer).toBeHidden();

  // Opened from its icon: the pop-up; « Plus tard » sets it aside on this device.
  await installedApp(lea);
  await pushCapableDevice(lea);
  await lea.reload();
  await expect(offer).toBeVisible();
  await expect(offer).toContainText('APPLI INSTALLÉE');
  await offer.getByRole('button', { name: 'Plus tard' }).click();
  await expect(offer).toBeHidden();
  expect(await answered()).toBe('1');
  await lea.reload();
  await expect(une).toBeVisible();
  await expect(offer).toBeHidden();

  // As on a new device: « Activer les notifications » asks the browser, then sends this device
  // to the server, and the pop-up is done.
  await lea.evaluate(() => localStorage.removeItem('sibylle.push-dialog.done'));
  await lea.reload();
  const subscribed = lea.waitForResponse(
    (r) => r.url().endsWith('/api/me/push-subscriptions') && r.request().method() === 'POST',
  );
  await offer.getByRole('button', { name: 'Activer les notifications' }).click();
  expect((await subscribed).status()).toBe(201);
  await expect(offer).toBeHidden();
  await expect(lea.getByText('Notifications activées sur cet appareil.')).toBeVisible();
  expect(await answered()).toBe('1');
  await lea.reload();
  await expect(une).toBeVisible();
  await expect(offer).toBeHidden();
});

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
  await expect(cami.getByRole('heading', { name: /^La une de / })).toBeVisible();
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

// US2 of specs/002-keycloak-auth: Keycloak sends the address check at sign-up and again from the
// settings; its link confirms the address and opens the notification e-mails.
test("the address check of Keycloak's e-mail opens the notification e-mails", async ({
  browser,
}, testInfo) => {
  const SUBJECT = 'Confirme ton adresse pour Sibylle';
  const cami = await newPerson(browser, testInfo, 'Camille');
  const email = emailOf(cami);
  await keycloakLinkInMail(email, SUBJECT);

  await cami.goto('/compte#notifications');
  const settings = cami.getByRole('region', { name: 'NOTIFICATIONS' });
  await expect(settings).toContainText("Ton adresse n'est pas encore confirmée");
  await settings.getByRole('button', { name: "Renvoyer l'e-mail de confirmation" }).click();
  await expect(notes(cami)).toContainText("L'e-mail de confirmation vient de partir.");
  const link = await keycloakLinkInMail(email, SUBJECT, 2);

  // Followed in the same browser, the link confirms the address and leads back to the settings.
  await cami.goto(link);
  await cami.getByRole('link', { name: 'Continuer' }).click();
  await expect(cami.getByRole('heading', { name: 'Compte à jour' })).toBeVisible();
  await cami.getByRole('link', { name: 'Retour à Sibylle' }).click();
  await backOnSibylle(cami, testInfo);
  await expect(cami).toHaveURL(/\/compte$/);
  await expect(settings.getByRole('switch', { name: 'Résultats par e-mail' })).toBeVisible();
  await expect(settings).not.toContainText('pas encore confirmée');
  await expect(
    settings.getByRole('button', { name: "Renvoyer l'e-mail de confirmation" }),
  ).toBeHidden();
  expect((await call(cami, 'GET', '/me')).body.email_verified).toBe(true);
});
