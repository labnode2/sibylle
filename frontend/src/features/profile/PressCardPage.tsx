// The press card (canvas B-Profil on a phone, B-Web-Profil on a computer), as every member of
// the newsroom sees it: the ink band and number, the avatar in its frame beside the pseudo and
// its chain of wins, the role, arrival and record of wins, the three things the member chose to
// show; three statistics in green laurels; the balls collected (an engraved ball per season
// played, the others from secret codes). On one's own card: « Personnaliser ma carte », the
// public profile, the collection, settings and sign-out; then the other objects and the
// statement. The newsroom has a tab of its own, « La rédaction ».
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Card, Icon, Laurel, TopBar } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import { Streak, STREAK_SHOWN_FROM } from '../../ui/Flame';
import { FramedAvatar } from '../../ui/FramedAvatar';
import type { Variant } from '../../vendor/crystal-ball/crystal-ball.js';
import { useLogoutConfirm } from '../auth/LogoutDialog';
import { ItemPreview } from '../collection/ItemPreview';
import { useOrg } from '../orgs/api';
import { usePressCard, type CardFace, type PressCard } from './api';
import { LedgerList } from './LedgerList';
import styles from './profile.module.css';
import { PublicCardSetting } from './PublicCardSetting';

type Trophy = PressCard['trophies'][number];

function useTrophyName() {
  const { t } = useTranslation('profile');
  return (trophy: Trophy) =>
    t('trophies.season', { season: t(`seasons.${trophy.season.name}`), year: trophy.season.year });
}

