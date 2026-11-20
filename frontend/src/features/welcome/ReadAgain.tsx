// « Tuto » and « Charte »: the game's bases (the welcome's steps) and the newsroom's charter, to
// read again at any time. « Tuto » is on la une, at the left of the navigation on a computer and
// right of the newsroom's card on a phone; « Charte » on « La rédaction », in the newsroom's card,
// only when the newsroom has a charter. Each is a small, still pixel-art icon (art.ts), the book
// and the parchment, without a word under it: screen readers say what it opens, and so does the
// hint of a mouse. The charter opens like the welcome, a card in the middle of a computer's
// screen, a sheet rising from the bottom of a phone's, its line breaks kept.
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Org } from '../../api/types';
import { Button, Kicker } from '../../ui/components';
import { ART } from './art';
import { WelcomeDialog } from './WelcomeDialog';
import styles from './welcome.module.css';

/** A drawing of art.ts, 32 pixels square as drawn, 64 at the top of the charter's window; it
 *  says nothing to screen readers. */
function Picture({ src }: { src: string }) {
  return <img className={styles.picture} src={src} alt="" />;
}

/** A drawing that opens something, named by what it opens, in 44 pixels to tap; `className`
 *  places it. */
function PictureButton({
  src,
  name,
  className = '',
  onClick,
}: {
  src: string;
  name: string;
  className?: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className={`${styles.pictureButton} ${className}`}
      aria-label={name}
      title={name}
      onClick={onClick}
    >
      <Picture src={src} />
    </button>
  );
}

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
        <div className={styles.art}>
          <Picture src={ART.charter} />
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

/** « Tuto », the open book: the welcome again, with the newsroom and the member's role. */
export function TutoButton({ org, className }: { org: Org; className?: string }) {
  const { t } = useTranslation('welcome');
  const [open, setOpen] = useState(false);
  return (
    <>
      <PictureButton
        src={ART.tuto}
        name={t('readAgain.tutoName')}
        className={className}
        onClick={() => setOpen(true)}
      />
      {open && (
        <WelcomeDialog
          org={org.title}
          role={org.my_membership.role}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}

/** « Charte », the parchment: the newsroom's charter as written. Nothing without a charter. */
export function CharterButton({ org, className }: { org: Org; className?: string }) {
  const { t } = useTranslation('welcome');
  const [open, setOpen] = useState(false);
  const charter = org.charter.trim();
  if (!charter) return null;
  return (
    <>
      <PictureButton
        src={ART.charter}
        name={t('readAgain.charterName')}
        className={className}
        onClick={() => setOpen(true)}
      />
      {open && <CharterDialog org={org.title} charter={charter} onClose={() => setOpen(false)} />}
    </>
  );
}
