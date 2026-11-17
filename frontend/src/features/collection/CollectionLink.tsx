// « Ma collection » in one click: a chest beside my pseudo in the computer's date bar, and beside
// my laurels on la une's top line on a phone. Like the line under my press card, it tells the
// collection which page opened it, for its way back.
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useMatch } from 'react-router';

import { Icon } from '../../ui/components';

export function CollectionLink({ orgId, className }: { orgId: string; className?: string }) {
  const { t } = useTranslation('profile');
  const { pathname, state } = useLocation();
  // Opened again from the collection itself, it keeps the way back it already has.
  const here = useMatch('/o/:orgId/collection') !== null;
  return (
    <Link
      to={`/o/${orgId}/collection`}
      state={here ? state : { from: pathname }}
      className={className}
      title={t('collectionLink')}
      aria-label={t('collectionLink')}
      aria-current={here ? 'page' : undefined}
    >
      <Icon name="chest" size={24} />
    </Link>
  );
}
