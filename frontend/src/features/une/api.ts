import { useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';

export type FrontPage = components['schemas']['FrontPage'];
export type LatestResult = components['schemas']['LatestResult'];

const frontPageKey = (orgId: string) => ['front-page', orgId] as const;

// Everything la une shows moves with these events of the newsroom.
const REFRESHING = ['bet.placed', 'leaderboard.changed', 'season.closed'];

export function useFrontPage(orgId: string) {
  const client = useQueryClient();
  useTopic(`org:${orgId}`, (event) => {
    if (event.event.startsWith('prono.') || REFRESHING.includes(event.event)) {
      void client.invalidateQueries({ queryKey: frontPageKey(orgId) });
    }
  });
  return useQuery({
    queryKey: frontPageKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/front-page', { params: { path: { org_id: orgId } } })),
  });
}
