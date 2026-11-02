// Routes: public pages (sign-in, sign-up, links from e-mails), pages behind a session, and a
// newsroom's pages under /o/:orgId. Each user story adds its screens here.
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { createBrowserRouter, isRouteErrorResponse, Outlet, useRouteError } from 'react-router';

import {
  ForgotPasswordPage,
  LoginPage,
  ResetPasswordPage,
  SignupPage,
  VerifyEmailPage,
} from '../features/auth/AuthPages';
import { RequireAuth } from '../features/auth/RequireAuth';
import { CreateOrgPage, HomeRedirect, JoinPage, StartPage } from '../features/orgs/OrgPages';
import { OrgSwitcherPage } from '../features/orgs/OrgSwitcher';
import { CreatePronoPage } from '../features/pronos/CreatePronoPage';
import { PronoListPage } from '../features/pronos/PronoListPage';
import { PronoPage } from '../features/pronos/PronoPage';
import { UnePage } from '../features/une/UnePage';
import { ButtonLink, Masthead } from '../ui/components';
import { OfflineBanner } from './AppShell';
import { OrgLayout } from './OrgLayout';
import styles from './shell.module.css';

function PublicPage({ children }: { children?: ReactNode }) {
  return (
    <div className={styles.page}>
      <Masthead size="compact" />
      <OfflineBanner />
      <main className={styles.main}>{children ?? <Outlet />}</main>
    </div>
  );
}

function NotFound() {
  const { t } = useTranslation();
  return (
    <div className={styles.centered}>
      <p>{t('shell.notFound')}</p>
      <ButtonLink to="/" variant="secondary">
        {t('shell.backHome')}
      </ButtonLink>
    </div>
  );
}

function RouteError() {
  const error = useRouteError();
  const { t } = useTranslation();
  return (
    <PublicPage>
      {isRouteErrorResponse(error) && error.status === 404 ? (
        <NotFound />
      ) : (
        <div className={styles.centered}>
          <p role="alert">{t('shell.error')}</p>
        </div>
      )}
    </PublicPage>
  );
}

export const router = createBrowserRouter([
  {
    element: <PublicPage />,
    errorElement: <RouteError />,
    children: [
      { path: '/connexion', element: <LoginPage /> },
      { path: '/inscription', element: <SignupPage /> },
      { path: '/mot-de-passe/oubli', element: <ForgotPasswordPage /> },
      { path: '/mot-de-passe/nouveau', element: <ResetPasswordPage /> },
      { path: '/verifier-email', element: <VerifyEmailPage /> },
    ],
  },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <HomeRedirect /> },
      {
        element: <PublicPage />,
        children: [
          { path: '/bienvenue', element: <StartPage /> },
          { path: '/creer', element: <CreateOrgPage /> },
          { path: '/rejoindre', element: <JoinPage /> },
          { path: '/rejoindre/:token', element: <JoinPage /> },
          { path: '/redactions', element: <OrgSwitcherPage /> },
        ],
      },
      {
        path: '/o/:orgId',
        element: <OrgLayout />,
        children: [
          { index: true, element: <UnePage /> },
          { path: 'pronos', element: <PronoListPage /> },
          { path: 'pronos/nouveau', element: <CreatePronoPage /> },
          { path: 'pronos/:pronoId', element: <PronoPage /> },
        ],
      },
    ],
  },
  {
    path: '*',
    element: (
      <PublicPage>
        <NotFound />
      </PublicPage>
    ),
  },
]);
