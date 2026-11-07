// A newsroom's frame: loads it, then fills the shell's desktop slots (laurels and coins, pseudo,
// the newsroom's small card), and shows the good news of Monday's coins, then the installed
// app's offer of notifications.
import { useQueryClient } from '@tanstack/react-query';
import { Navigate, useParams } from 'react-router';

import { ApiError } from '../api/client';
import { useTopic } from '../api/realtime';
import { reportsKey } from '../features/admin/api';
import { useWeeklyCoins, weeklyCoinsKey } from '../features/coins/api';
import { WeeklyCoinsDialog } from '../features/coins/WeeklyCoinsDialog';
import { InstalledPushDialog } from '../features/notifications/InstalledPushDialog';
import { orgKey, useOrg } from '../features/orgs/api';
import { pronoKey } from '../features/pronos/api';
import { NewsroomSwitcher } from '../features/orgs/NewsroomPage';
import { Wallet } from '../ui/components';
import { PixelImage } from '../ui/PixelImage';
import { AppShell } from './AppShell';

/** A newsroom's pop-ups, one at a time: Monday's good news first, then the installed app's offer
 *  to turn notifications on. */
function Dialogs({ orgId, coins }: { orgId: string; coins: number }) {
  const weekly = useWeeklyCoins(orgId);
  return (
    <>
      <WeeklyCoinsDialog orgId={orgId} coins={coins} />
      {!weekly.isPending && !weekly.data && <InstalledPushDialog />}
    </>
  );
}

export function OrgLayout() {
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const client = useQueryClient();
  // A result, a refund or a correction moves the balance: the header follows.
  useTopic('me', (event) => {
    if (event.event === 'balance.changed' && event.data.org_id === orgId) {
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
    }
    // Monday's conversion while the app is open: the counters move and the good news shows.
    if (event.event === 'coins.granted' && event.data.org_id === orgId) {
      void client.invalidateQueries({ queryKey: orgKey(orgId) });
      void client.invalidateQueries({ queryKey: weeklyCoinsKey(orgId) });
    }
    // A new report for the editor; a handled one for its author, on the prono's page.
    if (event.event === 'report.created') {
      void client.invalidateQueries({ queryKey: reportsKey(orgId) });
    }
    if (event.event === 'report.handled') {
      void client.invalidateQueries({ queryKey: pronoKey(orgId, String(event.data.prono_id)) });
    }
  });

  if (org.error instanceof ApiError && org.error.status === 404) return <Navigate to="/" replace />;
  if (!org.data) return <AppShell />;
  const me = org.data.my_membership;

  return (
    <>
      <AppShell
        account={
          <>
            <Wallet balance={me.balance} gold={me.gold} coins={me.coins} />
            <span aria-hidden="true">·</span>
            <PixelImage image={me.avatar} size={24} />
            <span>{me.pseudo.toUpperCase()}</span>
          </>
        }
        issue={org.data.edition_number}
        newsroom={<NewsroomSwitcher org={org.data} />}
      />
      <Dialogs orgId={orgId} coins={me.coins} />
    </>
  );
}
