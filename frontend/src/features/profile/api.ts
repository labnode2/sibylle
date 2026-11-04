import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { orgKey } from '../orgs/api';

export type PressCard = components['schemas']['PressCard'];
export type CatalogItem = components['schemas']['CatalogItemOut'];
export type CatalogEntry = components['schemas']['CatalogEntry'];
export type LedgerEntry = components['schemas']['LedgerEntryOut'];
export type MemberPatch = components['schemas']['MemberPatch'];

export const pressCardKey = (orgId: string, memberId: string) =>
  ['press-card', orgId, memberId] as const;
const catalogKey = (orgId: string) => ['catalog', orgId] as const;
const ledgerKey = (orgId: string) => ['ledger', orgId] as const;

export function usePressCard(orgId: string, memberId: string | undefined) {
  return useQuery({
    queryKey: pressCardKey(orgId, memberId ?? ''),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/members/{member_id}', {
          params: { path: { org_id: orgId, member_id: memberId! } },
        }),
      ),
    enabled: Boolean(memberId),
  });
}

export function useLedger(orgId: string) {
  return useInfiniteQuery({
    queryKey: ledgerKey(orgId),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET('/api/orgs/{org_id}/members/me/ledger', {
          params: {
            path: { org_id: orgId },
            query: { limit: 20, ...(pageParam ? { cursor: pageParam } : {}) },
          },
        }),
      ),
    getNextPageParam: (page) => page.next_cursor,
  });
}

/** Changes the member's own profile, then refreshes everything that shows it. */
export function useUpdateProfile(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: MemberPatch) =>
      unwrap(
        api.PATCH('/api/orgs/{org_id}/members/me', { params: { path: { org_id: orgId } }, body }),
      ),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
      void client.invalidateQueries({ queryKey: ['press-card', orgId] });
      void client.invalidateQueries({ queryKey: ['members', orgId] });
    },
  });
}

export function useCatalog(orgId: string) {
  return useQuery({
    queryKey: catalogKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/catalog', { params: { path: { org_id: orgId } } })),
  });
}

export function useCollectionActions(orgId: string) {
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: catalogKey(orgId) });
    void client.invalidateQueries({ queryKey: orgKey(orgId) });
    void client.invalidateQueries({ queryKey: ledgerKey(orgId) });
    void client.invalidateQueries({ queryKey: ['press-card', orgId] });
  };
  return {
    buy: useMutation({
      mutationFn: (itemId: string) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/catalog/{item_id}/purchase', {
            params: { path: { org_id: orgId, item_id: itemId } },
          }),
        ),
      onSuccess: refresh,
    }),
    redeem: useMutation({
      mutationFn: (code: string) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/secret-codes/redeem', {
            params: { path: { org_id: orgId } },
            body: { code },
          }),
        ),
      onSuccess: refresh,
    }),
  };
}
