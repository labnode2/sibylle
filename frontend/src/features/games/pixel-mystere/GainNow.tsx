// What finding the word now would pay, in a box beside the countdown so that it catches the eye:
// « SI TU TROUVES MAINTENANT » over a big « +42 » and a gold laurel. Nothing for whoever cannot
// win (the drawing's author, whoever already found, a finished drawing).
import { useTranslation } from 'react-i18next';

import { Card, Laurel } from '../../../ui/components';
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
          +{gain} <Laurel size={32} tone="gold" />
        </span>
      </Card>
    </div>
  );
}
