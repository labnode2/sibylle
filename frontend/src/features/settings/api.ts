import { useMutation, useQueryClient } from '@tanstack/react-query';

import { api, ApiError, unwrap } from '../../api/client';
import { realtime } from '../../api/realtime';
import type { components } from '../../api/schema';
import type { Me } from '../../api/types';
import { meKey } from '../auth/api';

type MePatch = components['schemas']['MePatch'];

/** Saves the account's display settings; the screen has them at once. */
export function useUpdateAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: MePatch) => unwrap(api.PATCH('/api/me', { body })),
    onMutate: (body) => {
      const before = client.getQueryData<Me>(meKey);
      if (before) client.setQueryData<Me>(meKey, { ...before, ...body } as Me);
      return { before };
    },
    onError: (_error, _body, context) => client.setQueryData(meKey, context?.before),
    onSuccess: (me) => client.setQueryData(meKey, me),
    meta: { success: 'settings:display.saved' },
  });
}

export function useLeaveNewsroom() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (orgId: string) =>
      unwrap(api.DELETE('/api/orgs/{org_id}/members/me', { params: { path: { org_id: orgId } } })),
    onSuccess: (_data, orgId) => {
      client.removeQueries({ predicate: (query) => query.queryKey.includes(orgId) });
      void client.invalidateQueries({ queryKey: meKey });
    },
    // The screen names the newsroom and links to its members.
    meta: { shown: ['last_editor'] },
  });
}

export function useDeleteAccount() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.DELETE('/api/me', { body: { confirm: true } })),
    onSuccess: () => {
      realtime.close();
      client.clear();
    },
    meta: { shown: ['last_editor'] },
  });
}

/** Downloads the export as the file the server names. */
export async function downloadMyData(): Promise<void> {
  const { data, response } = await api.GET('/api/me/export', { parseAs: 'blob' });
  if (!response.ok || !data) throw new ApiError(response.status, undefined);
  const disposition = response.headers.get('content-disposition') ?? '';
  const name = /filename="([^"]+)"/.exec(disposition)?.[1] ?? 'sibylle-mes-donnees.json';
  const url = URL.createObjectURL(data);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}
