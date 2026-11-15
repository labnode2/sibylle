// The laurels ranking counts the gold laurels, all time: its title and its note say so.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, describe, expect, it, vi } from 'vitest';

import '../../src/i18n';
import { LeaderboardPage } from '../../src/features/leaderboard/LeaderboardPage';

vi.mock('../../src/ui/PixelImage', () => ({ PixelImage: () => null }));
vi.mock('../../src/features/leaderboard/api', () => ({
  useLeaderboard: () => ({
    isPending: false,
    data: {
      period_label: 'all_time',
      rows: [
        {
          rank: 1,
          member: { id: 'm', pseudo: 'Léo', avatar: { size: 16, palette: 'x', pixels: '' } },
          value: 125,
          is_me: false,
          streak: 0,
        },
      ],
    },
  }),
  useCurrentSeason: () => ({ data: undefined }),
}));

afterEach(cleanup);

describe('LeaderboardPage', () => {
  it('titles the laurels ranking with the gold laurels, all time only', () => {
    render(
      <MemoryRouter>
        <LeaderboardPage />
      </MemoryRouter>,
    );
    expect(screen.getByText("LAURIERS D'OR · DEPUIS TOUJOURS")).toBeTruthy();
    expect(screen.queryByText(/LAURIERS VERTS/)).toBeNull();
    // Only « depuis toujours » is offered for the laurels.
    expect(screen.queryByRole('button', { name: 'SAISON' })).toBeNull();
    expect(screen.getByRole('button', { name: 'DEPUIS TOUJOURS' })).toBeTruthy();
  });
});
