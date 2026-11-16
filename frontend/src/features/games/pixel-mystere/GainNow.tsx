// What finding the word now would pay, in a gold box beside the countdown so that it catches
// the eye: « TROUVE MAINTENANT » over a big « +42 LAURIERS ». Nothing for whoever cannot win
// (the drawing's author, whoever already found, a finished drawing).
import { useTranslation } from 'react-i18next';

import { Card } from '../../../ui/components';
import type { PixelStatus } from '../api';
import styles from '../games.module.css';
import { useGainNow } from './gain';

export function GainNow({ status }: { status: PixelStatus }) {
  const { t } = useTranslation('games');
  const gain = useGainNow(status);
  if (status.state !== 'active' || gain == null) return null;
  return (
    <div role="status" aria-label={t('pixel.gainNow', { laurels: gain })}>
      <Card as="div" className={styles.gainNow}>
        <span className={styles.gainNowLabel}>{t('pixel.gainNowLabel')}</span>
        <span className={styles.gainNowValue}>
          +{gain} <span className={styles.gainNowUnit}>{t('pixel.gainNowUnit')}</span>
        </span>
      </Card>
    </div>
  );
}
