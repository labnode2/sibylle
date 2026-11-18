// Publishing a prono (canvas G-Créer): its own header (close, title, role), type, section,
// question, choices, closing and fixed gain side by side, the switches, and the button kept at
// the bottom of the screen. Journalists and the editor publish directly; a reader proposes, and
// a journalist publishes.
// The same form edits a prono (« Modifier » on its page): all of it until the first bet. After
// that, what the bets were placed on is greyed, each with why, and the closing only moves later;
// only what changed is sent, and the prono's history keeps it.
import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useParams } from 'react-router';

import { fromParisInput, parisDayAt, toParisInput } from '../../i18n';
import { Button, Chip, Field, Icon, Segmented, Stepper, SwitchRow } from '../../ui/components';
import { toast } from '../../ui/Toaster';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import {
  useCreateProno,
  useEditProno,
  useProno,
  useSections,
  useUpload,
  type LockedField,
  type PronoDetail,
  type PronoIn,
  type PronoPatch,
  type Section,
} from './api';
import styles from './pronos.module.css';

type Kind = PronoIn['kind'];
type Role = 'reader' | 'journalist' | 'editor';

const KINDS: Kind[] = ['choice', 'yes_no', 'number', 'date'];
const QUESTION_MAX = 200;
const GAIN_STEP = 5;

const toIso = (value: string) => (value ? fromParisInput(value).toISOString() : null);
const parisInput = (value: string | null | undefined) =>
  value ? toParisInput(new Date(value)) : '';
// Tomorrow at 18:00, Paris time: a sensible default closing time.
const defaultClosing = () => parisDayAt(1, 18);

/** What the form holds, as typed. */
type Values = {
  kind: Kind;
  sectionId: string;
  question: string;
  options: string[];
  unit: string;
  openEnded: boolean;
  link: string;
  imageId: string | null;
  scheduled: boolean;
  opensAt: string;
  closesAt: string;
  resultAt: string;
  gain: number;
};

function blank(sections: Section[], maxGain: number): Values {
  return {
    kind: 'choice',
    sectionId: sections[0]?.id ?? '',
    question: '',
    options: ['', ''],
    unit: '',
    openEnded: false,
    link: '',
    imageId: null,
    scheduled: false,
    opensAt: '',
    closesAt: defaultClosing(),
    resultAt: '',
    gain: Math.min(20, maxGain),
  };
}

function valuesOf(prono: PronoDetail): Values {
  return {
    kind: prono.kind,
    sectionId: prono.section.id,
    question: prono.question,
    options: prono.kind === 'choice' ? prono.options.map((o) => o.label) : ['', ''],
    unit: prono.number_unit ?? '',
    openEnded: prono.open_ended,
    link: prono.link_url ?? '',
    imageId: prono.image_id ?? null,
    scheduled: Boolean(prono.opens_at),
    opensAt: parisInput(prono.opens_at),
    closesAt: prono.closes_at ? parisInput(prono.closes_at) : defaultClosing(),
    resultAt: parisInput(prono.result_expected_at),
    gain: prono.base_gain,
  };
}

/** A locked field shows as the prono has it now, whatever was typed before it locked. */
function withLocked(values: Values, live: Values, locked: ReadonlySet<LockedField>): Values {
  const keep = <K extends keyof Values>(field: LockedField, key: K): Values[K] =>
    locked.has(field) ? live[key] : values[key];
  return {
    ...values,
    kind: keep('kind', 'kind'),
    options: keep('options', 'options'),
    unit: keep('number_unit', 'unit'),
    gain: keep('base_gain', 'gain'),
    openEnded: keep('open_ended', 'openEnded'),
    scheduled: keep('opens_at', 'scheduled'),
    opensAt: keep('opens_at', 'opensAt'),
    closesAt: keep('closes_at', 'closesAt'),
  };
}

/** The prono the values describe, as the server takes it. */
function bodyOf(values: Values): PronoIn {
  const openEnded = values.kind === 'date' && values.openEnded;
  return {
    kind: values.kind,
    question: values.question.trim(),
    section_id: values.sectionId,
    options: values.kind === 'choice' ? values.options.map((o) => o.trim()).filter(Boolean) : [],
    base_gain: values.gain,
    link_url: values.link.trim() || null,
    image_id: values.imageId,
    opens_at: values.scheduled ? toIso(values.opensAt) : null,
    closes_at: openEnded ? null : toIso(values.closesAt),
    open_ended: openEnded,
    result_expected_at: toIso(values.resultAt),
    number_unit: values.kind === 'number' ? values.unit.trim() || null : null,
  };
}

