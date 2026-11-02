// Publishing a prono (canvas G-Créer): type, section, question, answers, dates and fixed gain.
// Journalists and the editor publish directly; readers' proposals come with US5.
import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { fromParisInput, parisDayAt } from '../../i18n';
import { Button, Field, Icon, Stepper, Switch } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { useCreateProno, useSections, useUpload, type PronoIn } from './api';
import styles from './pronos.module.css';

type Kind = PronoIn['kind'];

const KINDS: Kind[] = ['choice', 'yes_no', 'number', 'date'];
const QUESTION_MAX = 200;
const GAIN_STEP = 5;

const toIso = (value: string) => (value ? fromParisInput(value).toISOString() : null);

export function CreatePronoPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '' } = useParams();
  const navigate = useNavigate();
  const org = useOrg(orgId);
  const sections = useSections(orgId);
  const create = useCreateProno(orgId);
  const upload = useUpload(orgId);
  const errors = useFormErrors(create.error);
  const uploadErrors = useFormErrors(upload.error);
  const questionId = useId();

  const [kind, setKind] = useState<Kind>('choice');
  const [sectionId, setSectionId] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [options, setOptions] = useState(['', '']);
  const [unit, setUnit] = useState('');
  const [openEnded, setOpenEnded] = useState(false);
  const [link, setLink] = useState('');
  const [imageId, setImageId] = useState<string | null>(null);
  const [scheduled, setScheduled] = useState(false);
  const [opensAt, setOpensAt] = useState('');
  // Tomorrow at 18:00, Paris time: a sensible default closing time.
  const [closesAt, setClosesAt] = useState(() => parisDayAt(1, 18));
  const [resultAt, setResultAt] = useState('');
  const [gain, setGain] = useState<number | null>(null);

  if (!org.data || !sections.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;
  if (me.role === 'reader') return <p className={styles.alert}>{t('create.readerSoon')}</p>;

  const maxGain = org.data.max_base_gain;
  const baseGain = gain ?? Math.min(20, maxGain);
  const section = sectionId ?? sections.data[0]?.id ?? '';
  const isOpenEnded = kind === 'date' && openEnded;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const body: PronoIn = {
      kind,
      question: question.trim(),
      section_id: section,
      options: kind === 'choice' ? options.map((o) => o.trim()).filter(Boolean) : [],
      base_gain: baseGain,
      link_url: link.trim() || null,
      image_id: imageId,
      opens_at: scheduled ? toIso(opensAt) : null,
      closes_at: isOpenEnded ? null : toIso(closesAt),
      open_ended: isOpenEnded,
      result_expected_at: toIso(resultAt),
      number_unit: kind === 'number' ? unit.trim() || null : null,
    };
    create.mutate(body, {
      onSuccess: (prono) => void navigate(`/o/${orgId}/pronos/${prono.id}`),
    });
  };

  const setOption = (index: number, value: string) =>
    setOptions((current) => current.map((o, i) => (i === index ? value : o)));

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <h1 className={styles.question}>{t('create.title')}</h1>

      <fieldset className={styles.fieldset}>
        <legend>{t('create.kind')}</legend>
        <div className={styles.filters}>
          {KINDS.map((value) => (
            <button
              key={value}
              type="button"
              className={styles.filter}
              aria-pressed={kind === value}
              onClick={() => setKind(value)}
            >
              {t(`kind.${value}`)}
            </button>
          ))}
        </div>
      </fieldset>

      <fieldset className={styles.fieldset}>
        <legend>{t('create.section')}</legend>
        <div className={styles.filters}>
          {sections.data.map((s) => (
            <button
              key={s.id}
              type="button"
              className={styles.filter}
              aria-pressed={section === s.id}
              onClick={() => setSectionId(s.id)}
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
          className={styles.textarea}
          value={question}
          maxLength={QUESTION_MAX}
          placeholder={t('create.questionPlaceholder')}
          onChange={(event) => setQuestion(event.target.value)}
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
        <fieldset className={styles.fieldset}>
          <legend>{t('create.options')}</legend>
          {options.map((option, index) => (
            <div key={index} className={styles.optionRow}>
              <input
                aria-label={t('create.option', { n: index + 1 })}
                value={option}
                maxLength={80}
                onChange={(event) => setOption(index, event.target.value)}
              />
              {options.length > 2 && (
                <button
                  type="button"
                  className={styles.iconButton}
                  aria-label={t('create.removeOption', { n: index + 1 })}
                  onClick={() => setOptions((current) => current.filter((_, i) => i !== index))}
                >
                  <Icon name="cross" size={12} />
                </button>
              )}
            </div>
          ))}
          <Button variant="secondary" onClick={() => setOptions((current) => [...current, ''])}>
            <Icon name="plus" size={12} /> {t('create.addOption')}
          </Button>
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
          value={unit}
          maxLength={20}
          onChange={(event) => setUnit(event.target.value)}
        />
      )}
      {kind === 'date' && (
        <div className={styles.switchRow}>
          <span>{t('create.openEnded')}</span>
          <Switch checked={openEnded} onChange={setOpenEnded} label={t('create.openEnded')} />
        </div>
      )}

      <div className={styles.switchRow}>
        <span>{t('create.schedule')}</span>
        <Switch checked={scheduled} onChange={setScheduled} label={t('create.schedule')} />
      </div>
      <div className={styles.row}>
        {scheduled && (
          <Field
            label={t('create.opensAt')}
            type="datetime-local"
            value={opensAt}
            onChange={(event) => setOpensAt(event.target.value)}
            error={errors.field('opens_at')}
          />
        )}
        {!isOpenEnded && (
          <Field
            label={t('create.closesAt')}
            type="datetime-local"
            value={closesAt}
            onChange={(event) => setClosesAt(event.target.value)}
            error={errors.field('closes_at')}
            required
          />
        )}
        <Field
          label={t('create.resultAt')}
          type="datetime-local"
          value={resultAt}
          onChange={(event) => setResultAt(event.target.value)}
          error={errors.field('result_expected_at')}
        />
      </div>

      <Field
        label={t('create.link')}
        type="url"
        placeholder="https://"
        value={link}
        onChange={(event) => setLink(event.target.value)}
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
            if (file) upload.mutate(file, { onSuccess: (image) => setImageId(image.id) });
          }}
          error={uploadErrors.message}
        />
        {upload.isPending && <p role="status">{t('create.uploading')}</p>}
        {imageId && (
          <>
            <img src={`/api/orgs/${orgId}/uploads/${imageId}`} alt="" className={styles.preview} />
            <Button variant="link" onClick={() => setImageId(null)}>
              {t('create.imageRemove')}
            </Button>
          </>
        )}
      </div>

      <div className={styles.switchRow}>
        <span className={styles.label}>{t('create.gain', { max: maxGain })}</span>
        <Stepper
          label={t('create.gainLabel')}
          value={baseGain}
          onChange={setGain}
          min={0}
          max={maxGain}
          step={GAIN_STEP}
        />
      </div>

      {(errors.message || errors.field('base_gain') || errors.field('section_id')) && (
        <p role="alert" className={styles.alert}>
          {errors.message ?? errors.field('base_gain') ?? errors.field('section_id')}
        </p>
      )}
      <Button type="submit" block disabled={create.isPending || upload.isPending}>
        {t('create.submit')}
      </Button>
    </form>
  );
}
