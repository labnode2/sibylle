// Push notifications on this device: the browser asks for permission only after a click, the
// subscription goes to the server, and an iPhone is told what it needs first (iOS 16.4 or later
// and the app added to the home screen).
import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { toast } from '../../ui/Toaster';
import { forgetSubscription, sendSubscription, useVapidKey } from './api';

export type PushStatus =
  | 'loading'
  // An iPhone or iPad where the app is not on the home screen yet.
  | 'ios-install'
  // A browser without push, or the app without its service worker (development).
  | 'unsupported'
  // The server has no push keys.
  | 'unavailable'
  // Refused in the browser: only its settings can change that.
  | 'denied'
  | 'off'
  | 'on';

export type PushEnvironment = {
  ios: boolean;
  standalone: boolean;
  supported: boolean;
  key: string | null | undefined;
  permission: NotificationPermission;
  subscribed: boolean | undefined;
};

export function pushStatus(env: PushEnvironment): PushStatus {
  if (env.ios && !env.standalone) return 'ios-install';
  if (!env.supported) return 'unsupported';
  if (env.key === undefined || env.subscribed === undefined) return 'loading';
  if (env.key === null) return 'unavailable';
  if (env.permission === 'denied') return 'denied';
  return env.subscribed && env.permission === 'granted' ? 'on' : 'off';
}

/** The server's key, base64url as `sibylle gen-secrets` writes it, as the browser wants it. */
export function keyBytes(key: string): Uint8Array<ArrayBuffer> {
  const base64 = (key + '='.repeat((4 - (key.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  const raw = atob(base64);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes;
}

function isIos(): boolean {
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  );
}

function isStandalone(): boolean {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function hasPush(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

async function registration(): Promise<ServiceWorkerRegistration | undefined> {
  return hasPush() ? navigator.serviceWorker.getRegistration() : undefined;
}

export function usePush() {
  const { t } = useTranslation('notifications');
  const key = useVapidKey();
  const [worker, setWorker] = useState<ServiceWorkerRegistration | null | undefined>(undefined);
  const [subscribed, setSubscribed] = useState<boolean | undefined>(undefined);
  const [permission, setPermission] = useState<NotificationPermission>(
    hasPush() ? Notification.permission : 'default',
  );
  const [busy, setBusy] = useState(false);

  // What this device has now; a subscription found is attached again to whoever is signed in.
  useEffect(() => {
    let active = true;
    void (async () => {
      const found = (await registration()) ?? null;
      const subscription = await found?.pushManager.getSubscription();
      if (subscription) await sendSubscription(subscription).catch(() => undefined);
      if (!active) return;
      setWorker(found);
      setSubscribed(Boolean(subscription));
    })();
    return () => {
      active = false;
    };
  }, []);

  const status = pushStatus({
    ios: isIos(),
    standalone: isStandalone(),
    supported: hasPush() && worker !== null,
    key: key.data,
    permission,
    subscribed: worker === undefined ? undefined : subscribed,
  });

  const enable = useCallback(async () => {
    if (!worker || !key.data) return;
    setBusy(true);
    try {
      const answer = await Notification.requestPermission();
      setPermission(answer);
      if (answer !== 'granted') return;
      const subscription = await worker.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: keyBytes(key.data),
      });
      await sendSubscription(subscription);
      setSubscribed(true);
      toast.success(t('device.enabled'));
    } catch {
      toast.error(t('device.failed'));
    } finally {
      setBusy(false);
    }
  }, [worker, key.data, t]);

  const disable = useCallback(async () => {
    if (!worker) return;
    setBusy(true);
    try {
      const subscription = await worker.pushManager.getSubscription();
      if (subscription) {
        await forgetSubscription(await sendSubscription(subscription));
        await subscription.unsubscribe();
      }
      setSubscribed(false);
      toast.success(t('device.disabled'));
    } catch {
      toast.error(t('device.disableFailed'));
    } finally {
      setBusy(false);
    }
  }, [worker, t]);

  return { status, busy, enable, disable };
}
