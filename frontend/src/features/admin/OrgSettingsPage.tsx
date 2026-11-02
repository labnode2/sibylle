// The card and the laurels (canvas G-Orga): logo, background and title; the gain ceiling, the
// starting balance and the early-bird bonus; the editor's note, the charter and the sections.
import { useState, type FormEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import type { Org } from '../../api/types';
import { Button, Card, Field, Icon, Kicker, Stepper } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useContent, useOrg } from '../orgs/api';
import { AvatarPicker, BackgroundPicker } from '../orgs/pickers';
import { useSections } from '../pronos/api';
import { useSectionActions, useUpdateOrg } from './api';
import styles from './admin.module.css';

function Setting({ label, hint, children }: { label: string; hint: string; children: ReactNode }) {
  return (
    <div className={styles.setting}>
      <div className={styles.settingText}>
        <span className={styles.label}>{label}</span>
        <span className={styles.hint}>{hint}</span>
      </div>
      {children}
    </div>
  );
}

function SettingsForm({ orgId, org }: { orgId: string; org: Org }) {
  const { t } = useTranslation('admin');
  const content = useContent();
  const update = useUpdateOrg(orgId);
  const errors = useFormErrors(update.error);
  const [title, setTitle] = useState(org.title);
  const [background, setBackground] = useState(org.background_key);
  const [logo, setLogo] = useState(org.logo);
  const [maxGain, setMaxGain] = useState(org.max_base_gain);
  const [starting, setStarting] = useState(org.starting_balance);
  const [earlyPct, setEarlyPct] = useState(org.early_bird_pct);
  const [earlyCount, setEarlyCount] = useState(org.early_bird_count);
  const [note, setNote] = useState(org.editor_note ?? '');
  const [charter, setCharter] = useState(org.charter);
  const [saved, setSaved] = useState(false);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    update.mutate(
      {
        title: title.trim(),
        background_key: background,
        logo,
        max_base_gain: maxGain,
        starting_balance: starting,
        early_bird_pct: earlyPct,
        early_bird_count: earlyCount,
        editor_note: note.trim() || null,
        charter: charter.trim(),
      },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <form className={styles.page} onSubmit={submit} noValidate>
      <Card className={styles.panel} aria-label={t('card.title')}>
        <h2 className={styles.heading}>{t('card.title')}</h2>
        <Field
          label={t('card.name')}
          value={title}
          maxLength={40}
          onChange={(event) => setTitle(event.target.value)}
          error={errors.field('title')}
        />
        <span id="admin-logo" className={styles.label}>
          {t('card.logo')}
        </span>
        <AvatarPicker
          templates={content.data?.logos ?? []}
          value={logo ?? null}
          onChange={setLogo}
          labelId="admin-logo"
        />
        <span id="admin-background" className={styles.label}>
          {t('card.background')}
        </span>
        <BackgroundPicker
          keys={content.data?.backgrounds ?? []}
          value={background}
          onChange={setBackground}
          labelId="admin-background"
        />
      </Card>

      <Card className={styles.panel} aria-label={t('laurels.title')}>
        <h2 className={styles.heading}>{t('laurels.title')}</h2>
        <Setting label={t('laurels.maxGain')} hint={t('laurels.maxGainHint')}>
          <Stepper
            label={t('laurels.maxGain')}
            value={maxGain}
            onChange={setMaxGain}
            min={0}
            max={500}
            step={5}
          />
        </Setting>
        <Setting label={t('laurels.starting')} hint={t('laurels.startingHint')}>
          <Stepper
            label={t('laurels.starting')}
            value={starting}
            onChange={setStarting}
            min={0}
            max={10_000}
            step={10}
          />
        </Setting>
        <Setting label={t('laurels.earlyPct')} hint={t('laurels.earlyPctHint')}>
          <Stepper
            label={t('laurels.earlyPct')}
            value={earlyPct}
            onChange={setEarlyPct}
            min={0}
            max={100}
            step={5}
            format={(value) => `${value} %`}
          />
        </Setting>
        <Setting label={t('laurels.earlyCount')} hint={t('laurels.earlyCountHint')}>
          <Stepper
            label={t('laurels.earlyCount')}
            value={earlyCount}
            onChange={setEarlyCount}
            min={0}
            max={50}
          />
        </Setting>
      </Card>

      <Card className={styles.panel} aria-label={t('words.title')}>
        <h2 className={styles.heading}>{t('words.title')}</h2>
        <label className={styles.block}>
          <span className={styles.label}>{t('words.note')}</span>
          <textarea
            className={styles.textarea}
            value={note}
            maxLength={500}
            onChange={(event) => setNote(event.target.value)}
          />
        </label>
        <label className={styles.block}>
          <span className={styles.label}>{t('words.charter')}</span>
          <textarea
            className={styles.textarea}
            rows={8}
            value={charter}
            onChange={(event) => setCharter(event.target.value)}
          />
        </label>
      </Card>

      {(errors.message || errors.field('charter')) && (
        <p role="alert" className={styles.alert}>
          {errors.message ?? errors.field('charter')}
        </p>
      )}
      {saved && <p role="status">{t('saved')}</p>}
      <Button type="submit" disabled={update.isPending}>
        {t('save')}
      </Button>
    </form>
  );
}

