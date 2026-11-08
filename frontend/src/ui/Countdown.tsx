// The time left before a moment: a box of days, hours and minutes (canvas B-Prono: white box,
// 2 px rule, hard shadow), or a short line of text. A prono's closing, Pixel mystère's end.
import type { TFunction } from 'i18next';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Card } from './components';
import styles from './countdown.module.css';

/** The current time, refreshed every `every` milliseconds. */
export function useNow(every: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(timer);
  }, [every]);
  return now;
}

function split(left: number) {
  return {
    days: Math.floor(left / 86_400_000),
    hours: Math.floor(left / 3_600_000) % 24,
    minutes: Math.floor(left / 60_000) % 60,
  };
}

/** "2 J 5 H", "5 H 12 MIN" or "12 MIN": the time left before `until`, for a line of text. */
export function shortTimeLeft(t: TFunction, until: string, now: number): string {
  const { days, hours, minutes } = split(Math.max(0, new Date(until).getTime() - now));
  if (days > 0) return t('common:countdown.short.days', { days, hours });
  if (hours > 0) return t('common:countdown.short.hours', { hours, minutes });
  return t('common:countdown.short.minutes', { minutes });
}

/** `large`: the prono's, bigger on a computer. */
export function Countdown({
  until,
  label,
  large = false,
}: {
  until: string;
  label: string;
  large?: boolean;
}) {
  const { t } = useTranslation('common');
  const now = useNow(15_000);
  const { days, hours, minutes } = split(Math.max(0, new Date(until).getTime() - now));
  const units = [
    { value: days, label: t('countdown.days') },
    { value: hours, label: t('countdown.hours') },
    { value: minutes, label: t('countdown.minutes') },
  ];
  return (
    <div role="timer" aria-label={label}>
      <Card as="div" className={`${styles.countdown} ${large ? styles.large : ''}`}>
        {units.map((unit) => (
          <div key={unit.label}>
            <span className={styles.value}>{String(unit.value).padStart(2, '0')}</span>
            <span className={styles.unit}>{unit.label}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}
