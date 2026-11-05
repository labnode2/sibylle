// « Signaler une erreur »: a member tells the editors that a result is wrong or a content is not
// welcome, with a message of 500 characters at most.
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Card } from '../../ui/components';
import { useFormErrors } from '../forms';
import pronoStyles from '../pronos/pronos.module.css';
import { useReport, type ReportIn } from './api';
import styles from './results.module.css';

const MESSAGE_MAX = 500;
const KINDS: ReportIn['kind'][] = ['result_error', 'content'];

export function ReportForm({
  orgId,
  pronoId,
  initialKind,
}: {
  orgId: string;
  pronoId: string;
  initialKind: ReportIn['kind'];
}) {
  const { t } = useTranslation('results');
  const report = useReport(orgId, pronoId);
  const errors = useFormErrors(report.error);
  const id = useId();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState(initialKind);
  const [message, setMessage] = useState('');

  if (!open) {
    return (
      <Button variant="link" className={styles.linkButton} onClick={() => setOpen(true)}>
        {initialKind === 'result_error' ? t('report.open') : t('report.openContent')}
      </Button>
    );
  }
  return (
    <Card as="div" shadow={0} className={styles.report}>
      <form
        className={styles.panel}
        onSubmit={(event) => {
          event.preventDefault();
          report.mutate(
            { kind, message: message.trim() || null },
            {
              onSuccess: () => {
                setOpen(false);
                setMessage('');
              },
            },
          );
        }}
      >
        <fieldset className={styles.reportKinds}>
          <legend>{t('report.kind')}</legend>
          {KINDS.map((value) => (
            <label key={value} className={styles.radio}>
              <input
                type="radio"
                name={`${id}-kind`}
                checked={kind === value}
                onChange={() => setKind(value)}
              />
              {t(`report.${value}`)}
            </label>
          ))}
        </fieldset>
        <label htmlFor={`${id}-message`} className={pronoStyles.label}>
          {t('report.message')}
        </label>
        <textarea
          id={`${id}-message`}
          className={styles.textarea}
          value={message}
          maxLength={MESSAGE_MAX}
          aria-describedby={`${id}-count`}
          onChange={(event) => setMessage(event.target.value)}
        />
        <span id={`${id}-count`} className={pronoStyles.counter}>
          {t('report.counter', { count: message.length })}
        </span>
        {errors.field('message') && (
          <p role="alert" className={pronoStyles.alert}>
            {errors.field('message')}
          </p>
        )}
        <div className={styles.actions}>
          <Button type="submit" disabled={report.isPending}>
            {t('report.send')}
          </Button>
          <Button variant="secondary" onClick={() => setOpen(false)}>
            {t('report.close')}
          </Button>
        </div>
      </form>
    </Card>
  );
}
