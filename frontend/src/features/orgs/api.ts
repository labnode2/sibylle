import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import type { PixelImage } from '../../api/types';
import { meKey } from '../auth/api';

export function useContent() {
  return useQuery({
    queryKey: ['content'],
    queryFn: () => unwrap(api.GET('/api/content')),
    staleTime: Infinity,
  });
}

export const orgKey = (orgId: string) => ['org', orgId] as const;

export function useOrg(orgId: string) {
  return useQuery({
    queryKey: orgKey(orgId),
    queryFn: () => unwrap(api.GET('/api/orgs/{org_id}', { params: { path: { org_id: orgId } } })),
  });
}

export function useCreateOrg() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      title: string;
      background_key: string;
      pseudo: string;
      avatar: PixelImage;
    }) => unwrap(api.POST('/api/orgs', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: meKey }),
  });
}

export type JoinSource = { token: string } | { code: string };

export function useJoinPreview(source: JoinSource | null) {
  return useQuery({
    queryKey: ['join-preview', source],
    queryFn: () => unwrap(api.POST('/api/join/preview', { body: source! })),
    enabled: source !== null,
    retry: false,
  });
}

export function useJoin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (
      body: JoinSource & { pseudo: string; avatar: PixelImage; charter_accepted: true },
    ) => unwrap(api.POST('/api/join', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: meKey }),
  });
}

export const invitationsKey = (orgId: string) => ['invitations', orgId] as const;

export function useInvite(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (
      body: components['schemas']['LinkInvitationIn'] | components['schemas']['EmailInvitationIn'],
    ) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/invitations', {
          params: { path: { org_id: orgId } },
          body,
        }),
      ),
    // The editor's list of invitations shows the new one at once.
    onSuccess: () => client.invalidateQueries({ queryKey: invitationsKey(orgId) }),
  });
}