/** What an edit changes, as the server takes it: nothing locked, nothing left as it was. */
function changesOf(before: Values, after: Values, locked: ReadonlySet<LockedField>): PronoPatch {
  const old = bodyOf(before);
  const now = bodyOf(after);
  const keys = Object.keys(now) as (keyof PronoIn)[];
  return Object.fromEntries(
    keys
      .filter((key) => !locked.has(key as LockedField))
      .filter((key) => JSON.stringify(now[key]) !== JSON.stringify(old[key]))
      .map((key) => [key, now[key]]),
  );
}

/** Why a greyed field no longer changes: under it, or as its hint. */
function LockedHint({ id, children }: { id?: string; children: string }) {
  return (
    <span id={id} className={styles.lockedHint}>
      <Icon name="lock" size={10} />
      {children}
    </span>
  );
}

function PronoForm({
  orgId,
  role,
  maxGain,
  sections,
  prono,
}: {
  orgId: string;
  role: Role;
  maxGain: number;
  sections: Section[];
  /** The prono to edit; a new one without it. */
  prono?: PronoDetail;
}) {
  const { t } = useTranslation('pronos');
  const navigate = useNavigate();
  const create = useCreateProno(orgId);
  const edit = useEditProno(orgId, prono?.id ?? '');
  const save = prono ? edit : create;
  const upload = useUpload(orgId);
  const errors = useFormErrors(save.error);
  const uploadErrors = useFormErrors(upload.error);
  const questionId = useId();
  const lockId = useId();

  const [initial] = useState(() => (prono ? valuesOf(prono) : blank(sections, maxGain)));
  const [values, setValues] = useState(initial);
  const set = <K extends keyof Values>(key: K, value: Values[K]) =>
    setValues((current) => ({ ...current, [key]: value }));

  const locked = new Set(prono?.locked_fields ?? []);
  // The prono as the server has it now: what has locked shows as it is.
  const live = prono ? valuesOf(prono) : initial;
  const shown = prono ? withLocked(values, live, locked) : values;
  const { kind, question, options, scheduled, opensAt, closesAt, resultAt, imageId } = shown;
  const changes = prono ? changesOf(initial, shown, locked) : {};
  const unchanged = Boolean(prono) && Object.keys(changes).length === 0;

  const proposing = !prono && role === 'reader';
  const isOpenEnded = kind === 'date' && shown.openEnded;
  // A prono still to open can open later; an open one has opened.
  const schedulable = !prono || prono.state === 'proposed' || prono.state === 'scheduled';
  // An archived section stays its own until another is chosen.
  const sectionChoices =
    prono && !sections.some((s) => s.id === prono.section.id)
      ? [prono.section, ...sections]
      : sections;
  const pronoPath = prono ? `/o/${orgId}/pronos/${prono.id}` : '';
  const closed = prono?.state === 'closed';
  const afterBets = locked.size > 0;
  const lockedHint = (field: LockedField) => (locked.has(field) ? `${lockId}-${field}` : undefined);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (prono) {
      edit.mutate(changes, {
        onSuccess: () => {
          toast.success(t('toast.edited'));
          void navigate(pronoPath);
        },
      });
      return;
    }
    create.mutate(bodyOf(shown), {
      onSuccess: (created) => {
        toast.success(t(proposing ? 'toast.proposed' : 'toast.published'));
        void navigate(`/o/${orgId}/pronos/${created.id}`);
      },
    });
  };

  const setOption = (index: number, value: string) =>
    set(
      'options',
      options.map((o, i) => (i === index ? value : o)),
    );

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <header className={styles.formHead}>
        <Link
          to={prono ? pronoPath : `/o/${orgId}`}
          className={styles.close}
          aria-label={t(prono ? 'edit.close' : 'create.close')}
        >
          <Icon name="cross" size={24} />
        </Link>
        <h1 className={styles.formTitle}>
          {t(prono ? 'edit.title' : proposing ? 'create.titlePropose' : 'create.title')}
        </h1>
        <Chip variant="ink">{t(`create.role.${role}`)}</Chip>
      </header>

      {prono && afterBets && (
        <div className={`${styles.alert} ${styles.lockNote}`} role="note">
          <p>{t(closed ? 'edit.afterBetsClosed' : 'edit.afterBets', { count: prono.bet_count })}</p>
          {closed && <p>{t('edit.closed')}</p>}
        </div>
      )}

      <fieldset className={styles.fieldset}>
        <legend>{t('create.kind')}</legend>
        <Segmented
          label={t('create.kind')}
          options={KINDS.map((value) => ({ value, label: t(`kind.${value}`) }))}
          value={kind}
          onChange={(value) => set('kind', value)}
          disabled={locked.has('kind')}
          describedBy={lockedHint('kind')}
        />
        {locked.has('kind') && <LockedHint id={lockedHint('kind')!}>{t('edit.locked')}</LockedHint>}
      </fieldset>

      <fieldset className={styles.fieldset}>
        <legend>{t('create.section')}</legend>
        <div className={styles.filters}>
          {sectionChoices.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`${styles.filter} ${styles.sectionChip}`}
              aria-pressed={shown.sectionId === s.id}
              onClick={() => set('sectionId', s.id)}
            >
              {s.name.toUpperCase()}
            </button>
          ))}
        </div>
      </fieldset>

      <div className={styles.fieldset}>
        <label htmlFor={questionId} className={styles.label}>
          {t('create.question')}
        </label>
        <textarea
          id={questionId}
          className={`${styles.textarea} ${styles.questionInput}`}
          rows={2}
          value={question}
          maxLength={QUESTION_MAX}
          placeholder={t('create.questionPlaceholder')}
          onChange={(event) => set('question', event.target.value)}
          aria-invalid={errors.field('question') ? true : undefined}
          aria-describedby={`${questionId}-count`}
          required
        />
        <span id={`${questionId}-count`} className={styles.counter}>
          {t('create.counter', { count: question.length })}
        </span>
        {errors.field('question') && (
          <span role="alert" className={styles.alert}>
            {errors.field('question')}
          </span>
        )}
      </div>

      {kind === 'choice' && (
        <fieldset
          className={styles.fieldset}
          disabled={locked.has('options')}
          aria-describedby={lockedHint('options')}
        >
          <legend>{t('create.options', { count: options.length })}</legend>
          {options.map((option, index) => (
            <div key={index} className={styles.optionRow}>
              <input
                aria-label={t('create.option', { n: index + 1 })}
                value={option}
                maxLength={80}
                onChange={(event) => setOption(index, event.target.value)}
              />
              {!locked.has('options') && (
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label={t('create.removeOption', { n: index + 1 })}
                  disabled={options.length <= 2}
                  onClick={() =>
                    set(
                      'options',
                      options.filter((_, i) => i !== index),
                    )
                  }
                >
                  <Icon name="cross" size={24} />
                </button>
              )}
            </div>
          ))}
          {locked.has('options') ? (
            <LockedHint id={lockedHint('options')!}>{t('edit.locked')}</LockedHint>
          ) : (
            <button
              type="button"
              className={styles.addOption}
              onClick={() => set('options', [...options, ''])}
            >
              <Icon name="plus" size={12} /> {t('create.addOption')}
            </button>
          )}
          {errors.field('options') && (
            <span role="alert" className={styles.alert}>
              {errors.field('options')}
            </span>
          )}
        </fieldset>
      )}
      {kind === 'yes_no' && <p className={styles.meta}>{t('create.yesNo')}</p>}
      {kind === 'number' && (
        <Field
          label={t('create.unit')}
          placeholder={t('create.unitPlaceholder')}
          value={shown.unit}
          maxLength={20}
          onChange={(event) => set('unit', event.target.value)}
          disabled={locked.has('number_unit')}
          hint={locked.has('number_unit') ? <LockedHint>{t('edit.locked')}</LockedHint> : undefined}
          error={errors.field('number_unit')}
        />
      )}
      <div className={styles.pair}>
        {!isOpenEnded && (
          <Field
            label={t('create.closesAt')}
            type="datetime-local"
            value={closesAt}
            // After the first bet, the closing only moves later.
            min={afterBets ? live.closesAt : undefined}
            onChange={(event) => set('closesAt', event.target.value)}
            disabled={locked.has('closes_at')}
            hint={
              locked.has('closes_at') ? (
                <LockedHint>{t('edit.lockedClosed')}</LockedHint>
              ) : afterBets ? (
                t('edit.laterOnly')
              ) : undefined
            }
            error={errors.field('closes_at')}
            required
          />
        )}
        <div className={styles.fieldset}>
          <span className={styles.label}>{t('create.gain', { max: maxGain })}</span>
          <Stepper
            label={t('create.gainLabel')}
            value={shown.gain}
            onChange={(value) => set('gain', value)}
            min={0}
            max={maxGain}
            step={GAIN_STEP}
            block
            disabled={locked.has('base_gain')}
            describedBy={lockedHint('base_gain')}
          />
          {locked.has('base_gain') && (
            <LockedHint id={lockedHint('base_gain')!}>{t('edit.locked')}</LockedHint>
          )}
        </div>
      </div>

      {(kind === 'date' || schedulable) && (
        <div className={styles.switches}>
          {kind === 'date' && (
            <SwitchRow
              checked={shown.openEnded}
              onChange={(value) => set('openEnded', value)}
              label={t('create.openEnded')}
              hint={
                locked.has('open_ended') ? (
                  <LockedHint>{t('edit.locked')}</LockedHint>
                ) : (
                  t('create.openEndedHint')
                )
              }
              disabled={locked.has('open_ended')}
            />
          )}
          {schedulable && (
            <SwitchRow
              checked={scheduled}
              onChange={(value) => set('scheduled', value)}
              label={t('create.schedule')}
              hint={t('create.scheduleHint')}
            />
          )}
        </div>
      )}
      {schedulable && scheduled && (
        <Field
          label={t('create.opensAt')}
          type="datetime-local"
          value={opensAt}
          max={isOpenEnded ? undefined : closesAt}
          onChange={(event) => set('opensAt', event.target.value)}
          error={errors.field('opens_at')}
        />
      )}
      <Field
        label={t('create.resultAt')}
        type="datetime-local"
        value={resultAt}
        min={isOpenEnded ? undefined : closesAt}
        onChange={(event) => set('resultAt', event.target.value)}
        error={errors.field('result_expected_at')}
      />

      <Field
        label={t('create.link')}
        type="url"
        placeholder="https://"
        value={shown.link}
        onChange={(event) => set('link', event.target.value)}
        error={errors.field('link_url')}
      />

      <div className={styles.fieldset}>
        <Field
          label={t('create.image')}
          hint={t('create.imageHint')}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) upload.mutate(file, { onSuccess: (image) => set('imageId', image.id) });
          }}
          error={uploadErrors.message}
        />
        {upload.isPending && <p role="status">{t('create.uploading')}</p>}
        {imageId && (
          <>
            <img src={`/api/orgs/${orgId}/uploads/${imageId}`} alt="" className={styles.preview} />
            <Button variant="link" onClick={() => set('imageId', null)}>
              {t('create.imageRemove')}
            </Button>
          </>
        )}
      </div>

      {(errors.field('base_gain') ??
        errors.field('section_id') ??
        errors.field('kind') ??
        errors.field('open_ended')) && (
        <p role="alert" className={styles.alert}>
          {errors.field('base_gain') ??
            errors.field('section_id') ??
            errors.field('kind') ??
            errors.field('open_ended')}
        </p>
      )}
      <footer className={styles.formFoot}>
        <Button type="submit" block disabled={save.isPending || upload.isPending || unchanged}>
          {t(prono ? 'edit.submit' : proposing ? 'create.submitPropose' : 'create.submit')}
        </Button>
        <p className={styles.note}>
          {t(prono ? 'edit.foot' : proposing ? 'create.footPropose' : 'create.foot')}
        </p>
      </footer>
    </form>
  );
}

export function CreatePronoPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const sections = useSections(orgId);
  if (!org.data || !sections.data) return <p role="status">{t('common:shell.loading')}</p>;
  return (
    <PronoForm
      orgId={orgId}
      role={org.data.my_membership.role}
      maxGain={org.data.max_base_gain}
      sections={sections.data}
    />
  );
}

/** « Modifier » on a prono's page; one that no longer changes leads back to its page. */
export function EditPronoPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '', pronoId = '' } = useParams();
  const org = useOrg(orgId);
  const sections = useSections(orgId);
  const prono = useProno(orgId, pronoId);
  if (!org.data || !sections.data || !prono.data) {
    return <p role="status">{t('common:shell.loading')}</p>;
  }
  if (!prono.data.can_edit) return <Navigate to={`/o/${orgId}/pronos/${pronoId}`} replace />;
  return (
    <PronoForm
      key={prono.data.id}
      orgId={orgId}
      role={org.data.my_membership.role}
      maxGain={org.data.max_base_gain}
      sections={sections.data}
      prono={prono.data}
    />
  );
}
