// The account pages lead to Keycloak's (specs/002-keycloak-auth/contracts/auth.md, « Pages de
// l'interface »): /connexion, /inscription and /mot-de-passe/oubli go there through the server;
// an error of the way back explains and offers to start again; a link of the former e-mails says
// it no longer works (FR-018). Keycloak's pages wear the same Gazette look (keycloak/theme).
import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { AppVersion, ButtonLink, Kicker } from '../../ui/components';
import styles from './auth.module.css';
import { nextPath } from './RequireAuth';
import { browser, signInUrl } from './signIn';

/** Leaves at once for `url`, unless it is null. */
function useLeaveFor(url: string | null) {
  useEffect(() => {
    if (url) browser.go(url);
  }, [url]);
}

/** What shows while the browser leaves for Keycloak's page. */
function Leaving() {
  const { t } = useTranslation('auth');
  return (
    <section className={styles.page}>
      <p role="status" className={styles.lead}>
        {t('leaving')}
      </p>
    </section>
  );
}

const REASONS = ['expired', 'denied', 'email_taken', 'failed'];

/** /connexion goes to Keycloak's sign-in page; with `?erreur=…`, it says why the last sign-in did
 *  not go through and offers to start again. */
export function LoginPage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  const error = search.get('erreur');
  const again = signInUrl('login', nextPath(search));
  useLeaveFor(error === null ? again : null);
  if (error === null) return <Leaving />;
  const reason = REASONS.includes(error) ? error : 'failed';
  return (
    <section className={styles.page}>
      <Kicker tone="indigo">{t('kicker')}</Kicker>
      <h1 className={styles.title}>{t('error.title')}</h1>
      <p className={styles.lead}>{t(`error.${reason}`)}</p>
      <ButtonLink to={again} reloadDocument block>
        {t('error.again')}
      </ButtonLink>
      <AppVersion />
    </section>
  );
}

export function SignupPage() {
  const [search] = useSearchParams();
  useLeaveFor(signInUrl('signup', nextPath(search)));
  return <Leaving />;
}

export function ForgotPasswordPage() {
  useLeaveFor(signInUrl('forgot'));
  return <Leaving />;
}

/** Keycloak does not answer: those signed in play on, a sign-in waits (FR-017). */
export function SignInUnavailablePage() {
  const { t } = useTranslation('auth');
  const [search] = useSearchParams();
  return (
    <section className={styles.page}>
      <Kicker tone="indigo">{t('kicker')}</Kicker>
      <h1 className={styles.title}>{t('unavailable.title')}</h1>
      <p className={styles.lead}>{t('unavailable.lead')}</p>
      <ButtonLink to={signInUrl('login', nextPath(search))} reloadDocument block>
        {t('unavailable.again')}
      </ButtonLink>
    </section>
  );
}

/** A link from an e-mail of the former sign-in: a new password, or an address to confirm. It no
 *  longer works; the page says so and leads to Keycloak's (FR-018). */
export function OldLinkPage({ link }: { link: 'password' | 'address' }) {
  const { t } = useTranslation('auth');
  const target = link === 'password' ? signInUrl('forgot') : signInUrl('login', '/compte');
  return (
    <section className={styles.page}>
      <Kicker tone="indigo">{t('kicker')}</Kicker>
      <h1 className={styles.title}>{t('oldLink.title')}</h1>
      <p className={styles.lead}>{t(`oldLink.${link}`)}</p>
      <ButtonLink to={target} reloadDocument block>
        {t(`oldLink.${link}Action`)}
      </ButtonLink>
    </section>
  );
}

/** After deleting one's account, which Keycloak deleted too: goodbye, and a way to start again. */
export function GoodbyePage() {
  const { t } = useTranslation('auth');
  return (
    <section className={styles.page}>
      <Kicker tone="indigo">{t('deleted.kicker')}</Kicker>
      <h1 className={styles.title}>{t('deleted.title')}</h1>
      <p className={styles.lead}>{t('deleted.lead')}</p>
      <ButtonLink to="/inscription" variant="secondary" block>
        {t('deleted.again')}
      </ButtonLink>
    </section>
  );
}
