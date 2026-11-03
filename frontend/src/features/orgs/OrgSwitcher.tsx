// The account's newsrooms (from GET /me): switch between them, or join / create another one.
import { useTranslation } from 'react-i18next';
import { Link, useNavigate, useParams } from 'react-router';

import type { OrgCard } from '../../api/types';
import { Button, ButtonLink, Icon } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useLogout, useMe } from '../auth/api';
import styles from './orgs.module.css';

export function OrgSwitcherPage() {
  const { t } = useTranslation('orgs');
  const { orgId } = useParams();
  const me = useMe();
  const logout = useLogout();
  const navigate = useNavigate();
  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('switcher.title')}</h1>
      <nav className={styles.switcher} aria-label={t('switcher.title')}>
        {me.data?.memberships.map(({ org, membership }) => (
          <Link
            key={org.id}
            to={`/o/${org.id}`}
            className={styles.switcherItem}
            aria-current={org.id === orgId ? 'page' : undefined}
          >
            <PixelImage image={membership.avatar} size={32} />
            <span>{org.title}</span>
          </Link>
        ))}
      </nav>
      <ButtonLink to="/bienvenue" variant="secondary">
        <Icon name="plus" />
        {t('switcher.more')}
      </ButtonLink>
      <ButtonLink to="/compte" variant="secondary">
        <Icon name="gear" />
        {t('switcher.settings')}
      </ButtonLink>
      <Button
        variant="link"
        disabled={logout.isPending}
        onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/connexion') })}
      >
        {t('switcher.logout')}
      </Button>
    </section>
  );
}

/** « ÉDITION SOPHIA OFFICE » in the desktop navigation: opens the newsroom list. */
export function EditionLink({ org }: { org: OrgCard }) {
  const { t } = useTranslation('orgs');
  return (
    <Link to="/redactions" className={styles.edition}>
      {org.logo && <PixelImage image={org.logo} size={16} avatar={false} />}
      <span>{t('switcher.edition', { title: org.title.toUpperCase() })}</span>
      <Icon name="chevronDown" />
    </Link>
  );
}
