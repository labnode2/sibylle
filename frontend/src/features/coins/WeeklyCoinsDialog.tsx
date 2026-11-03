// The good news of Monday: the gold laurels became coins. Shown once per week, at the first
// opening after the conversion (or straight away when it happens while the app is open).
import { useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { formatDate, formatNumber } from '../../i18n';
import { Button, ButtonLink, Coins, Kicker } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import { useWeeklyCoins, useWeeklyCoinsSeen } from './api';
import styles from './coins.module.css';

export function WeeklyCoinsDialog({ orgId, coins }: { orgId: string; coins: number }) {
  const { t } = useTranslation('coins');
  const weekly = useWeeklyCoins(orgId);
  const seen = useWeeklyCoinsSeen(orgId);
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const news = weekly.data;

  useEffect(() => {
    if (news && !dialog.current?.open) dialog.current?.showModal();
  }, [news]);

  if (!news) return null;
  // Escape, the close button or the link to the collection: the news has been seen.
  const dismiss = () => {
    if (!seen.isPending) seen.mutate(news.week_start);
  };
  const close = () => dialog.current?.close();
  const day = formatDate(`${news.week_start}T12:00:00Z`, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId} onClose={dismiss}>
      <div className={styles.ball} aria-hidden="true">
        <CrystalBall size={64} loops={1} />
      </div>
      <Kicker tone="indigo">{t('kicker', { day: day.toUpperCase() })}</Kicker>
      <h2 id={titleId} className={styles.title}>
        {t('title')}
      </h2>
      <p className={styles.amount}>
        <span>+</span>
        <Coins value={news.amount} size={32} />
      </p>
      <p className={styles.text}>
        {t('body', {
          gold: formatNumber(news.gold),
          count: news.amount,
          amount: formatNumber(news.amount),
        })}
      </p>
      <p className={styles.text}>{t('total', { count: coins, coins: formatNumber(coins) })}</p>
      <div className={styles.actions}>
        <ButtonLink to={`/o/${orgId}/collection`} onClick={close}>
          {t('spend')}
        </ButtonLink>
        <Button variant="secondary" onClick={close}>
          {t('close')}
        </Button>
      </div>
    </dialog>
  );
}
