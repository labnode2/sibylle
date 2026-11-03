// The press card (canvas B-Profil on a phone, B-Web-Profil on a computer). The card itself, its
// ink band and number, the avatar in its frame beside the pseudo, role and arrival; three
// statistics; the balls collected. On one's own card: « Modifier mon pixel art », the newsroom,
// the preferences, the account and the collection; on a computer « Mon organisation » beside
// them. Then the engraved trophies, the other objects and the statement.
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { formatDate, formatNumber } from '../../i18n';
import { Card, Icon, TopBar } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import { FramedAvatar } from '../../ui/FramedAvatar';
import { PixelImage } from '../../ui/PixelImage';
import type { Variant } from '../../vendor/crystal-ball/crystal-ball.js';
import { useMembers } from '../admin/api';
import { ItemPreview } from '../collection/ItemPreview';
import { useOrg } from '../orgs/api';
import {
  useCatalog,
  usePressCard,
  useUpdateProfile,
  type CatalogItem,
  type PressCard,
} from './api';
import { LedgerList } from './LedgerList';
import styles from './profile.module.css';

function Stats({ card }: { card: PressCard }) {
  const { t } = useTranslation('profile');
  const { stats } = card;
  return (
    <dl className={styles.stats} aria-label={t('stats.label')}>
      <div>
        <dt>{t('stats.laurels')}</dt>
        <dd>{formatNumber(stats.laurels)}</dd>
      </div>
      <div>
        <dt>{t('stats.played')}</dt>
        <dd>{formatNumber(stats.pronos_played)}</dd>
      </div>
      <div>
        <dt>{t('stats.rate')}</dt>
        <dd>{stats.success_rate === null ? '—' : `${stats.success_rate} %`}</dd>
      </div>
    </dl>
  );
}

function Identity({
  orgId,
  org,
  card,
  mine,
}: {
  orgId: string;
  org: Org;
  card: PressCard;
  mine: boolean;
}) {
  const { t } = useTranslation('profile');
  const since = formatDate(card.joined_at, { month: 'long', year: 'numeric' }).toUpperCase();
  return (
    <Card as="section" shadow={6} className={styles.card} aria-label={t('title')}>
      <div className={styles.band}>
        <span className={styles.bandName}>{t('common:masthead.name')}</span>
        <span className={styles.bandNumber}>{t('number', { number: card.card_number })}</span>
      </div>
      <div className={styles.identity}>
        <span className="only-mobile">
          <FramedAvatar image={card.avatar} frame={card.frame} size={96} />
        </span>
        <span className="only-desktop">
          <FramedAvatar image={card.avatar} frame={card.frame} size={128} />
        </span>
        <div className={styles.identityText}>
          <h2 className={styles.pseudo}>{card.pseudo}</h2>
          <p className={styles.meta}>
            <span className={styles.role}>{t(`roles.${card.role}`)}</span> {org.title.toUpperCase()}
            <br />
            {t('since', { date: since })}
          </p>
        </div>
      </div>
      {mine && (
        <div className={styles.cardFoot}>
          <Link to={`/o/${orgId}/profil/avatar`} className={styles.editLink}>
            {t('editor.open')}
          </Link>
          <span className={styles.meta}>{t('editor.sizes')}</span>
        </div>
      )}
    </Card>
  );
}

const ballVariant = (item: CatalogItem) => String(item.data.variant) as Variant;

