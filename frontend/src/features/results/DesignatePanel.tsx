// Designating the result (canvas G-Designer): a journalist ticks the correct answers or types the
// real value, or relaunches a postponed prono. The editor can also correct a published result and
// cancel a prono, each after a confirmation.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { formatNumber, fromParisInput, parisDayAt, parseDecimal } from '../../i18n';
import { Button, Card, Field, Icon } from '../../ui/components';
import { useFormErrors } from '../forms';
import type { PronoDetail } from '../pronos/api';
import pronoStyles from '../pronos/pronos.module.css';
import { useCancel, useCorrect, useRelaunch, useResolve, type ResultIn } from './api';
import styles from './results.module.css';

type Role = 'reader' | 'journalist' | 'editor';

const CANCELLABLE = ['scheduled', 'open', 'closed', 'resolved'];

function correctIds(prono: PronoDetail): string[] {
  return prono.options.filter((o) => o.is_correct).map((o) => o.id);
}

function ResultForm({
  orgId,
  prono,
  role,
  correcting,
}: {
  orgId: string;
  prono: PronoDetail;
  role: Role;
  correcting: boolean;
}) {
  const { t } = useTranslation('results');
  const resolve = useResolve(orgId, prono.id);
  const correct = useCorrect(orgId, prono.id);
  const action = correcting ? correct : resolve;
  const errors = useFormErrors(action.error);
  const [picks, setPicks] = useState<string[]>(() => (correcting ? correctIds(prono) : []));
  const [number, setNumber] = useState('');
  const [day, setDay] = useState('');
  const [confirming, setConfirming] = useState(false);
  const choosing = prono.kind === 'choice' || prono.kind === 'yes_no';

  const body: ResultIn | null = choosing
    ? picks.length
      ? { correct_option_ids: picks }
      : null
    : prono.kind === 'number'
      ? parseDecimal(number)
        ? { result_number: parseDecimal(number) }
        : null
      : day
        ? { result_date: day }
        : null;

  const right = prono.options
    .filter((o) => picks.includes(o.id))
    .reduce((total, o) => total + o.count, 0);
  const preview = !choosing
    ? t('designate.closest')
    : !picks.length
      ? t('designate.nobodyPicked')
      : right
        ? t('designate.right', { count: right })
        : t('designate.rightNone');

  const toggle = (id: string) =>
    setPicks((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id],
    );

  const submit = () => {
    if (!body) return;
    if (correcting && !confirming) {
      setConfirming(true);
      return;
    }
    action.mutate(body, { onSuccess: () => setConfirming(false) });
  };

  const fieldError =
    errors.field('correct_option_ids') ??
    errors.field('result_number') ??
    errors.field('result_date') ??
    errors.field('result');

  return (
    <div className={styles.panel}>
      <div className={styles.status} role="status">
        <span className={styles.statusLabel}>
          {correcting
            ? t('designate.statusCorrect')
            : prono.state === 'open'
              ? t('designate.statusOpenEnded')
              : t('designate.status')}
        </span>
        <span className={styles.statusText}>
          {!choosing
            ? t(prono.kind === 'date' ? 'designate.dateHint' : 'designate.valueHint')
            : role === 'editor'
              ? t('designate.editor')
              : t('designate.journalist')}
        </span>
      </div>

      {choosing ? (
        <div className={pronoStyles.page}>
          <span className={pronoStyles.label}>{t('designate.answers')}</span>
          <div role="group" aria-label={t('designate.answers')} className={pronoStyles.ballot}>
            {prono.options.map((option) => {
              const on = picks.includes(option.id);
              return (
                <button
                  key={option.id}
                  type="button"
                  className={pronoStyles.choice}
                  aria-pressed={on}
                  onClick={() => toggle(option.id)}
                >
                  <span className={pronoStyles.box} aria-hidden="true">
                    {on && <Icon name="check" size={12} />}
                  </span>
                  <span className={pronoStyles.choiceLabel}>{option.label}</span>
                  <span className={pronoStyles.pct}>
                    {t('designate.stat', { count: option.count, pct: option.share_pct })}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        <label className={pronoStyles.fieldset}>
          <span className={pronoStyles.label}>
            {prono.kind === 'date' ? t('designate.date') : t('designate.value')}
            {prono.number_unit && ` · ${prono.number_unit}`}
          </span>
          {prono.kind === 'date' ? (
            <input
              className={pronoStyles.answerInput}
              type="date"
              value={day}
              onChange={(event) => setDay(event.target.value)}
            />
          ) : (
            <input
              className={pronoStyles.answerInput}
              inputMode="decimal"
              value={number}
              onChange={(event) => setNumber(event.target.value)}
            />
          )}
        </label>
      )}

      <Card className={styles.preview}>
        <span className={styles.previewTitle}>{preview}</span>
        <span className={styles.small}>
          {t('designate.gains', { gain: prono.base_gain, pot: formatNumber(prono.pot) })}
        </span>
      </Card>

      {fieldError && (
        <p role="alert" className={pronoStyles.alert}>
          {fieldError}
        </p>
      )}
      {confirming ? (
        <div className={styles.confirm}>
          <p>{t('designate.correctConfirm')}</p>
          <div className={styles.actions}>
            <Button onClick={submit} disabled={action.isPending}>
              {t('designate.confirm')}
            </Button>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              {t('designate.back')}
            </Button>
          </div>
        </div>
      ) : (
        <Button block onClick={submit} disabled={!body || action.isPending}>
          {correcting ? t('designate.correct') : t('designate.publish')}
        </Button>
      )}
    </div>
  );
}

function RelaunchForm({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('results');
  const relaunch = useRelaunch(orgId, prono.id);
  const errors = useFormErrors(relaunch.error);
  const [open, setOpen] = useState(false);
  const [closesAt, setClosesAt] = useState(() => parisDayAt(7, 18));
  const [resultAt, setResultAt] = useState('');
  const [reason, setReason] = useState('');

  if (!open) {
    return (
      <div className={styles.panel}>
        <Button variant="secondary" block onClick={() => setOpen(true)}>
          {t('designate.relaunch')}
        </Button>
        <p className={`${styles.small} ${styles.centered}`}>{t('designate.relaunchNote')}</p>
      </div>
    );
  }
  return (
    <form
      className={styles.confirm}
      onSubmit={(event) => {
        event.preventDefault();
        relaunch.mutate({
          closes_at: fromParisInput(closesAt).toISOString(),
          result_expected_at: resultAt ? fromParisInput(resultAt).toISOString() : null,
          reason: reason.trim() || null,
        });
      }}
    >
      <Field
        label={t('designate.relaunchClose')}
        type="datetime-local"
        value={closesAt}
        onChange={(event) => setClosesAt(event.target.value)}
        error={errors.field('closes_at')}
        required
      />
      <Field
        label={t('designate.relaunchResult')}
        type="datetime-local"
        value={resultAt}
        min={closesAt}
        onChange={(event) => setResultAt(event.target.value)}
        error={errors.field('result_expected_at')}
      />
      <Field
        label={t('designate.relaunchReason')}
        placeholder={t('designate.relaunchReasonPlaceholder')}
        value={reason}
        maxLength={200}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className={styles.actions}>
        <Button type="submit" disabled={relaunch.isPending}>
          {t('designate.relaunchSubmit')}
        </Button>
        <Button variant="secondary" onClick={() => setOpen(false)}>
          {t('designate.back')}
        </Button>
      </div>
    </form>
  );
}

function CancelForm({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('results');
  const cancel = useCancel(orgId, prono.id);
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');

  if (!open) {
    return (
      <Button variant="link" className={styles.linkButton} onClick={() => setOpen(true)}>
        {t('designate.cancel')}
      </Button>
    );
  }
  return (
    <form
      className={styles.confirm}
      onSubmit={(event) => {
        event.preventDefault();
        cancel.mutate({ reason: reason.trim() || null });
      }}
    >
      <p>{t('designate.cancelConfirm')}</p>
      <Field
        label={t('designate.cancelReason')}
        value={reason}
        maxLength={200}
        onChange={(event) => setReason(event.target.value)}
      />
      <div className={styles.actions}>
        <Button type="submit" disabled={cancel.isPending}>
          {t('designate.cancelSubmit')}
        </Button>
        <Button variant="secondary" onClick={() => setOpen(false)}>
          {t('designate.back')}
        </Button>
      </div>
    </form>
  );
}

export function DesignatePanel({
  orgId,
  prono,
  role,
}: {
  orgId: string;
  prono: PronoDetail;
  role: Role;
}) {
  const { t } = useTranslation('results');
  const [correcting, setCorrecting] = useState(false);
  const newsroom = role !== 'reader';
  const designating =
    newsroom && (prono.state === 'closed' || (prono.state === 'open' && prono.open_ended));
  const canCorrect = role === 'editor' && prono.state === 'resolved';
  const canRelaunch = newsroom && prono.state === 'closed';
  const canCancel = role === 'editor' && CANCELLABLE.includes(prono.state);
  if (!designating && !canCorrect && !canRelaunch && !canCancel) return null;

  return (
    <section className={styles.panel} aria-label={t('designate.label')}>
      {designating &&
        (prono.bet_count > 0 ? (
          <ResultForm orgId={orgId} prono={prono} role={role} correcting={false} />
        ) : (
          prono.state === 'closed' && <p className={pronoStyles.alert}>{t('designate.noBets')}</p>
        ))}
      {canCorrect &&
        (correcting ? (
          <ResultForm orgId={orgId} prono={prono} role={role} correcting />
        ) : (
          <Button variant="secondary" block onClick={() => setCorrecting(true)}>
            {t('designate.correctOpen')}
          </Button>
        ))}
      {canRelaunch && <RelaunchForm orgId={orgId} prono={prono} />}
      {canCancel && <CancelForm orgId={orgId} prono={prono} />}
    </section>
  );
}
