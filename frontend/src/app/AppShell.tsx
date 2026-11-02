// The frame of a newsroom's pages: compact masthead and bottom tabs on a phone; date bar, large
// masthead and top navigation on a computer (canvas pages « Mobile » and « Ordinateur »).
import { useSyncExternalStore, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useParams } from 'react-router';

import { formatDate } from '../i18n';
import { Masthead, TabBar, type Tab } from '../ui/components';
import styles from './shell.module.css';

function subscribeOnline(callback: () => void) {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
}

export function useOnline(): boolean {
  return useSyncExternalStore(
    subscribeOnline,
    () => navigator.onLine,
    () => true,
  );
}

export function OfflineBanner() {
  const { t } = useTranslation();
  const online = useOnline();
  if (online) return null;
  return (
    <p className={styles.offline} role="status">
      {t('shell.offline')}
    </p>
  );
}

export type ShellSlots = {
  /** Right side of the desktop date bar (laurels, avatar, pseudo). */
  account?: ReactNode;
  /** Left side of the desktop navigation (newsroom switcher). */
  edition?: ReactNode;
  /** Right side of the desktop navigation (main action). */
  action?: ReactNode;
  /** The editor also gets the newsroom's settings. */
  admin?: boolean;
};

export function AppShell({ account, edition, action, admin = false }: ShellSlots) {
  const { t } = useTranslation();
  const { orgId = '' } = useParams();
  const base = `/o/${orgId}`;
  const tabs: Tab[] = [
    { to: base, label: t('tabs.une'), icon: 'home', end: true },
    { to: `${base}/pronos`, label: t('tabs.pronos'), icon: 'ball' },
    { to: `${base}/classement`, label: t('tabs.ranking'), icon: 'trophy' },
    { to: `${base}/profil`, label: t('tabs.profile'), icon: 'user' },
    ...(admin ? [{ to: `${base}/reglages`, label: t('tabs.settings'), icon: 'gear' } as Tab] : []),
  ];
  const today = formatDate(new Date(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className={styles.page}>
      <div className={styles.desktopOnly}>
        <div className={styles.infoBar}>
          <span>{today.toUpperCase()}</span>
          <span className={styles.slot}>{account}</span>
        </div>
        <Masthead size="large" />
        <div className={styles.navBar}>
          <span className={styles.slot}>{edition}</span>
          <nav className={styles.nav} aria-label={t('tabs.label')}>
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) =>
                  `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`
                }
              >
                <span>{tab.label}</span>
              </NavLink>
            ))}
          </nav>
          <span className={styles.slot}>{action}</span>
        </div>
      </div>
      <div className={styles.mobileOnly}>
        <Masthead size="compact" />
      </div>
      <OfflineBanner />
      <main className={styles.main}>
        <Outlet />
      </main>
      <div className={styles.mobileOnly}>
        <TabBar tabs={tabs} label={t('tabs.label')} />
      </div>
    </div>
  );
}
