// Card #28: an unconfirmed address (`email_verified: false`) holds back the notification e-mails
// only. This device's push is turned on from the settings as for anyone, its switches stay on
// hand, and the page never promises e-mails that will not leave before the confirmation. The
// device is a phone's browser that accepts push; the server's answers are stand-ins.
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { KINDS } from '../../src/features/notifications/api';
import { NotificationPrefs } from '../../src/features/notifications/NotificationPrefs';

const server = vi.hoisted(() => ({
  // The account's switches: all on, as for a new account.
  prefs: [
    'new_prono',
    'closing_soon',
    'result',
    'designation_reminder',
    'report',
    'mention',
    'discussion',
  ].flatMap((type) => ['push', 'email'].map((channel) => ({ type, channel, enabled: true }))),
  setPref: vi.fn(),
  sendSubscription: vi.fn(async () => 'abonnement-1'),
  resend: vi.fn(),
}));

vi.mock('../../src/features/notifications/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/notifications/api')>()),
  useNotificationPrefs: () => ({ data: server.prefs }),
  useSetNotificationPref: () => ({ mutate: server.setPref }),
  useVapidKey: () => ({ data: 'BP_-AQID' }),
  sendSubscription: server.sendSubscription,
  forgetSubscription: vi.fn(),
}));
vi.mock('../../src/features/auth/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/auth/api')>()),
  useResendVerification: () => ({ mutate: server.resend, isPending: false }),
}));

/** The phone's browser: a service worker whose push manager subscribes once permission is
 *  given, or (`withPush: false`) a browser without push. */
const device = {
  subscription: null as null | { endpoint: string; toJSON: () => object },
  permission: 'default' as NotificationPermission,
  subscribe: vi.fn(),
  requestPermission: vi.fn(),
};

function phone({ withPush = true } = {}) {
  device.subscription = null;
  device.permission = 'default';
  device.subscribe.mockImplementation(async () => {
    device.subscription = {
      endpoint: 'https://fcm.googleapis.com/fcm/send/telephone-de-zoe',
      toJSON: () => ({}),
    };
    return device.subscription;
  });
  device.requestPermission.mockImplementation(async () => {
    device.permission = 'granted';
    return 'granted';
  });
  const pushManager = {
    getSubscription: async () => device.subscription,
    subscribe: device.subscribe,
  };
  Object.defineProperty(navigator, 'serviceWorker', {
    configurable: true,
    value: { getRegistration: async () => (withPush ? { pushManager } : undefined) },
  });
  Object.defineProperty(window, 'PushManager', { configurable: true, value: class {} });
  Object.defineProperty(window, 'Notification', {
    configurable: true,
    value: {
      get permission() {
        return device.permission;
      },
      requestPermission: device.requestPermission,
    },
  });
}

beforeEach(() => phone());

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  for (const [target, name] of [
    [navigator, 'serviceWorker'],
    [window, 'PushManager'],
    [window, 'Notification'],
  ] as const) {
    Reflect.deleteProperty(target, name);
  }
});

function settings(emailVerified: boolean) {
  render(
    <MemoryRouter initialEntries={['/compte']}>
      <NotificationPrefs emailVerified={emailVerified} />
    </MemoryRouter>,
  );
  return screen.getByRole('region', { name: 'NOTIFICATIONS' });
}

const LABELS: Record<string, string> = {
  new_prono: 'Nouveau prono',
  closing_soon: 'Plus que 2 h',
  result: 'Résultats',
  designation_reminder: 'Résultats à désigner',
  report: 'Signalements',
  mention: 'Tags',
  discussion: 'Discussions',
};

describe('an unconfirmed address', () => {
  it('turns push on from the settings, and waits for the confirmation for the e-mails only', async () => {
    const user = userEvent.setup();
    const section = settings(false);

    // The device's push, on hand, beside what is said of the address.
    const enable = await within(section).findByRole('button', {
      name: 'Activer sur cet appareil',
    });
    expect(enable).toBeEnabled();
    expect(section).toHaveTextContent(
      "Ton adresse n'est pas encore confirmée. Seuls les e-mails de notification attendent sa confirmation : les notifications push marchent déjà.",
    );
    expect(
      within(section).getByRole('button', { name: "Renvoyer l'e-mail de confirmation" }),
    ).toBeEnabled();

    // Only the e-mail switches wait; every push switch can be flipped.
    for (const kind of KINDS) {
      expect(
        within(section).getByRole('switch', { name: `${LABELS[kind]} par push` }),
      ).toBeEnabled();
      expect(
        within(section).getByRole('switch', { name: `${LABELS[kind]} par e-mail` }),
      ).toBeDisabled();
    }
    await user.click(within(section).getByRole('switch', { name: 'Résultats par push' }));
    expect(server.setPref).toHaveBeenCalledWith({
      type: 'result',
      channel: 'push',
      enabled: false,
    });

    // The browser asks, the device subscribes, and the server gets it.
    await user.click(enable);
    expect(device.requestPermission).toHaveBeenCalledOnce();
    expect(device.subscribe).toHaveBeenCalledWith(
      expect.objectContaining({ userVisibleOnly: true }),
    );
    expect(server.sendSubscription).toHaveBeenCalledWith(device.subscription);
    expect(
      await within(section).findByText('Les notifications push arrivent sur cet appareil.'),
    ).toBeVisible();
    expect(within(section).getByRole('button', { name: 'Couper sur cet appareil' })).toBeEnabled();
  });

  it('is not promised e-mails where this device cannot take push', async () => {
    phone({ withPush: false });
    const section = settings(false);
    expect(
      await within(section).findByText(
        'Ce navigateur ne reçoit pas les notifications push. Les e-mails arriveront une fois ton adresse confirmée.',
      ),
    ).toBeVisible();
    expect(section).not.toHaveTextContent('Les e-mails arrivent quand même');
  });
});

describe('a confirmed address', () => {
  it('has every switch, and the e-mails where this device cannot take push', async () => {
    phone({ withPush: false });
    const section = settings(true);
    expect(
      await within(section).findByText(
        'Ce navigateur ne reçoit pas les notifications push. Les e-mails arrivent quand même.',
      ),
    ).toBeVisible();
    expect(section).not.toHaveTextContent('pas encore confirmée');
    for (const kind of KINDS) {
      expect(
        within(section).getByRole('switch', { name: `${LABELS[kind]} par e-mail` }),
      ).toBeEnabled();
    }
  });
});
