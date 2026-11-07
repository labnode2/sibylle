// The account's settings (US11): display, notifications (US8), newsrooms to leave, the password
// (on Keycloak's page), the export of one's data and the deletion of the account. Reached from the
// gear of the pages outside a newsroom and from the press card, it leads back where one came
// from; notification e-mails link to `#notifications`.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useNavigate } from 'react-router';

import { ApiError } from '../../api/client';
import type { Me } from '../../api/types';
import { usePreferences, type Theme } from '../../app/preferences';
import { AppVersion, Button, ButtonLink, Card, Icon, Switch } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { toast } from '../../ui/Toaster';
import { useMe } from '../auth/api';
import { useLogoutConfirm } from '../auth/LogoutDialog';
import { signInUrl } from '../auth/signIn';
import { NotificationPrefs } from '../notifications/NotificationPrefs';
import { downloadMyData, useDeleteAccount, useLeaveNewsroom, useUpdateAccount } from './api';
import styles from './settings.module.css';

const THEMES: Theme[] = ['light', 'dark', 'auto'];

/** Keycloak did not answer the deletion: nothing is deleted, try again later (FR-013). */
function SignInServiceDown({ error }: { error: unknown }) {
  const { t } = useTranslation('settings');
  if (!(error instanceof ApiError) || error.code !== 'identity_unavailable') return null;
  return (
    <div role="alert" className={styles.alert}>
      <p>{t('delete.unavailable')}</p>
    </div>
  );
}

/** « Nomme d'abord une autre rédaction en chef », with the way to do it. */
function LastEditor({ error, me }: { error: unknown; me: Me }) {
  const { t } = useTranslation('settings');
  if (!(error instanceof ApiError) || error.code !== 'last_editor') return null;
  const orgId = error.fields.org_id;
  const org = me.memberships.find((m) => m.org.id === orgId)?.org.title ?? '';
  return (
    <div role="alert" className={styles.alert}>
      <p>{t('lastEditor', { org })}</p>
      {orgId && <Link to={`/o/${orgId}/reglages/membres`}>{t('lastEditorLink', { org })}</Link>}
    </div>
  );
}

function Display() {
  const { t } = useTranslation('settings');
  const preferences = usePreferences();
  const update = useUpdateAccount();
  return (
    <section className={styles.section} aria-labelledby="settings-display">
      <h2 id="settings-display" className={styles.sectionTitle}>
        {t('display.title')}
      </h2>
      <fieldset className={styles.themes}>
        <legend className={styles.label}>{t('display.theme')}</legend>
        {THEMES.map((theme) => (
          <label key={theme} className={styles.theme}>
            <input
              type="radio"
              name="theme"
              checked={preferences.theme === theme}
              onChange={() => {
                preferences.setTheme(theme);
                update.mutate({ theme });
              }}
            />
            {t(`display.themes.${theme}`)}
          </label>
        ))}
      </fieldset>
      <p className={styles.hint}>{t('display.autoHint')}</p>
      <div className={styles.row}>
        <div>
          <span className={styles.rowLabel}>{t('display.reduceMotion')}</span>
          <span className={styles.hint}>{t('display.reduceMotionHint')}</span>
        </div>
        <Switch
          checked={preferences.reduceMotion}
          label={t('display.reduceMotion')}
          onChange={(reduce) => {
            preferences.setReduceMotion(reduce);
            update.mutate({ reduce_motion: reduce });
          }}
        />
      </div>
    </section>
  );
}

