// The newsroom's rankings: laurels or pronos won, over the month, the season or all time
// (canvas G-Classement). Settlements and the end of a season refresh it live.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Card, Laurel } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useCurrentSeason, useLeaderboard, type Metric, type Period } from './api';
import styles from './leaderboard.module.css';

const METRICS: Metric[] = ['laurels', 'wins'];
const PERIODS: Period[] = ['month', 'season', 'all_time'];

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

function Toggle<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: T[];
  value: T;
  onChange: (value: T) => void;
}) {
  const { t } = useTranslation('leaderboard');
  return (
    <div className={styles.toggle} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          className={styles.toggleButton}
          aria-pressed={value === option}
          onClick={() => onChange(option)}
        >
          {t(`option.${option}`)}
        </button>
      ))}
    </div>
  );
}

export function LeaderboardPage() {
  const { t } = useTranslation('leaderboard');
  const { orgId = '' } = useParams();
  const [metric, setMetric] = useState<Metric>('laurels');
  const [period, setPeriod] = useState<Period>('season');
  const board = useLeaderboard(orgId, metric, period);
  const season = useCurrentSeason(orgId);
  const title = usePeriodTitle(board.data?.period_label);
  const until =
    season.data &&
    formatDate(new Date(new Date(season.data.ends_at).getTime() - 1), {
      day: 'numeric',
      month: 'long',
    });

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.kicker}>
          {season.data
            ? t('kicker', {
                season: t(`season.${season.data.name}`),
                year: season.data.year,
                until,
              }).toUpperCase()
            : ' '}
        </span>
        <h1 className={styles.title}>{t('title')}</h1>
      </header>

      <div className={styles.controls}>
        <Toggle label={t('metricLabel')} options={METRICS} value={metric} onChange={setMetric} />
        <Toggle label={t('periodLabel')} options={PERIODS} value={period} onChange={setPeriod} />
      </div>

      <Card shadow={0} className={styles.board}>
        {board.isPending ? (
          <p role="status">{t('common:shell.loading')}</p>
        ) : (
          <table className={styles.table}>
            <caption className={styles.caption}>
              {t(`caption.${metric}`, { period: title })}
            </caption>
            <thead className="visually-hidden">
              <tr>
                <th scope="col">{t('column.rank')}</th>
                <th scope="col">{t('column.member')}</th>
                <th scope="col">{t(`column.${metric}`)}</th>
              </tr>
            </thead>
            <tbody>
              {board.data?.rows.map((row) => (
                <tr
                  key={row.member.id}
                  className={row.is_me ? styles.me : undefined}
                  aria-current={row.is_me ? 'true' : undefined}
                >
                  <td className={styles.rank}>{row.rank}</td>
                  <th scope="row" className={styles.member}>
                    <PixelImage image={row.member.avatar} size={32} />
                    <span>{row.member.pseudo}</span>
                    {row.is_me && <span className={styles.you}>{t('you')}</span>}
                  </th>
                  <td className={styles.value}>
                    {metric === 'laurels' ? (
                      <Laurel value={row.value} />
                    ) : (
                      t('wins', { count: row.value, value: formatNumber(row.value) })
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      <p className={styles.note}>{t(`note.${metric}`)}</p>
    </div>
  );
}
