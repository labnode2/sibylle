// The bell's list: what happened in the newsroom, the unread first marked; a click leads to the
// prono concerned and marks the line read.
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { formatDate } from '../../i18n';
import { Button, Kicker } from '../../ui/components';
import { useMarkRead, useNotificationList } from './api';
import styles from './notifications.module.css';

export function NotificationsPage() {
  const { t } = useTranslation('notifications');
  const { orgId = '' } = useParams();
  const navigate = useNavigate();
  const list = useNotificationList(orgId);
  const markRead = useMarkRead(orgId);
  if (!list.data) return <p role="status">{t('common:shell.loading')}</p>;
  const { items, unread } = list.data;

  return (
    <section className={styles.section} aria-label={t('list.title')}>
      <h1 className={styles.title}>{t('list.title')}</h1>
      {unread > 0 && (
        <Button variant="secondary" onClick={() => markRead.mutate(undefined)}>
          {t('list.readAll')}
        </Button>
      )}
      {items.length === 0 && <p>{t('list.none')}</p>}
      <ul className={styles.list}>
        {items.map((item) => (
          <li key={item.id}>
            <button
              type="button"
              className={`${styles.line} ${item.read_at ? '' : styles.lineUnread}`}
              onClick={() => {
                if (!item.read_at) markRead.mutate(item.id);
                void navigate(`/o/${orgId}/pronos/${item.prono_id}`);
              }}
            >
              <Kicker tone="indigo">
                {t(`list.lines.${item.type}`)} ·{' '}
                {formatDate(item.created_at, {
                  day: 'numeric',
                  month: 'short',
                  hour: '2-digit',
                  minute: '2-digit',
                }).toUpperCase()}
              </Kicker>
              <span>{item.question}</span>
              {!item.read_at && <span className="visually-hidden">{t('list.unread')}</span>}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
