// Pixel mystère's « Déposer un dessin »: under « LE MOT À DEVINER », the rules the server holds the
// word to (backend domain/minigames.py, `valid_word` and `normalize_word`): letters, in one word or
// several joined by a space, a hyphen or an apostrophe (« Tour Eiffel », « porte-monnaie »,
// « aujourd'hui »), 24 characters at most, spaces included; case and accents do not count.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { PixelMysterePage } from '../../src/features/games/pixel-mystere/PixelMysterePage';

vi.mock('../../src/features/games/api', () => ({
  // A week with Pixel mystère, no drawing under way and none waiting.
  useGames: () => ({ data: { scheduled: ['pixel'] } }),
  usePixel: () => ({ data: null }),
  useGuess: () => ({ mutate: () => {}, isPending: false, error: null }),
  usePixelQueue: () => ({ data: [] }),
  usePostPuzzle: () => ({ mutate: () => {}, reset: () => {}, isPending: false, error: null }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { my_membership: { role: 'journalist', unlocked_colors: [] } } }),
}));
// The editor draws on a canvas, which jsdom does not have.
vi.mock('../../src/features/pixel-editor/PixelEditor', () => ({ PixelEditor: () => null }));

afterEach(cleanup);

const RULES =
  'Des lettres, en un ou plusieurs mots séparés par un espace, un tiret ou une apostrophe ; ' +
  '24 caractères au plus, espaces compris. Majuscules et accents ne comptent pas.';

describe('Déposer un dessin', () => {
  it('says under the word to guess what the server accepts', () => {
    render(
      <MemoryRouter initialEntries={['/o/org/jeux/pixel']}>
        <Routes>
          <Route path="/o/:orgId/jeux/pixel" element={<PixelMysterePage />} />
        </Routes>
      </MemoryRouter>,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Dessiner un Pixel mystère' }));
    const word = screen.getByLabelText('LE MOT À DEVINER');
    expect(word).toHaveAccessibleDescription(RULES);
    expect(screen.getByText(RULES)).toBeVisible();
  });
});
