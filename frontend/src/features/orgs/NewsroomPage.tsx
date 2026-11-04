// « La rédaction », a tab of the newsroom (FR-097): the newsroom's card with its members and
// editors, and for the editor the invitations, the access code and the settings; then every
// member with their role, the editors first, each line opening their press card. The newsroom's
// small card, in the navigation on a computer and on la une on a phone, opens the newsroom list.
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { Chip, Icon } from '../../ui/components';
import { FramedAvatar } from '../../ui/FramedAvatar';
import { PixelImage } from '../../ui/PixelImage';
import { useMembers, type Role } from '../admin/api';
import { useOrg } from './api';
import styles from './newsroom.module.css';

const ORDER: Record<Role, number> = { editor: 0, journalist: 1, reader: 2 };
const CHIP = { editor: 'ink', journalist: 'grey', reader: 'outline' } as const;

/** The newsroom's logo; until the editor gives it one, its initial in the masthead's letters. */
function OrgLogo({ org, size }: { org: Org; size: 24 | 64 }) {
  if (org.logo) return <PixelImage image={org.logo} size={size} avatar={false} />;
  return (
    <span className={`${styles.initial} ${size === 64 ? styles.initialLarge : ''}`}>
      {org.title.trim().charAt(0).toUpperCase()}
    </span>
  );
}

/** The newsroom's small card: its band and logo, its name and members; it opens the newsroom
 *  list, to change newsroom. */
export function NewsroomCardLink({ org }: { org: Org }) {
  const { t } = useTranslation('orgs');
  return (
    <Link to="/redactions" className={styles.cardLink}>
      <span className={`${styles.cardLinkBand} bg-${org.background_key}`} aria-hidden="true">
        <OrgLogo org={org} size={24} />
      </span>
      <span className={styles.cardLinkText}>
        <span className={styles.cardLinkName}>{org.title}</span>
        <span className={styles.label}>{t('newsroom.count', { count: org.member_count })}</span>
      </span>
      <span className={styles.cardLinkMore}>
        <Icon name="chevronDown" />
        <span className="visually-hidden">{t('une.switch')}</span>
      </span>
    </Link>
  );
}

/** The newsroom's card, then for the editor the ways in and the settings. */
function OrgCard({ org, editors }: { org: Org; editors: string[] }) {
  const { t } = useTranslation('orgs');
  const base = `/o/${org.id}`;
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
      {org.my_membership.role === 'editor' && (
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
            <span aria-hidden="true"> →</span>
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
              <FramedAvatar image={member.avatar} frame={member.frame ?? null} size={32} />
              <Link to={`/o/${orgId}/membres/${member.id}`} className={styles.member}>
                {member.id === me ? t('newsroom.you', { pseudo: member.pseudo }) : member.pseudo}
              </Link>
              <Chip variant={CHIP[member.role]}>{t(`profile:roles.${member.role}`)}</Chip>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
