// Theme and motion preferences, applied to <html>: data-theme (light, dark, or auto to follow the
// system) and the reduce-motion class. The account's own settings (PATCH /me) are adopted once
// known; until then the last choice made on this device is used, and the light theme by default.
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Theme = 'auto' | 'light' | 'dark';

type Stored = { theme: Theme; reduceMotion: boolean };

type Preferences = Stored & {
  setTheme: (theme: Theme) => void;
  setReduceMotion: (reduce: boolean) => void;
  /** The signed-in account's settings, which win over this device's last choice. */
  adopt: (account: Stored) => void;
};

// ".v2": the first version saved its "auto" default on every load, before anyone could choose a
// theme, and reading it back would keep those devices on the system's dark mode.
export const STORAGE_KEY = 'sibylle.preferences.v2';

function readStored(): Stored {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}') as Partial<Stored>;
    return {
      theme: stored.theme === 'dark' || stored.theme === 'auto' ? stored.theme : 'light',
      reduceMotion: stored.reduceMotion === true,
    };
  } catch {
    return { theme: 'light', reduceMotion: false };
  }
}

// Only a choice is saved, so that the defaults can still change.
function save(preferences: Stored) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // private browsing or blocked storage: the choice lasts until the tab closes
  }
}

const PreferencesContext = createContext<Preferences | null>(null);

export function PreferencesProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState(readStored);

  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', state.theme);
    root.classList.toggle('reduce-motion', state.reduceMotion);
  }, [state]);

  // Stable, so that adopting the account's settings never undoes a choice made meanwhile.
  const adopt = useCallback((account: Stored) => {
    setState((current) => {
      if (current.theme === account.theme && current.reduceMotion === account.reduceMotion) {
        return current;
      }
      save(account);
      return account;
    });
  }, []);

  const value = useMemo<Preferences>(() => {
    const choose = (next: Stored) => {
      setState(next);
      save(next);
    };
    return {
      ...state,
      setTheme: (theme) => choose({ ...state, theme }),
      setReduceMotion: (reduceMotion) => choose({ ...state, reduceMotion }),
      adopt,
    };
  }, [state, adopt]);

  return <PreferencesContext.Provider value={value}>{children}</PreferencesContext.Provider>;
}

export function usePreferences(): Preferences {
  const preferences = useContext(PreferencesContext);
  if (!preferences) throw new Error('usePreferences must be used inside PreferencesProvider');
  return preferences;
}
