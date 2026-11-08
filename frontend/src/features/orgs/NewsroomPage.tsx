// « La rédaction », a tab of the newsroom (FR-097): the newsroom's card with its members and
// editors, and for the editor the invitations, the access code and the settings; then every
// member with their role and their chain of wins, the editors first, each line opening their
// press card. The newsroom's small card, in the navigation on a computer and on la une on a
// phone, opens a menu where it is: the account's newsrooms, then « Rejoindre ou créer une
// rédaction ».
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { Button, Chip, CountBadge, Icon } from '../../ui/components';
import { Streak } from '../../ui/Flame';
import { FramedAvatar } from '../../ui/FramedAvatar';
import { PixelImage } from '../../ui/PixelImage';
import { useMembers, useReports, type Role } from '../admin/api';
import { useMe } from '../auth/api';
import { WelcomeDialog } from '../welcome/WelcomeDialog';
import { useOrg } from './api';
import styles from './newsroom.module.css';

const ORDER: Record<Role, number> = { editor: 0, journalist: 1, reader: 2 };
const CHIP = { editor: 'ink', journalist: 'grey', reader: 'outline' } as const;

/** The newsroom's logo: the default one until the editor chooses or draws another. */
export function OrgLogo({ org, size }: { org: Pick<Org, 'logo'>; size: 24 | 64 }) {
  return <PixelImage image={org.logo} size={size} avatar={false} />;
}

/** The newsroom's small card: its band and logo, its name and members. It opens a menu below
 *  it: the account's newsrooms, the current one marked, then « Rejoindre ou créer une
 *  rédaction ». Escape, a click elsewhere or a choice closes it. `align` is the side the menu
 *  keeps: the card's right edge in the navigation, its left edge on la une of a phone. */
export function NewsroomSwitcher({ org, align = 'end' }: { org: Org; align?: 'start' | 'end' }) {
  const { t } = useTranslation('orgs');
  const me = useMe();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const memberships = me.data?.memberships ?? [];
  // The open pronos without my bet in my other newsrooms: la une already lists this one's.
  const elsewhere = memberships
    .filter((entry) => entry.org.id !== org.id)
    .reduce((sum, entry) => sum + entry.unanswered, 0);

  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  const close = () => setOpen(false);
  return (
    <div ref={box} className={styles.switcher}>
      <button
        ref={button}
        type="button"
        className={styles.cardLink}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((value) => !value)}
      >
        <span className={`${styles.cardLinkBand} bg-${org.background_key}`} aria-hidden="true">
          <OrgLogo org={org} size={24} />
        </span>
        <span className={styles.cardLinkText}>
          <span className={styles.cardLinkName}>{org.title}</span>
          <span className={styles.label}>{t('newsroom.count', { count: org.member_count })}</span>
        </span>
        <span className={styles.cardLinkMore}>
          <CountBadge
            count={elsewhere}
            label={t('unansweredElsewhere', { count: elsewhere })}
            className={styles.cardLinkBadge}
          />
          <Icon name="chevronDown" />
          <span className="visually-hidden">{t('une.switch')}</span>
        </span>
      </button>
      {open && (
        <div id={menuId} className={`${styles.menu} ${align === 'start' ? styles.menuStart : ''}`}>
          <ul className={styles.menuList} aria-label={t('switcher.title')}>
            {memberships.map(({ org: other, unanswered }) => (
              <li key={other.id}>
                <Link
                  to={`/o/${other.id}`}
                  className={styles.menuItem}
                  aria-current={other.id === org.id ? 'true' : undefined}
                  onClick={close}
                >
                  <span
                    className={`${styles.menuBand} bg-${other.background_key}`}
                    aria-hidden="true"
                  >
                    <OrgLogo org={other} size={24} />
                  </span>
                  <span className={styles.menuName}>{other.title}</span>
                  <CountBadge count={unanswered} label={t('unanswered', { count: unanswered })} />
                  {other.id === org.id && <Icon name="check" />}
                </Link>
              </li>
            ))}
          </ul>
          <Link to="/bienvenue" className={styles.menuMore} onClick={close}>
            <Icon name="plus" />
            {t('switcher.more')}
          </Link>
        </div>
      )}
    </div>
  );
}

