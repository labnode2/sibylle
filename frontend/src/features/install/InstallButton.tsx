// « Installer l'appli », in a browser's tab only: beside the newsroom's card on a phone's une, in
// the date bar on a computer. Where the browser has its own install dialog (Chrome, Edge), the
// click opens it; on a phone without one (Safari on an iPhone, Firefox), a short guide in three
// steps. A card in the middle of a computer's screen, a sheet rising from the bottom of a
// phone's, like the welcome.
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Icon, Kicker } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import type { IconName } from '../../ui/icons';
import { useInstall } from './install';
import styles from './install.module.css';

type GuidePlatform = 'ios' | 'android';

const STEPS: Record<GuidePlatform, { key: string; icon: IconName }[]> = {
  ios: [
    { key: 'share', icon: 'share' },
    { key: 'home', icon: 'plus' },
    { key: 'add', icon: 'check' },
  ],
  android: [
    { key: 'menu', icon: 'menu' },
    { key: 'install', icon: 'download' },
    { key: 'confirm', icon: 'check' },
  ],
};

function InstallGuide({ platform, onClose }: { platform: GuidePlatform; onClose: () => void }) {
  const { t } = useTranslation('install');
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal();
  }, []);

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId} onClose={onClose}>
      <div className={styles.art} aria-hidden="true">
        <CrystalBall size={56} loops={1} />
      </div>
      <Kicker tone="indigo">{t(`${platform}.kicker`)}</Kicker>
      <h2 id={titleId} className={styles.title}>
        {t('guide.title')}
      </h2>
      <p className={styles.text}>{t('guide.text')}</p>
      <ol className={styles.steps}>
        {STEPS[platform].map((step, index) => (
          <li key={step.key} className={styles.step}>
            <span className={styles.stepNumber} aria-hidden="true">
              {index + 1}
            </span>
            <span className={styles.stepIcon} aria-hidden="true">
              <Icon name={step.icon} size={18} />
            </span>
            <span>{t(`${platform}.${step.key}`)}</span>
          </li>
        ))}
      </ol>
      <p className={styles.note}>{t(`${platform}.note`)}</p>
      <div className={styles.actions}>
        <Button onClick={() => dialog.current?.close()}>{t('guide.close')}</Button>
      </div>
    </dialog>
  );
}

export function InstallButton({ variant = 'card' }: { variant?: 'card' | 'inline' }) {
  const { t } = useTranslation('install');
  const { offer, platform, install } = useInstall();
  const [guide, setGuide] = useState(false);

  // The browser's dialog when it has one; a refusal is the person's answer. Without it, or when
  // the browser would not show it after all, the guide (on a phone).
  const click = async () => {
    if (offer === 'prompt' && (await install()) !== 'unavailable') return;
    if (platform !== 'other') setGuide(true);
  };

  return (
    <>
      {offer && (
        <>
          <button
            type="button"
            className={variant === 'inline' ? styles.inline : styles.card}
            onClick={() => void click()}
          >
            {variant === 'inline' ? (
              <>
                <Icon name="download" size={12} />
                <span className={styles.label}>{t('button').toUpperCase()}</span>
              </>
            ) : (
              // Two lines, like the newsroom's card beside it: « Installer », then « L'APPLI ».
              <>
                <Icon name="download" size={16} />
                <span className={styles.cardText}>
                  <span className={styles.label}>{t('card.title')}</span>{' '}
                  <span className={styles.cardSub}>{t('card.sub')}</span>
                </span>
              </>
            )}
          </button>
          {variant === 'inline' && <span aria-hidden="true">·</span>}
        </>
      )}
      {guide && platform !== 'other' && (
        <InstallGuide platform={platform} onClose={() => setGuide(false)} />
      )}
    </>
  );
}
