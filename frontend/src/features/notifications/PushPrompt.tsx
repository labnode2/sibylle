// After a bet: an offer to turn push notifications on, until it is accepted or set aside.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Card, Kicker } from '../../ui/components';
import styles from './notifications.module.css';
import { usePush } from './usePush';

const DISMISSED_KEY = 'sibylle.push-prompt.dismissed';

function wasDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_KEY) === '1';
  } catch {
    return false;
  }
}

export function PushPrompt() {
  const { t } = useTranslation('notifications');
  const push = usePush();
  const [dismissed, setDismissed] = useState(wasDismissed);
  if (dismissed || push.status !== 'off') return null;

  const later = () => {
    try {
      localStorage.setItem(DISMISSED_KEY, '1');
    } catch {
      // Private browsing: the offer simply comes back next time.
    }
    setDismissed(true);
  };

  return (
    <Card className={styles.prompt} shadow={0} aria-label={t('prompt.kicker')}>
      <Kicker tone="indigo">{t('prompt.kicker')}</Kicker>
      <p className={styles.text}>{t('prompt.text')}</p>
      <div className={styles.actions}>
        <Button onClick={() => void push.enable()} disabled={push.busy}>
          {t('prompt.enable')}
        </Button>
        <Button variant="secondary" onClick={later}>
          {t('prompt.later')}
        </Button>
      </div>
      {push.failed && (
        <p role="alert" className={styles.alert}>
          {t('device.failed')}
        </p>
      )}
    </Card>
  );
}
