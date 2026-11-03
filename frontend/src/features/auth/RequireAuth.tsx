import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Navigate, Outlet, useLocation } from 'react-router';

import { ApiError } from '../../api/client';
import { usePreferences } from '../../app/preferences';
import { useMe } from './api';

/** Pages behind a session: without one, go sign in and come back afterwards. */
export function RequireAuth() {
  const { t } = useTranslation();
  const location = useLocation();
  const me = useMe();
  const { adopt } = usePreferences();
  const theme = me.data?.theme;
  const reduceMotion = me.data?.reduce_motion;

  // The account's display settings follow it from device to device.
  useEffect(() => {
    if (theme !== undefined && reduceMotion !== undefined) adopt({ theme, reduceMotion });
  }, [theme, reduceMotion, adopt]);

  if (me.isPending) return <p role="status">{t('shell.loading')}</p>;
  if (me.error instanceof ApiError && me.error.status === 401) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/connexion?suite=${next}`} replace />;
  }
  if (me.error) return <p role="alert">{t('shell.error')}</p>;
  return <Outlet />;
}

/** After signing in: back where the person was going, or to their first newsroom. */
export function nextPath(search: URLSearchParams): string {
  const next = search.get('suite');
  return next && next.startsWith('/') && !next.startsWith('//') ? next : '/';
}
