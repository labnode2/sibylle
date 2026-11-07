import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import {
  DONE_KEY,
  InstalledPushDialog,
} from '../../src/features/notifications/InstalledPushDialog';
import type { PushStatus } from '../../src/features/notifications/usePush';

// The device as the pop-up sees it: the installed app or a browser's tab, and where push stands.
const device = vi.hoisted(() => ({
  standalone: true,
  status: 'loading' as PushStatus,
  enable: vi.fn(async () => undefined),
  asked: 0,
}));

vi.mock('../../src/features/notifications/usePush', () => ({
  isStandalone: () => device.standalone,
  usePush: () => {
    device.asked += 1;
    return { status: device.status, busy: false, enable: device.enable, disable: vi.fn() };
  },
}));

// The crystal ball draws on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));

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

beforeEach(() => {
  device.standalone = true;
  device.status = 'loading';
  device.enable.mockClear();
  device.asked = 0;
});

afterEach(() => {
  cleanup();
  localStorage.clear();
});

const offer = () => screen.queryByRole('dialog', { name: 'Activer les notifications ?' });

/** The app opened with push at `status`, once its checks are done. */
function open(status: PushStatus) {
  const view = render(<InstalledPushDialog />);
  device.status = status;
  view.rerender(<InstalledPushDialog />);
  return view;
}

describe('InstalledPushDialog', () => {
  it('stays out of a browser tab, without even looking at push', () => {
    device.standalone = false;
    const { container } = open('off');
    expect(container).toBeEmptyDOMElement();
    expect(device.asked).toBe(0);
  });

  it('opens in the installed app once this device can turn push on', () => {
    const view = render(<InstalledPushDialog />);
    expect(offer()).toBeNull();
    device.status = 'off';
    view.rerender(<InstalledPushDialog />);
    expect(offer()).toHaveTextContent('Reçois sur cet appareil les nouveaux pronos');
  });

  it('asks the browser on a click, then closes for good once push is on', () => {
    const view = open('off');
    fireEvent.click(screen.getByRole('button', { name: 'Activer les notifications' }));
    expect(device.enable).toHaveBeenCalledOnce();
    // The browser's question left unanswered: the offer is still there.
    view.rerender(<InstalledPushDialog />);
    expect(offer()).not.toBeNull();

    device.status = 'on';
    view.rerender(<InstalledPushDialog />);
    expect(offer()).toBeNull();
    expect(localStorage.getItem(DONE_KEY)).toBe('1');
    view.unmount();
    device.status = 'off';
    expect(render(<InstalledPushDialog />).container).toBeEmptyDOMElement();
  });

  it('closes for good when the browser was told no', () => {
    const view = open('off');
    fireEvent.click(screen.getByRole('button', { name: 'Activer les notifications' }));
    device.status = 'denied';
    view.rerender(<InstalledPushDialog />);
    expect(offer()).toBeNull();
    expect(localStorage.getItem(DONE_KEY)).toBe('1');
  });

  it('« Plus tard » sets it aside on this device', () => {
    const view = open('off');
    fireEvent.click(screen.getByRole('button', { name: 'Plus tard' }));
    expect(offer()).toBeNull();
    expect(device.enable).not.toHaveBeenCalled();
    expect(localStorage.getItem(DONE_KEY)).toBe('1');
    view.unmount();
    expect(render(<InstalledPushDialog />).container).toBeEmptyDOMElement();
  });

  it.each<PushStatus>(['on', 'denied'])('has nothing to offer when push is %s', (status) => {
    const { container } = open(status);
    expect(container).toBeEmptyDOMElement();
    expect(localStorage.getItem(DONE_KEY)).toBe('1');
  });

  it.each<PushStatus>(['unsupported', 'unavailable'])(
    'waits for a next opening when push is %s',
    (status) => {
      open(status);
      expect(offer()).toBeNull();
      expect(localStorage.getItem(DONE_KEY)).toBeNull();
    },
  );
});