function Newsrooms({ me }: { me: Me }) {
  const { t } = useTranslation('settings');
  const leave = useLeaveNewsroom();
  const [asking, setAsking] = useState<string | null>(null);
  return (
    <section className={styles.section} aria-labelledby="settings-newsrooms">
      <h2 id="settings-newsrooms" className={styles.sectionTitle}>
        {t('newsrooms.title')}
      </h2>
      {me.memberships.length === 0 ? (
        <>
          <p className={styles.text}>{t('newsrooms.none')}</p>
          <ButtonLink to="/bienvenue" variant="secondary">
            {t('newsrooms.join')}
          </ButtonLink>
        </>
      ) : (
        <ul className={styles.newsrooms}>
          {me.memberships.map(({ org, membership }) => (
            <li key={org.id} className={styles.newsroom}>
              <div className={styles.row}>
                <Link to={`/o/${org.id}`} className={styles.org}>
                  <PixelImage image={membership.avatar} size={32} />
                  <span>
                    <span className={styles.rowLabel}>{org.title}</span>
                    <span className={styles.hint}>
                      {membership.pseudo} · {t(`newsrooms.role.${membership.role}`)}
                    </span>
                  </span>
                </Link>
                {asking !== org.id && (
                  <Button
                    variant="secondary"
                    aria-label={t('newsrooms.leaveLabel', { org: org.title })}
                    onClick={() => {
                      leave.reset();
                      setAsking(org.id);
                    }}
                  >
                    {t('newsrooms.leave')}
                  </Button>
                )}
              </div>
              {asking === org.id && (
                <Card as="div" shadow={0} className={styles.confirm}>
                  <p className={styles.text}>{t('newsrooms.confirm', { org: org.title })}</p>
                  <LastEditor error={leave.error} me={me} />
                  <div className={styles.actions}>
                    <Button
                      disabled={leave.isPending}
                      onClick={() =>
                        leave.mutate(org.id, {
                          onSuccess: () => {
                            setAsking(null);
                            toast.success(t('newsrooms.left', { org: org.title }));
                          },
                        })
                      }
                    >
                      {t('newsrooms.confirmYes')}
                    </Button>
                    <Button variant="secondary" onClick={() => setAsking(null)}>
                      {t('newsrooms.cancel')}
                    </Button>
                  </div>
                </Card>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** « Changer mon mot de passe »: Keycloak's page, which can also sign the other devices out, then
 *  back here (specs/002-keycloak-auth, FR-010). */
export function PasswordChange() {
  const { t } = useTranslation('settings');
  return (
    <section className={styles.section} aria-labelledby="settings-password">
      <h2 id="settings-password" className={styles.sectionTitle}>
        {t('password.title')}
      </h2>
      <p className={styles.text}>{t('password.text')}</p>
      <ButtonLink to={signInUrl('password', '/compte')} reloadDocument variant="secondary">
        {t('password.change')}
      </ButtonLink>
    </section>
  );
}

function MyData() {
  const { t } = useTranslation('settings');
  const [busy, setBusy] = useState(false);
  const download = async () => {
    setBusy(true);
    try {
      await downloadMyData();
      toast.success(t('data.done'));
    } catch {
      toast.error(t('data.failed'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className={styles.section} aria-labelledby="settings-data">
      <h2 id="settings-data" className={styles.sectionTitle}>
        {t('data.title')}
      </h2>
      <p className={styles.text}>{t('data.text')}</p>
      <Button variant="secondary" disabled={busy} onClick={() => void download()}>
        <Icon name="download" />
        {t('data.export')}
      </Button>
    </section>
  );
}

function DeleteAccount({ me }: { me: Me }) {
  const { t } = useTranslation('settings');
  const remove = useDeleteAccount();
  const navigate = useNavigate();
  const [asking, setAsking] = useState(false);
  return (
    <section className={styles.section} aria-labelledby="settings-delete">
      <h2 id="settings-delete" className={styles.sectionTitle}>
        {t('delete.title')}
      </h2>
      <p className={styles.text}>{t('delete.text')}</p>
      {asking ? (
        <Card as="div" shadow={0} className={styles.confirm}>
          <p className={styles.text}>{t('delete.confirm')}</p>
          <LastEditor error={remove.error} me={me} />
          <SignInServiceDown error={remove.error} />
          <div className={styles.actions}>
            <Button
              disabled={remove.isPending}
              onClick={() =>
                remove.mutate(undefined, {
                  onSuccess: () => void navigate('/au-revoir', { replace: true }),
                })
              }
            >
              {t('delete.confirmYes')}
            </Button>
            <Button variant="secondary" onClick={() => setAsking(false)}>
              {t('delete.cancel')}
            </Button>
          </div>
        </Card>
      ) : (
        <Button
          variant="secondary"
          onClick={() => {
            remove.reset();
            setAsking(true);
          }}
        >
          {t('delete.open')}
        </Button>
      )}
    </section>
  );
}

/** Back to the page that opened the settings (`state.from`), else to the first newsroom. */
function useWayBack(): { to: string; label: string } {
  const { t } = useTranslation('settings');
  const { state } = useLocation();
  const from = (state as { from?: unknown } | null)?.from;
  if (typeof from !== 'string' || !from.startsWith('/')) return { to: '/', label: t('back') };
  if (from === '/bienvenue') return { to: from, label: t('backStart') };
  if (/^\/o\/[^/]+\/profil$/.test(from)) return { to: from, label: t('backProfile') };
  return { to: from, label: t('back') };
}

export function SettingsPage() {
  const { t } = useTranslation('settings');
  const me = useMe();
  const logout = useLogoutConfirm();
  const back = useWayBack();
  if (!me.data) return <p role="status">{t('common:shell.loading')}</p>;
  return (
    <div className={styles.page}>
      {(me.data.memberships.length > 0 || back.to !== '/') && (
        <Link to={back.to} className={styles.back}>
          <Icon name="chevronLeft" size={12} />
          {back.label}
        </Link>
      )}
      <h1 className={styles.title}>{t('title')}</h1>
      <Display />
      <NotificationPrefs emailVerified={me.data.email_verified} />
      <Newsrooms me={me.data} />
      <PasswordChange />
      <MyData />
      <DeleteAccount me={me.data} />
      <Button variant="link" onClick={logout.ask}>
        {t('logout')}
      </Button>
      {logout.element}
      <AppVersion />
    </div>
  );
}
