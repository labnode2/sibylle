// « Les modifications » on a prono's page: each edit, when and by whom, and for each field what
// it was and what it became (FR-035). Every member reads it, so that a question reworded after
// the first bets still says what was bet on. The latest edit comes first.
import { useTranslation } from 'react-i18next';

import { formatDate } from '../../i18n';
import { SectionHead } from '../../ui/components';
import type { PronoDetail, PronoEvent } from './api';
import styles from './pronos.module.css';

/** A field an edit changed, as the server keeps it (data-model.md, prono_events). */
type Change = { field: string; before: unknown; after: unknown };

const DATES = new Set(['opens_at', 'closes_at', 'result_expected_at']);
// « aucune » clôture, ouverture, unité ; « aucun » lien, choix.
const FEMININE = new Set([...DATES, 'number_unit']);

/** The changes an edit noted, or none. */
export function changesOf(event: PronoEvent): Change[] {
  const changes = event.data.changes;
  return event.kind === 'edited' && Array.isArray(changes) ? (changes as Change[]) : [];
}

function useValueText() {
  const { t } = useTranslation('pronos');
  return (field: string, value: unknown): string => {
    if (value === null || value === undefined || value === '') {
      return t(FEMININE.has(field) ? 'history.noneFeminine' : 'history.none');
    }
    if (DATES.has(field)) {
      return formatDate(String(value), {
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        hour: '2-digit',
        minute: '2-digit',
      });
    }
    if (field === 'kind') return t(`kind.${String(value)}`);
    if (field === 'options') {
      return Array.isArray(value) && value.length ? value.join(' · ') : t('history.none');
    }
    if (field === 'base_gain') return t('history.gain', { gain: value });
    if (field === 'open_ended') return t(value ? 'history.yes' : 'history.no');
    return String(value);
  };
}

function ChangeRow({ change }: { change: Change }) {
  const { t } = useTranslation('pronos');
  const text = useValueText();
  const label = t(`history.field.${change.field}`, { defaultValue: change.field });
  // An image is not words: it was added, changed or taken away.
  if (change.field === 'image') {
    const what = !change.before ? 'added' : !change.after ? 'removed' : 'changed';
    return (
      <div className={styles.historyRow}>
        <dt>{label}</dt>
        <dd>{t(`history.${what}`)}</dd>
      </div>
    );
  }
  return (
    <div className={styles.historyRow}>
      <dt>{label}</dt>
      <dd>
        <del>
          <span className="visually-hidden">{t('history.before')} </span>
          {text(change.field, change.before)}
        </del>
        <ins>
          <span className="visually-hidden">{t('history.after')} </span>
          {text(change.field, change.after)}
        </ins>
      </dd>
    </div>
  );
}

export function PronoHistory({ prono }: { prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  const edits = prono.events.filter((event) => changesOf(event).length > 0).reverse();
  if (!edits.length) return null;
  return (
    <section className={styles.history} aria-labelledby="prono-history">
      <SectionHead id="prono-history" title={t('history.title')} meta={String(edits.length)} />
      <ol className={styles.historyList}>
        {edits.map((event, index) => {
          const when = formatDate(event.at, {
            weekday: 'short',
            day: 'numeric',
            month: 'short',
            hour: '2-digit',
            minute: '2-digit',
          }).toUpperCase();
          return (
            <li key={`${event.at}-${index}`} className={styles.historyItem}>
              <span className={styles.meta}>
                {event.by
                  ? t('history.by', { date: when, pseudo: event.by.pseudo.toUpperCase() })
                  : when}
              </span>
              <dl className={styles.historyChanges}>
                {changesOf(event).map((change) => (
                  <ChangeRow key={change.field} change={change} />
                ))}
              </dl>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
