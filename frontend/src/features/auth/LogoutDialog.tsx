// Signing out asks first: « Te déconnecter ? », then « Annuler » or « Me déconnecter », from the
// press card's « Déconnexion » and from the settings. Escape or « Annuler » keeps one signed in.
import { useId, useRef, type RefObject } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { Button } from '../../ui/components';
import { useLogout } from './api';
import styles from './logout.module.css';

function LogoutDialog({ dialog }: { dialog: RefObject<HTMLDialogElement | null> }) {
  const { t } = useTranslation();
  const logout = useLogout();
  const navigate = useNavigate();
  const titleId = useId();
  return (
    <dialog ref={dialog} className={styles.dialog} aria-labelledby={titleId}>
      <h2 id={titleId} className={styles.title}>
        {t('logout.title')}
      </h2>
      <p className={styles.text}>{t('logout.body')}</p>
      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => dialog.current?.close()}>
          {t('logout.cancel')}
        </Button>
        <Button
          className={styles.confirm}
          disabled={logout.isPending}
          onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/connexion') })}
        >
          {t('logout.confirm')}
        </Button>
      </div>
    </dialog>
  );
}

/** The confirmation of signing out: `element` to render, `ask` to open it. */
export function useLogoutConfirm() {
  const dialog = useRef<HTMLDialogElement>(null);
  return {
    ask: () => dialog.current?.showModal(),
    element: <LogoutDialog dialog={dialog} />,
  };
}