/** The newsroom's card, then for the editor the ways in and the settings. */
function OrgCard({ org, editors }: { org: Org; editors: string[] }) {
  const { t } = useTranslation('orgs');
  const base = `/o/${org.id}`;
  const editor = org.my_membership.role === 'editor';
  const reports = useReports(org.id, editor).data?.length ?? 0;
  return (
    <div className={styles.card}>
      <div className={`${styles.band} bg-${org.background_key}`} aria-hidden="true">
        <span className={styles.logo}>
          <OrgLogo org={org} size={64} />
        </span>
      </div>
      <div className={styles.body}>
        <p className={styles.name}>{org.title}</p>
        <p className={styles.label}>
          {t('newsroom.count', { count: org.member_count })}
          {editors.length > 0 &&
            ` · ${t('newsroom.editors', { names: editors.join(', ').toUpperCase() })}`}
        </p>
      </div>
      {editor && (
        <>
          <div className={styles.row}>
            <span className={styles.rowText}>
              <span className={styles.rowTitle}>{t('newsroom.invite')}</span>
              <span className={styles.label}>{t('newsroom.inviteHint')}</span>
            </span>
            <Link to={`${base}/reglages/membres`} className={styles.button}>
              {t('newsroom.inviteOpen')}
            </Link>
          </div>
          {org.access_code && (
            <div className={styles.row}>
              <span className={styles.rowText}>
                <span className={styles.rowTitle}>{t('newsroom.code')}</span>
                <span className={styles.label}>{t('newsroom.codeHint')}</span>
              </span>
              <span className={styles.code}>{org.access_code}</span>
            </div>
          )}
          <Link to={`${base}/reglages`} className={styles.settings}>
            {t('newsroom.settings')}
            <CountBadge count={reports} label={t('common:tabs.reports', { count: reports })} />
          </Link>
        </>
      )}
    </div>
  );
}

export function NewsroomPage() {
  const { t } = useTranslation('orgs');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const members = useMembers(orgId);
  const [replay, setReplay] = useState(false);
  if (!org.data || !members.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership.id;
  const sorted = [...members.data].sort(
    (a, b) => ORDER[a.role] - ORDER[b.role] || a.pseudo.localeCompare(b.pseudo, 'fr'),
  );
  const editors = sorted.filter((member) => member.role === 'editor').map((m) => m.pseudo);

  return (
    <div className={styles.page}>
      <section className={styles.section} aria-labelledby="newsroom-title">
        <h1 id="newsroom-title" className={styles.title}>
          {t('newsroom.title')}
        </h1>
        <OrgCard org={org.data} editors={editors} />
      </section>

      <section className={styles.section} aria-labelledby="newsroom-members">
        <div className={styles.sectionHead}>
          <h2 id="newsroom-members" className={styles.intertitle}>
            {t('newsroom.members')}
          </h2>
          <span className={styles.label}>{t('newsroom.count', { count: sorted.length })}</span>
        </div>
        <ul className={styles.directory}>
          {sorted.map((member) => (
            <li key={member.id} className={styles.line}>
              <FramedAvatar
                image={member.avatar}
                frame={member.frame ?? null}
                animation={member.animation ?? null}
                size={32}
              />
              <Link to={`/o/${orgId}/membres/${member.id}`} className={styles.member}>
                {member.id === me ? t('newsroom.you', { pseudo: member.pseudo }) : member.pseudo}
              </Link>
              <Streak value={member.streak} />
              <span className={styles.role}>
                <Chip variant={CHIP[member.role]}>{t(`profile:roles.${member.role}`)}</Chip>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <Button variant="link" onClick={() => setReplay(true)}>
        {t('welcome:replay')}
      </Button>
      {replay && (
        <WelcomeDialog
          org={org.data.title}
          role={org.data.my_membership.role}
          onClose={() => setReplay(false)}
        />
      )}
    </div>
  );
}
