import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { INSTALLED_KEY, listenForInstall } from '../../src/features/install/install';
import { InstallButton } from '../../src/features/install/InstallButton';

// The crystal ball draws on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));

const UA = {
  android:
    'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36',
  iphone:
    'Mozilla/5.0 (iPhone; CPU iPhone OS 18_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Mobile/15E148 Safari/604.1',
  computer:
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
};

let stop: (() => void) | undefined;

beforeAll(() => {
  // jsdom has the element, not its modal methods.
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
});

afterEach(() => {
  cleanup();
  stop?.();
  stop = undefined;
  localStorage.clear();
  vi.restoreAllMocks();
  // @ts-expect-error jsdom has no matchMedia: only some tests give it one.
  delete window.matchMedia;
});

/** This device: its browser, and whether the page runs as the installed app. */
function device(ua: keyof typeof UA, { standalone = false } = {}) {
  vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue(UA[ua]);
  window.matchMedia = vi.fn(
    (query: string) => ({ matches: standalone && query.includes('standalone') }) as MediaQueryList,
  );
  stop = listenForInstall();
}

/** Chromium's install offer, answered `outcome` once shown. */
function offer(outcome: 'accepted' | 'dismissed') {
  const event = new Event('beforeinstallprompt', { cancelable: true });
  const prompt = vi.fn(async () => undefined);
  Object.assign(event, { prompt, userChoice: Promise.resolve({ outcome }) });
  act(() => {
    window.dispatchEvent(event);
  });
  return { event, prompt };
}

const button = () => screen.queryByRole('button', { name: "Installer l'appli" });
const guide = () => screen.queryByRole('dialog', { name: 'Installer Sibylle' });

describe('InstallButton', () => {
  it('stays out of a computer whose browser offers nothing', () => {
    device('computer');
    render(<InstallButton />);
    expect(button()).toBeNull();
  });

  it("opens the browser's own dialog, then goes once the app is installed", async () => {
    device('computer');
    render(<InstallButton />);
    const { event, prompt } = offer('accepted');
    // No banner of the browser's own: the button opens its dialog.
    expect(event.defaultPrevented).toBe(true);

    fireEvent.click(button()!);
    expect(prompt).toHaveBeenCalledOnce();
    await waitFor(() => expect(button()).toBeNull());
    expect(guide()).toBeNull();
    expect(localStorage.getItem(INSTALLED_KEY)).toBe('1');
  });

  it("leaves the guide on a phone once the browser's dialog was refused", async () => {
    device('android');
    render(<InstallButton />);
    const { prompt } = offer('dismissed');
    fireEvent.click(button()!);
    await waitFor(() => expect(prompt).toHaveBeenCalledOnce());
    // The refusal was the answer: no guide on top of it.
    expect(guide()).toBeNull();

    fireEvent.click(button()!);
    expect(prompt).toHaveBeenCalledOnce();
    await waitFor(() => expect(guide()).not.toBeNull());
    expect(guide()).toHaveTextContent('Installer et créer un raccourci');
  });

  it("guides an iPhone to « Sur l'écran d'accueil », until « J'ai compris »", () => {
    device('iphone');
    render(<InstallButton />);
    fireEvent.click(button()!);
    expect(guide()).toHaveTextContent("Sur l'écran d'accueil");
    expect(guide()).toHaveTextContent('SUR IPHONE ET IPAD');

    fireEvent.click(screen.getByRole('button', { name: "J'ai compris" }));
    expect(guide()).toBeNull();
    expect(button()).not.toBeNull();
  });

  it("stays out of the installed app, and tells the browser's tab it is there", () => {
    device('android', { standalone: true });
    render(<InstallButton />);
    expect(button()).toBeNull();
    expect(localStorage.getItem(INSTALLED_KEY)).toBe('1');

    cleanup();
    stop?.();
    device('android');
    render(<InstallButton />);
    expect(button()).toBeNull();
  });

  it('comes back when the browser offers it again: the app was removed', () => {
    localStorage.setItem(INSTALLED_KEY, '1');
    device('android');
    render(<InstallButton />);
    expect(button()).toBeNull();

    offer('accepted');
    expect(button()).not.toBeNull();
    expect(localStorage.getItem(INSTALLED_KEY)).toBeNull();
  });

  it('goes as soon as the app is installed from the browser’s menu', () => {
    device('android');
    render(<InstallButton />);
    expect(button()).not.toBeNull();
    act(() => {
      window.dispatchEvent(new Event('appinstalled'));
    });
    expect(button()).toBeNull();
    expect(localStorage.getItem(INSTALLED_KEY)).toBe('1');
  });

  it("speaks the date bar's capitals on a computer", () => {
    device('computer');
    render(<InstallButton variant="inline" />);
    offer('accepted');
    expect(screen.getByRole('button', { name: "INSTALLER L'APPLI" })).toBeInTheDocument();
  });
});
