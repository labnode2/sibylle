// A press card its member made public (US15), for anyone, without an account: the card and its
// three figures, alone on the paper, small enough for another site's iframe. Search engines are
// asked to leave it out: the link is for those the member gives it to.
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { ApiError } from '../../api/client';
import { usePublicCard } from './api';
import { Identity, Stats } from './PressCardPage';
import styles from './profile.module.css';

export function PublicCardPage() {
  const { t } = useTranslation('profile');
  const { token = '' } = useParams();
  const card = usePublicCard(token);
  const missing = card.error instanceof ApiError && card.error.status === 404;

  return (
    <main className={styles.publicPage}>
      <meta name="robots" content="noindex" />
      {card.data ? (
        <div className={styles.publicCard}>
          <h1 className="visually-hidden">{t('titleOf', { pseudo: card.data.pseudo })}</h1>
          <Identity card={card.data} orgTitle={card.data.newsroom.title} />
          <Stats stats={card.data.stats} />
        </div>
      ) : card.error ? (
        <p role="alert" className={styles.publicMissing}>
          {t(missing ? 'public.missing' : 'public.error')}
        </p>
      ) : (
        <p role="status">{t('common:shell.loading')}</p>
      )}
    </main>
  );
}
