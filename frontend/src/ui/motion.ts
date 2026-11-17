// Less motion: the app's « couper les animations » (the reduce-motion class on <html>, see
// app/preferences.tsx) or the system's prefers-reduced-motion. CSS stops the animations and
// transitions by itself (styles/gazette.css); what moves on a timer asks here.
import { useSyncExternalStore } from 'react';

const QUERY = '(prefers-reduced-motion: reduce)';

export const motionReduced = () =>
  document.documentElement.classList.contains('reduce-motion') ||
  window.matchMedia?.(QUERY).matches === true;

function subscribe(onChange: () => void) {
  // The class comes and goes with the settings, and with the account's once it is known.
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
  const media = window.matchMedia?.(QUERY);
  media?.addEventListener?.('change', onChange);
  return () => {
    observer.disconnect();
    media?.removeEventListener?.('change', onChange);
  };
}

/** Whether to keep still, followed as either choice changes. */
export function useMotionReduced(): boolean {
  return useSyncExternalStore(subscribe, motionReduced);
}
