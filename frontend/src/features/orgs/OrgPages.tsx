// Creating a newsroom, joining one (G-Rejoindre), and the start page for accounts without one.
import { useId, useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router';

import type { OrgCard, PixelImage } from '../../api/types';
import { Button, ButtonLink, Card, Field, Icon, Rule } from '../../ui/components';
import { PixelImage as Pixels } from '../../ui/PixelImage';
import { useMe } from '../auth/api';
import { useFormErrors } from '../forms';
import { useContent, useCreateOrg, useJoin, useJoinPreview, type JoinSource } from './api';
import styles from './orgs.module.css';
import { AvatarPicker, BackgroundPicker } from './pickers';

/** `/`: the first newsroom of the account, or the start page. */
export function HomeRedirect() {
  const me = useMe();
  const first = me.data?.memberships[0];
  return <Navigate to={first ? `/o/${first.org.id}` : '/bienvenue'} replace />;
}

export function StartPage() {
  const { t } = useTranslation('orgs');
  const navigate = useNavigate();
  const [code, setCode] = useState('');
  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('start.title')}</h1>
      <p>{t('start.lead')}</p>
      <form
        className={styles.form}
        onSubmit={(event) => {
          event.preventDefault();
          navigate(`/rejoindre?code=${encodeURIComponent(code.trim())}`);
        }}
      >
        <Field
          label={t('join.code')}
          value={code}
          onChange={(e) => setCode(e.target.value.toUpperCase())}
          autoCapitalize="characters"
          placeholder="SOPHIA-7K2"
        />
        <Button type="submit" variant="secondary" disabled={!code.trim()}>
          {t('start.join')}
        </Button>
      </form>
      <Rule variant="light" />
      <ButtonLink to="/creer" block>
        {t('start.create')}
      </ButtonLink>
    </section>
  );
}

export function NewsroomCard({
  org,
  kicker,
  meta,
}: {
  org: OrgCard;
  kicker?: string;
  meta?: string;
}) {
  return (
    <Card className={styles.invitation} aria-label={org.title}>
      <div className={`${styles.band} bg-${org.background_key}`} aria-hidden="true">
        {org.logo && (
          <span className={styles.logo}>
            <Pixels image={org.logo} size={48} avatar={false} />
          </span>
        )}
      </div>
      <div className={styles.cardBody}>
        {kicker && <span className={styles.cardKicker}>{kicker}</span>}
        <h1 className={styles.title}>{org.title}</h1>
        {meta && <span className={styles.cardMeta}>{meta}</span>}
      </div>
    </Card>
  );
}

function ProfileFields({
  pseudo,
  setPseudo,
  avatar,
  setAvatar,
  pseudoError,
}: {
  pseudo: string;
  setPseudo: (value: string) => void;
  avatar: PixelImage | null;
  setAvatar: (value: PixelImage) => void;
  pseudoError?: string;
}) {
  const { t } = useTranslation('orgs');
  const content = useContent();
  const avatarLabel = useId();
  return (
    <>
      <Field
        label={t('join.pseudo')}
        hint={t('join.private')}
        value={pseudo}
        onChange={(e) => setPseudo(e.target.value)}
        maxLength={24}
        error={pseudoError}
        required
      />
      <span id={avatarLabel} className={styles.label}>
        {t('join.avatar')}
      </span>
      <div className={styles.choices}>
        <AvatarPicker
          templates={content.data?.avatars ?? []}
          value={avatar}
          onChange={setAvatar}
          labelId={avatarLabel}
        />
        <span className={styles.draw} aria-disabled="true" title={t('join.drawLater')}>
          {t('join.draw')}
        </span>
      </div>
    </>
  );
}

