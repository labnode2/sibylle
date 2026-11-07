// The notification settings: this device's push subscription, then four kinds × two channels
// (push, e-mail); the e-mail ones wait for a confirmed address, since no notification e-mail
// leaves before. Notification e-mails link here (`#notifications`).
import { useEffect, useId, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router';

import { Button, Switch } from '../../ui/components';
import { useResendVerification } from '../auth/api';
import { CHANNELS, KINDS, useNotificationPrefs, useSetNotificationPref } from './api';
import styles from './notifications.module.css';
import { usePush } from './usePush';

function PushDevice() {
  const { t } = useTranslation('notifications');
  const push = usePush();
  return (
    <div className={styles.device}>
      <span className={styles.label}>{t('device.label')}</span>
      <p className={styles.text} role="status">
        {t(`device.${push.status}`)}
      </p>
      {push.status === 'off' && (
        <Button onClick={() => void push.enable()} disabled={push.busy}>
          {t('device.enable')}
        </Button>
      )}
      {push.status === 'on' && (
        <Button variant="secondary" onClick={() => void push.disable()} disabled={push.busy}>
          {t('device.disable')}
        </Button>
      )}
    </div>
  );
}

/** An unconfirmed address: no notification e-mail before it is confirmed, and the address check
 *  that Keycloak sends again on demand (FR-008). */
function Unconfirmed() {
  const { t } = useTranslation('notifications');
  const resend = useResendVerification();
  return (
    <div className={styles.unconfirmed}>
      <p className={styles.note}>{t('unverified')}</p>
      <Button variant="secondary" onClick={() => resend.mutate()} disabled={resend.isPending}>
        {t('resend')}
      </Button>
    </div>
  );
}

export function NotificationPrefs({ emailVerified }: { emailVerified: boolean }) {
  const { t } = useTranslation('notifications');
  const prefs = useNotificationPrefs();
  const setPref = useSetNotificationPref();
  const titleId = useId();
  const section = useRef<HTMLElement>(null);
  const { hash } = useLocation();
  const loaded = Boolean(prefs.data);

  // Arriving from the link of an e-mail: straight to the settings.
  useEffect(() => {
    if (hash === '#notifications' && loaded) section.current?.scrollIntoView();
  }, [hash, loaded]);

  const enabled = (kind: string, channel: string) =>
    prefs.data?.find((p) => p.type === kind && p.channel === channel)?.enabled ?? true;

  return (
    <section id="notifications" ref={section} className={styles.section} aria-labelledby={titleId}>
      <h2 id={titleId} className={styles.title}>
        {t('title')}
      </h2>
      <p className={styles.text}>{t('intro')}</p>
      <PushDevice />
      {!emailVerified && <Unconfirmed />}
      {prefs.data && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" className={styles.label}>
                {t('kind')}
              </th>
              {CHANNELS.map((channel) => (
                <th key={channel} scope="col" className={styles.label}>
                  {t(`channels.${channel}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {KINDS.map((kind) => (
              <tr key={kind}>
                <th scope="row">
                  <span className={styles.kind}>{t(`kinds.${kind}.label`)}</span>
                  <span className={styles.hint}>{t(`kinds.${kind}.hint`)}</span>
                </th>
                {CHANNELS.map((channel) => (
                  <td key={channel}>
                    <Switch
                      checked={enabled(kind, channel)}
                      label={t('switch', {
                        kind: t(`kinds.${kind}.label`),
                        channel: t(`channels.${channel}`).toLowerCase(),
                      })}
                      disabled={channel === 'email' && !emailVerified}
                      onChange={(on) => setPref.mutate({ type: kind, channel, enabled: on })}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
