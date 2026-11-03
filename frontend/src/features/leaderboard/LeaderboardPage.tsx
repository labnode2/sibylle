// The newsroom's rankings (canvas G-Classement): laurels or pronos won, over the month, the
// season or all time, the first three on a podium and the others below, my line in light grey.
// Settlements and the end of a season refresh it live.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Laurel, Segmented, TopBar } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useOrg } from '../orgs/api';
import {
  useCurrentSeason,
  useLeaderboard,
  type Leaderboard,
  type Metric,
  type Period,
} from './api';
import styles from './leaderboard.module.css';

type Row = Leaderboard['rows'][number];

// The podium's steps, first to third: avatar size and step height (canvas G-Classement).
const STEPS = [
  { avatar: 80, height: 100 },
  { avatar: 64, height: 72 },
  { avatar: 64, height: 56 },
] as const;

/** "2026-11" → "NOVEMBRE 2026", "2026-autumn" → "AUTOMNE 2026", "all_time" → "DEPUIS TOUJOURS". */
function usePeriodTitle(label: string | undefined): string {
  const { t } = useTranslation('leaderboard');
  if (!label) return '';
  if (label === 'all_time') return t('period.all_time');
  const [year, part] = label.split('-');
  if (part && /^\d+$/.test(part)) {
    return formatDate(new Date(Number(year), Number(part) - 1, 15), {
      month: 'long',
      year: 'numeric',
    }).toUpperCase();
  }
  return t('seasonTitle', { season: t(`season.${part}`), year }).toUpperCase();
}

function Value({ row, metric }: { row: Row; metric: Metric }) {
  const { t } = useTranslation('leaderboard');
  return metric === 'laurels' ? (
    <Laurel value={row.value} />
  ) : (
    <span>{t('wins', { count: row.value, value: formatNumber(row.value) })}</span>
  );
}

function Name({ row }: { row: Row }) {
  const { t } = useTranslation('leaderboard');
  return <>{row.is_me ? t('you', { pseudo: row.member.pseudo }) : row.member.pseudo}</>;
}

export function LeaderboardPage() {
  const { t } = useTranslation('leaderboard');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const [metric, setMetric] = useState<Metric>('laurels');
  const [period, setPeriod] = useState<Period>('month');
  const board = useLeaderboard(orgId, metric, period);
  const season = useCurrentSeason(orgId);
  const title = usePeriodTitle(board.data?.period_label);
  const until =
    season.data &&
    formatDate(new Date(new Date(season.data.ends_at).getTime() - 1), {
      day: 'numeric',
      month: 'long',
    });
  const month = formatDate(new Date(), { month: 'long' }).toUpperCase();
  const rows = board.data?.rows ?? [];
  const podium = rows.slice(0, 3);
  const rest = rows.slice(3);
  const member = (row: Row) => `/o/${orgId}/membres/${row.member.id}`;

  return (
    <div className={styles.page}>
      <TopBar
        back={`/o/${orgId}`}
        backLabel={t('back')}
        aside={
          org.data &&
          t('newsroom', {
            org: org.data.title.toUpperCase(),
            count: org.data.member_count,
          })
        }
      />
      <h1 className={styles.title}>{t('title')}</h1>

      <div className={styles.controls}>
        <Segmented
          label={t('metricLabel')}
          options={[
            { value: 'laurels', label: t('option.laurels') },
            { value: 'wins', label: t('option.wins') },
          ]}
          value={metric}
          onChange={setMetric}
        />
        <Segmented
          label={t('periodLabel')}
          variant="tabs"
          options={[
            { value: 'month', label: month },
            { value: 'season', label: t('option.season') },
            { value: 'all_time', label: t('option.all_time') },
          ]}
          value={period}
          onChange={setPeriod}
        />
      </div>

      <section className={styles.board} aria-label={t(`caption.${metric}`, { period: title })}>
        {board.isPending ? (
          <p role="status">{t('common:shell.loading')}</p>
        ) : (
          <>
            <ol className={styles.podium}>
              {podium.map((row, index) => (
                <li
                  key={row.member.id}
                  className={`${styles.step} ${index === 0 ? styles.first : ''}`}
                  aria-current={row.is_me ? 'true' : undefined}
                >
                  <span className={styles.stepAvatar}>
                    <PixelImage image={row.member.avatar} size={STEPS[index]!.avatar} />
                  </span>
                  <Link to={member(row)} className={styles.stepName} data-part="name">
                    <Name row={row} />
                  </Link>
                  <span className={styles.stepValue} data-part="value">
                    <Value row={row} metric={metric} />
                  </span>
                  <span
                    className={styles.block}
                    style={{ height: STEPS[index]!.height }}
                    data-part="rank"
                  >
                    {row.rank}
                  </span>
                </li>
              ))}
            </ol>
            {rest.length > 0 && (
              <ol className={styles.rest} start={4}>
                {rest.map((row) => (
                  <li
                    key={row.member.id}
                    className={`${styles.line} ${row.is_me ? styles.me : ''}`}
                    aria-current={row.is_me ? 'true' : undefined}
                  >
                    <span className={styles.rank} data-part="rank">
                      {row.rank}
                    </span>
                    <PixelImage image={row.member.avatar} size={28} />
                    <Link to={member(row)} className={styles.lineName} data-part="name">
                      <Name row={row} />
                    </Link>
                    <span className={styles.value} data-part="value">
                      <Value row={row} metric={metric} />
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </section>
      <p className={styles.note}>{t('updated')}</p>
      <p className={styles.note}>{t(`note.${metric}`)}</p>
      {season.data && (
        <p className={styles.note}>
          {t('kicker', {
            season: t(`season.${season.data.name}`),
            year: season.data.year,
            until,
          }).toUpperCase()}
        </p>
      )}
    </div>
  );
}
