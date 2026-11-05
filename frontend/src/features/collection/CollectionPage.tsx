// The collection: colours for the pixel editor, avatar frames and crystal balls, bought with
// coins (laurels and score never move), the deal of the week, and secret codes for surprises.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { Button, Card, Chip, Coins, Field, TopBar } from '../../ui/components';
import { toast } from '../../ui/Toaster';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { useCatalog, useCollectionActions, type CatalogEntry } from '../profile/api';
import { ItemPreview } from './ItemPreview';
import styles from './collection.module.css';

const KINDS = ['color', 'frame', 'ball'] as const;

type Avatar = Parameters<typeof ItemPreview>[0]['avatar'];

/** « −30 % », the usual price struck through, then the deal's. */
function DealPrice({ entry }: { entry: CatalogEntry }) {
  const { t } = useTranslation('profile');
  return (
    <span className={styles.dealPrice}>
      <Chip variant="stamp">{t('collection.deal.off', { pct: entry.discount_pct })}</Chip>
      <s className={styles.was}>
        <span className="visually-hidden">{t('collection.deal.was')} </span>
        {formatNumber(entry.regular_price ?? 0)}
      </s>
    </span>
  );
}

/** « La promo de la semaine »: the object on sale this week, its share off and until when. */
function Deal({ entry, avatar }: { entry: CatalogEntry; avatar: Avatar }) {
  const { t } = useTranslation('profile');
  // The deal ends next Monday at 00:00: it runs until Sunday night.
  const lastDay = formatDate(new Date(new Date(entry.discount_until!).getTime() - 60_000), {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  });
  return (
    <Card className={styles.deal} aria-labelledby="collection-deal">
      <ItemPreview item={entry.item} avatar={avatar} />
      <div className={styles.dealText}>
        <h2 id="collection-deal" className={styles.dealTitle}>
          {t('collection.deal.title')}
        </h2>
        <p className={styles.name}>{t(`catalog.${entry.item.key}`)}</p>
        <p className={styles.dealLine}>
          <DealPrice entry={entry} />
          <Coins value={entry.price ?? 0} />
        </p>
        <p className={styles.hint}>
          {t('collection.deal.until', { day: lastDay.toUpperCase() })}
          {entry.owned && ` · ${t('collection.owned')}`}
        </p>
      </div>
    </Card>
  );
}

function Item({
  orgId,
  entry,
  coins,
  avatar,
}: {
  orgId: string;
  entry: CatalogEntry;
  coins: number;
  avatar: Avatar;
}) {
  const { t } = useTranslation('profile');
  const { buy } = useCollectionActions(orgId);
  const [confirming, setConfirming] = useState(false);
  const name = t(`catalog.${entry.item.key}`);
  const price = entry.price ?? 0;
  const onSale = entry.discount_pct != null;

  return (
    <li className={`${styles.item} ${onSale ? styles.itemDeal : ''}`} aria-label={name}>
      <ItemPreview item={entry.item} avatar={avatar} />
      <span className={styles.name}>{name}</span>
      {onSale && !entry.owned && <DealPrice entry={entry} />}
      {entry.owned ? (
        <Chip variant="ink">{t('collection.owned')}</Chip>
      ) : confirming ? (
        <div className={styles.confirm}>
          <span>{t('collection.confirm', { price: formatNumber(price) })}</span>
          <Button variant="secondary" onClick={() => setConfirming(false)}>
            {t('collection.no')}
          </Button>
          <Button
            onClick={() =>
              buy.mutate(
                { itemId: entry.item.id, price },
                {
                  onSuccess: () => {
                    setConfirming(false);
                    toast.success(t('collection.bought', { name }));
                  },
                },
              )
            }
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
          aria-label={
            onSale
              ? t('collection.buyDealLabel', { name, price, regular: entry.regular_price })
              : t('collection.buyLabel', { name, price })
          }
        >
          <Coins value={price} />
        </Button>
      )}
    </li>
  );
}

function SecretCode({ orgId }: { orgId: string }) {
  const { t } = useTranslation('profile');
  const { redeem } = useCollectionActions(orgId);
  const errors = useFormErrors(redeem.error);
  const [code, setCode] = useState('');

  const submit = (event: FormEvent) => {
    event.preventDefault();
    redeem.mutate(code.trim(), {
      onSuccess: ({ item }) => {
        toast.success(t('secret.unlocked', { name: t(`catalog.${item.key}`) }));
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
  const deal = catalog.data.find((entry) => entry.discount_pct != null);

  return (
    <div className={styles.page}>
      <TopBar back={`/o/${orgId}/profil`} backLabel={t('collection.back')} />
      <div className={styles.top}>
        <h1 className={styles.title}>{t('collection.title')}</h1>
        <span className={styles.balance}>
          {t('collection.coins')} <Coins value={me.coins} />
        </span>
      </div>
      <p className={styles.hint}>{t('collection.hint')}</p>
      {deal && <Deal entry={deal} avatar={me.avatar} />}
      {KINDS.map((kind) => {
        const entries = catalog.data.filter((entry) => entry.item.kind === kind);
        return (
          <Card key={kind} className={styles.panel} aria-label={t(`collection.kinds.${kind}`)}>
            <h2 className={styles.heading}>{t(`collection.kinds.${kind}`)}</h2>
            {/* The balls are not sold: only the ones won with a secret code show here. */}
            {kind === 'ball' && <p className={styles.hint}>{t('collection.noBall')}</p>}
            {entries.length > 0 && (
              <ul className={styles.items}>
                {entries.map((entry) => (
                  <Item
                    key={entry.item.id}
                    orgId={orgId}
                    entry={entry}
                    coins={me.coins}
                    avatar={me.avatar}
                  />
                ))}
              </ul>
            )}
          </Card>
        );
      })}
      <SecretCode orgId={orgId} />
      <Link to={`/o/${orgId}/profil`} className={styles.back}>
        {t('collection.backToCard')}
      </Link>
    </div>
  );
}
