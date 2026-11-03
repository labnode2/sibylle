import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { PreferencesProvider, STORAGE_KEY, usePreferences } from '../../src/app/preferences';

function ThemePicker() {
  const { theme, setTheme } = usePreferences();
  return (
    <button type="button" onClick={() => setTheme('dark')}>
      {theme}
    </button>
  );
}

function mount() {
  render(
    <PreferencesProvider>
      <ThemePicker />
    </PreferencesProvider>,
  );
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  document.documentElement.removeAttribute('data-theme');
});

describe('PreferencesProvider', () => {
  it('starts on the light theme and saves nothing until a choice is made', () => {
    mount();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("ignores the first version's saved default, which kept the system's dark mode", () => {
    localStorage.setItem('sibylle.preferences', JSON.stringify({ theme: 'auto' }));
    mount();
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('applies and saves a choice', () => {
    mount();
    act(() => screen.getByRole('button').click());
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '{}')).toEqual({
      theme: 'dark',
      reduceMotion: false,
    });
  });

  it('follows the system only when "auto" was chosen', () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ theme: 'auto' }));
    mount();
    expect(document.documentElement.dataset.theme).toBe('auto');
  });
});
