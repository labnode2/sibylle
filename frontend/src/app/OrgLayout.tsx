// A newsroom's frame: loads it, then fills the shell's desktop slots (laurels and coins, pseudo,
// edition, main action), and shows the good news of Monday's coins.
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { Navigate, useParams } from 'react-router';

import { ApiError } from '../api/client';
import { useTopic } from '../api/realtime';
import { reportsKey } from '../features/admin/api';
import { weeklyCoinsKey } from '../features/coins/api';
import { WeeklyCoinsDialog } from '../features/coins/WeeklyCoinsDialog';
import { orgKey, useOrg } from '../features/orgs/api';
import { pronoKey } from '../features/pronos/api';
import { EditionLink } from '../features/orgs/OrgSwitcher';
import { ButtonLink, Icon, Wallet } from '../ui/components';
import { PixelImage } from '../ui/PixelImage';
import { AppShell } from './AppShell';
import styles from './shell.module.css';

export function OrgLayout() {
  const { t } = useTranslation('pronos');
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
        edition={<EditionLink org={org.data} />}
        issue={org.data.edition_number}
        action={
          <ButtonLink to={`/o/${orgId}/pronos/nouveau`} className={styles.action}>
            <Icon name="plus" size={12} /> {t('list.proposeLong')}
          </ButtonLink>
        }
      />
      <WeeklyCoinsDialog orgId={orgId} coins={me.coins} />
    </>
  );
}
