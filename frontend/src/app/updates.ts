// A tab left open across a deploy keeps running the former interface against the new server,
// which may answer in ways it does not know. The service worker is checked for a new version
// every half hour and whenever the tab comes back; once a new version has taken over (sw.ts:
// skipWaiting, clients.claim), the next move to another page loads it, so that nothing being
// typed is lost.

type Router = {
  subscribe: (listener: (state: { location: { pathname: string } }) => void) => () => void;
};

const CHECK_EVERY = 30 * 60_000;

export function watchForUpdates(registration: ServiceWorkerRegistration, router: Router): void {
  const check = () => void registration.update().catch(() => undefined);
  setInterval(check, CHECK_EVERY);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') check();
  });

  // The very first install also takes control: only a change of controller counts.
  const hadController = Boolean(navigator.serviceWorker.controller);
  let stale = false;
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (hadController) stale = true;
  });
  let path = window.location.pathname;
  router.subscribe((state) => {
    if (stale && state.location.pathname !== path) window.location.reload();
    path = state.location.pathname;
  });
}

/** Fetches the new version if there is one, then reloads the page. */
export async function reloadLatest(): Promise<void> {
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    await registration?.update();
    if (registration?.installing || registration?.waiting) {
      await new Promise<void>((resolve) => {
        navigator.serviceWorker.addEventListener('controllerchange', () => resolve(), {
          once: true,
        });
        setTimeout(resolve, 5_000);
      });
    }
  } catch {
    // Offline, or no service worker: a plain reload.
  }
  window.location.reload();
}
