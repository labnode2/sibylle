import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, unwrap } from '../../api/client';
import type { components } from '../../api/schema';

export type NotificationPref = components['schemas']['NotificationPrefItem'];
export type NotificationKind = NotificationPref['type'];
export type NotificationChannel = NotificationPref['channel'];

export const KINDS: NotificationKind[] = [
  'new_prono',
  'closing_soon',
  'result',
  'designation_reminder',
  'report',
];
export const CHANNELS: NotificationChannel[] = ['push', 'email'];

const prefsKey = ['notification-prefs'] as const;
const vapidKey = ['vapid-public-key'] as const;

export function useNotificationPrefs() {
  return useQuery({
    queryKey: prefsKey,
    queryFn: () => unwrap(api.GET('/api/me/notification-prefs')),
  });
}

/** Flips one switch; the screen shows it at once and goes back if the server says no. */
export function useSetNotificationPref() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (pref: NotificationPref) =>
      unwrap(api.PUT('/api/me/notification-prefs', { body: [pref] })),
    onMutate: async (pref) => {
      await client.cancelQueries({ queryKey: prefsKey });
      const before = client.getQueryData<NotificationPref[]>(prefsKey);
      client.setQueryData<NotificationPref[]>(prefsKey, (prefs) =>
        prefs?.map((p) =>
          p.type === pref.type && p.channel === pref.channel ? { ...p, enabled: pref.enabled } : p,
        ),
      );
      return { before };
    },
    onError: (_error, _pref, context) => client.setQueryData(prefsKey, context?.before),
    onSuccess: (prefs) => client.setQueryData(prefsKey, prefs),
    meta: { success: 'notifications:saved' },
  });
}

/** The server's public key for push; null when push is not set up on the server. */
export function useVapidKey() {
  return useQuery({
    queryKey: vapidKey,
    queryFn: async () => (await unwrap(api.GET('/api/push/vapid-public-key'))).key ?? null,
    staleTime: Infinity,
  });
}

/** Attaches this device to the signed-in account; returns the subscription's id. */
export async function sendSubscription(subscription: PushSubscription): Promise<string> {
  const json = subscription.toJSON();
  const created = await unwrap(
    api.POST('/api/me/push-subscriptions', {
      body: {
        endpoint: subscription.endpoint,
        keys: { p256dh: json.keys?.p256dh ?? '', auth: json.keys?.auth ?? '' },
      },
    }),
  );
  return created.id;
}

export async function forgetSubscription(id: string): Promise<void> {
  await unwrap(
    api.DELETE('/api/me/push-subscriptions/{subscription_id}', {
      params: { path: { subscription_id: id } },
    }),
  );
}

// The bell: the member's notifications in a newsroom, and how many are unread.
export type NotificationItem = components['schemas']['NotificationOut'];
export type NotificationList = components['schemas']['NotificationList'];

export const notificationListKey = (orgId: string) => ['notification-list', orgId] as const;

export function useNotificationList(orgId: string) {
  return useQuery({
    queryKey: notificationListKey(orgId),
    queryFn: () =>
      unwrap(api.GET('/api/orgs/{org_id}/notifications', { params: { path: { org_id: orgId } } })),
  });
}

/** How many notifications are unread here (0 until the list is loaded). */
export function useUnreadCount(orgId: string): number {
  return useNotificationList(orgId).data?.unread ?? 0;
}

/** Marks one notification read, or all of them when no id is given; the list reloads. */
export function useMarkRead(orgId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (notificationId?: string) =>
      notificationId
        ? unwrap(
            api.POST('/api/orgs/{org_id}/notifications/{notification_id}/read', {
              params: { path: { org_id: orgId, notification_id: notificationId } },
            }),
          )
        : unwrap(
            api.POST('/api/orgs/{org_id}/notifications/read', {
              params: { path: { org_id: orgId } },
            }),
          ),
    onSettled: () => client.invalidateQueries({ queryKey: notificationListKey(orgId) }),
  });
}
