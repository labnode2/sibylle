import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import { realtime } from '../../api/realtime';

export const meKey = ['me'] as const;

export function useMe() {
  return useQuery({
    queryKey: meKey,
    queryFn: () => unwrap(api.GET('/api/me')),
    staleTime: 60_000,
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
