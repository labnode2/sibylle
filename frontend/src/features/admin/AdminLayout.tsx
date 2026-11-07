// The editor's settings, under /o/:orgId/reglages, reached from « La rédaction »: the card and
// the laurels, the members, the games of each week, the reports, and the parameters (deleting
// the newsroom). Other roles get a short notice (the server refuses them anyway).
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useParams } from 'react-router';

import { Chip, TopBar } from '../../ui/components';
import { useOrg } from '../orgs/api';
import { useReports } from './api';
import styles from './admin.module.css';

function OpenReports({ orgId }: { orgId: string }) {
  const reports = useReports(orgId);
  const count = reports.data?.length ?? 0;
  return count > 0 ? <span className={styles.badge}>{count}</span> : null;
}

export function AdminLayout() {
  const { t } = useTranslation('admin');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  if (!org.data) return <p role="status">{t('common:shell.loading')}</p>;
  if (org.data.my_membership.role !== 'editor') {
    return <p className={styles.alert}>{t('editorOnly')}</p>;
  }
  const base = `/o/${orgId}/reglages`;
  const link = ({ isActive }: { isActive: boolean }) =>
    `${styles.tab} ${isActive ? styles.tabActive : ''}`;

  return (
    <div className={styles.page}>
      <TopBar
        back={`/o/${orgId}/redaction`}
        backLabel={t('back')}
        aside={<Chip variant="ink">{t('roles.editor').toUpperCase()}</Chip>}
      />
      <header className={styles.head}>
        <h1 className={styles.title}>{org.data.title}</h1>
        <p className={styles.subtitle}>{t('title')}</p>
      </header>
      <nav className={styles.tabs} aria-label={t('nav')}>
        <NavLink to={base} end className={link}>
          {t('tabs.card')}
        </NavLink>
        <NavLink to={`${base}/membres`} className={link}>
          {t('tabs.members')}
        </NavLink>
        <NavLink to={`${base}/jeux`} className={link}>
          {t('tabs.games')}
        </NavLink>
        <NavLink to={`${base}/signalements`} className={link}>
          {t('tabs.reports')} <OpenReports orgId={orgId} />
        </NavLink>
        <NavLink to={`${base}/parametres`} className={link}>
          {t('tabs.parameters')}
        </NavLink>
      </nav>
      <Outlet />
    </div>
  );
}
