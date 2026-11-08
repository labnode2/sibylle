// The editor's invitations: a link with a number of places and an expiry (its URL shown once),
// a nominative invitation by e-mail, each with the role people get on joining, and the
// newsroom's access code (which lets people in as readers).
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Chip, Field, Kicker, Stepper } from '../../ui/components';
import { CopyButton } from '../../ui/CopyButton';
import { toast } from '../../ui/Toaster';
import { useFormErrors } from '../forms';
import { useInvite } from '../orgs/api';
import type { Role } from './api';
import styles from './admin.module.css';

const DURATIONS = [1, 7, 30];
const ROLES: Role[] = ['reader', 'journalist', 'editor'];

function RoleSelect({ value, onChange }: { value: Role; onChange: (role: Role) => void }) {
  const { t } = useTranslation('orgs');
  return (
    <label className={`${styles.select} ${styles[`role_${value}`]}`}>
      <span className="visually-hidden">{t('invite.role')}</span>
      <select value={value} onChange={(e) => onChange(e.target.value as Role)}>
        {ROLES.map((role) => (
          <option key={role} value={role}>
            {t(`invite.roles.${role}`)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function InvitePanel({ orgId, accessCode }: { orgId: string; accessCode: string | null }) {
  const { t } = useTranslation('orgs');
  const invite = useInvite(orgId);
  const errors = useFormErrors(invite.error);
  const [places, setPlaces] = useState(10);
  const [days, setDays] = useState(7);
  const [linkRole, setLinkRole] = useState<Role>('reader');
  const [email, setEmail] = useState('');
  const [emailRole, setEmailRole] = useState<Role>('reader');
  const [url, setUrl] = useState<string | null>(null);

  const createLink = () => {
    const expires = new Date(Date.now() + days * 24 * 3600 * 1000).toISOString();
    invite.mutate(
      { kind: 'link', max_uses: places, expires_at: expires, role: linkRole },
      {
        onSuccess: (created) => {
          setUrl(created.url ?? null);
          toast.success(t('invite.created'));
        },
      },
    );
  };

  const sendEmail = (event: FormEvent) => {
    event.preventDefault();
    invite.mutate(
      { kind: 'email', email, role: emailRole },
      {
        onSuccess: () => {
          toast.success(t('invite.sent', { email }));
          setEmail('');
        },
      },
    );
  };

  return (
    <section className={styles.panel} aria-label={t('invite.title')}>
      <h2 className={styles.heading}>{t('invite.title')}</h2>

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
          <RoleSelect value={linkRole} onChange={setLinkRole} />
        </div>
        <Button onClick={createLink} disabled={invite.isPending}>
          {t('invite.create')}
        </Button>
        {url && (
          <div className={styles.result}>
            <Field label={t('invite.url')} value={url} readOnly hint={t('invite.once')} />
            <CopyButton text={url} label={t('invite.copy')} />
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
        <div className={styles.inline}>
          <RoleSelect value={emailRole} onChange={setEmailRole} />
        </div>
        <Button type="submit" variant="secondary" disabled={invite.isPending || !email}>
          {t('invite.send')}
        </Button>
      </form>

      {accessCode && (
        <div className={styles.block}>
          <Kicker tone="indigo">{t('invite.code')}</Kicker>
          <div className={styles.inline}>
            <Chip variant="grey">{accessCode}</Chip>
            <CopyButton text={accessCode} label={t('invite.copy')} />
          </div>
        </div>
      )}
    </section>
  );
}
