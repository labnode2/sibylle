import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { api, unwrap } from '../../api/client';
import { useTopic } from '../../api/realtime';
import type { components } from '../../api/schema';
import { reportsKey } from '../admin/api';
import { meKey } from '../auth/api';

export type NotificationPref = components['schemas']['NotificationPrefItem'];
export type NotificationKind = NotificationPref['type'];
export type NotificationChannel = NotificationPref['channel'];

export const KINDS: NotificationKind[] = [
  'new_prono',
  'closing_soon',
  'result',
  'designation_reminder',
  'report',
  'mention',
  'discussion',
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

// The bubbles of the menus: per prono, the notifications still waiting for me in a newsroom.
// They are counted on the newsroom in the lists of newsrooms, beside « Pronos », then on the
// list's filters and on each prono; opening the prono reads them.
export type UnreadNotifications = components['schemas']['UnreadNotifications'];
export type UnreadProno = components['schemas']['UnreadProno'];

export const unreadKey = (orgId: string) => ['notifications-unread', orgId] as const;

// A notification arrived, was read on another device, or stopped counting (its prono closed…).
const NOTIFICATION_EVENTS = ['notification.created', 'notification.read', 'notification.changed'];

/** The bubbles follow the server's events on my own topic, without a reload: those of a
 *  newsroom's menus (« Pronos », and « La rédaction » for the editor's open reports), and each
 *  newsroom's own in the lists of newsrooms, which adds them up (`waiting` in `/api/me`). */
export function useBubbleEvents() {
  const client = useQueryClient();
  useTopic('me', (event) => {
    const orgId = typeof event.data.org_id === 'string' ? event.data.org_id : null;
    if (NOTIFICATION_EVENTS.includes(event.event)) {
      void client.invalidateQueries({ queryKey: meKey });
      if (orgId) void client.invalidateQueries({ queryKey: unreadKey(orgId) });
    }
    // A report filed, or handled by an editor: the editors' counts of open reports.
    if (event.event === 'report.created' || event.event === 'report.handled') {
      void client.invalidateQueries({ queryKey: meKey });
      void client.invalidateQueries({ queryKey: orgId ? reportsKey(orgId) : ['reports'] });
    }
  });
}

export function useUnread(orgId: string) {
  return useQuery({
    queryKey: unreadKey(orgId),
    queryFn: () =>
      unwrap(
        api.GET('/api/orgs/{org_id}/notifications/unread', {
          params: { path: { org_id: orgId } },
        }),
      ),
  });
}

/** The bubbles without a prono's: what is left once it is read. */
function without(unread: UnreadNotifications, pronoId: string): UnreadNotifications {
  const pronos = unread.pronos.filter((prono) => prono.prono_id !== pronoId);
  return { total: pronos.reduce((sum, prono) => sum + prono.unread, 0), pronos };
}

/** Opening a prono reads its notifications, those that arrive while it is open too: its bubbles
 *  go at once, and on my other screens through the server's event. */
export function useReadProno(orgId: string, pronoId: string) {
  const client = useQueryClient();
  const waiting = useUnread(orgId).data?.pronos.some((prono) => prono.prono_id === pronoId);
  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST('/api/orgs/{org_id}/notifications/read', {
          params: { path: { org_id: orgId } },
          body: { prono_id: pronoId },
        }),
      ),
    // The bubbles go at once. After a failure, the next refresh shows them again and so tries
    // again: refreshing right away would try again and again while the server cannot answer.
    onMutate: async () => {
      await client.cancelQueries({ queryKey: unreadKey(orgId) });
      client.setQueryData<UnreadNotifications>(
        unreadKey(orgId),
        (unread) => unread && without(unread, pronoId),
      );
    },
    // The newsroom's bubble in the lists of newsrooms follows (the server's event says it too).
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: unreadKey(orgId) }),
        client.invalidateQueries({ queryKey: meKey }),
      ]),
    // Nobody asked for it: no note when it fails.
    meta: { quiet: true },
  });
  useEffect(() => {
    if (waiting && !isPending) mutate();
  }, [waiting, isPending, mutate]);
}