export function CreateOrgPage() {
  const { t } = useTranslation('orgs');
  const navigate = useNavigate();
  const content = useContent();
  const create = useCreateOrg();
  const errors = useFormErrors(create.error);
  const backgroundLabel = useId();
  const [title, setTitle] = useState('');
  const [background, setBackground] = useState('mer');
  const [pseudo, setPseudo] = useState('');
  const [avatar, setAvatar] = useState<PixelImage | null>(null);
  const chosenAvatar = avatar ?? content.data?.avatars[0]?.image ?? null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!chosenAvatar) return;
    create.mutate(
      { title, background_key: background, pseudo, avatar: chosenAvatar },
      { onSuccess: (created) => navigate(`/o/${created.org.id}`) },
    );
  };

  return (
    <section className={styles.page}>
      <h1 className={styles.title}>{t('create.title')}</h1>
      <form className={styles.form} onSubmit={submit} noValidate>
        {errors.message && (
          <p className={styles.alert} role="alert">
            {errors.message}
          </p>
        )}
        <Field
          label={t('create.name')}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          maxLength={40}
          error={errors.field('title')}
          required
        />
        <span id={backgroundLabel} className={styles.label}>
          {t('create.background')}
        </span>
        <BackgroundPicker
          keys={content.data?.backgrounds ?? []}
          value={background}
          onChange={setBackground}
          labelId={backgroundLabel}
        />
        <ProfileFields
          pseudo={pseudo}
          setPseudo={setPseudo}
          avatar={chosenAvatar}
          setAvatar={setAvatar}
          pseudoError={errors.field('pseudo')}
        />
        <Button type="submit" block disabled={create.isPending || !title.trim()}>
          {t('create.submit')}
        </Button>
        <p className={styles.hint}>{t('create.editor')}</p>
      </form>
    </section>
  );
}

export function JoinPage() {
  const { t } = useTranslation('orgs');
  const navigate = useNavigate();
  const { token } = useParams();
  const [search] = useSearchParams();
  const code = search.get('code');
  const source: JoinSource | null = token ? { token } : code ? { code } : null;
  const preview = useJoinPreview(source);
  const join = useJoin();
  const errors = useFormErrors(join.error);
  const content = useContent();
  const [pseudo, setPseudo] = useState('');
  const [avatar, setAvatar] = useState<PixelImage | null>(null);
  const [accepted, setAccepted] = useState(false);
  const chosenAvatar = avatar ?? content.data?.avatars[0]?.image ?? null;

  if (!source) return <Navigate to="/bienvenue" replace />;
  if (preview.isPending) return <p role="status">{t('common:shell.loading')}</p>;
  if (preview.isError) {
    return (
      <section className={styles.page}>
        <p className={styles.alert} role="alert">
          {t('join.invalid')}
        </p>
        <Link to="/bienvenue">{t('join.back')}</Link>
      </section>
    );
  }

  const data = preview.data;
  const meta = [
    t('join.members', { count: data.member_count }),
    data.places_left !== null ? t('join.places', { count: data.places_left }) : null,
  ]
    .filter(Boolean)
    .join(' · ');

  if (data.already_member) {
    return (
      <section className={styles.page}>
        <NewsroomCard org={data.org} meta={meta} />
        <p>{t('join.already')}</p>
        <ButtonLink to={`/o/${data.org.id}`}>{t('join.open')}</ButtonLink>
      </section>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!chosenAvatar || !accepted) return;
    join.mutate(
      { ...source, pseudo, avatar: chosenAvatar, charter_accepted: true },
      { onSuccess: (joined) => navigate(`/o/${joined.org.id}`) },
    );
  };

  return (
    <section className={styles.page}>
      <NewsroomCard
        org={data.org}
        kicker={
          data.invited_by_pseudo
            ? t('join.invitedBy', { pseudo: data.invited_by_pseudo.toUpperCase() })
            : undefined
        }
        meta={meta.toUpperCase()}
      />
      {code && (
        <div className={styles.code}>
          <Field label={t('join.code')} value={code} readOnly />
          <span className={styles.valid}>
            <Icon name="check" />
            {t('join.valid')}
          </span>
        </div>
      )}
      <form className={styles.form} onSubmit={submit} noValidate>
        {errors.message && (
          <p className={styles.alert} role="alert">
            {errors.message}
          </p>
        )}
        <ProfileFields
          pseudo={pseudo}
          setPseudo={setPseudo}
          avatar={chosenAvatar}
          setAvatar={setAvatar}
          pseudoError={errors.field('pseudo')}
        />
        <details className={styles.charter}>
          <summary>{t('join.charterTitle')}</summary>
          {data.charter}
        </details>
        <label className={styles.check}>
          <input
            type="checkbox"
            checked={accepted}
            onChange={(e) => setAccepted(e.target.checked)}
          />
          {t('join.accept')}
        </label>
        <Button
          type="submit"
          block
          disabled={join.isPending || !accepted || pseudo.trim().length < 2}
        >
          {t('join.submit')}
        </Button>
        <p className={styles.hint}>{t('join.later')}</p>
      </form>
    </section>
  );
}
