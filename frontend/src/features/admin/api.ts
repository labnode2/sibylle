// The editor's settings: the card and the laurels, the access code, invitations, members,
// sections and reports.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';
import { orgKey } from '../orgs/api';

export type OrgPatch = components['schemas']['OrgPatch'];
export type Invitation = components['schemas']['InvitationOut'];
export type ReportDetail = components['schemas']['ReportDetail'];
export type Role = components['schemas']['MemberPublic']['role'];

const membersKey = (orgId: string) => ['members', orgId] as const;
const invitationsKey = (orgId: string) => ['invitations', orgId] as const;
const sectionsKey = (orgId: string) => ['sections', orgId] as const;
export const reportsKey = (orgId: string) => ['reports', orgId] as const;

export function useUpdateOrg(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: OrgPatch) =>
      unwrap(api.PATCH('/api/orgs/{org_id}', { params: { path: { org_id: orgId } }, body })),
    onSuccess: (org) => client.setQueryData(orgKey(orgId), org),
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
    }),
    disable: useMutation({
      mutationFn: () => unwrap(api.DELETE('/api/orgs/{org_id}/access-code', { params })),
      onSuccess: refresh,
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
    }),
    remove: useMutation({
      mutationFn: (sectionId: string) =>
        unwrap(api.DELETE('/api/orgs/{org_id}/sections/{section_id}', { params: path(sectionId) })),
      onSuccess: refresh,
    }),
  };
}

export function useReports(orgId: string) {
  return useQuery({
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
  });
}
