// La une's shares (card #23): the headline's gauge and the briefs show each answer's share of the
// laurels staked, and say so. A prono whose only bets were placed without a stake, before the
// minimum stake, has no favourite to show.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import type { FrontPage, FrontProno } from '../../src/features/une/api';
import { UnePage } from '../../src/features/une/UnePage';

const front = vi.hoisted(() => ({ page: undefined as unknown }));

vi.mock('../../src/features/une/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/une/api')>()),
  useFrontPage: () => ({ data: front.page }),
}));
vi.mock('../../src/features/orgs/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/orgs/api')>()),
  useOrg: () => ({
    data: {
      id: 'org',
      title: 'La Gazette',
      edition_number: 305,
      my_membership: { id: 'me', role: 'reader', balance: 100, gold: 100, coins: 0 },
    },
  }),
}));
// A week without games, and neither the switcher of newsrooms nor the install button.
vi.mock('../../src/features/games/api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../src/features/games/api')>()),
  useGames: () => ({ data: { scheduled: [] } }),
}));
vi.mock('../../src/features/orgs/NewsroomPage', () => ({ NewsroomSwitcher: () => null }));
vi.mock('../../src/features/install/InstallButton', () => ({ InstallButton: () => null }));
// The masthead's crystal ball draws on a canvas, which jsdom does not have.
vi.mock('../../src/ui/CrystalBall', () => ({ CrystalBall: () => null }));

afterEach(cleanup);

const option = (label: string, count: number, stake: number, pct: number) => ({
  id: label,
  label,
  is_correct: null,
  count,
  stake_total: stake,
  share_pct: pct,
});

function prono(id: string, question: string, over: Partial<FrontProno>): FrontProno {
  return {
    id,
    number: 1,
    kind: 'choice',
    question,
    section: { id: 'sport', name: 'Sport', position: 0 },
    created_by: { id: 'hugo', pseudo: 'Hugo', avatar: null },
    state: 'open',
    base_gain: 20,
    opens_at: null,
    closes_at: null,
    open_ended: true,
    result_expected_at: null,
    number_unit: null,
    link_url: null,
    image_url: null,
    bet_count: 0,
    pot: 0,
    relaunch_count: 0,
    message_count: 0,
    options: [],
    distribution: [],
    ...over,
  } as FrontProno;
}

/** La une with its headline, then the other open pronos: the first one beside the games on a
 *  phone (and in the briefs on a computer), the others in the briefs. */
function show(headline: FrontProno, open: FrontProno[]) {
  front.page = {
    headline,
    open,
    open_count: open.length + 1,
    to_designate: null,
    latest_results: [],
    leaderboard_top: [],
    leaderboard_period: 'all_time',
    editor_note: null,
  } satisfies FrontPage;
  render(
    <MemoryRouter initialEntries={['/o/org']}>
      <Routes>
        <Route path="/o/:orgId" element={<UnePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('la une', () => {
  it('shows the shares of the laurels staked, on the gauge and in the briefs', () => {
    show(
      prono('derby', 'Nice ou Monaco samedi ?', {
        bet_count: 4,
        pot: 40,
        options: [option('Nice', 1, 30, 75), option('Monaco', 3, 10, 25)],
      }),
      [
        prono('coffee', 'Combien de cafés jeudi ?', {}),
        prono('rain', 'Il pleuvra dimanche ?', {
          kind: 'yes_no',
          bet_count: 3,
          pot: 25,
          options: [option('Oui', 2, 7, 28), option('Non', 1, 18, 72)],
        }),
      ],
    );
    expect(
      screen.getByRole('img', { name: /^Répartition des lauriers misés/ }),
    ).toHaveAccessibleName('Répartition des lauriers misés : Nice 75 %, Monaco 25 %');
    expect(screen.getByText('EN % DES LAURIERS MISÉS')).toBeInTheDocument();
    // One person on Non, but most of the laurels: the brief names it the favourite.
    expect(screen.getByRole('link', { name: /Il pleuvra dimanche/ })).toHaveTextContent(
      'NON 72 % DES LAURIERS · SANS DATE DE CLÔTURE',
    );
  });

  it('names no favourite while nothing is staked', () => {
    show(prono('derby', 'Nice ou Monaco samedi ?', {}), [
      prono('coffee', 'Combien de cafés jeudi ?', {}),
      // Two bets placed without a stake, before the minimum stake: no laurels to share.
      prono('rain', 'Il pleuvra dimanche ?', {
        kind: 'yes_no',
        bet_count: 2,
        options: [option('Oui', 2, 0, 0), option('Non', 0, 0, 0)],
      }),
    ]);
    const brief = screen.getByRole('link', { name: /Il pleuvra dimanche/ });
    expect(brief).toHaveTextContent('SANS DATE DE CLÔTURE');
    expect(brief).not.toHaveTextContent('%');
  });
});
