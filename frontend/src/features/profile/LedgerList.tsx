// The member's statement: every movement of their laurels, newest first, with its reason.
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Button } from '../../ui/components';
import { useLedger, type LedgerEntry } from './api';
import styles from './profile.module.css';

const signed = (value: number) => (value > 0 ? `+${formatNumber(value)}` : formatNumber(value));

/** What the entry is: a reversal that took a result back says so, rather than « correction ». */
const kindKey = (entry: LedgerEntry) =>
  entry.kind === 'reversal' && entry.settlement_kind === 'result_cancellation'
    ? 'ledger.resultCancelled'
    : `ledger.kind.${entry.kind}`;

function Detail({ orgId, entry }: { orgId: string; entry: LedgerEntry }) {
  const { t } = useTranslation('profile');
  const { pathname } = useLocation();
  // A deleted prono's refunds stay in the history, without a link: its page is gone.
  if (entry.prono?.deleted) {
    return (
      <span className={styles.ledgerDetail}>
        {t('pronos:detail.deletedRef', { question: entry.prono.question })}
      </span>
    );
  }
  if (entry.prono) {
    return (
      <Link
        to={`/o/${orgId}/pronos/${entry.prono.id}`}
        state={{ from: pathname }}
        className={styles.ledgerDetail}
      >
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
  if (entry.kind === 'pixel_author_bonus')
    return <span className={styles.ledgerDetail}>{t('ledger.pixelBonus')}</span>;
  if (entry.kind === 'pixel_author_find')
    return <span className={styles.ledgerDetail}>{t('ledger.pixelFind')}</span>;
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
                {t(kindKey(entry))} ·{' '}
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
