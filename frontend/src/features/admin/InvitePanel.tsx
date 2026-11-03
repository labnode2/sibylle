// The editor's invitations: a link with a number of places and an expiry (its URL shown once),
// a nominative invitation by e-mail, and the newsroom's access code.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Chip, Field, Icon, Kicker, Stepper } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useInvite } from '../orgs/api';
import styles from './admin.module.css';

const DURATIONS = [1, 7, 30];

function CopyButton({ text }: { text: string }) {
  const { t } = useTranslation('orgs');
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setCopied(true));
      }}
    >
      <Icon name={copied ? 'check' : 'copy'} />
      {copied ? t('invite.copied') : t('invite.copy')}
    </Button>
  );
}

export function InvitePanel({ orgId, accessCode }: { orgId: string; accessCode: string | null }) {
  const { t } = useTranslation('orgs');
  const invite = useInvite(orgId);
  const errors = useFormErrors(invite.error);
  const [places, setPlaces] = useState(10);
  const [days, setDays] = useState(7);
  const [email, setEmail] = useState('');
  const [url, setUrl] = useState<string | null>(null);
  const [sentTo, setSentTo] = useState<string | null>(null);

  const createLink = () => {
    const expires = new Date(Date.now() + days * 24 * 3600 * 1000).toISOString();
    invite.mutate(
      { kind: 'link', max_uses: places, expires_at: expires },
      { onSuccess: (created) => setUrl(created.url ?? null) },
    );
  };

  const sendEmail = (event: FormEvent) => {
    event.preventDefault();
    invite.mutate(
      { kind: 'email', email },
      {
        onSuccess: () => {
          setSentTo(email);
          setEmail('');
        },
      },
    );
  };

  return (
    <section className={styles.panel} aria-label={t('invite.title')}>
      <h2 className={styles.heading}>{t('invite.title')}</h2>
      {errors.message && (
        <p className={styles.alert} role="alert">
          {errors.message}
        </p>
      )}

      <div className={styles.block}>
        <Kicker tone="indigo">{t('invite.link')}</Kicker>
        <div className={styles.inline}>
          <Stepper
            label={t('invite.places')}
            value={places}
            onChange={setPlaces}
            min={1}
            max={100}
            format={(n) => t('invite.placesValue', { count: n })}
          />
          <label className={styles.select}>
            <span className="visually-hidden">{t('invite.duration')}</span>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
              {DURATIONS.map((d) => (
                <option key={d} value={d}>
                  {t('invite.days', { count: d })}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Button onClick={createLink} disabled={invite.isPending}>
          {t('invite.create')}
        </Button>
        {url && (
          <div className={styles.result} role="status">
            <Field label={t('invite.url')} value={url} readOnly hint={t('invite.once')} />
            <CopyButton text={url} />
          </div>
        )}
      </div>

      <form className={styles.block} onSubmit={sendEmail} noValidate>
        <Kicker tone="indigo">{t('invite.email')}</Kicker>
        <Field
          label={t('invite.address')}
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.field('email')}
        />
        <Button type="submit" variant="secondary" disabled={invite.isPending || !email}>
          {t('invite.send')}
        </Button>
        {sentTo && <p role="status">{t('invite.sent', { email: sentTo })}</p>}
      </form>

      {accessCode && (
        <div className={styles.block}>
          <Kicker tone="indigo">{t('invite.code')}</Kicker>
          <div className={styles.inline}>
            <Chip variant="grey">{accessCode}</Chip>
            <CopyButton text={accessCode} />
          </div>
        </div>
      )}
    </section>
  );
}
