// The welcome pop-up, shown in the person's first newsroom: the game in a few steps (pronos,
// laurels, coins, the leaderboard), then what their role lets them do. Closed whichever way, it
// does not come back (`welcomed`, on every device); « Revoir les bases du jeu » on « La
// rédaction » opens it again. A card in the middle of a computer's screen, a sheet rising from the
// bottom of a phone's.
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { Button, Coins, Icon, Kicker, Laurel } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import type { Role } from '../admin/api';
import styles from './welcome.module.css';

type Step = { key: string; art: ReactNode; more?: boolean };

const STEPS: Step[] = [
  { key: 'intro', art: <CrystalBall size={64} loops={1} /> },
  { key: 'pronos', art: <Icon name="ball" size={48} />, more: true },
  {
    key: 'laurels',
    art: (
      <>
        <Laurel size={32} />
        <Laurel size={32} tone="gold" />
      </>
    ),
    more: true,
  },
  { key: 'coins', art: <Coins size={32} /> },
  { key: 'leaderboard', art: <Icon name="trophy" size={48} /> },
];

export function WelcomeDialog({
  org,
  role,
  onClose,
}: {
  org: string;
  role: Role;
  onClose: () => void;
}) {
  const { t } = useTranslation('welcome');
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [index, setIndex] = useState(0);
  const steps: Step[] = [
    ...STEPS,
    { key: `role.${role}`, art: <Icon name={role === 'reader' ? 'plus' : 'people'} size={48} /> },
  ];
  const step = steps[index] ?? steps[0]!;
  const last = index === steps.length - 1;

  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal();
  }, []);

  const close = () => dialog.current?.close();

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId} onClose={onClose}>
      <div aria-live="polite" className={styles.body}>
        <div className={styles.art} aria-hidden="true">
          {step.art}
        </div>
        <Kicker tone="indigo">{t('step', { step: index + 1, count: steps.length })}</Kicker>
        <h2 id={titleId} className={styles.title}>
          {t(`${step.key}.title`, { org })}
        </h2>
        <p className={styles.text}>{t(`${step.key}.text`)}</p>
        {step.more && <p className={styles.more}>{t(`${step.key}.more`)}</p>}
      </div>
      <ol className={styles.dots} aria-hidden="true">
        {steps.map((other, position) => (
          <li key={other.key} className={position === index ? styles.dotOn : styles.dot} />
        ))}
      </ol>
      <div className={styles.actions}>
        {index > 0 ? (
          <Button variant="secondary" onClick={() => setIndex(index - 1)}>
            {t('previous')}
          </Button>
        ) : (
          <Button variant="secondary" onClick={close}>
            {t('skip')}
          </Button>
        )}
        {last ? (
          <Button onClick={close}>{t('done')}</Button>
        ) : (
          <Button onClick={() => setIndex(index + 1)}>{t('next')}</Button>
        )}
      </div>
    </dialog>
  );
}
