// Theme and motion preferences, applied to <html>: data-theme (absent = follow the system) and
// the reduce-motion class. The account's own settings (PATCH /me) are passed in once known; until
// then the last choice made on this device is used.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';

export type Theme = 'auto' | 'light' | 'dark';

type Preferences = {
  theme: Theme;
  reduceMotion: boolean;
  setTheme: (theme: Theme) => void;
  setReduceMotion: (reduce: boolean) => void;
};

const STORAGE_KEY = 'sybille.preferences';

function readStored(): { theme: Theme; reduceMotion: boolean } {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<Preferences>;
    return {
      theme: stored.theme === 'light' || stored.theme === 'dark' ? stored.theme : 'auto',
      reduceMotion: stored.reduceMotion === true,
    };
  } catch {
    return { theme: 'auto', reduceMotion: false };
  }
}

const PreferencesContext = createContext<Preferences | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(readStored);

  useEffect(() => {
    const root = document.documentElement;
    if (state.theme === 'auto') root.removeAttribute('data-theme');
    else root.setAttribute('data-theme', state.theme);
    root.classList.toggle('reduce-motion', state.reduceMotion);
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // private browsing or blocked storage: the choice lasts until the tab closes
    }
  }, [state]);

  const value = useMemo<Preferences>(
    () => ({
      ...state,
      setTheme: (theme) => setState((current) => ({ ...current, theme })),
      setReduceMotion: (reduceMotion) => setState((current) => ({ ...current, reduceMotion })),
    }),
    [state],
  );

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): Preferences {
  const preferences = useContext(PreferencesContext);
  if (!preferences) throw new Error('usePreferences must be used inside PreferencesProvider');
  return preferences;
}