export function Stats({ stats }: { stats: PressCard['stats'] }) {
  const { t } = useTranslation('profile');
  return (
    <dl className={styles.stats} aria-label={t('stats.label')}>
      <div>
        <dt>{t('stats.laurels')}</dt>
        <dd className={styles.statLaurels}>
          {formatNumber(stats.laurels)} <Laurel size={32} />
        </dd>
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

/** « Mis en avant »: up to three objects or engraved trophies, chosen by the member. */
function Showcase({ card }: { card: CardFace }) {
  const { t } = useTranslation('profile');
  const trophyName = useTrophyName();
  if (card.showcase.length === 0) return null;
  return (
    <div className={styles.showcase}>
      <span className={styles.label}>{t('showcase.title')}</span>
      <ul className={styles.showcaseList} aria-label={t('showcase.title')}>
        {card.showcase.map((entry, index) => (
          <li
            key={entry.trophy?.id ?? entry.item?.id ?? index}
            className={`${styles.showcaseItem} ${entry.trophy?.podium ? styles.podium : ''}`}
          >
            {entry.trophy ? (
              <CrystalBall variant={entry.trophy.season.name as Variant} size={48} loops={0} />
            ) : (
              entry.item && <ItemPreview item={entry.item} avatar={card.avatar} size={48} />
            )}
            <span className={styles.showcaseName}>
              {entry.trophy
                ? trophyName(entry.trophy)
                : entry.item && t(`catalog.${entry.item.key}`)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The card itself; « Personnaliser ma carte » shows it as it goes, and the public card (US15)
 *  as anyone sees it. Only one's own card has `editTo`, the way to customise it. */
export function Identity({
  card,
  orgTitle,
  editTo,
}: {
  card: CardFace;
  orgTitle: string;
  editTo?: string;
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
          <div className={styles.pseudoLine}>
            <h2 className={styles.pseudo}>{card.pseudo}</h2>
            <Streak value={card.stats.streak} size={16} className={styles.pseudoStreak} />
          </div>
          <p className={styles.meta}>
            <span className={styles.role}>{t(`roles.${card.role}`)}</span> {orgTitle.toUpperCase()}
            <br />
            {t('since', { date: since })}
            {card.stats.best_streak >= STREAK_SHOWN_FROM && (
              <>
                <br />
                {t('record', { count: card.stats.best_streak })}
              </>
            )}
          </p>
        </div>
      </div>
      <Showcase card={card} />
      {editTo && (
        <div className={styles.cardFoot}>
          <Link to={editTo} className={styles.editLink}>
            {t('customize.open')}
          </Link>
        </div>
      )}
    </Card>
  );
}

/** « Boules collectionnées »: an engraved ball for each season played (the podium's framed in
 *  gold), then the balls of the secret codes. They are not sold. */
function Balls({ card, mine }: { card: PressCard; mine: boolean }) {
  const { t } = useTranslation('profile');
  const trophyName = useTrophyName();
  const balls = [
    ...card.trophies.map((trophy) => ({
      key: trophy.id,
      variant: trophy.season.name as Variant,
      short: trophyName(trophy),
      name: `${trophyName(trophy)} · ${t('trophies.score', {
        score: formatNumber(trophy.score),
        rank: trophy.rank,
      })}`,
      podium: trophy.podium,
    })),
    ...card.collection
      .filter((owned) => owned.item.kind === 'ball')
      .map((owned) => ({
        key: owned.item.id,
        variant: String(owned.item.data.variant) as Variant,
        short: t(`ballShort.${owned.item.key}`),
        name: t(`catalog.${owned.item.key}`),
        podium: false,
      })),
  ];
  return (
    <section className={`${styles.section} ${styles.ballsSection}`} aria-labelledby="card-balls">
      <div className={styles.sectionHead}>
        <h2 id="card-balls" className={styles.intertitle}>
          {t('balls.title')}
        </h2>
        <span className={styles.label}>{formatNumber(balls.length)}</span>
      </div>
      {balls.length === 0 ? (
        <p className={styles.meta}>{t('balls.none')}</p>
      ) : (
        <ul className={styles.balls}>
          {balls.map((ball) => (
            <li key={ball.key} className={`${styles.ball} ${ball.podium ? styles.podium : ''}`}>
              <span className="only-mobile">
                <CrystalBall variant={ball.variant} size={32} loops={0} />
              </span>
              <span className="only-desktop">
                <CrystalBall variant={ball.variant} size={48} loops={0} />
              </span>
              <span className={styles.ballName} aria-hidden="true">
                {ball.short}
              </span>
              <span className="visually-hidden">{ball.name}</span>
            </li>
          ))}
        </ul>
      )}
      {mine && balls.length > 0 && <p className={styles.meta}>{t('balls.how')}</p>}
    </section>
  );
}

/** The lines under my card: « Ma collection », « Réglages » (which lead back here), then
 *  « Déconnexion », which asks first. */
function Lines({ orgId }: { orgId: string }) {
  const { t } = useTranslation('profile');
  const { pathname } = useLocation();
  const logout = useLogoutConfirm();
  return (
    <nav className={styles.lines} aria-label={t('lines.label')}>
      <Link to={`/o/${orgId}/collection`} className={styles.line}>
        <span className={styles.lineText}>{t('collectionLink')}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
      <Link to="/compte" state={{ from: pathname }} className={styles.line}>
        <span className={styles.lineText}>{t('lines.settings')}</span>
        <Icon name="chevronRight" size={24} />
      </Link>
      <button type="button" className={`${styles.line} ${styles.lineButton}`} onClick={logout.ask}>
        <span className={styles.lineText}>{t('lines.logout')}</span>
      </button>
      {logout.element}
    </nav>
  );
}

export function PressCardPage() {
  const { t } = useTranslation('profile');
  const { orgId = '', memberId } = useParams();
  const { pathname } = useLocation();
  const org = useOrg(orgId);
  const me = org.data?.my_membership;
  const id = memberId ?? me?.id;
  const card = usePressCard(orgId, id);
  if (!card.data || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const data = card.data;
  const mine = data.id === me?.id;
  const objects = data.collection.filter((owned) => owned.item.kind !== 'ball');

  return (
    <div className={styles.page}>
      {mine ? (
        <header className={styles.header}>
          <h1 className={styles.headerTitle}>{t('profile')}</h1>
          <Link
            to="/compte"
            state={{ from: pathname }}
            className={`only-mobile ${styles.gear}`}
            aria-label={t('settingsLink')}
          >
            <Icon name="gear" size={24} />
          </Link>
        </header>
      ) : (
        <>
          <TopBar back={`/o/${orgId}/redaction`} backLabel={t('backNewsroom')} />
          <h1 className="visually-hidden">{t('titleOf', { pseudo: data.pseudo })}</h1>
        </>
      )}

      <div className={styles.columns}>
        <div className={styles.left}>
          <Identity
            card={data}
            orgTitle={org.data.title}
            editTo={mine ? `/o/${orgId}/profil/carte` : undefined}
          />
          <Stats stats={data.stats} />
          {mine && me && <PublicCardSetting orgId={orgId} orgTitle={org.data.title} member={me} />}
          {mine && <Lines orgId={orgId} />}
        </div>

        <div className={styles.right}>
          <Balls card={data} mine={mine} />

          <div className={styles.tail}>
            {objects.length > 0 && (
              <section className={styles.section} aria-labelledby="card-collection">
                <h2 id="card-collection" className={styles.intertitle}>
                  {t('objects.title')}
                </h2>
                <ul className={styles.items}>
                  {objects.map((owned) => (
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
