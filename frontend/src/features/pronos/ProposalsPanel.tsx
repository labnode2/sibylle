// Readers' proposals, for the journalists: publish one with the gain they choose, or turn it
// down with a reason its author will read.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Button, Card, Stepper } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { usePronoList, useProposalDecision, type PronoSummary } from './api';
import styles from './pronos.module.css';

const GAIN_STEP = 5;

/** Validate or reject one proposal. */
export function ProposalDecision({ orgId, prono }: { orgId: string; prono: PronoSummary }) {
  const { t } = useTranslation('pronos');
  const org = useOrg(orgId);
  const { validate, reject } = useProposalDecision(orgId, prono.id);
  const [gain, setGain] = useState(prono.base_gain);
  const [refusing, setRefusing] = useState(false);
  const [reason, setReason] = useState('');
  const errors = useFormErrors(validate.error ?? reject.error);
  const maxGain = org.data?.max_base_gain ?? prono.base_gain;
  const busy = validate.isPending || reject.isPending;

  return (
    <div className={styles.decision}>
      <div className={styles.switchRow}>
        <span className={styles.label}>{t('proposals.gain', { max: maxGain })}</span>
        <Stepper
          label={t('proposals.gainLabel')}
          value={Math.min(gain, maxGain)}
          onChange={setGain}
          min={0}
          max={maxGain}
          step={GAIN_STEP}
        />
      </div>
      {refusing && (
        <label className={styles.fieldset}>
          <span className={styles.label}>{t('proposals.reason')}</span>
          <textarea
            className={styles.textarea}
            maxLength={500}
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
        </label>
      )}
      {(errors.field('base_gain') || errors.field('closes_at')) && (
        <p role="alert" className={styles.alert}>
          {errors.field('base_gain') ?? errors.field('closes_at')}
        </p>
      )}
      <div className={styles.actions}>
        {refusing ? (
          <>
            <Button variant="secondary" onClick={() => setRefusing(false)} disabled={busy}>
              {t('proposals.back')}
            </Button>
            <Button onClick={() => reject.mutate(reason)} disabled={busy}>
              {t('proposals.confirmReject')}
            </Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={() => setRefusing(true)} disabled={busy}>
              {t('proposals.reject')}
            </Button>
            <Button onClick={() => validate.mutate(Math.min(gain, maxGain))} disabled={busy}>
              {t('proposals.validate')}
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

/** Every proposal waiting for a journalist, on la une. */
export function ProposalsPanel({ orgId }: { orgId: string }) {
  const { t } = useTranslation('pronos');
  const list = usePronoList(orgId, ['proposed']);
  const proposals = list.data?.pages.flatMap((page) => page.items) ?? [];
  if (proposals.length === 0) return null;

  return (
    <section className={styles.page} aria-label={t('proposals.title')}>
      <span className={styles.label}>
        {t('proposals.title')} · {proposals.length}
      </span>
      {proposals.map((prono) => (
        <Card key={prono.id} shadow={0} className={styles.proposal}>
          <span className={styles.kicker}>
            {t('proposals.by', {
              section: prono.section.name.toUpperCase(),
              author: prono.created_by.pseudo.toUpperCase(),
            })}
          </span>
          <Link to={`/o/${orgId}/pronos/${prono.id}`} className={styles.itemTitle}>
            {prono.question}
          </Link>
          <ProposalDecision orgId={orgId} prono={prono} />
        </Card>
      ))}
    </section>
  );
}
