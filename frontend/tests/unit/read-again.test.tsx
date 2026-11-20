// « Tuto » and « Charte » (card #27): the game's bases and the newsroom's charter, to read again
// at any time, under the editor's note on la une (or in its place) and on « La rédaction », where
// they replace « Revoir les bases du jeu ». Each is a still pixel-art image (art.ts), without a
// word under it. « Tuto » opens the welcome with the newsroom and the member's role; « Charte »
// the charter, its line breaks kept; no « Charte » without a charter.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { NewsroomPage } from '../../src/features/orgs/NewsroomPage';
import type { FrontPage } from '../../src/features/une/api';
import { UnePage } from '../../src/features/une/UnePage';
import { ART } from '../../src/features/welcome/art';

const CHARTER =
  'On joue pour le plaisir.\nEn rejoignant la rédaction, je m’engage à :\n- respecter les autres ;\n- signaler un résultat erroné.\n\nLa rédaction en chef modère.';

const state = vi.hoisted(() => ({
  charter: '',
  role: 'reader' as 'reader' | 'journalist' | 'editor',
  note: null as string | null,
}));

vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({
    data: {
      id: 'org',
      title: 'La Gazette',
      logo: null,
      background_key: 'mer',
      charter: state.charter,
      access_code: null,
      member_count: 1,
      edition_number: 305,
      my_membership: { id: 'me', role: state.role, balance: 100, gold: 100, coins: 0 },
    },
  }),
}));
vi.mock('../../src/features/une/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/une/api')>()),
  useFrontPage: () => ({
    data: {
      headline: null,
      open: [],
      open_count: 0,
      to_designate: null,
      latest_results: [],
      leaderboard_top: [],
      leaderboard_period: 'all_time',
      editor_note: state.note,
    } satisfies FrontPage,
  }),
}));
vi.mock('../../src/features/admin/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/admin/api')>()),
  useMembers: () => ({
    data: [
      {
        id: 'me',
        pseudo: 'Inès',
        avatar: null,
        frame: null,
        animation: null,
        role: state.role,
        joined_at: '2026-11-01T09:00:00Z',
        streak: 0,
        balance: 100,
      },
    ],
  }),
  useReports: () => ({ data: [] }),
}));
vi.mock('../../src/features/auth/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/auth/api')>()),
  useMe: () => ({ data: { memberships: [] } }),
}));
// A week without games, and neither the proposals to review nor the install button.
vi.mock('../../src/features/games/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/games/api')>()),
  useGames: () => ({ data: { scheduled: [] } }),
}));
vi.mock('../../src/features/pronos/ProposalsPanel', () => ({ ProposalsPanel: () => null }));
vi.mock('../../src/features/install/InstallButton', () => ({ InstallButton: () => null }));
// The crystal ball and the pixel images draw on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));
vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));

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
  state.charter = CHARTER;
  state.role = 'reader';
  state.note = null;
});

afterEach(cleanup);

function show(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/o/:orgId" element={<UnePage />} />
        <Route path="/o/:orgId/redaction" element={<NewsroomPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const tuto = () => screen.getByRole('button', { name: 'Tuto : revoir les bases du jeu' });
const charter = () =>
  screen.queryByRole('button', { name: 'Charte : relire la charte de la rédaction' });

describe.each([
  ['la une', '/o/org'],
  ['« La rédaction »', '/o/org/redaction'],
])('on %s', (_page, path) => {
  it('shows « Tuto » and « Charte », each named in full, without a word on screen', () => {
    show(path);
    expect(tuto()).toHaveTextContent(/^$/);
    expect(charter()).toHaveTextContent(/^$/);
  });

  it('draws each as pixel art, the book and the scroll, unseen by screen readers', () => {
    show(path);
    for (const [button, src] of [
      [tuto(), ART.tuto],
      [charter()!, ART.charter],
    ] as const) {
      const image = button.querySelector('img');
      expect(image).toHaveAttribute('src', src);
      expect(image).toHaveAttribute('alt', '');
    }
  });

  it('opens the welcome with the newsroom and my role', () => {
    state.role = 'journalist';
    show(path);
    fireEvent.click(tuto());
    const welcome = screen.getByRole('dialog', { name: 'Bienvenue dans La Gazette !' });
    expect(within(welcome).getByText('ÉTAPE 1 SUR 5')).toBeVisible();
    for (let step = 1; step < 5; step += 1) {
      fireEvent.click(within(welcome).getByRole('button', { name: 'Suivant' }));
    }
    expect(within(welcome).getByRole('heading', { name: 'Tu tiens la plume' })).toBeVisible();
    fireEvent.click(within(welcome).getByRole('button', { name: "C'est parti !" }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('opens the charter, its line breaks kept', () => {
    show(path);
    fireEvent.click(charter()!);
    const dialog = screen.getByRole('dialog', { name: 'La charte de la rédaction' });
    expect(within(dialog).getByText('LA GAZETTE')).toBeVisible();
    // The scroll on top, as on the button.
    expect(dialog.querySelector('img')).toHaveAttribute('src', ART.charter);
    // The text as written, each line kept (white-space: pre-line).
    expect(
      within(dialog).getByText(
        (_text, element) => element?.tagName === 'P' && element.textContent === CHARTER,
      ),
    ).toBeVisible();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Fermer' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(charter()).toBeInTheDocument();
  });

  it.each(['', ' \n '])('shows no « Charte » without a charter (%j)', (blank) => {
    state.charter = blank;
    show(path);
    expect(tuto()).toBeInTheDocument();
    expect(charter()).toBeNull();
  });
});

describe('la une', () => {
  it('puts them right under the editor’s note', () => {
    state.note = 'Bonne semaine à toutes et à tous !';
    show('/o/org');
    const note = screen.getByRole('region', { name: 'Le mot de la rédaction en chef' });
    expect(note.nextElementSibling).toContainElement(tuto());
    expect(note.nextElementSibling).toContainElement(charter());
  });

  it('keeps them in the note’s place when there is none', () => {
    show('/o/org');
    expect(screen.queryByRole('region', { name: 'Le mot de la rédaction en chef' })).toBeNull();
    const aside = screen.getByRole('complementary', { name: 'Le classement et les jeux' });
    expect(aside.lastElementChild).toContainElement(tuto());
  });
});

describe('« La rédaction »', () => {
  it('no longer has the link « Revoir les bases du jeu »', () => {
    show('/o/org/redaction');
    expect(screen.queryByRole('button', { name: 'Revoir les bases du jeu' })).toBeNull();
    expect(screen.queryByRole('link', { name: 'Revoir les bases du jeu' })).toBeNull();
    expect(tuto()).toBeInTheDocument();
  });
});
