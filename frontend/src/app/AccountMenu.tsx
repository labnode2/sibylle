// My avatar and pseudo at the right of the computer's date bar: a click opens the small menu of
// my account. « Profil », « Collection » and « Réglages » tell the page they open which page
// opened it, for its way back; « Déconnexion » asks first, like the press card's line. Escape, a
// click or the focus elsewhere close it, and so does following one of its links.
import { useEffect, useId, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router';

import type { Org } from '../api/types';
import { useLogoutConfirm } from '../features/auth/LogoutDialog';
import { Icon } from '../ui/components';
import { PixelImage } from '../ui/PixelImage';
import styles from './shell.module.css';

export function AccountMenu({ orgId, me }: { orgId: string; me: Org['my_membership'] }) {
  const { t } = useTranslation();
  const { pathname, state } = useLocation();
  // Open on the page it was opened on: on another page (a link followed, the browser's back),
  // it is closed.
  const [openOn, setOpenOn] = useState<string | null>(null);
  const open = openOn === pathname;
  const box = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const logout = useLogoutConfirm();

  useEffect(() => {
    if (!open) return;
    const outside = (event: Event) => {
      if (!box.current?.contains(event.target as Node)) setOpenOn(null);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      setOpenOn(null);
      button.current?.focus();
    };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('pointerdown', outside);
      document.removeEventListener('focusin', outside);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  const close = () => setOpenOn(null);
  const collection = `/o/${orgId}/collection`;
  const links = [
    { to: `/o/${orgId}/profil`, label: t('account.profile'), state: undefined },
    // Opened again from the collection, it keeps the way back the collection already has.
    {
      to: collection,
      label: t('account.collection'),
      state: pathname === collection ? state : { from: pathname },
    },
    { to: '/compte', label: t('account.settings'), state: { from: pathname } },
  ];
  const pseudo = me.pseudo.toUpperCase();
  return (
    <div ref={box} className={styles.account}>
      <button
        ref={button}
        type="button"
        className={styles.accountButton}
        aria-label={t('account.open', { pseudo })}
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpenOn(open ? null : pathname)}
      >
        <PixelImage image={me.avatar} size={24} />
        <span>{pseudo}</span>
        <Icon name="chevronDown" />
      </button>
      {open && (
        <div id={menuId} className={styles.accountMenu}>
          <ul className={styles.accountList} aria-label={t('account.label')}>
            {links.map((link) => (
              <li key={link.to}>
                <Link
                  to={link.to}
                  state={link.state}
                  className={styles.accountItem}
                  aria-current={pathname === link.to ? 'page' : undefined}
                  onClick={close}
                >
                  {link.label}
                </Link>
              </li>
            ))}
            <li className={styles.accountLogout}>
              <button
                type="button"
                className={styles.accountItem}
                onClick={() => {
                  // The dialog gives the focus back where it found it: on my avatar, since this
                  // entry goes with the menu.
                  button.current?.focus();
                  close();
                  logout.ask();
                }}
              >
                {t('account.logout')}
              </button>
            </li>
          </ul>
        </div>
      )}
      {logout.element}
    </div>
  );
}
