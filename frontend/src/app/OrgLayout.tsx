// A newsroom's frame: loads it, then fills the shell's desktop slots (laurels, pseudo, edition,
// main action).
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import { Navigate, useParams } from 'react-router';

import { ApiError } from '../api/client';
import { useTopic } from '../api/realtime';
import { orgKey, useOrg } from '../features/orgs/api';
import { EditionLink } from '../features/orgs/OrgSwitcher';
import { ButtonLink, Icon, Laurel } from '../ui/components';
import { PixelImage } from '../ui/PixelImage';
import { AppShell } from './AppShell';

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
  });

  if (org.error instanceof ApiError && org.error.status === 404) return <Navigate to="/" replace />;
  if (!org.data) return <AppShell />;
  const me = org.data.my_membership;

  return (
    <AppShell
      account={
        <>
          <Laurel value={me.balance} />
          <span aria-hidden="true">·</span>
          <PixelImage image={me.avatar} size={24} />
          <span>{me.pseudo.toUpperCase()}</span>
        </>
      }
      edition={<EditionLink org={org.data} />}
      action={
        <ButtonLink to={`/o/${orgId}/pronos/nouveau`}>
          <Icon name="plus" size={12} /> {t(me.role === 'reader' ? 'list.propose' : 'list.new')}
        </ButtonLink>
      }
    />
  );
}
