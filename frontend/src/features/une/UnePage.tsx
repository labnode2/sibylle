// La une (canvas B-Accueil on a phone, B-Web-Accueil on a computer): the prono closing first,
// the other open pronos, what waits for a result (journalists), the latest results, the top of
// the ranking, the games of the week and the editor's note, in that order (FR-080).
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { ButtonLink, Card, Kicker, Laurel } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useOrg } from '../orgs/api';
import type { PronoSummary } from '../pronos/api';
import { ProposalsPanel } from '../pronos/ProposalsPanel';
import { ReactionBar } from '../pronos/ReactionBar';
import { useFrontPage, type LatestResult } from './api';
import styles from './une.module.css';

const closing = (value: string) =>
  formatDate(value, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();

function Block({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.block} aria-label={title}>
      <h2 className={styles.blockTitle}>{title}</h2>
      {children}
    </section>
  );
}

/** "CLÔTURE {day time} · {n} PRONOS · CAGNOTTE {pot}" */
function PronoLine({ prono }: { prono: PronoSummary }) {
  const { t } = useTranslation('une');
  return (
    <span className={styles.meta}>
      {[
        prono.closes_at ? t('closes', { date: closing(prono.closes_at) }) : t('openEnded'),
        t('bets', { count: prono.bet_count }),
        t('pot', { pot: formatNumber(prono.pot) }),
      ].join(' · ')}
    </span>
  );
}

function Headline({ orgId, prono }: { orgId: string; prono: PronoSummary }) {
  const { t } = useTranslation('une');
  return (
    <Card as="article" className={styles.headline} aria-label={t('headline')}>
      <Kicker tone="indigo">
        {t('headlineKicker', { section: prono.section.name.toUpperCase() })}
      </Kicker>
      <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.headlineTitle}>
        {prono.question}
      </Link>
      <PronoLine prono={prono} />
      <div className={styles.headlineFoot}>
        <ReactionBar orgId={orgId} pronoId={prono.id} />
        <ButtonLink to={`/o/${orgId}/pronos/${prono.id}`}>{t('play')}</ButtonLink>
      </div>
    </Card>
  );
}

function PronoRows({ orgId, pronos }: { orgId: string; pronos: PronoSummary[] }) {
  return (
    <ul className={styles.rows}>
      {pronos.map((prono) => (
        <li key={prono.id}>
          <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.row}>
            <span className={styles.rowTitle}>{prono.question}</span>
            <PronoLine prono={prono} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ResultRows({ orgId, results }: { orgId: string; results: LatestResult[] }) {
  const { t } = useTranslation('une');
  return (
    <ul className={styles.rows}>
      {results.map(({ prono, result, my_outcome, my_payout }) => (
        <li key={prono.id}>
          <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.row}>
            <span className={styles.rowTitle}>{prono.question}</span>
            <span className={styles.meta}>
              {t('result', { result: result ?? '—' })}
              {my_outcome === 'won' && ` · ${t('won', { payout: formatNumber(my_payout ?? 0) })}`}
              {my_outcome === 'lost' && ` · ${t('lost')}`}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export function UnePage() {
  const { t } = useTranslation('une');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const page = useFrontPage(orgId);
  if (!org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;
  const front = page.data;
  const newsroom = me.role !== 'reader';

  return (
    <div className={styles.une}>
      <div className={styles.hello}>
        <PixelImage image={me.avatar} size={48} />
        <div className={styles.helloText}>
          <Kicker tone="indigo">
            {t('orgs:une.edition', { title: org.data.title.toUpperCase() })}
          </Kicker>
          <h1 className={styles.title}>{t('orgs:une.hello', { pseudo: me.pseudo })}</h1>
          <Laurel value={me.balance} />
        </div>
      </div>

      {!front ? (
        <p role="status">{t('common:shell.loading')}</p>
      ) : (
        <div className={styles.columns}>
          <div className={styles.main}>
            {front.headline ? (
              <Headline orgId={orgId} prono={front.headline} />
            ) : (
              <Card shadow={0} className={styles.empty}>
                <p>{t('noOpen')}</p>
                <ButtonLink to={`/o/${orgId}/pronos/nouveau`} variant="secondary">
                  {t(newsroom ? 'publish' : 'propose')}
                </ButtonLink>
              </Card>
            )}
            {front.open.length > 0 && (
              <Block title={t('open')}>
                <PronoRows orgId={orgId} pronos={front.open} />
              </Block>
            )}
            {front.to_designate && front.to_designate.length > 0 && (
              <Block title={t('toDesignate')}>
                <PronoRows orgId={orgId} pronos={front.to_designate} />
              </Block>
            )}
            {newsroom && <ProposalsPanel orgId={orgId} />}
            {front.latest_results.length > 0 && (
              <Block title={t('latestResults')}>
                <ResultRows orgId={orgId} results={front.latest_results} />
              </Block>
            )}
          </div>

          <aside className={styles.side}>
            <Block title={t('leaderboard')}>
              <ol className={styles.top}>
                {front.leaderboard_top.map((row) => (
                  <li
                    key={row.member.id}
                    className={row.is_me ? styles.me : undefined}
                    aria-current={row.is_me ? 'true' : undefined}
                  >
                    <span className={styles.rank}>{row.rank}</span>
                    <PixelImage image={row.member.avatar} size={24} />
                    <span className={styles.topName}>{row.member.pseudo}</span>
                    <Laurel value={row.value} />
                  </li>
                ))}
              </ol>
              <Link to={`/o/${orgId}/classement`} className={styles.more}>
                {t('fullLeaderboard')}
              </Link>
            </Block>
            <Block title={t('games')}>
              <p className={styles.meta}>{t('gamesSoon')}</p>
            </Block>
            {front.editor_note && (
              <Block title={t('editorNote')}>
                <blockquote className={styles.note}>{front.editor_note}</blockquote>
              </Block>
            )}
          </aside>
        </div>
      )}

      <Link to="/redactions" className={styles.more}>
        {t('orgs:une.switch')}
      </Link>
    </div>
  );
}