/** « Boules collectionnées 6 / 21 »: mine in colour, the others greyed until they are mine. */
function Balls({ orgId, card, mine }: { orgId: string; card: PressCard; mine: boolean }) {
  const { t } = useTranslation('profile');
  const catalog = useCatalog(orgId);
  const owned = card.collection.filter((o) => o.item.kind === 'ball').map((o) => o.item);
  const ownedIds = new Set(owned.map((item) => item.id));
  const all = (catalog.data ?? []).filter((entry) => entry.item.kind === 'ball').map((e) => e.item);
  // Mine first, then the others, on my own card; on someone else's, only theirs.
  const shown = mine ? [...owned, ...all.filter((item) => !ownedIds.has(item.id))] : owned;
  const total = all.length || owned.length;
  return (
    <section className={`${styles.section} ${styles.ballsSection}`} aria-labelledby="card-balls">
      <div className={styles.sectionHead}>
        <h2 id="card-balls" className={styles.intertitle}>
          {t('balls.title')}
        </h2>
        <span className={styles.label}>{t('balls.count', { owned: owned.length, total })}</span>
      </div>
      {shown.length === 0 ? (
        <p className={styles.meta}>{t('balls.none')}</p>
      ) : (
        <ul className={styles.balls}>
          {shown.map((item) => {
            const has = ownedIds.has(item.id);
            const name = t(`catalog.${item.key}`);
            return (
              <li key={item.id} className={`${styles.ball} ${has ? '' : styles.locked}`}>
                <span className="only-mobile">
                  <CrystalBall variant={ballVariant(item)} size={32} loops={0} />
                </span>
                <span className="only-desktop">
                  <CrystalBall variant={ballVariant(item)} size={48} loops={0} />
                </span>
                <span className={styles.ballName}>{t(`ballShort.${item.key}`)}</span>
                <span className="visually-hidden">{has ? name : t('balls.locked', { name })}</span>
              </li>
            );
          })}
        </ul>
      )}
      {mine && (
        <Link to={`/o/${orgId}/collection`} className={styles.more}>
          {t('balls.more')}
        </Link>
      )}
    </section>
  );
}

/** The lines under my card: the newsroom, its settings for the editor, preferences, account. */
function Lines({ orgId, org }: { orgId: string; org: Org }) {
  const { t } = useTranslation('profile');
  const editor = org.my_membership.role === 'editor';
  return (
    <nav className={styles.lines} aria-label={t('lines.label')}>
      <Link to="/redactions" className={styles.line}>
        {org.logo ? (
          <PixelImage image={org.logo} size={28} avatar={false} />
        ) : (
          <span className={styles.lineLogo} aria-hidden="true" />
        )}
        <span className={styles.lineText}>{org.title}</span>
        <span className={styles.label}>{t('lines.members', { count: org.member_count })}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
      {editor && (
        <Link to={`/o/${orgId}/reglages`} className={styles.line}>
          <span className={styles.lineText}>{t('lines.newsroomSettings')}</span>
          <Icon name="chevronRight" size={24} />
        </Link>
      )}
      <Link to={`/o/${orgId}/collection`} className={styles.line}>
        <span className={styles.lineText}>{t('collectionLink')}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
      <Link to="/compte" className={styles.line}>
        <span className={styles.lineText}>{t('lines.preferences')}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
      <Link to="/compte#settings-data" className={styles.line}>
        <span className={styles.lineText}>{t('lines.account')}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
    </nav>
  );
}

/** « Mon organisation » on a computer: the newsroom's card, its editors, and for the editor the
 *  way to its settings and its access code. */
function MyNewsroom({ orgId, org }: { orgId: string; org: Org }) {
  const { t } = useTranslation('profile');
  const members = useMembers(orgId);
  const editors = (members.data ?? []).filter((m) => m.role === 'editor').map((m) => m.pseudo);
  const editor = org.my_membership.role === 'editor';
  return (
    <section className={`only-desktop ${styles.section}`} aria-labelledby="card-newsroom">
      <h2 id="card-newsroom" className={styles.intertitle}>
        {t('newsroom.title')}
      </h2>
      <div className={styles.newsroom}>
        <div className={`${styles.newsroomBand} bg-${org.background_key}`} aria-hidden="true">
          {org.logo && (
            <span className={styles.newsroomLogo}>
              <PixelImage image={org.logo} size={64} avatar={false} />
            </span>
          )}
        </div>
        <div className={styles.newsroomBody}>
          <p className={styles.newsroomName}>{org.title}</p>
          <p className={styles.label}>
            {t('lines.members', { count: org.member_count })}
            {editors.length > 0 &&
              ` · ${t('newsroom.editors', { names: editors.join(', ').toUpperCase() })}`}
          </p>
        </div>
        {editor && (
          <>
            <div className={styles.newsroomRow}>
              <span className={styles.newsroomRowText}>
                <span className={styles.newsroomRowTitle}>{t('newsroom.invite')}</span>
                <span className={styles.label}>{t('newsroom.inviteHint')}</span>
              </span>
              <Link to={`/o/${orgId}/reglages/membres`} className={styles.newsroomButton}>
                {t('newsroom.inviteOpen')}
              </Link>
            </div>
            {org.access_code && (
              <div className={styles.newsroomRow}>
                <span className={styles.newsroomRowText}>
                  <span className={styles.newsroomRowTitle}>{t('newsroom.code')}</span>
                  <span className={styles.label}>{t('newsroom.codeHint')}</span>
                </span>
                <span className={styles.code}>{org.access_code}</span>
              </div>
            )}
            <Link to={`/o/${orgId}/reglages`} className={styles.newsroomSettings}>
              {t('lines.newsroomSettings')} →
            </Link>
          </>
        )}
      </div>
    </section>
  );
}

