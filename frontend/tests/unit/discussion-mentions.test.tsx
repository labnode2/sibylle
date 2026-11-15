// Tagging in the discussion: « @ » proposes the active members, the choice is sent with the
// message, and the tagged names are highlighted.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { Composer, MessageBody } from '../../src/features/pronos/Discussion';

vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));
vi.mock('../../src/ui/Toaster', () => ({ toast: { success: vi.fn() } }));

const avatar = { size: 16, palette: 'x', pixels: '' };
const mutate = vi.fn();
vi.mock('../../src/features/admin/api', () => ({
  useMembers: () => ({
    data: [
      { id: 'me', pseudo: 'Cami', avatar },
      { id: 'leo', pseudo: 'Léo', avatar },
      { id: 'lea', pseudo: 'Léa', avatar },
      { id: 'hugo', pseudo: 'Hugo', avatar },
    ],
  }),
}));
vi.mock('../../src/features/pronos/api', () => ({
  useDiscussion: () => ({ write: { mutate, isPending: false, error: null } }),
}));

afterEach(() => {
  cleanup();
  mutate.mockReset();
});

function type(text: string) {
  const box = screen.getByRole('combobox');
  fireEvent.change(box, { target: { value: text, selectionStart: text.length } });
  return box;
}

describe('the composer', () => {
  it('proposes the active members after an @, without the author', () => {
    render(<Composer orgId="org" pronoId="p" me="me" />);
    type('Salut @');
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Léo', 'Léa', 'Hugo']);
    type('Salut @lé');
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Léo', 'Léa']);
    type('Salut Léo');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('inserts the chosen name and sends the tagged members with the message', () => {
    render(<Composer orgId="org" pronoId="p" me="me" />);
    const box = type('Salut @hu');
    fireEvent.keyDown(box, { key: 'Enter' });
    expect(box).toHaveProperty('value', 'Salut @Hugo ');
    expect(screen.queryByRole('listbox')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Publier' }));
    expect(mutate).toHaveBeenCalledOnce();
    expect(mutate.mock.calls[0]?.[0]).toEqual({ body: 'Salut @Hugo ', mentions: ['hugo'] });
  });

  it('picks with the mouse, and drops a tag whose name was erased', () => {
    render(<Composer orgId="org" pronoId="p" me="me" />);
    type('@Lé');
    fireEvent.mouseDown(screen.getByRole('option', { name: 'Léa' }));
    type('Finalement rien');
    fireEvent.click(screen.getByRole('button', { name: 'Publier' }));
    expect(mutate.mock.calls[0]?.[0]).toEqual({ body: 'Finalement rien', mentions: [] });
  });

  it('closes the list on Escape', () => {
    render(<Composer orgId="org" pronoId="p" me="me" />);
    const box = type('@');
    fireEvent.keyDown(box, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
  });
});

describe('a message with tags', () => {
  it('highlights the tagged names only', () => {
    const { container } = render(
      <p>
        <MessageBody
          body="@Léo et @Hugo, avec @Inès (pas taguée)"
          mentions={[
            { id: 'leo', pseudo: 'Léo' },
            { id: 'hugo', pseudo: 'Hugo' },
          ]}
        />
      </p>,
    );
    expect([...container.querySelectorAll('strong')].map((n) => n.textContent)).toEqual([
      '@Léo',
      '@Hugo',
    ]);
    expect(container.textContent).toBe('@Léo et @Hugo, avec @Inès (pas taguée)');
  });

  it('is plain text without tags', () => {
    const { container } = render(<MessageBody body="Allez @Nice" mentions={[]} />);
    expect(container.querySelector('strong')).toBeNull();
  });
});
