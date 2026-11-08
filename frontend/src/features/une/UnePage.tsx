// La une (canvas B-Accueil on a phone, B-Web-Accueil on a computer). On a phone: the number and
// date of the edition with my laurels, the newspaper's title, the edition and its readers, then
// the prono closing first with its gauge, a brief beside the games, the month's ranking and the
// other briefs. On a computer the title and the navigation come from the frame; the prono runs
// large beside the ranking and the games, and « En bref » closes the page. The blocks keep the
// spec's order (FR-080): pronos, what waits for a result (journalists), results, ranking, games,
// the editor's note. A week without a game (US12) has no games block at all.
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { formatDate, formatNumber } from '../../i18n';
import {
  ButtonLink,
  Card,
  Kicker,
  KeyPhrase,
  Laurel,
  Masthead,
  SectionHead,
  Wallet,
} from '../../ui/components';
import { Streak } from '../../ui/Flame';
import { PixelImage } from '../../ui/PixelImage';
import { useGames } from '../games/api';
import { WeeklyGames } from '../games/WeeklyGames';
import { NewsroomSwitcher } from '../orgs/NewsroomPage';
import { useOrg } from '../orgs/api';
import type { PronoSummary } from '../pronos/api';
import { ProposalsPanel } from '../pronos/ProposalsPanel';
import { useFrontPage, type FrontPage, type FrontProno, type LatestResult } from './api';
import styles from './une.module.css';

// On a phone, the ranking stops at the third line (and mine).
const PHONE_TOP = 3;

