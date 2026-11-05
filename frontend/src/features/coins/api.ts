import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type WeeklyCoins = components['schemas']['WeeklyCoins'];

export const weeklyCoinsKey = (orgId: string) => ['coins-weekly', orgId] as const;

/** Monday's conversion, as long as the member has not seen its good news. */
export function useWeeklyCoins(orgId: string) {
  return useQuery({
    queryKey: weeklyCoinsKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/coins/weekly', { params: { path: { org_id: orgId } } })),
  });
}

export function useWeeklyCoinsSeen(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (weekStart: string) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/coins/weekly/seen', {
          params: { path: { org_id: orgId } },
          body: { week_start: weekStart },
        }),
      ),
    onSuccess: () => client.setQueryData(weeklyCoinsKey(orgId), null),
    // Closing the good news: nothing to say if the server missed it, it will show again.
    meta: { quiet: true },
  });
}
