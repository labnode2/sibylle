// The frame of a newsroom's pages (canvas pages « Mobile » and « Ordinateur »). On a phone: the
// page itself, then four tabs at the bottom; only la une shows the newspaper's title, the other
// pages a top line of their own. On a computer: the date bar, then the large title and the
// navigation on la une, or the title in one line with the navigation on the other pages.
import { useSyncExternalStore, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { NavLink, Outlet, useMatch, useMatches, useParams } from 'react-router';

import { formatDate } from '../i18n';
import { Logo, Masthead, Rule, TabBar, type Tab } from '../ui/components';
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
  /** Right side of the desktop navigation (the newsroom's small card, to change newsroom). */
  newsroom?: ReactNode;
  /** « N° 305 »: the day of the newsroom's life, before the date. */
  issue?: number;
};

/** A route's `handle`: `bare` pages (an editor, a form with its own header) have no tabs. */
export type RouteHandle = { bare?: boolean };

export function AppShell({ account, newsroom, issue }: ShellSlots) {
  const { t } = useTranslation();
  const { orgId = '' } = useParams();
  const base = `/o/${orgId}`;
  const onUne = useMatch({ path: '/o/:orgId', end: true }) !== null;
  const bare = useMatches().some((match) => (match.handle as RouteHandle | undefined)?.bare);
  const tabs: (Tab & { long: string })[] = [
    { to: base, label: t('tabs.une'), long: t('tabs.une'), icon: 'home', end: true },
    { to: `${base}/pronos`, label: t('tabs.pronos'), long: t('tabs.pronosLong'), icon: 'ball' },
    {
      to: `${base}/redaction`,
      label: t('tabs.newsroom'),
      long: t('tabs.newsroomLong'),
      icon: 'people',
    },
    { to: `${base}/profil`, label: t('tabs.profile'), long: t('tabs.profileLong'), icon: 'user' },
  ];
  const today = formatDate(new Date(), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  }).toUpperCase();
  const nav = (
    <nav className={styles.nav} aria-label={t('tabs.label')}>
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ''}`}
        >
          <span>{tab.long}</span>
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className={`${styles.page} ${bare ? styles.pageBare : ''}`}>
      <div className="only-desktop">
        <div className={styles.infoBar}>
          <span>{issue ? t('shell.dateline', { number: issue, date: today }) : today}</span>
          <span className={styles.slot}>{account}</span>
        </div>
        {onUne ? (
          <>
            <Masthead size="large" />
            <div className={styles.navBar}>
              <span />
              {nav}
              <span className={styles.slot}>{newsroom}</span>
            </div>
          </>
        ) : (
          <>
            <div className={`${styles.navBar} ${styles.navBarCompact}`}>
              <Logo to={base} />
              {nav}
              <span className={styles.slot}>{newsroom}</span>
            </div>
            <Rule variant="double" />
          </>
        )}
      </div>
      <OfflineBanner />
      <main className={styles.main}>
        <Outlet />
      </main>
      {!bare && (
        <div className="only-mobile">
          <TabBar tabs={tabs} label={t('tabs.label')} />
        </div>
      )}
    </div>
  );
}