function FrameChoice({ orgId, card }: { orgId: string; card: PressCard }) {
  const { t } = useTranslation('profile');
  const update = useUpdateProfile(orgId);
  const frames = card.collection.filter((owned) => owned.item.kind === 'frame');
  if (frames.length === 0) return null;
  const current = frames.find((owned) => owned.item.key === card.frame)?.item.id ?? '';
  return (
    <label className={styles.frameChoice}>
      <span className={styles.label}>{t('frame.label')}</span>
      <select
        value={current}
        disabled={update.isPending}
        onChange={(event) => update.mutate({ avatar_frame_item_id: event.target.value || null })}
      >
        <option value="">{t('frame.none')}</option>
        {frames.map((owned) => (
          <option key={owned.item.id} value={owned.item.id}>
            {t(`catalog.${owned.item.key}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function PressCardPage() {
  const { t } = useTranslation('profile');
  const { orgId = '', memberId } = useParams();
  const org = useOrg(orgId);
  const me = org.data?.my_membership;
  const id = memberId ?? me?.id;
  const card = usePressCard(orgId, id);
  if (!card.data || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const data = card.data;
  const mine = data.id === me?.id;
  const others = data.collection.filter((owned) => owned.item.kind !== 'ball');

  return (
    <div className={styles.page}>
      {mine ? (
        <header className={styles.header}>
          <h1 className={styles.headerTitle}>{t('profile')}</h1>
          <Link
            to="/compte"
            className={`only-mobile ${styles.gear}`}
            aria-label={t('settingsLink')}
          >
            <Icon name="gear" size={24} />
          </Link>
        </header>
      ) : (
        <>
          <TopBar back={`/o/${orgId}/classement`} backLabel={t('backRanking')} />
          <h1 className="visually-hidden">{t('titleOf', { pseudo: data.pseudo })}</h1>
        </>
      )}

      <div className={styles.columns}>
        <div className={styles.left}>
          <Identity orgId={orgId} org={org.data} card={data} mine={mine} />
          <Stats card={data} />
          {mine && <Lines orgId={orgId} org={org.data} />}
          {mine && <FrameChoice orgId={orgId} card={data} />}
        </div>

        <div className={styles.right}>
          <Balls orgId={orgId} card={data} mine={mine} />
          {mine && <MyNewsroom orgId={orgId} org={org.data} />}

          <div className={styles.tail}>
            <section className={styles.section} aria-labelledby="card-trophies">
              <h2 id="card-trophies" className={styles.intertitle}>
                {t('trophies.title')}
              </h2>
              {data.trophies.length === 0 ? (
                <p className={styles.meta}>{t('trophies.none')}</p>
              ) : (
                <ul className={styles.items}>
                  {data.trophies.map((trophy) => (
                    <li
                      key={`${trophy.season.year}-${trophy.season.name}`}
                      className={`${styles.trophy} ${trophy.podium ? styles.podium : ''}`}
                    >
                      <CrystalBall variant={trophy.season.name as Variant} size={48} />
                      <span className={styles.engraved}>
                        {t('trophies.season', {
                          season: t(`seasons.${trophy.season.name}`),
                          year: trophy.season.year,
                        })}
                      </span>
                      <span className={styles.meta}>
                        {t('trophies.score', {
                          score: formatNumber(trophy.score),
                          rank: trophy.rank,
                        })}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            {others.length > 0 && (
              <section className={styles.section} aria-labelledby="card-collection">
                <h2 id="card-collection" className={styles.intertitle}>
                  {t('objects.title')}
                </h2>
                <ul className={styles.items}>
                  {others.map((owned) => (
                    <li key={owned.item.id} className={styles.item}>
                      <ItemPreview item={owned.item} avatar={data.avatar} />
                      <span className={styles.meta}>{t(`catalog.${owned.item.key}`)}</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {mine && <LedgerList orgId={orgId} />}
          </div>
        </div>
      </div>
    </div>
  );
}
