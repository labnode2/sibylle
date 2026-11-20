// « Tuto » and « Charte »: the game's bases (the welcome's steps) and the newsroom's charter, to
// read again at any time, under the editor's note on la une and on « La rédaction ». Two small
// buttons, a pixel icon and a short word; « Charte » only when the newsroom has a charter. The
// charter opens like the welcome, a card in the middle of a computer's screen, a sheet rising
// from the bottom of a phone's, its line breaks kept.
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Org } from '../../api/types';
import { Button, Icon, Kicker } from '../../ui/components';
import { WelcomeDialog } from './WelcomeDialog';
import styles from './welcome.module.css';

function CharterDialog({
  org,
  charter,
  onClose,
}: {
  org: string;
  charter: string;
  onClose: () => void;
}) {
  const { t } = useTranslation('welcome');
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!dialog.current?.open) dialog.current?.showModal();
  }, []);

  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId} onClose={onClose}>
      <div className={styles.body}>
        <div className={styles.art} aria-hidden="true">
          <Icon name="scroll" size={48} />
        </div>
        <Kicker tone="indigo">{org.toUpperCase()}</Kicker>
        <h2 id={titleId} className={styles.title}>
          {t('charter.title')}
        </h2>
        <p className={styles.charter}>{charter}</p>
      </div>
      <div className={styles.actions}>
        <Button onClick={() => dialog.current?.close()}>{t('charter.close')}</Button>
      </div>
    </dialog>
  );
}

export function ReadAgain({ org }: { org: Org }) {
  const { t } = useTranslation('welcome');
  const [open, setOpen] = useState<'tuto' | 'charter' | null>(null);
  const charter = org.charter.trim();
  const close = () => setOpen(null);

  return (
    <div className={styles.readAgain}>
      <button
        type="button"
        className={styles.readAgainButton}
        aria-label={t('readAgain.tutoName')}
        onClick={() => setOpen('tuto')}
      >
        <Icon name="book" size={24} />
        {t('readAgain.tuto')}
      </button>
      {charter && (
        <button
          type="button"
          className={styles.readAgainButton}
          aria-label={t('readAgain.charterName')}
          onClick={() => setOpen('charter')}
        >
          <Icon name="scroll" size={24} />
          {t('readAgain.charter')}
        </button>
      )}
      {open === 'tuto' && (
        <WelcomeDialog org={org.title} role={org.my_membership.role} onClose={close} />
      )}
      {open === 'charter' && charter && (
        <CharterDialog org={org.title} charter={charter} onClose={close} />
      )}
    </div>
  );
}
