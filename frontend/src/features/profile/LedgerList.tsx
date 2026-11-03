// The member's statement: every movement of their laurels, newest first, with its reason.
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Button } from '../../ui/components';
import { useLedger, type LedgerEntry } from './api';
import styles from './profile.module.css';

const signed = (value: number) => (value > 0 ? `+${formatNumber(value)}` : formatNumber(value));

function Detail({ orgId, entry }: { orgId: string; entry: LedgerEntry }) {
  const { t } = useTranslation('profile');
  if (entry.prono) {
    return (
      <Link to={`/o/${orgId}/pronos/${entry.prono.id}`} className={styles.ledgerDetail}>
        {entry.prono.question}
      </Link>
    );
  }
  if (entry.kind === 'purchase' && entry.reason) {
    return <span className={styles.ledgerDetail}>{t(`catalog.${entry.reason}`)}</span>;
  }
  // « runner:2026-11-02 »: the ball's race of the week that began that Monday.
  const week = entry.kind === 'minigame' && /^runner:(\d{4}-\d{2}-\d{2})$/.exec(entry.reason ?? '');
  if (week) {
    const day = formatDate(`${week[1]}T12:00:00Z`, { day: 'numeric', month: 'long' });
    return <span className={styles.ledgerDetail}>{t('ledger.runner', { day })}</span>;
  }
  // « pixel:Café »: the word found at Pixel mystère.
  const pixel = entry.kind === 'minigame' && /^pixel:(.+)$/.exec(entry.reason ?? '');
  if (pixel)
    return <span className={styles.ledgerDetail}>{t('ledger.pixel', { word: pixel[1] })}</span>;
  return entry.reason ? <span className={styles.ledgerDetail}>« {entry.reason} »</span> : null;
}

export function LedgerList({ orgId }: { orgId: string }) {
  const { t } = useTranslation('profile');
  const ledger = useLedger(orgId);
  const entries = ledger.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section className={styles.section} aria-labelledby="card-ledger">
      <h2 id="card-ledger" className={styles.intertitle}>
        {t('ledger.title')}
      </h2>
      <ul className={styles.ledger}>
        {entries.map((entry) => (
          <li key={entry.id} className={styles.ledgerRow}>
            <div className={styles.ledgerText}>
              <span className={styles.ledgerKind}>
                {t(`ledger.kind.${entry.kind}`)} ·{' '}
                {formatDate(entry.created_at, { day: 'numeric', month: 'short' }).toUpperCase()}
              </span>
              <Detail orgId={orgId} entry={entry} />
            </div>
            <div className={styles.ledgerAmounts}>
              {entry.amount !== 0 && (
                <span className={styles.amount}>
                  {t('ledger.amount', { value: signed(entry.amount) })}
                </span>
              )}
              {entry.score_delta !== 0 && (
                <span className={styles.score}>
                  {t('ledger.score', { value: signed(entry.score_delta) })}
                </span>
              )}
            </div>
          </li>
        ))}
      </ul>
      {ledger.hasNextPage && (
        <Button
          variant="secondary"
          onClick={() => void ledger.fetchNextPage()}
          disabled={ledger.isFetchingNextPage}
        >
          {t('ledger.more')}
        </Button>
      )}
    </section>
  );
}
