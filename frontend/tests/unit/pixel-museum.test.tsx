// Pixel mystère's museum: the drawings already played, the latest first, hung one at a time with
// their word, « par » their author and the day; the next one comes every 4 s, the first again
// after the last, and the buttons go back and forth, pause and play. With less motion, nothing
// moves by itself: only the buttons. An empty museum says how drawings get in. The game's page
// leads there, for everyone.
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { PixelMuseumItem } from '../../src/features/games/api';
import { PixelMuseumPage, SLIDE_MS } from '../../src/features/games/pixel-mystere/PixelMuseumPage';
import { PixelMysterePage } from '../../src/features/games/pixel-mystere/PixelMysterePage';

// What the server answers for the museum.
const museum = { data: undefined as PixelMuseumItem[] | undefined, isError: false };

vi.mock('../../src/features/games/api', () => ({
  usePixelMuseum: () => museum,
  // The game's page, a week without Pixel mystère and without a drawing.
  useGames: () => ({ data: { scheduled: ['runner'] } }),
  usePixel: () => ({ data: null }),
  useGuess: () => ({ mutate: () => {}, isPending: false, error: null }),
  usePixelQueue: () => ({ data: [] }),
  usePostPuzzle: () => ({ mutate: () => {}, reset: () => {}, isPending: false, error: null }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({ data: { my_membership: { role: 'reader', unlocked_colors: [] } } }),
}));
// The drawings and the avatars draw on a canvas, which jsdom does not have: each drawing stands
// here as a picture with its name.
vi.mock('../../src/ui/PixelImage', () => ({
  PixelImage: ({ label }: { label?: string }) =>
    label ? <span role="img" aria-label={label} /> : null,
}));

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  museum.data = undefined;
  museum.isError = false;
  document.documentElement.classList.remove('reduce-motion');
  // @ts-expect-error jsdom has no matchMedia: only some tests give it one.
  delete window.matchMedia;
});

const IMAGE = { size: 16, palette: 'base-v1', pixels: '' } as const;

function drawing(
  n: number,
  word: string,
  pseudo: string,
  finished_at: string,
  found_count: number,
): PixelMuseumItem {
  return {
    puzzle_id: `00000000-0000-0000-0000-00000000000${n}`,
    size: 16,
    drawing: IMAGE,
    word,
    author: {
      id: `00000000-0000-0000-0000-0000000000a${n}`,
      pseudo,
      avatar: IMAGE,
      role: 'journalist',
      joined_at: '2026-10-01T08:00:00Z',
    },
    finished_at,
    found_count,
  };
}

// The latest first, as the server sends them.
const BOULE = drawing(3, 'Boule', 'Inès', '2026-11-16T07:00:00Z', 3);
const CAFE = drawing(2, 'Café', 'Hugo', '2026-11-09T07:00:00Z', 1);
const LAURIER = drawing(1, 'Laurier', 'Cami', '2026-11-02T07:00:00Z', 0);
const ALL = [BOULE, CAFE, LAURIER];

/** The museum with these drawings, and `refresh`: the museum as the server sends it again. */
function visit(items: PixelMuseumItem[]) {
  museum.data = items;
  const page = () => (
    <MemoryRouter initialEntries={['/o/org/jeux/pixel/musee']}>
      <Routes>
        <Route path="/o/:orgId/jeux/pixel/musee" element={<PixelMuseumPage />} />
      </Routes>
    </MemoryRouter>
  );
  const { rerender } = render(page());
  return {
    refresh(next: PixelMuseumItem[]) {
      museum.data = next;
      rerender(page());
    },
  };
}

/** The drawing on the wall, by its name. */
const onTheWall = () => screen.getByRole('img').getAttribute('aria-label');
const named = (item: PixelMuseumItem) => `Le dessin « ${item.word} », par ${item.author.pseudo}`;
const press = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const wait = (ms: number) =>
  act(() => {
    vi.advanceTimersByTime(ms);
  });

