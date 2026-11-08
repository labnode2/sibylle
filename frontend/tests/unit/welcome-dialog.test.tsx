// The welcome pop-up of the first newsroom: the game in steps, the last one about the person's
// role, closed by « Passer » as by « C'est parti ! ».
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { WelcomeDialog } from '../../src/features/welcome/WelcomeDialog';

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

afterEach(cleanup);

const next = () => fireEvent.click(screen.getByRole('button', { name: 'Suivant' }));

describe('WelcomeDialog', () => {
  it('walks through the game, then the editor’s part, and closes', () => {
    const onClose = vi.fn();
    render(<WelcomeDialog org="Sophia Office" role="editor" onClose={onClose} />);
    expect(
      screen.getByRole('dialog', { name: 'Bienvenue dans Sophia Office\u00a0!' }),
    ).toBeVisible();
    expect(screen.getByText('ÉTAPE 1 SUR 6')).toBeVisible();

    next();
    expect(screen.getByRole('heading', { name: 'Un prono, une réponse' })).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Précédent' }));
    expect(
      screen.getByRole('heading', { name: 'Bienvenue dans Sophia Office\u00a0!' }),
    ).toBeVisible();

    for (let step = 1; step < 6; step += 1) next();
    expect(screen.getByText('ÉTAPE 6 SUR 6')).toBeVisible();
    expect(screen.getByRole('heading', { name: 'À toi de lancer la rédaction' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'Suivant' })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: "C'est parti\u00a0!" }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('ends on proposing a prono for a reader', () => {
    render(<WelcomeDialog org="Sophia Office" role="reader" onClose={vi.fn()} />);
    for (let step = 1; step < 6; step += 1) next();
    expect(screen.getByRole('heading', { name: 'Une idée de prono\u00a0?' })).toBeVisible();
  });

  it('can be skipped from the first step', () => {
    const onClose = vi.fn();
    render(<WelcomeDialog org="Sophia Office" role="journalist" onClose={onClose} />);
    fireEvent.click(screen.getByRole('button', { name: 'Passer' }));
    expect(onClose).toHaveBeenCalledOnce();
  });
});
