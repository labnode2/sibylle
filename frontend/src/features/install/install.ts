// Installing Sibylle as an app, from a browser's tab. Chromium browsers (Chrome, Edge, Samsung
// Internet) hand over their own install dialog (`beforeinstallprompt`): kept from the page's
// start, it is shown on a click. Safari and Firefox have none: on a phone, a short guide then
// says where their menu hides it. The installed app, opened from its icon, has nothing to offer.
import { useCallback, useSyncExternalStore } from 'react';

import { isIos, isStandalone } from '../notifications/usePush';

/** Chromium's install dialog, which TypeScript's DOM types do not know. */
type InstallPromptEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
};

/** Set once the app is installed on this device or opened from its icon: on Android and on a
 *  computer the app shares the browser's storage, so the browser's tab knows it is there. An
 *  iPhone keeps them apart. */
export const INSTALLED_KEY = 'sibylle.installed';

export type InstallPlatform = 'ios' | 'android' | 'other';

export type InstallOffer =
  // One click opens the browser's own install dialog.
  | 'prompt'
  // A phone's browser without that dialog: the guide says where its menu hides it.
  | 'guide'
  | null;

type State = { prompt: InstallPromptEvent | null; installed: boolean };

let state: State = { prompt: null, installed: false };
const listeners = new Set<() => void>();

function update(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((listener) => listener());
}

function remember(installed: boolean) {
  try {
    if (installed) localStorage.setItem(INSTALLED_KEY, '1');
    else localStorage.removeItem(INSTALLED_KEY);
  } catch {
    // Private browsing: the tab simply does not know.
  }
}

function remembered(): boolean {
  try {
    return localStorage.getItem(INSTALLED_KEY) === '1';
  } catch {
    return false;
  }
}

/** From the page's start (the browser's offer may come before the first render): the offer
 *  kept for a click, and the app remembered once installed. Returns what stops listening. */
export function listenForInstall(): () => void {
  const standalone = isStandalone();
  if (standalone) remember(true);
  state = { prompt: null, installed: standalone || remembered() };

  const offered = (event: Event) => {
    // No banner of the browser's own: la une's button opens the dialog. An offer also means the
    // app is not (or no longer) installed here.
    event.preventDefault();
    remember(false);
    update({ prompt: event as InstallPromptEvent, installed: false });
  };
  const installed = () => {
    remember(true);
    update({ prompt: null, installed: true });
  };
  window.addEventListener('beforeinstallprompt', offered);
  window.addEventListener('appinstalled', installed);
  return () => {
    window.removeEventListener('beforeinstallprompt', offered);
    window.removeEventListener('appinstalled', installed);
    state = { prompt: null, installed: false };
  };
}

export function installPlatform(): InstallPlatform {
  if (isIos()) return 'ios';
  return /Android/i.test(navigator.userAgent) ? 'android' : 'other';
}

/** What the button does, if it shows at all: nothing in the installed app nor once installed;
 *  the browser's dialog when it has one; else the guide, on a phone only. */
export function installOffer(env: {
  standalone: boolean;
  prompt: boolean;
  installed: boolean;
  platform: InstallPlatform;
}): InstallOffer {
  if (env.standalone) return null;
  if (env.prompt) return 'prompt';
  if (env.installed || env.platform === 'other') return null;
  return 'guide';
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function useInstall() {
  const current = useSyncExternalStore(
    subscribe,
    () => state,
    () => state,
  );
  const platform = installPlatform();
  const offer = installOffer({
    standalone: isStandalone(),
    prompt: current.prompt !== null,
    installed: current.installed,
    platform,
  });

  /** The browser's dialog, once: Chromium shows it a single time per offer, so a refusal waits
   *  for its next one. `unavailable` when there is none, or the browser would not show it. */
  const install = useCallback(async (): Promise<'accepted' | 'dismissed' | 'unavailable'> => {
    const prompt = state.prompt;
    if (!prompt) return 'unavailable';
    update({ prompt: null });
    try {
      await prompt.prompt();
      const { outcome } = await prompt.userChoice;
      // `appinstalled` follows, a moment later: the button goes now.
      if (outcome === 'accepted') {
        remember(true);
        update({ installed: true });
      }
      return outcome;
    } catch {
      return 'unavailable';
    }
  }, []);

  return { offer, platform, install };
}
