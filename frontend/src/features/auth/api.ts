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

function useSignedIn() {
  const client = useQueryClient();
  return (me: Me) => {
    client.setQueryData(meKey, me);
    realtime.restart();
  };
}

export function useSignup() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (body: {
      email: string;
      password: string;
      first_name: string;
      last_name: string;
    }) => unwrap(api.POST('/api/auth/signup', { body })),
    onSuccess: signedIn,
  });
}

export function useLogin() {
  const signedIn = useSignedIn();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      unwrap(api.POST('/api/auth/login', { body })),
    onSuccess: signedIn,
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

export function useRequestReset() {
  return useMutation({
    mutationFn: (email: string) =>
      unwrap(api.POST('/api/auth/password-reset', { body: { email } })),
  });
}

export function useConfirmReset() {
  return useMutation({
    mutationFn: (body: { token: string; password: string }) =>
      unwrap(api.POST('/api/auth/password-reset/confirm', { body })),
  });
}

export function useVerifyEmail() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => unwrap(api.POST('/api/auth/verify-email', { body: { token } })),
    onSuccess: () => client.invalidateQueries({ queryKey: meKey }),
  });
}