describe('PixelMuseumPage', () => {
  it('hangs the latest drawing first, with its word, its author and the day it ended', () => {
    visit(ALL);
    expect(screen.getByRole('heading', { name: 'Le musée' })).toBeVisible();
    expect(screen.getByRole('link', { name: 'Retour au Pixel mystère' })).toHaveAttribute(
      'href',
      '/o/org/jeux/pixel',
    );
    const slide = screen.getByRole('group', { name: '1 sur 3' });
    expect(within(slide).getByRole('img')).toHaveAccessibleName(named(BOULE));
    expect(within(slide).getByText('Boule')).toBeVisible();
    expect(within(slide).getByText('par Inès')).toBeVisible();
    expect(within(slide).getByText('16 NOVEMBRE 2026')).toHaveAttribute(
      'datetime',
      BOULE.finished_at,
    );
    expect(within(slide).getByText('TROUVÉ PAR 3 PERSONNES')).toBeVisible();
    expect(screen.getByText('1 / 3')).toBeVisible();
  });

  it('moves on every 4 seconds or so, and starts again after the last', () => {
    expect(SLIDE_MS).toBe(4000);
    vi.useFakeTimers();
    visit(ALL);
    wait(SLIDE_MS - 1);
    expect(onTheWall()).toBe(named(BOULE));
    wait(1);
    expect(onTheWall()).toBe(named(CAFE));
    expect(screen.getByRole('group', { name: '2 sur 3' })).toHaveTextContent(
      'TROUVÉ PAR 1 PERSONNE',
    );
    wait(SLIDE_MS);
    expect(onTheWall()).toBe(named(LAURIER));
    expect(screen.getByText("PERSONNE NE L'A TROUVÉ")).toBeVisible();
    wait(SLIDE_MS);
    expect(onTheWall()).toBe(named(BOULE));
    expect(screen.getByText('1 / 3')).toBeVisible();
  });

  it('goes back and forth with the buttons, round the loop both ways', () => {
    vi.useFakeTimers();
    visit(ALL);
    press('Dessin précédent');
    expect(onTheWall()).toBe(named(LAURIER));
    expect(screen.getByRole('group', { name: '3 sur 3' })).toBeVisible();
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(BOULE));
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(CAFE));
    // A drawing chosen with the buttons stays its 4 seconds too.
    wait(SLIDE_MS - 1000);
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(LAURIER));
    wait(SLIDE_MS - 1);
    expect(onTheWall()).toBe(named(LAURIER));
    wait(1);
    expect(onTheWall()).toBe(named(BOULE));
  });

  it('keeps a drawing on the wall while paused, and moves on again once played', () => {
    vi.useFakeTimers();
    visit(ALL);
    press('Mettre le diaporama en pause');
    wait(SLIDE_MS * 3);
    expect(onTheWall()).toBe(named(BOULE));
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(CAFE));
    wait(SLIDE_MS * 3);
    expect(onTheWall()).toBe(named(CAFE));
    press('Relancer le diaporama');
    expect(screen.getByRole('button', { name: 'Mettre le diaporama en pause' })).toBeVisible();
    wait(SLIDE_MS);
    expect(onTheWall()).toBe(named(LAURIER));
  });

  it('keeps still once « couper les animations » is chosen: only the buttons move it', () => {
    vi.useFakeTimers();
    document.documentElement.classList.add('reduce-motion');
    visit(ALL);
    wait(SLIDE_MS * 3);
    expect(onTheWall()).toBe(named(BOULE));
    // Nothing to pause or play: it never moves by itself.
    expect(screen.queryByRole('button', { name: 'Mettre le diaporama en pause' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Relancer le diaporama' })).toBeNull();
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(CAFE));
    wait(SLIDE_MS * 3);
    expect(onTheWall()).toBe(named(CAFE));
    press('Dessin précédent');
    expect(onTheWall()).toBe(named(BOULE));
  });

  it('keeps still when the system asks for less motion', () => {
    vi.useFakeTimers();
    window.matchMedia = vi.fn(
      (query: string) =>
        ({ matches: query === '(prefers-reduced-motion: reduce)' }) as MediaQueryList,
    );
    visit(ALL);
    wait(SLIDE_MS * 3);
    expect(onTheWall()).toBe(named(BOULE));
    expect(screen.queryByRole('button', { name: 'Mettre le diaporama en pause' })).toBeNull();
    press('Dessin suivant');
    expect(onTheWall()).toBe(named(CAFE));
  });

  it('stops as soon as « couper les animations » is chosen, the page already open', async () => {
    vi.useFakeTimers();
    visit(ALL);
    await act(async () => {
      document.documentElement.classList.add('reduce-motion');
    });
    wait(SLIDE_MS * 2);
    expect(onTheWall()).toBe(named(BOULE));
  });

  it('says a change made with the buttons to screen readers, not each turn by itself', () => {
    vi.useFakeTimers();
    visit(ALL);
    const live = () => screen.getByRole('group', { name: /sur 3$/ }).parentElement;
    expect(live()).toHaveAttribute('aria-live', 'off');
    press('Mettre le diaporama en pause');
    expect(live()).toHaveAttribute('aria-live', 'polite');
  });

  it('keeps the drawing on the wall when another one enters the museum', () => {
    vi.useFakeTimers();
    const page = visit(ALL);
    press('Dessin suivant');
    const newest = drawing(4, 'Plume', 'Léo', '2026-11-17T07:00:00Z', 2);
    page.refresh([newest, ...ALL]);
    expect(onTheWall()).toBe(named(CAFE));
    expect(screen.getByRole('group', { name: '3 sur 4' })).toBeVisible();
  });

  it('shows a single drawing without buttons, standing still', () => {
    vi.useFakeTimers();
    visit([CAFE]);
    wait(SLIDE_MS * 2);
    expect(onTheWall()).toBe(named(CAFE));
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('says how drawings get in while the museum is empty', () => {
    visit([]);
    expect(
      screen.getByText(
        'Le musée est encore vide : les dessins y entrent une fois leur partie terminée.',
      ),
    ).toBeVisible();
    expect(screen.queryByRole('img')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
  });
});

describe('PixelMysterePage', () => {
  it('leads to the museum, a reader too, even a week without Pixel mystère', () => {
    render(
      <MemoryRouter initialEntries={['/o/org/jeux/pixel']}>
        <Routes>
          <Route path="/o/:orgId/jeux/pixel" element={<PixelMysterePage />} />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("Pixel mystère n'est pas au programme cette semaine.")).toBeVisible();
    expect(screen.getByRole('link', { name: /^Le musée/ })).toHaveAttribute(
      'href',
      '/o/org/jeux/pixel/musee',
    );
  });
});
