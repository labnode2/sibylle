// The collection: colours for the pixel editor, avatar frames and crystal balls, bought with
// coins (laurels and score never move), and secret codes for surprises.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatNumber } from '../../i18n';
import { Button, Card, Chip, Coins, Field } from '../../ui/components';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { useCatalog, useCollectionActions, type CatalogEntry } from '../profile/api';
import { ItemPreview } from './ItemPreview';
import styles from './collection.module.css';

const KINDS = ['color', 'frame', 'ball'] as const;

function Item({
  orgId,
  entry,
  coins,
  avatar,
}: {
  orgId: string;
  entry: CatalogEntry;
  coins: number;
  avatar: Parameters<typeof ItemPreview>[0]['avatar'];
}) {
  const { t } = useTranslation('profile');
  const { buy } = useCollectionActions(orgId);
  const errors = useFormErrors(buy.error);
  const [confirming, setConfirming] = useState(false);
  const name = t(`catalog.${entry.item.key}`);
  const price = entry.price ?? 0;

  return (
    <li className={styles.item} aria-label={name}>
      <ItemPreview item={entry.item} avatar={avatar} />
      <span className={styles.name}>{name}</span>
      {entry.owned ? (
        <Chip variant="ink">{t('collection.owned')}</Chip>
      ) : confirming ? (
        <div className={styles.confirm}>
          <span>{t('collection.confirm', { price: formatNumber(price) })}</span>
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            {t('collection.no')}
          </Button>
          <Button
            onClick={() => buy.mutate(entry.item.id, { onSuccess: () => setConfirming(false) })}
            disabled={buy.isPending}
          >
            {t('collection.yes')}
          </Button>
        </div>
      ) : (
        <Button
          variant="secondary"
          onClick={() => setConfirming(true)}
          disabled={price > coins}
          aria-label={t('collection.buyLabel', { name, price })}
        >
          <Coins value={price} />
        </Button>
      )}
      {errors.message && (
        <p role="alert" className={styles.alert}>
          {errors.message}
        </p>
      )}
    </li>
  );
}

function SecretCode({ orgId }: { orgId: string }) {
  const { t } = useTranslation('profile');
  const { redeem } = useCollectionActions(orgId);
  const errors = useFormErrors(redeem.error);
  const [code, setCode] = useState('');
  const [unlocked, setUnlocked] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setUnlocked(null);
    redeem.mutate(code.trim(), {
      onSuccess: ({ item }) => {
        setUnlocked(t(`catalog.${item.key}`));
        setCode('');
      },
    });
  };

  return (
    <Card className={styles.panel} aria-label={t('secret.title')}>
      <h2 className={styles.heading}>{t('secret.title')}</h2>
      <form className={styles.secret} onSubmit={submit} noValidate>
        <Field
          label={t('secret.label')}
          value={code}
          maxLength={64}
          autoComplete="off"
          onChange={(event) => setCode(event.target.value)}
          error={errors.field('code') ? t('secret.unknown') : undefined}
        />
        <Button type="submit" disabled={!code.trim() || redeem.isPending}>
          {t('secret.submit')}
        </Button>
      </form>
      {unlocked && <p role="status">{t('secret.unlocked', { name: unlocked })}</p>}
      {errors.message && !errors.field('code') && (
        <p role="alert" className={styles.alert}>
          {errors.message}
        </p>
      )}
    </Card>
  );
}

export function CollectionPage() {
  const { t } = useTranslation('profile');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const catalog = useCatalog(orgId);
  if (!org.data || !catalog.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <h1 className={styles.title}>{t('collection.title')}</h1>
        <span className={styles.balance}>
          {t('collection.coins')} <Coins value={me.coins} />
        </span>
      </div>
      <p className={styles.hint}>{t('collection.hint')}</p>
      {KINDS.map((kind) => (
        <Card key={kind} className={styles.panel} aria-label={t(`collection.kinds.${kind}`)}>
          <h2 className={styles.heading}>{t(`collection.kinds.${kind}`)}</h2>
          <ul className={styles.items}>
            {catalog.data
              .filter((entry) => entry.item.kind === kind)
              .map((entry) => (
                <Item
                  key={entry.item.id}
                  orgId={orgId}
                  entry={entry}
                  coins={me.coins}
                  avatar={me.avatar}
                />
              ))}
          </ul>
        </Card>
      ))}
      <SecretCode orgId={orgId} />
      <Link to={`/o/${orgId}/profil`} className={styles.back}>
        {t('collection.backToCard')}
      </Link>
    </div>
  );
}
