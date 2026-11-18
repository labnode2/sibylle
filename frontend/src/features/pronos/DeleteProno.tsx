// « Supprimer le prono », on the page of a cancelled prono, for whoever may delete it (the editor,
// as for cancelling): after a confirmation it leaves the lists and la une for the whole newsroom,
// and the page goes on to the list. Its stakes are already back, and the refunds stay in each
// member's history.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router';

import { Button } from '../../ui/components';
import { useDeleteProno, type PronoDetail } from './api';
import styles from './pronos.module.css';

export function DeleteProno({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  const navigate = useNavigate();
  const remove = useDeleteProno(orgId, prono.id);
  const [asking, setAsking] = useState(false);

  if (!prono.can_delete) return null;
  if (!asking) {
    return (
      <Button variant="dangerSecondary" className={styles.edit} onClick={() => setAsking(true)}>
        {t('detail.delete')}
      </Button>
    );
  }
  return (
    <div className={styles.confirm} role="group" aria-label={t('detail.delete')}>
      <p>{t('detail.deleteConfirm')}</p>
      <div className={styles.actions}>
        <Button variant="secondary" onClick={() => setAsking(false)}>
          {t('detail.deleteBack')}
        </Button>
        <Button
          variant="danger"
          disabled={remove.isPending}
          onClick={() =>
            remove.mutate(undefined, {
              onSuccess: () => void navigate(`/o/${orgId}/pronos`, { replace: true }),
            })
          }
        >
          {t('detail.deleteSubmit')}
        </Button>
      </div>
    </div>
  );
}
