import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { toast, Toaster } from '../../src/ui/Toaster';

const notes = () => screen.getByRole('region', { name: 'Infos' });

beforeEach(() => {
  vi.useFakeTimers();
  render(<Toaster />);
});

afterEach(() => {
  // Every note goes before the next test, which shares the same pile.
  act(() => {
    vi.runAllTimers();
  });
  cleanup();
  vi.useRealTimers();
});

describe('Toaster', () => {
  it('shows a note after an action, then lets it go when its bar has run out', () => {
    act(() => toast.success('Pari enregistré.'));
    expect(within(notes()).getByRole('status')).toHaveTextContent('Pari enregistré.');
    act(() => {
      vi.advanceTimersByTime(3999);
    });
    expect(within(notes()).queryByRole('status')).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(within(notes()).queryByRole('status')).toBeNull();
  });

  it('says what went wrong as an alert, which stays longer', () => {
    act(() => toast.error('Le prix a changé.'));
    expect(within(notes()).getByRole('alert')).toHaveTextContent('Le prix a changé.');
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(within(notes()).queryByRole('alert')).not.toBeNull();
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    expect(within(notes()).queryByRole('alert')).toBeNull();
  });

  it('shows the same note once, and three at most, the oldest giving way', () => {
    act(() => {
      toast.success('Copié.');
      toast.success('Copié.');
    });
    expect(within(notes()).getAllByRole('status')).toHaveLength(1);
    act(() => {
      toast.success('Rubrique ajoutée.');
      toast.success('Rubrique modifiée.');
      toast.success('Rubrique supprimée.');
    });
    expect(
      within(notes())
        .getAllByRole('status')
        .map((note) => note.textContent),
    ).toEqual(['Rubrique ajoutée.', 'Rubrique modifiée.', 'Rubrique supprimée.']);
  });

  it('waits while its cross has the focus, and goes at once when it is pressed', () => {
    act(() => toast.success('Réglages enregistrés.'));
    const close = within(notes()).getByRole('button', { name: 'Fermer ce message' });
    act(() => close.focus());
    act(() => {
      vi.advanceTimersByTime(10_000);
    });
    expect(within(notes()).queryByRole('status')).not.toBeNull();
    fireEvent.click(close);
    expect(within(notes()).queryByRole('status')).toBeNull();
  });
});