function SectionsPanel({ orgId }: { orgId: string }) {
  const { t } = useTranslation('admin');
  const sections = useSections(orgId);
  const { create, update, remove } = useSectionActions(orgId);
  const errors = useFormErrors(create.error ?? update.error ?? remove.error);
  const [name, setName] = useState('');
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null);
  const list = sections.data ?? [];

  const add = (event: FormEvent) => {
    event.preventDefault();
    create.mutate(name.trim(), { onSuccess: () => setName('') });
  };

  return (
    <Card className={styles.panel} aria-label={t('sections.title')}>
      <h2 className={styles.heading}>{t('sections.title')}</h2>
      <p className={styles.hint}>{t('sections.hint')}</p>
      <ul className={styles.rows}>
        {list.map((section, index) => (
          <li key={section.id} className={styles.row}>
            {editing?.id === section.id ? (
              <form
                className={styles.inline}
                onSubmit={(event) => {
                  event.preventDefault();
                  update.mutate(
                    { sectionId: section.id, name: editing.name.trim() },
                    { onSuccess: () => setEditing(null) },
                  );
                }}
              >
                <input
                  className={styles.input}
                  aria-label={t('sections.rename', { name: section.name })}
                  value={editing.name}
                  maxLength={40}
                  onChange={(event) => setEditing({ id: section.id, name: event.target.value })}
                />
                <Button type="submit" variant="secondary">
                  {t('sections.ok')}
                </Button>
              </form>
            ) : (
              <span className={styles.rowName}>{section.name}</span>
            )}
            <div className={styles.inline}>
              <button
                type="button"
                className={styles.iconButton}
                aria-label={t('sections.up', { name: section.name })}
                disabled={index === 0}
                onClick={() => update.mutate({ sectionId: section.id, position: index - 1 })}
              >
                <Icon name="chevronLeft" />
              </button>
              <button
                type="button"
                className={styles.iconButton}
                aria-label={t('sections.down', { name: section.name })}
                disabled={index === list.length - 1}
                onClick={() => update.mutate({ sectionId: section.id, position: index + 1 })}
              >
                <Icon name="chevronRight" />
              </button>
              <Button
                variant="link"
                onClick={() => setEditing({ id: section.id, name: section.name })}
              >
                {t('sections.edit')}
              </Button>
              {list.length > 1 && (
                <Button variant="link" onClick={() => remove.mutate(section.id)}>
                  {t('sections.remove')}
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
      <form className={styles.inline} onSubmit={add} noValidate>
        <input
          className={styles.input}
          aria-label={t('sections.new')}
          placeholder={t('sections.newPlaceholder')}
          value={name}
          maxLength={40}
          onChange={(event) => setName(event.target.value)}
        />
        <Button type="submit" variant="secondary" disabled={!name.trim() || create.isPending}>
          {t('sections.add')}
        </Button>
      </form>
      {(errors.field('name') || errors.message) && (
        <p role="alert" className={styles.alert}>
          {errors.field('name') ?? errors.message}
        </p>
      )}
    </Card>
  );
}

export function OrgSettingsPage() {
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  if (!org.data) return null;
  return (
    <>
      <Kicker tone="indigo">{org.data.title.toUpperCase()}</Kicker>
      <SettingsForm key={org.data.id} orgId={orgId} org={org.data} />
      <SectionsPanel orgId={orgId} />
    </>
  );
}
