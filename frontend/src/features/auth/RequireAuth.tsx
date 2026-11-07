import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet, useLocation } from 'react-router';

import { ApiError } from '../../api/client';
import { usePreferences } from '../../app/preferences';
import { useMe } from './api';
import { browser, isAppPath, signInUrl } from './signIn';

/** Pages behind a session: without one, go sign in on Keycloak's page and come back here. */
export function RequireAuth() {
  const { t } = useTranslation();
  const location = useLocation();
  const me = useMe();
  const { adopt } = usePreferences();
  const theme = me.data?.theme;
  const reduceMotion = me.data?.reduce_motion;
  const signedOut = me.error instanceof ApiError && me.error.status === 401;
  const here = location.pathname + location.search;

  // The account's display settings follow it from device to device.
  useEffect(() => {
    if (theme !== undefined && reduceMotion !== undefined) adopt({ theme, reduceMotion });
  }, [theme, reduceMotion, adopt]);

  useEffect(() => {
    if (signedOut) browser.go(signInUrl('login', here));
  }, [signedOut, here]);

  if (me.isPending || signedOut) return <p role="status">{t('shell.loading')}</p>;
  if (me.error) return <p role="alert">{t('shell.error')}</p>;
  return <Outlet />;
}

/** After signing in: back where the person was going, or to their first newsroom. */
export function nextPath(search: URLSearchParams): string {
  const next = search.get('suite');
  return next && isAppPath(next) ? next : '/';
}
