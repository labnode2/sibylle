// Routes: public pages (the ways to Keycloak's pages), pages behind a session, and a
// newsroom's pages under /o/:orgId. Each user story adds its screens here.
import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import {
  createBrowserRouter,
  isRouteErrorResponse,
  Link,
  Navigate,
  Outlet,
  useLocation,
  useRouteError,
} from 'react-router';

import {
  ForgotPasswordPage,
  GoodbyePage,
  LoginPage,
  OldLinkPage,
  SignInUnavailablePage,
  SignupPage,
} from '../features/auth/AuthPages';
import { RequireAuth } from '../features/auth/RequireAuth';
import { NewsroomPage } from '../features/orgs/NewsroomPage';
import { CreateOrgPage, HomeRedirect, JoinPage, StartPage } from '../features/orgs/OrgPages';
import { AdminLayout } from '../features/admin/AdminLayout';
import { GameSchedulePage } from '../features/admin/GameSchedulePage';
import { MembersPage } from '../features/admin/MembersPage';
import { OrgSettingsPage } from '../features/admin/OrgSettingsPage';
import { ParametersPage } from '../features/admin/ParametersPage';
import { ReportsPage } from '../features/admin/ReportsPage';
import { CollectionPage } from '../features/collection/CollectionPage';
import { LeaderboardPage } from '../features/leaderboard/LeaderboardPage';
import { CreatePronoPage } from '../features/pronos/CreatePronoPage';
import { PronoListPage } from '../features/pronos/PronoListPage';
import { PronoPage } from '../features/pronos/PronoPage';
import { PixelMysterePage } from '../features/games/pixel-mystere/PixelMysterePage';
import { RunnerPage } from '../features/games/runner/RunnerPage';
import { CardEditorPage } from '../features/profile/CardEditorPage';
import { PressCardPage } from '../features/profile/PressCardPage';
import { PublicCardPage } from '../features/profile/PublicCardPage';
import { SettingsPage } from '../features/settings/SettingsPage';
import { UnePage } from '../features/une/UnePage';
import { Button, ButtonLink, Icon, Masthead } from '../ui/components';
import { reloadLatest } from './updates';
import { OfflineBanner } from './AppShell';
import { OrgLayout } from './OrgLayout';
import styles from './shell.module.css';

/** The pages outside a newsroom, under the masthead. Signed in, a gear at the top right opens the
 *  account's settings, which lead back here. */
function PublicPage({ children, signedIn = false }: { children?: ReactNode; signedIn?: boolean }) {
  const { t } = useTranslation();
  const { pathname } = useLocation();
  return (
    <div className={styles.page}>
      <div className={styles.publicHead}>
        <Masthead size="compact" />
        {signedIn && pathname !== '/compte' && (
          <Link
            to="/compte"
            state={{ from: pathname }}
            className={styles.publicSettings}
            aria-label={t('shell.settings')}
            title={t('shell.settings')}
          >
            <Icon name="gear" size={24} />
          </Link>
        )}
      </div>
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
          {/* Often a tab left open across a deploy: the new version usually fixes it. */}
          <Button onClick={() => void reloadLatest()}>{t('shell.reload')}</Button>
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
      // Keycloak's pages, through the server (specs/002-keycloak-auth/contracts/auth.md). The
      // last two are the links of the former sign-in's e-mails.
      { path: '/connexion', element: <LoginPage /> },
      { path: '/connexion-indisponible', element: <SignInUnavailablePage /> },
      { path: '/inscription', element: <SignupPage /> },
      { path: '/mot-de-passe/oubli', element: <ForgotPasswordPage /> },
      { path: '/mot-de-passe/nouveau', element: <OldLinkPage link="password" /> },
      { path: '/verifier-email', element: <OldLinkPage link="address" /> },
      // After deleting one's account.
      { path: '/au-revoir', element: <GoodbyePage /> },
    ],
  },
  // A press card its member made public (US15): without an account and without the app's
  // frame, so that another site can show it in an iframe.
  { path: '/carte/:token', element: <PublicCardPage />, errorElement: <RouteError /> },
  {
    element: <RequireAuth />,
    errorElement: <RouteError />,
    children: [
      { path: '/', element: <HomeRedirect /> },
      {
        element: <PublicPage signedIn />,
        children: [
          { path: '/bienvenue', element: <StartPage /> },
          { path: '/creer', element: <CreateOrgPage /> },
          { path: '/rejoindre', element: <JoinPage /> },
          { path: '/rejoindre/:token', element: <JoinPage /> },
          // The former list of newsrooms: they are on the welcome page now.
          { path: '/redactions', element: <Navigate to="/bienvenue" replace /> },
          { path: '/compte', element: <SettingsPage /> },
        ],
      },
      {
        path: '/o/:orgId',
        element: <OrgLayout />,
        children: [
          { index: true, element: <UnePage /> },
          { path: 'pronos', element: <PronoListPage /> },
          { path: 'pronos/nouveau', element: <CreatePronoPage />, handle: { bare: true } },
          { path: 'pronos/:pronoId', element: <PronoPage /> },
          { path: 'classement', element: <LeaderboardPage /> },
          { path: 'profil', element: <PressCardPage /> },
          { path: 'profil/carte', element: <CardEditorPage /> },
          { path: 'redaction', element: <NewsroomPage /> },
          { path: 'membres/:memberId', element: <PressCardPage /> },
          { path: 'collection', element: <CollectionPage /> },
          { path: 'jeux/course', element: <RunnerPage /> },
          { path: 'jeux/pixel', element: <PixelMysterePage /> },
          {
            path: 'reglages',
            element: <AdminLayout />,
            children: [
              { index: true, element: <OrgSettingsPage /> },
              { path: 'membres', element: <MembersPage /> },
              { path: 'jeux', element: <GameSchedulePage /> },
              { path: 'signalements', element: <ReportsPage /> },
              { path: 'parametres', element: <ParametersPage /> },
            ],
          },
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
