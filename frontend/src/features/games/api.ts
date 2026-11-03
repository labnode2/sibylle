import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';
import { orgKey } from '../orgs/api';

export type Games = components['schemas']['Games'];
export type RunnerStatus = components['schemas']['RunnerStatus'];

export const gamesKey = (orgId: string) => ['games', orgId] as const;

/** The games of the week; a run finished by anyone in the newsroom refreshes the ranking. */
export function useGames(orgId: string) {
  const client = useQueryClient();
  useTopic(`org:${orgId}`, (event) => {
    if (event.event === 'games.runner.updated') {
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
    }
  });
  return useQuery({
    queryKey: gamesKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/games', { params: { path: { org_id: orgId } } })),
  });
}

export function useStartRun(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/orgs/{org_id}/games/runner/runs', { params: { path: { org_id: orgId } } }),
      ),
    // One attempt fewer, even if the run is never finished.
    onSettled: () => void client.invalidateQueries({ queryKey: gamesKey(orgId) }),
  });
}

export function useFinishRun(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      runId,
      score,
      durationMs,
    }: {
      runId: string;
      score: number;
      durationMs: number;
    }) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/games/runner/runs/{run_id}/finish', {
          params: { path: { org_id: orgId, run_id: runId } },
          body: { score, duration_ms: durationMs },
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
    },
  });
}
