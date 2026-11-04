import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';
import { orgKey } from '../orgs/api';

export type PronoSummary = components['schemas']['PronoSummary'];
export type PronoDetail = components['schemas']['PronoDetail'];
export type PronoIn = components['schemas']['PronoIn'];
export type Bet = components['schemas']['BetOut'];
export type BetIn = components['schemas']['BetIn'];
export type Section = components['schemas']['SectionOut'];
export type Message = components['schemas']['MessageOut'];

export const pronoKey = (orgId: string, pronoId: string) => ['prono', orgId, pronoId] as const;
export const pronoListKey = (orgId: string) => ['pronos', orgId] as const;
export const messagesKey = (orgId: string, pronoId: string) =>
  ['messages', orgId, pronoId] as const;

export function useSections(orgId: string) {
  return useQuery({
    queryKey: ['sections', orgId],
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/sections', { params: { path: { org_id: orgId } } })),
  });
}

export function usePronoList(orgId: string, states: string[], section?: string) {
  const client = useQueryClient();
  // New pronos, bets and state changes of the newsroom refresh the lists.
  useTopic(`org:${orgId}`, (event) => {
    if (event.event.startsWith('prono.') || event.event === 'bet.placed') {
      void client.invalidateQueries({ queryKey: pronoListKey(orgId) });
    }
  });
  return useInfiniteQuery({
    queryKey: [...pronoListKey(orgId), states, section ?? null],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/orgs/{org_id}/pronos', {
          params: {
            path: { org_id: orgId },
            query: {
              state: states,
              ...(section ? { section } : {}),
              ...(pageParam ? { cursor: pageParam } : {}),
            },
          },
        }),
      ),
    getNextPageParam: (page) => page.next_cursor,
  });
}

export function useProno(orgId: string, pronoId: string) {
  const client = useQueryClient();
  useTopic(`prono:${pronoId}`, (event) => {
    // The discussion reloads itself; the prono only takes its new number of messages.
    if (event.event.startsWith('message.')) {
      const count = event.data.message_count;
      if (typeof count === 'number') {
        client.setQueryData<PronoDetail>(pronoKey(orgId, pronoId), (prono) =>
          prono ? { ...prono, message_count: count } : prono,
        );
      }
      return;
    }
    void client.invalidateQueries({ queryKey: pronoKey(orgId, pronoId) });
  });
  return useQuery({
    queryKey: pronoKey(orgId, pronoId),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/pronos/{prono_id}', {
          params: { path: { org_id: orgId, prono_id: pronoId } },
        }),
      ),
  });
}

export function useCreateProno(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PronoIn) =>
      unwrap(api.POST('/api/orgs/{org_id}/pronos', { params: { path: { org_id: orgId } }, body })),
    onSuccess: () => client.invalidateQueries({ queryKey: pronoListKey(orgId) }),
  });
}

export function usePlaceBet(orgId: string, pronoId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: BetIn) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/pronos/{prono_id}/bets', {
          params: { path: { org_id: orgId, prono_id: pronoId } },
          body,
        }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: pronoKey(orgId, pronoId) });
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
    },
  });
}

export function useUpload(orgId: string) {
  return useMutation({
    mutationFn: async (file: File) => {
      const body = new FormData();
      body.append('file', file);
      return unwrap(
        api.POST('/api/orgs/{org_id}/uploads', {
          params: { path: { org_id: orgId } },
          // openapi-fetch sends FormData as is.
          body: body as unknown as { file: string },
          bodySerializer: (value) => value as unknown as FormData,
        }),
      );
    },
  });
}

export function useProposalDecision(orgId: string, pronoId: string) {
  const client = useQueryClient();
  const settled = () => {
    void client.invalidateQueries({ queryKey: pronoKey(orgId, pronoId) });
    void client.invalidateQueries({ queryKey: pronoListKey(orgId) });
    void client.invalidateQueries({ queryKey: ['front-page', orgId] });
  };
  const path = { org_id: orgId, prono_id: pronoId };
  return {
    validate: useMutation({
      mutationFn: (baseGain: number) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/pronos/{prono_id}/validate', {
            params: { path },
            body: { base_gain: baseGain },
          }),
        ),
      onSuccess: settled,
    }),
    reject: useMutation({
      mutationFn: (reason: string) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/pronos/{prono_id}/reject', {
            params: { path },
            body: { reason: reason.trim() || null },
          }),
        ),
      onSuccess: settled,
    }),
  };
}

export type ReactionKind = 'bien_vu' | 'rire' | 'choc' | 'bravo' | 'doute';

export function useReact(orgId: string, pronoId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({ kind, on }: { kind: ReactionKind; on: boolean }) => {
      const params = { path: { org_id: orgId, prono_id: pronoId, kind } };
      await unwrap(
        on
          ? api.PUT('/api/orgs/{org_id}/pronos/{prono_id}/reactions/{kind}', { params })
          : api.DELETE('/api/orgs/{org_id}/pronos/{prono_id}/reactions/{kind}', { params }),
      );
    },
    onSettled: () => client.invalidateQueries({ queryKey: pronoKey(orgId, pronoId) }),
  });
}

/** The discussion of a prono (US14): the latest messages first loaded, older pages on demand;
 *  `message.*` events of the prono's topic reload what is on screen. */
export function useMessages(orgId: string, pronoId: string) {
  const client = useQueryClient();
  useTopic(`prono:${pronoId}`, (event) => {
    if (event.event.startsWith('message.')) {
      void client.invalidateQueries({ queryKey: messagesKey(orgId, pronoId) });
    }
  });
  return useInfiniteQuery({
    queryKey: messagesKey(orgId, pronoId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/orgs/{org_id}/pronos/{prono_id}/messages', {
          params: {
            path: { org_id: orgId, prono_id: pronoId },
            query: pageParam ? { before: pageParam } : {},
          },
        }),
      ),
    // The next page holds the older messages, before the oldest one shown.
    getNextPageParam: (page) => (page.has_more ? (page.items[0]?.id ?? null) : null),
  });
}

export function useDiscussion(orgId: string, pronoId: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: messagesKey(orgId, pronoId) });
  const path = { org_id: orgId, prono_id: pronoId };
  return {
    write: useMutation({
      mutationFn: (body: string) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/pronos/{prono_id}/messages', {
            params: { path },
            body: { body },
          }),
        ),
      onSuccess: refresh,
    }),
    like: useMutation({
      mutationFn: async ({ id, on }: { id: string; on: boolean }) => {
        const params = { path: { ...path, message_id: id } };
        await unwrap(
          on
            ? api.PUT('/api/orgs/{org_id}/pronos/{prono_id}/messages/{message_id}/like', {
                params,
              })
            : api.DELETE('/api/orgs/{org_id}/pronos/{prono_id}/messages/{message_id}/like', {
                params,
              }),
        );
      },
      onSettled: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: string) => {
        await unwrap(
          api.DELETE('/api/orgs/{org_id}/pronos/{prono_id}/messages/{message_id}', {
            params: { path: { ...path, message_id: id } },
          }),
        );
      },
      onSettled: refresh,
    }),
  };
}
