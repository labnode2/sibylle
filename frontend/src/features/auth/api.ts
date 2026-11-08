import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { realtime } from '../../api/realtime';
import type { Me } from '../../api/types';

export const meKey = ['me'] as const;

export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: () => unwrap(api.GET('/api/me')),
    staleTime: 60_000,
  });
}

/** The welcome pop-up is closed: the account remembers it, on every device. */
export function useWelcomed() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.PATCH('/api/me', { body: { welcomed: true } })),
    onMutate: () => {
      const before = client.getQueryData<Me>(meKey);
      if (before) client.setQueryData<Me>(meKey, { ...before, welcomed: true });
    },
    onSuccess: (me) => client.setQueryData(meKey, me),
    // Missed by the server: the pop-up shows once more, nothing else to say.
    meta: { quiet: true },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/logout')),
    onSuccess: () => {
      realtime.close();
      client.clear();
    },
  });
}

/** Has Keycloak send the address check again (at most 3 an hour, FR-008). */
export function useResendVerification() {
  return useMutation({
    mutationFn: () => unwrap(api.POST('/api/auth/verify-email/resend')),
    meta: { success: 'notifications:resent' },
  });
}