const closing = (value: string) =>
  formatDate(value, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();

/** The answers and their shares, the favourite first: options, or the split of the values. */
function shares(prono: FrontProno): { label: string; pct: number }[] {
  const rows = prono.options.length
    ? prono.options.map((o) => ({ label: o.label, pct: o.share_pct }))
    : prono.distribution.map((b) => ({ label: b.label, pct: b.share_pct }));
  return rows;
}

/** "CLÔTURE {day time} · {n} PRONOS · CAGNOTTE {pot} · {n} MESSAGES" (messages once there are). */
function PronoLine({ prono, gain = false }: { prono: PronoSummary; gain?: boolean }) {
  const { t } = useTranslation('une');
  return (
    <p className={styles.meta}>
      {[
        prono.closes_at ? t('closes', { date: closing(prono.closes_at) }) : t('openEnded'),
        t('bets', { count: prono.bet_count }),
        t('pot', { pot: formatNumber(prono.pot) }),
        prono.message_count > 0 && t('messages', { count: prono.message_count }),
      ]
        .filter(Boolean)
        .join(' · ')}
      {gain && <span className="only-desktop">{` · ${t('gain', { gain: prono.base_gain })}`}</span>}
    </p>
  );
}

/** The gauge of la une: the favourite in ink, the others in indigo and mist (canvas G-Style). */
function Poll({ prono }: { prono: FrontProno }) {
  const { t } = useTranslation('une');
  const rows = shares(prono);
  if (prono.bet_count === 0 || rows.length === 0) return null;
  const top = Math.max(...rows.map((r) => r.pct));
  let other = 0;
  const label = t('poll', { split: rows.map((r) => `${r.label} ${r.pct} %`).join(', ') });
  return (
    <div className={styles.poll} role="img" aria-label={label}>
      {rows.map((row) => {
        const tone =
          row.pct === top ? styles.fillInk : other++ % 2 ? styles.fillIndigo : styles.fillMist;
        return (
          <div key={row.label} className={styles.pollRow} aria-hidden="true">
            <span className={styles.pollLabel}>{row.label}</span>
            <span className={styles.rail}>
              <span className={`${styles.fill} ${tone}`} style={{ width: `${row.pct}%` }} />
            </span>
            <span className={styles.pollPct}>{row.pct} %</span>
          </div>
        );
      })}
    </div>
  );
}

function Headline({ orgId, front }: { orgId: string; front: FrontPage }) {
  const { t } = useTranslation('une');
  const prono = front.headline!;
  const to = `/o/${orgId}/pronos/${prono.id}`;
  const deck =
    (prono.closes_at
      ? t('deckClose', {
          date: formatDate(prono.closes_at, {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            hour: '2-digit',
            minute: '2-digit',
          }),
        })
      : t('deckOpenEnded')) +
    ' ' +
    (prono.bet_count === 0 ? t('deckNobody') : t('deckCount', { count: prono.bet_count }));
  return (
    <article className={styles.lead} aria-label={t('headline')}>
      <Kicker tone="indigo">
        {t('headlineKicker', {
          section: prono.section.name.toUpperCase(),
          author: prono.created_by.pseudo.toUpperCase(),
        })}
      </Kicker>
      <h2 id="une-headline" className={styles.leadTitle}>
        <Link to={to} state={{ from: 'une' }}>
          <KeyPhrase text={prono.question} />
        </Link>
      </h2>
      <p className={`only-desktop ${styles.deck}`}>{deck}</p>
      <Poll prono={prono} />
      <PronoLine prono={prono} gain />
      <div className={styles.leadActions}>
        <ButtonLink to={to} state={{ from: 'une' }} className={styles.play}>
          {t('play')}
        </ButtonLink>
        <Link to={`/o/${orgId}/pronos`} className={styles.allOpen}>
          {front.open_count > 1 ? t('allOpen', { count: front.open_count }) : t('allPronos')}
        </Link>
      </div>
    </article>
  );
}

/** "NON 72 % · JEU. 9:00": the favourite answer, then the closing. */
function briefTag(t: TFunction<'une'>, prono: FrontProno): string {
  const rows = shares(prono);
  const favourite = rows.reduce<{ label: string; pct: number } | null>(
    (best, row) => (!best || row.pct > best.pct ? row : best),
    null,
  );
  return [
    prono.bet_count > 0 && favourite ? `${favourite.label.toUpperCase()} ${favourite.pct} %` : null,
    prono.closes_at ? t('closes', { date: closing(prono.closes_at) }) : t('openEnded'),
  ]
    .filter(Boolean)
    .join(' · ');
}

function Brief({ orgId, prono }: { orgId: string; prono: FrontProno }) {
  const { t } = useTranslation('une');
  return (
    <Link to={`/o/${orgId}/pronos/${prono.id}`} state={{ from: 'une' }} className={styles.brief}>
      <span className={styles.briefKicker}>{prono.section.name.toUpperCase()}</span>
      <span className={styles.briefTitle}>{prono.question}</span>
      <span className={styles.tag}>{briefTag(t, prono)}</span>
    </Link>
  );
}

function ResultBrief({ orgId, latest }: { orgId: string; latest: LatestResult }) {
  const { t } = useTranslation('une');
  const { prono, result, my_outcome, my_payout } = latest;
  const won = my_outcome === 'won';
  return (
    <Link to={`/o/${orgId}/pronos/${prono.id}`} state={{ from: 'une' }} className={styles.brief}>
      <span className={styles.briefKicker}>
        {t('resultKicker', { section: prono.section.name.toUpperCase() })}
      </span>
      <span className={styles.briefTitle}>{prono.question}</span>
      <span className={`${styles.tag} ${won ? styles.tagWon : ''}`}>
        {[
          t('result', { result: result ?? '—' }),
          won ? t('won', { payout: formatNumber(my_payout ?? 0) }) : null,
          my_outcome === 'lost' ? t('lost') : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </span>
    </Link>
  );
}

function Ranking({ orgId, front }: { orgId: string; front: FrontPage }) {
  const { t } = useTranslation('une');
  // "2026-autumn" → "SAISON D'AUTOMNE 2026".
  const [year, name] = front.leaderboard_period.split('-');
  return (
    <section className={styles.ranking} aria-labelledby="une-ranking">
      <SectionHead
        id="une-ranking"
        title={t('leaderboard')}
        meta={t('leaderboard:seasonTitle', {
          season: t(`leaderboard:season.${name}`),
          year,
        }).toUpperCase()}
      />
      <ol className={styles.top}>
        {front.leaderboard_top.map((row, index) => (
          <li
            key={row.member.id}
            className={[
              row.is_me ? styles.me : '',
              index >= PHONE_TOP && !row.is_me ? styles.computerOnly : '',
            ].join(' ')}
            aria-current={row.is_me ? 'true' : undefined}
          >
            <span className={styles.rank}>{row.rank}</span>
            <PixelImage image={row.member.avatar} size={28} />
            <Link to={`/o/${orgId}/membres/${row.member.id}`} className={styles.topName}>
              {row.is_me ? t('you', { pseudo: row.member.pseudo }) : row.member.pseudo}
            </Link>
            <Streak value={row.streak} />
            <span className={styles.topValue}>
              <Laurel value={row.value} />
            </span>
          </li>
        ))}
      </ol>
      <Link to={`/o/${orgId}/classement`} className={styles.more}>
        {t('fullLeaderboard')}
      </Link>
    </section>
  );
}

/** « N° 305 · DIM. 1 NOV. 2026 », then my laurels: the phone's top line. */
function Dateline({ org }: { org: Org }) {
  const { t } = useTranslation('une');
  const me = org.my_membership;
  const today = formatDate(new Date(), {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).toUpperCase();
  return (
    <div className={`only-mobile ${styles.dateline}`}>
      <span>{t('common:shell.dateline', { number: org.edition_number, date: today })}</span>
      <span className={styles.mine}>
        <Wallet balance={me.balance} gold={me.gold} coins={me.coins} />
      </span>
    </div>
  );
}

export function UnePage() {
  const { t } = useTranslation('une');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const page = useFrontPage(orgId);
  const games = useGames(orgId);
  if (!org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;
  const front = page.data;
  const newsroom = me.role !== 'reader';
  const [first, ...others] = front?.open ?? [];
  // The games' place stays while they load; it goes once the week turns out to have none.
  const hasGames = !games.data || games.data.scheduled.length > 0;

  return (
    <div className={styles.une}>
      <h1 className="visually-hidden">{t('title', { org: org.data.title })}</h1>
      <Dateline org={org.data} />
      <div className="only-mobile">
        <Masthead size="compact" />
      </div>
      <div className={`only-mobile ${styles.editionBar}`}>
        <NewsroomSwitcher org={org.data} align="start" />
      </div>

      {!front ? (
        <p role="status">{t('common:shell.loading')}</p>
      ) : (
        <>
          <div className={styles.columns}>
            <div className={styles.main}>
              {front.headline ? (
                <Headline orgId={orgId} front={front} />
              ) : (
                <Card shadow={0} className={styles.empty}>
                  <p>{t('noOpen')}</p>
                  <ButtonLink to={`/o/${orgId}/pronos/nouveau`} variant="secondary">
                    {t(newsroom ? 'publish' : 'propose')}
                  </ButtonLink>
                </Card>
              )}

              {/* On a phone, the next prono beside the games. */}
              {(first || hasGames) && (
                <div
                  className={`only-mobile ${styles.pair} ${first && hasGames ? '' : styles.pairAlone}`}
                >
                  {first && (
                    <div className={styles.pairBrief}>
                      <Brief orgId={orgId} prono={first} />
                    </div>
                  )}
                  {hasGames && (
                    <section className={styles.pairGames} aria-label={t('games')}>
                      <span className={styles.briefKicker}>{t('games').toUpperCase()}</span>
                      <WeeklyGames orgId={orgId} size={32} />
                    </section>
                  )}
                </div>
              )}

              {front.to_designate && front.to_designate.length > 0 && (
                <section className={styles.block} aria-labelledby="une-designate">
                  <SectionHead
                    id="une-designate"
                    title={t('toDesignate')}
                    meta={String(front.to_designate.length)}
                  />
                  <ul className={styles.rows}>
                    {front.to_designate.map((prono) => (
                      <li key={prono.id}>
                        <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.row}>
                          <span className={styles.rowTitle}>{prono.question}</span>
                          <PronoLine prono={prono} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {newsroom && <ProposalsPanel orgId={orgId} />}
            </div>

            <aside className={styles.side} aria-label={t('aside')}>
              <Ranking orgId={orgId} front={front} />
              {hasGames && (
                <Card
                  as="section"
                  className={`only-desktop ${styles.gamesBox}`}
                  aria-label={t('games')}
                >
                  <span className={styles.briefKicker}>{t('games').toUpperCase()}</span>
                  <WeeklyGames orgId={orgId} size={48} />
                </Card>
              )}
              {front.editor_note && (
                <section className={styles.block} aria-labelledby="une-note">
                  <SectionHead id="une-note" title={t('editorNote')} />
                  <blockquote className={styles.note}>{front.editor_note}</blockquote>
                </section>
              )}
            </aside>
          </div>

          {(others.length > 0 || front.latest_results.length > 0 || first) && (
            <section
              className={`${styles.briefs} ${others.length || front.latest_results.length ? '' : 'only-desktop'}`}
              aria-labelledby="une-briefs"
            >
              <h2 id="une-briefs" className={styles.briefsTitle}>
                {t('briefs')}
              </h2>
              <div className={styles.briefGrid}>
                {first && (
                  <div className="only-desktop">
                    <Brief orgId={orgId} prono={first} />
                  </div>
                )}
                {others.map((prono) => (
                  <Brief key={prono.id} orgId={orgId} prono={prono} />
                ))}
                {front.latest_results.map((latest) => (
                  <ResultBrief key={latest.prono.id} orgId={orgId} latest={latest} />
                ))}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
