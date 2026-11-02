// First version of the front page: the newsroom, your pseudo and balance. US5 replaces it with the
// full front page.
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { Kicker, Laurel } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { InvitePanel } from '../admin/InvitePanel';
import { useOrg } from '../orgs/api';
import styles from './une.module.css';

export function UnePage() {
  const { t } = useTranslation('orgs');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  if (!org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;

  return (
    <div className={styles.une}>
      <div className={styles.hello}>
        <PixelImage image={me.avatar} size={48} />
        <div className={styles.helloText}>
          <Kicker tone="indigo">{t('une.edition', { title: org.data.title.toUpperCase() })}</Kicker>
          <h1 className={styles.title}>{t('une.hello', { pseudo: me.pseudo })}</h1>
          <Laurel value={me.balance} />
        </div>
      </div>
      <p className={styles.soon}>{t('une.soon')}</p>
      <Link to="/redactions">{t('une.switch')}</Link>
      {me.role === 'editor' && <InvitePanel orgId={orgId} accessCode={org.data.access_code} />}
    </div>
  );
}
