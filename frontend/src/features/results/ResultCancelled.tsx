// « Résultat annulé », on the page of a prono whose result the editor took back: why its special
// edition is gone, and that the bets and their stakes wait for a new result, with the editor's
// reason when given. Shown until the prono moves on (edited, relaunched, resolved again…).
import { useTranslation } from 'react-i18next';

import type { PronoDetail, PronoEvent } from '../pronos/api';

/** The cancellation of the result the prono still waits after, or null. */
export function cancelledResult(prono: PronoDetail): PronoEvent | null {
  const last = prono.events.at(-1);
  const waiting = prono.state === 'closed' || prono.state === 'open';
  return waiting && last?.kind === 'result_cancelled' ? last : null;
}

export function ResultCancelled({ event, className }: { event: PronoEvent; className?: string }) {
  const { t } = useTranslation('results');
  const reason = typeof event.data.reason === 'string' ? event.data.reason : '';
  return (
    <p className={className}>
      {t('resultCancelled.notice')}
      {reason && ` ${t('resultCancelled.reason', { reason })}`}
    </p>
  );
}
