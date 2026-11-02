import { useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';

export type Leaderboard = components['schemas']['Leaderboard'];
export type LeaderboardRow = components['schemas']['LeaderboardRow'];
export type Metric = 'laurels' | 'wins';
export type Period = 'month' | 'season' | 'all_time';

const leaderboardKey = (orgId: string) => ['leaderboard', orgId] as const;
const seasonKey = (orgId: string) => ['season', orgId] as const;

export function useLeaderboard(orgId: string, metric: Metric, period: Period) {
  const client = useQueryClient();
  // A settlement moves the rankings; the end of a season moves the season as well.
  useTopic(`org:${orgId}`, (event) => {
    if (event.event === 'leaderboard.changed' || event.event === 'season.closed') {
      void client.invalidateQueries({ queryKey: leaderboardKey(orgId) });
    }
    if (event.event === 'season.closed') {
      void client.invalidateQueries({ queryKey: seasonKey(orgId) });
    }
  });
  return useQuery({
    queryKey: [...leaderboardKey(orgId), metric, period],
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/leaderboard', {
          params: { path: { org_id: orgId }, query: { metric, period } },
        }),
      ),
  });
}

export function useCurrentSeason(orgId: string) {
  return useQuery({
    queryKey: seasonKey(orgId),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/seasons/current', { params: { path: { org_id: orgId } } }),
      ),
  });
}
