// The ball's race: the game, the attempts left and the week's ranking, with what Monday pays.
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../../i18n';
import { Icon } from '../../../ui/components';
import { PixelImage } from '../../../ui/PixelImage';
import { useOrg } from '../../orgs/api';
import { useGames } from '../api';
import styles from '../games.module.css';
import { RunnerGame } from './RunnerGame';

/** The Monday after the week, when the attempts come back. */
function nextMonday(weekStart: string): string {
  const monday = new Date(`${weekStart}T12:00:00Z`);
  monday.setUTCDate(monday.getUTCDate() + 7);
  return formatDate(monday, { weekday: 'long', day: 'numeric', month: 'long' });
}

export function RunnerPage() {
  const { t } = useTranslation('games');
  const { orgId = '' } = useParams();
  const games = useGames(orgId);
  const org = useOrg(orgId);
  const runner = games.data?.runner;
  if (!runner || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership.id;

  return (
    <article className={styles.page}>
      <Link to={`/o/${orgId}`} className={styles.back}>
        <Icon name="chevronLeft" size={12} />
        {t('runner.back')}
      </Link>
      <h1 className={styles.title}>{t('runner.title')}</h1>
      <p className={styles.text}>{t('runner.intro')}</p>
      <p className={styles.label}>{t('runner.attempts', { count: runner.attempts_left })}</p>
      <RunnerGame orgId={orgId} attemptsLeft={runner.attempts_left} />
      {runner.attempts_left === 0 && (
        <p className={styles.text}>
          {t('runner.exhausted', { date: nextMonday(runner.week_start) })}
        </p>
      )}

      <section className={styles.section} aria-labelledby="runner-week">
        <h2 id="runner-week" className={styles.sectionTitle}>
          {t('runner.week')}
        </h2>
        {runner.top.length === 0 ? (
          <p className={styles.note}>{t('runner.nobody')}</p>
        ) : (
          <ol className={styles.top}>
            {runner.top.map((row) => (
              <li
                key={row.member.id}
                className={row.member.id === me ? styles.me : undefined}
                aria-current={row.member.id === me ? 'true' : undefined}
              >
                <span className={styles.rank}>{row.rank}</span>
                <PixelImage image={row.member.avatar} size={24} />
                <span className={styles.name}>{row.member.pseudo}</span>
                <span className={styles.score}>{formatNumber(row.score)}</span>
              </li>
            ))}
          </ol>
        )}
        <p className={styles.note}>{t('runner.gains')}</p>
      </section>
    </article>
  );
}
