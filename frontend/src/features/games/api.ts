import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';
import i18n from '../../i18n';
import { toast } from '../../ui/Toaster';
import { orgKey } from '../orgs/api';

export type Games = components['schemas']['Games'];
export type Game = Games['scheduled'][number];
export type GameSchedule = components['schemas']['GameSchedule'];
export type RunnerStatus = components['schemas']['RunnerStatus'];
export type PixelStatus = components['schemas']['PixelStatus'];
export type PixelPuzzleIn = components['schemas']['PixelPuzzleIn'];

/** Every game, in the order the server lists them. */
export const GAMES: readonly Game[] = ['runner', 'pixel'];

export const gamesKey = (orgId: string) => ['games', orgId] as const;
const queueKey = (orgId: string) => ['pixel-queue', orgId] as const;
const scheduleKey = (orgId: string) => ['game-schedule', orgId] as const;
const GAME_EVENTS = new Set([
  'games.runner.updated',
  'games.pixel.revealed',
  'games.pixel.found',
  'games.pixel.finished',
  'games.schedule.changed',
]);

/** The games of the week, live: a run finished, pixels shown, a word found, a game ended, the
 *  week's games changed by the editor. */
export function useGames(orgId: string) {
  const client = useQueryClient();
  useTopic(`org:${orgId}`, (event) => {
    if (GAME_EVENTS.has(event.event)) {
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
    }
    if (event.event === 'games.pixel.finished' || event.event === 'games.pixel.revealed') {
      void client.invalidateQueries({ queryKey: queueKey(orgId) });
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
    meta: { quiet: true },
    onError: () => toast.error(i18n.t('games:runner.failed')),
  });
}

export function useGuess(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (word: string) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/games/pixel/guesses', {
          params: { path: { org_id: orgId } },
          body: { word },
        }),
      ),
    onSuccess: (answer) => {
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
      if (answer.correct) void client.invalidateQueries({ queryKey: orgKey(orgId) });
    },
  });
}

/** The drawings to come, for the journalists. */
export function usePixelQueue(orgId: string, enabled: boolean) {
  return useQuery({
    queryKey: queueKey(orgId),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/games/pixel/puzzles', { params: { path: { org_id: orgId } } }),
      ),
    enabled,
  });
}

export function usePostPuzzle(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PixelPuzzleIn) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/games/pixel/puzzles', {
          params: { path: { org_id: orgId } },
          body,
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
      void client.invalidateQueries({ queryKey: queueKey(orgId) });
    },
  });
}

/** The editor's planning: an ordinary week, then this week and the three after it. */
export function useGameSchedule(orgId: string) {
  return useQuery({
    queryKey: scheduleKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/games/schedule', { params: { path: { org_id: orgId } } })),
  });
}

/** A change of the planning answers with the whole planning; this week's games may change too. */
function useScheduleChange<T>(orgId: string, change: (input: T) => Promise<GameSchedule>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: change,
    onSuccess: (schedule) => {
      client.setQueryData(scheduleKey(orgId), schedule);
      void client.invalidateQueries({ queryKey: gamesKey(orgId) });
    },
    meta: { success: 'admin:games.saved' },
  });
}

/** The games of an ordinary week, from next week on. */
export function useSetOrdinaryWeek(orgId: string) {
  return useScheduleChange(orgId, (games: Game[]) =>
    unwrap(
      api.PUT('/api/orgs/{org_id}/games/schedule/default', {
        params: { path: { org_id: orgId } },
        body: { games },
      }),
    ),
  );
}

/** Games of its own for a week (its Monday, `AAAA-MM-JJ`). */
export function usePlanWeek(orgId: string) {
  return useScheduleChange(orgId, ({ week, games }: { week: string; games: Game[] }) =>
    unwrap(
      api.PUT('/api/orgs/{org_id}/games/schedule/weeks/{week_start}', {
        params: { path: { org_id: orgId, week_start: week } },
        body: { games },
      }),
    ),
  );
}

/** An upcoming week back to an ordinary week. */
export function useUnplanWeek(orgId: string) {
  return useScheduleChange(orgId, (week: string) =>
    unwrap(
      api.DELETE('/api/orgs/{org_id}/games/schedule/weeks/{week_start}', {
        params: { path: { org_id: orgId, week_start: week } },
      }),
    ),
  );
}
