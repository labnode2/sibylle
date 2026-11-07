// The installed app (added to the home screen from Chrome on Android or Safari on an iPhone, or
// installed on a computer): the first time it opens on a newsroom, a pop-up offers to turn push
// notifications on. Its button asks the browser, whose own question only comes after a click.
// Once answered on a device, it does not come back there: the settings and the offer after a
// bet remain.
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Kicker } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import styles from './notifications.module.css';
import { isStandalone, usePush } from './usePush';

export const DONE_KEY = 'sibylle.push-dialog.done';

function wasDone(): boolean {
  try {
    return localStorage.getItem(DONE_KEY) === '1';
  } catch {
    return false;
  }
}

function Offer({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation('notifications');
  const push = usePush();
  const { status } = push;
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const textId = useId();

  // It opens once this device can say yes, and closes once the browser has the answer. Already
  // on, or refused in the browser: nothing to offer on this device. Without push in the browser
  // or on the server, it waits for a next opening.
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (status === 'off' && !element.open) element.showModal();
    if (status === 'on' || status === 'denied') {
      if (element.open) element.close();
      else onDone();
    }
  }, [status, onDone]);

  // Escape, the back gesture of a phone or « Plus tard » close it too: the offer was answered.
  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby={titleId}
      aria-describedby={textId}
      onClose={onDone}
    >
      <div className={styles.ball} aria-hidden="true">
        {/* Mounted with the opening, so that its single loop is seen. */}
        {status === 'off' && <CrystalBall size={64} loops={1} />}
      </div>
      <Kicker tone="indigo">{t('installed.kicker')}</Kicker>
      <h2 id={titleId} className={styles.dialogTitle}>
        {t('installed.title')}
      </h2>
      <p id={textId} className={styles.dialogText}>
        {t('installed.text')}
      </p>
      <p className={styles.note}>{t('installed.note')}</p>
      <div className={styles.dialogActions}>
        <Button onClick={() => void push.enable()} disabled={push.busy}>
          {t('installed.enable')}
        </Button>
        <Button variant="secondary" onClick={() => dialog.current?.close()}>
          {t('installed.later')}
        </Button>
      </div>
    </dialog>
  );
}

/** The installed app's offer of notifications, once per device; nothing in a browser's tab. */
export function InstalledPushDialog() {
  const [pending, setPending] = useState(() => isStandalone() && !wasDone());
  const done = useCallback(() => {
    try {
      localStorage.setItem(DONE_KEY, '1');
    } catch {
      // Private browsing: the offer comes back at the next opening.
    }
    setPending(false);
  }, []);
  return pending ? <Offer onDone={done} /> : null;
}
