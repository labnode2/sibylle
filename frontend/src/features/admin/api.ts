// The editor's settings: the card and the laurels, the access code, invitations, members,
// sections, reports, and deleting the newsroom.
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import type { Me } from '../../api/types';
import { meKey } from '../auth/api';
import { orgKey } from '../orgs/api';

export type OrgPatch = components['schemas']['OrgPatch'];
export type Invitation = components['schemas']['InvitationOut'];
export type ReportDetail = components['schemas']['ReportDetail'];
export type Role = components['schemas']['MemberPublic']['role'];

const membersKey = (orgId: string) => ['members', orgId] as const;
const invitationsKey = (orgId: string) => ['invitations', orgId] as const;
const sectionsKey = (orgId: string) => ['sections', orgId] as const;
export const reportsKey = (orgId: string) => ['reports', orgId] as const;

/** Saves some of the settings; `success` is the toast's text key. */
export function useUpdateOrg(orgId: string, success = 'admin:saved') {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: OrgPatch) =>
      unwrap(api.PATCH('/api/orgs/{org_id}', { params: { path: { org_id: orgId } }, body })),
    onSuccess: (org) => client.setQueryData(orgKey(orgId), org),
    meta: { success },
  });
}

export const deleteOrgKey = (orgId: string) => ['deleteOrg', orgId] as const;

/** Forgets a deleted newsroom: out of the account's newsrooms at once, so that « / » does not
 *  lead back to it, and every query about it dropped. */
export function forgetOrg(client: QueryClient, orgId: string) {
  client.setQueryData<Me>(
    meKey,
    (me) => me && { ...me, memberships: me.memberships.filter((entry) => entry.org.id !== orgId) },
  );
  client.removeQueries({ predicate: (query) => query.queryKey.includes(orgId) });
  void client.invalidateQueries({ queryKey: meKey });
}

/** Deletes the newsroom (a mark the server can take back). */
export function useDeleteOrg(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationKey: deleteOrgKey(orgId),
    mutationFn: () =>
      unwrap(api.DELETE('/api/orgs/{org_id}', { params: { path: { org_id: orgId } } })),
    onSuccess: () => forgetOrg(client, orgId),
    meta: { success: 'admin:toasts.orgDeleted' },
  });
}

export function useAccessCode(orgId: string) {
  const client = useQueryClient();
  const params = { path: { org_id: orgId } };
  const refresh = () => client.invalidateQueries({ queryKey: orgKey(orgId) });
  return {
    renew: useMutation({
      mutationFn: () => unwrap(api.POST('/api/orgs/{org_id}/access-code', { params })),
      onSuccess: refresh,
      meta: { success: 'admin:toasts.codeRenewed' },
    }),
    disable: useMutation({
      mutationFn: () => unwrap(api.DELETE('/api/orgs/{org_id}/access-code', { params })),
      onSuccess: refresh,
      meta: { success: 'admin:toasts.codeDisabled' },
    }),
  };
}

export function useInvitations(orgId: string) {
  return useQuery({
    queryKey: invitationsKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/invitations', { params: { path: { org_id: orgId } } })),
  });
}

export function useRevokeInvitation(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) =>
      unwrap(
        api.DELETE('/api/orgs/{org_id}/invitations/{invitation_id}', {
          params: { path: { org_id: orgId, invitation_id: invitationId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: invitationsKey(orgId) }),
    meta: { success: 'admin:toasts.invitationRevoked' },
  });
}

export function useMembers(orgId: string) {
  return useQuery({
    queryKey: membersKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/members', { params: { path: { org_id: orgId } } })),
  });
}

export function useMemberActions(orgId: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: membersKey(orgId) });
  const path = (memberId: string) => ({ path: { org_id: orgId, member_id: memberId } });
  return {
    changeRole: useMutation({
      mutationFn: ({ memberId, role }: { memberId: string; role: Role }) =>
        unwrap(
          api.PATCH('/api/orgs/{org_id}/members/{member_id}/role', {
            params: path(memberId),
            body: { role },
          }),
        ),
      onSuccess: () => {
        void refresh();
        // Changing one's own role changes what one may do.
        void client.invalidateQueries({ queryKey: orgKey(orgId) });
      },
    }),
    remove: useMutation({
      mutationFn: (memberId: string) =>
        unwrap(api.DELETE('/api/orgs/{org_id}/members/{member_id}', { params: path(memberId) })),
      onSuccess: refresh,
    }),
    adjust: useMutation({
      mutationFn: ({
        memberId,
        amount,
        reason,
      }: {
        memberId: string;
        amount: number;
        reason: string;
      }) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/members/{member_id}/adjustments', {
            params: path(memberId),
            body: { amount, reason },
          }),
        ),
      // The list shows each member's green laurels.
      onSuccess: refresh,
    }),
  };
}

export function useSectionActions(orgId: string) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: sectionsKey(orgId) });
  const path = (sectionId: string) => ({ path: { org_id: orgId, section_id: sectionId } });
  return {
    create: useMutation({
      mutationFn: (name: string) =>
        unwrap(
          api.POST('/api/orgs/{org_id}/sections', {
            params: { path: { org_id: orgId } },
            body: { name },
          }),
        ),
      onSuccess: refresh,
      meta: { success: 'admin:toasts.sectionAdded' },
    }),
    update: useMutation({
      mutationFn: ({
        sectionId,
        ...body
      }: {
        sectionId: string;
        name?: string;
        position?: number;
      }) =>
        unwrap(
          api.PATCH('/api/orgs/{org_id}/sections/{section_id}', {
            params: path(sectionId),
            body,
          }),
        ),
      onSuccess: refresh,
      meta: { success: 'admin:toasts.sectionChanged' },
    }),
    remove: useMutation({
      mutationFn: (sectionId: string) =>
        unwrap(api.DELETE('/api/orgs/{org_id}/sections/{section_id}', { params: path(sectionId) })),
      onSuccess: refresh,
      meta: { success: 'admin:toasts.sectionRemoved' },
    }),
  };
}

/** The open reports; `enabled` false for a member who is not an editor (the server refuses). */
export function useReports(orgId: string, enabled = true) {
  return useQuery({
    enabled,
    queryKey: reportsKey(orgId),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/reports', {
          params: { path: { org_id: orgId }, query: { state: 'open' } },
        }),
      ),
  });
}

export function useHandleReport(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({
      reportId,
      state,
      note,
    }: {
      reportId: string;
      state: 'resolved' | 'dismissed';
      note: string;
    }) =>
      unwrap(
        api.POST('/api/orgs/{org_id}/reports/{report_id}/handle', {
          params: { path: { org_id: orgId, report_id: reportId } },
          body: { state, note: note.trim() || null },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: reportsKey(orgId) }),
    meta: { success: 'admin:toasts.reportHandled' },
  });
}
