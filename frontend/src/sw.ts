/// <reference lib="webworker" />
// Service worker: keeps the app's shell for offline reading (betting needs a connection: the
// shell shows a banner when offline), and shows the push notifications (US8).
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';

declare const self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: (string | { url: string; revision: string | null })[];
};

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

// Every page of the app is the same index.html; the API is never served from the cache. A public
// press card always comes from the server, with the headers that let other sites frame it (the
// cached index.html forbids it).
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/carte\//],
  }),
);

self.addEventListener('install', () => {
  void self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// The message the server sends (contracts/notifications.md).
type PushMessage = {
  type: string;
  title: string;
  body: string;
  url: string;
  tag: string;
  icon: string;
};

function readMessage(data: PushMessageData | null): PushMessage | null {
  try {
    const message = data?.json() as Partial<PushMessage> | undefined;
    return message?.title ? (message as PushMessage) : null;
  } catch {
    return null;
  }
}

// Only a page of the app: never somewhere else, whatever the message says.
function appUrl(path: unknown): string {
  const safe = typeof path === 'string' && path.startsWith('/') && !path.startsWith('//');
  return new URL(safe ? path : '/', self.location.origin).href;
}

self.addEventListener('push', (event) => {
  const message = readMessage(event.data);
  if (!message) return;
  event.waitUntil(
    self.registration.showNotification(message.title, {
      body: message.body,
      icon: message.icon,
      badge: '/favicon-48.png',
      lang: 'fr',
      // A newer message about the same prono replaces the older one.
      tag: message.tag,
      data: { url: message.url },
    }),
  );
});

// A click opens the app on the prono, or brings an open window to the front and takes it there.
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = appUrl((event.notification.data as { url?: unknown } | null)?.url);
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
      const open = windows.find((client) => new URL(client.url).origin === self.location.origin);
      if (!open) {
        await self.clients.openWindow(url);
        return;
      }
      const focused = await open.focus();
      if (focused.url !== url)
        await focused.navigate(url).catch(() => self.clients.openWindow(url));
    })(),
  );
});
