// « Paramètres »: deleting the newsroom. The editor types its name to confirm; it then disappears
// for every member at once, but nothing is erased, so that it can be restored as it was.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { Button, Field } from '../../ui/components';
import { useOrg } from '../orgs/api';
import { useDeleteOrg } from './api';
import styles from './admin.module.css';

/** Names compare loosely: spaces around and letter case do not count. */
const loose = (name: string) => name.trim().toLocaleLowerCase('fr');

function DeleteNewsroom({ org }: { org: Org }) {
  const { t } = useTranslation('admin');
  const navigate = useNavigate();
  const remove = useDeleteOrg(org.id);
  const [asking, setAsking] = useState(false);
  const [name, setName] = useState('');
  const confirmed = loose(name) === loose(org.title);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!confirmed || remove.isPending) return;
    remove.mutate(undefined, { onSuccess: () => void navigate('/', { replace: true }) });
  };

  return (
    <section className={styles.panel} aria-labelledby="admin-delete">
      <h2 id="admin-delete" className={styles.heading}>
        {t('parameters.delete.title')}
      </h2>
      <p className={styles.text}>{t('parameters.delete.text')}</p>
      <p className={styles.text}>{t('parameters.delete.restore')}</p>
      {asking ? (
        <form className={styles.danger} onSubmit={submit} noValidate>
          <p>{t('parameters.delete.confirm', { org: org.title })}</p>
          <Field
            label={t('parameters.delete.name')}
            value={name}
            maxLength={40}
            autoComplete="off"
            onChange={(event) => setName(event.target.value)}
          />
          <div className={styles.actions}>
            <Button
              variant="secondary"
              onClick={() => {
                setAsking(false);
                setName('');
              }}
            >
              {t('parameters.delete.cancel')}
            </Button>
            <Button type="submit" variant="danger" disabled={!confirmed || remove.isPending}>
              {t('parameters.delete.confirmYes')}
            </Button>
          </div>
        </form>
      ) : (
        <div>
          <Button variant="dangerSecondary" onClick={() => setAsking(true)}>
            {t('parameters.delete.open')}
          </Button>
        </div>
      )}
    </section>
  );
}

export function ParametersPage() {
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  if (!org.data) return null;
  return <DeleteNewsroom org={org.data} />;
}
