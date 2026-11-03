// The press card (canvas B-Profil on a phone, B-Web-Profil on a computer): number, pseudo,
// avatar in its frame, arrival, statistics, engraved trophies (a gold frame for the podium) and
// the collection. On one's own card: the avatar editor, the frame, the collection and the
// statement.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { formatDate, formatNumber } from '../../i18n';
import { ButtonLink, Button, Card, Kicker, Laurel } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import { FramedAvatar } from '../../ui/FramedAvatar';
import type { Variant } from '../../vendor/crystal-ball/crystal-ball.js';
import { useMe } from '../auth/api';
import { ItemPreview } from '../collection/ItemPreview';
import { useFormErrors } from '../forms';
import { NotificationPrefs } from '../notifications/NotificationPrefs';
import { useOrg } from '../orgs/api';
import { PixelEditor } from '../pixel-editor/PixelEditor';
import { usePressCard, useUpdateProfile, type PressCard } from './api';
import { LedgerList } from './LedgerList';
import styles from './profile.module.css';

function Stats({ card }: { card: PressCard }) {
  const { t } = useTranslation('profile');
  const { stats } = card;
  return (
    <dl className={styles.stats}>
      <div>
        <dt>{t('stats.laurels')}</dt>
        <dd>
          <Laurel value={stats.laurels} />
        </dd>
      </div>
      <div>
        <dt>{t('stats.played')}</dt>
        <dd>{formatNumber(stats.pronos_played)}</dd>
      </div>
      <div>
        <dt>{t('stats.wins')}</dt>
        <dd>{formatNumber(stats.wins)}</dd>
      </div>
      <div>
        <dt>{t('stats.rate')}</dt>
        <dd>{stats.success_rate === null ? '—' : `${stats.success_rate} %`}</dd>
      </div>
    </dl>
  );
}

function MyTools({ orgId, card }: { orgId: string; card: PressCard }) {
  const { t } = useTranslation('profile');
  const org = useOrg(orgId);
  const update = useUpdateProfile(orgId);
  const errors = useFormErrors(update.error);
  const [editing, setEditing] = useState(false);
  const frames = card.collection.filter((owned) => owned.item.kind === 'frame');
  const currentFrame = frames.find((owned) => owned.item.key === card.frame)?.item.id ?? '';

  return (
    <div className={styles.tools}>
      {editing ? (
        <PixelEditor
          initial={card.avatar}
          unlocked={org.data?.my_membership.unlocked_colors ?? []}
          title={t('editor.title')}
          saveLabel={t('editor.save')}
          busy={update.isPending}
          error={errors.field('avatar') ?? errors.message}
          onCancel={() => setEditing(false)}
          onSave={(avatar) => update.mutate({ avatar }, { onSuccess: () => setEditing(false) })}
        />
      ) : (
        <div className={styles.actions}>
          <Button onClick={() => setEditing(true)}>{t('editor.open')}</Button>
          <ButtonLink to={`/o/${orgId}/collection`} variant="secondary">
            {t('collectionLink')}
          </ButtonLink>
        </div>
      )}
      {frames.length > 0 && (
        <label className={styles.frameChoice}>
          <span className={styles.label}>{t('frame.label')}</span>
          <select
            value={currentFrame}
            disabled={update.isPending}
            onChange={(event) =>
              update.mutate({ avatar_frame_item_id: event.target.value || null })
            }
          >
            <option value="">{t('frame.none')}</option>
            {frames.map((owned) => (
              <option key={owned.item.id} value={owned.item.id}>
                {t(`catalog.${owned.item.key}`)}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}

export function PressCardPage() {
  const { t } = useTranslation('profile');
  const { orgId = '', memberId } = useParams();
  const org = useOrg(orgId);
  const me = org.data?.my_membership;
  const id = memberId ?? me?.id;
  const card = usePressCard(orgId, id);
  const account = useMe();
  if (!card.data || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const data = card.data;
  const mine = data.id === me?.id;
  const since = formatDate(data.joined_at, { month: 'long', year: 'numeric' }).toUpperCase();

  return (
    <div className={styles.page}>
      <Card className={styles.card} aria-label={t('title')}>
        <div className={styles.cardHead}>
          <Kicker tone="indigo">{t('number', { number: data.card_number })}</Kicker>
          <Kicker>{org.data.title.toUpperCase()}</Kicker>
        </div>
        <div className={styles.identity}>
          <FramedAvatar image={data.avatar} frame={data.frame} size={96} />
          <div className={styles.identityText}>
            <span className={styles.label}>{t('title')}</span>
            <h1 className={styles.pseudo}>{data.pseudo}</h1>
            <span className={styles.meta}>
              {t(`roles.${data.role}`)} · {t('since', { date: since })}
            </span>
          </div>
        </div>
        <Stats card={data} />
      </Card>

      {mine && <MyTools orgId={orgId} card={data} />}

      <section className={styles.section} aria-label={t('trophies.title')}>
        <h2 className={styles.sectionTitle}>{t('trophies.title')}</h2>
        {data.trophies.length === 0 ? (
          <p className={styles.meta}>{t('trophies.none')}</p>
        ) : (
          <ul className={styles.items}>
            {data.trophies.map((trophy) => (
              <li
                key={`${trophy.season.year}-${trophy.season.name}`}
                className={`${styles.trophy} ${trophy.podium ? styles.podium : ''}`}
              >
                <CrystalBall variant={trophy.season.name as Variant} size={48} />
                <span className={styles.engraved}>
                  {t('trophies.season', {
                    season: t(`seasons.${trophy.season.name}`),
                    year: trophy.season.year,
                  })}
                </span>
                <span className={styles.meta}>
                  {t('trophies.score', { score: formatNumber(trophy.score), rank: trophy.rank })}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={styles.section} aria-label={t('collection.title')}>
        <h2 className={styles.sectionTitle}>{t('collection.title')}</h2>
        {data.collection.length === 0 ? (
          <p className={styles.meta}>{t('collection.none')}</p>
        ) : (
          <ul className={styles.items}>
            {data.collection.map((owned) => (
              <li key={owned.item.id} className={styles.item}>
                <ItemPreview item={owned.item} avatar={data.avatar} />
                <span className={styles.meta}>{t(`catalog.${owned.item.key}`)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {mine && account.data && <NotificationPrefs emailVerified={account.data.email_verified} />}

      {mine && <LedgerList orgId={orgId} />}
    </div>
  );
}
