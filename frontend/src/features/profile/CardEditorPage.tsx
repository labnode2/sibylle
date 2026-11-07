// « Personnaliser ma carte » (canvases G-Pixel and B-Profil together): the press card as the other
// members will see it, redrawn at each change, with « Annuler » and « Enregistrer » under it,
// which wake up once something changed; beside it, what makes the card: the pseudo, the pixel
// art, the frame and the animation among those of the collection, and up to three objects or
// engraved trophies shown in the order they were chosen. Saving keeps the page open;
// « Annuler » puts back what was saved.
import { useCallback, useState, type FormEvent, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import type { Org } from '../../api/types';
import { Button, Field, TopBar } from '../../ui/components';
import { CrystalBall } from '../../ui/CrystalBall';
import { FramedAvatar } from '../../ui/FramedAvatar';
import { decodePixels, encodePixels } from '../../ui/PixelImage';
import { toast } from '../../ui/Toaster';
import type { Variant } from '../../vendor/crystal-ball/crystal-ball.js';
import { ItemPreview } from '../collection/ItemPreview';
import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { PixelEditor, type Drawing } from '../pixel-editor/PixelEditor';
import { usePressCard, useUpdateProfile, type PressCard } from './api';
import { Identity } from './PressCardPage';
import styles from './profile.module.css';

const SHOWCASE_MAX = 3;

type Ref = { kind: 'item' | 'trophy'; id: string };
type Candidate = Ref & { name: string; preview: ReactNode; podium?: boolean };
type Shown = PressCard['showcase'][number];
/** What the page edits: saved, or in progress. */
type Draft = {
  pseudo: string;
  avatar: Drawing;
  frameId: string;
  animationId: string;
  showcase: Ref[];
};
type Wearable = 'frame' | 'animation';

/** The id of the frame or the animation the card wears, among the member's collection. */
const wornId = (card: PressCard, kind: Wearable) =>
  card.collection.find((owned) => owned.item.kind === kind && owned.item.key === card[kind])?.item
    .id ?? '';

const same = (a: Ref) => (b: Ref) => a.kind === b.kind && a.id === b.id;

function draftOf(card: PressCard): Draft {
  return {
    pseudo: card.pseudo,
    // Encoded as the editor encodes it, so that an untouched drawing compares equal.
    avatar: {
      size: card.avatar.size,
      palette: 'base-v1',
      pixels: encodePixels(decodePixels(card.avatar)),
    },
    frameId: wornId(card, 'frame'),
    animationId: wornId(card, 'animation'),
    showcase: card.showcase.flatMap((entry): Ref[] => {
      if (entry.kind === 'item' && entry.item) return [{ kind: 'item', id: entry.item.id }];
      if (entry.kind === 'trophy' && entry.trophy) return [{ kind: 'trophy', id: entry.trophy.id }];
      return [];
    }),
  };
}

const unchanged = (a: Draft, b: Draft) =>
  a.pseudo.trim() === b.pseudo.trim() &&
  a.avatar.size === b.avatar.size &&
  a.avatar.pixels === b.avatar.pixels &&
  a.frameId === b.frameId &&
  a.animationId === b.animationId &&
  a.showcase.length === b.showcase.length &&
  a.showcase.every((ref, index) => same(ref)(b.showcase[index]!));

/** The frames, or the animations, of the member's collection, « none » first; or, without any,
 *  the way to the collection. */
function WearablePicker({
  kind,
  orgId,
  owned,
  chosen,
  onChoose,
  preview,
}: {
  kind: Wearable;
  orgId: string;
  owned: PressCard['collection'];
  chosen: string;
  onChoose: (id: string) => void;
  preview: (key: string | null) => ReactNode;
}) {
  const { t } = useTranslation('profile');
  const legend = t(`customize.${kind}`);
  return (
    <fieldset className={styles.choices}>
      <legend className={styles.label}>{legend}</legend>
      {owned.length === 0 ? (
        <p className={styles.meta}>
          {t(`customize.no.${kind}`)}{' '}
          <Link to={`/o/${orgId}/collection`}>{t('customize.collection')}</Link>
        </p>
      ) : (
        <div className={styles.choiceGrid} role="radiogroup" aria-label={legend}>
          {[
            { id: '', key: null, name: t(`${kind}.none`) },
            ...owned.map((entry) => ({
              id: entry.item.id,
              key: entry.item.key,
              name: t(`catalog.${entry.item.key}`),
            })),
          ].map((choice) => (
            <button
              key={choice.id || 'none'}
              type="button"
              role="radio"
              aria-checked={chosen === choice.id}
              className={styles.choice}
              onClick={() => onChoose(choice.id)}
            >
              {preview(choice.key)}
              <span className={styles.choiceName}>{choice.name}</span>
            </button>
          ))}
        </div>
      )}
    </fieldset>
  );
}

function CardEditor({ orgId, org, card }: { orgId: string; org: Org; card: PressCard }) {
  const { t } = useTranslation('profile');
  const update = useUpdateProfile(orgId);
  const errors = useFormErrors(update.error);
  const [saved, setSaved] = useState(() => draftOf(card));
  const [draft, setDraft] = useState(saved);
  // « Annuler » starts the pixel editor again from the saved drawing.
  const [round, setRound] = useState(0);
  const setAvatar = useCallback((avatar: Drawing) => setDraft((d) => ({ ...d, avatar })), []);
  const dirty = !unchanged(draft, saved);
  const owned = (kind: Wearable) => card.collection.filter((entry) => entry.item.kind === kind);
  const keyOf = (id: string) => card.collection.find((entry) => entry.item.id === id)?.item.key;
  const frameKey = (draft.frameId && keyOf(draft.frameId)) || null;
  const animationKey = (draft.animationId && keyOf(draft.animationId)) || null;

  // The card as the others will see it once saved.
  const preview: PressCard = {
    ...card,
    pseudo: draft.pseudo.trim() || saved.pseudo,
    avatar: draft.avatar,
    frame: frameKey,
    animation: animationKey,
    showcase: draft.showcase.flatMap((ref): Shown[] => {
      if (ref.kind === 'trophy') {
        const trophy = card.trophies.find((entry) => entry.id === ref.id);
        return trophy ? [{ kind: 'trophy', trophy }] : [];
      }
      const owned = card.collection.find((entry) => entry.item.id === ref.id);
      return owned ? [{ kind: 'item', item: owned.item }] : [];
    }),
  };

  const candidates: Candidate[] = [
    ...card.trophies.map((trophy) => ({
      kind: 'trophy' as const,
      id: trophy.id,
      name: t('trophies.season', {
        season: t(`seasons.${trophy.season.name}`),
        year: trophy.season.year,
      }),
      preview: <CrystalBall variant={trophy.season.name as Variant} size={48} loops={0} />,
      podium: trophy.podium,
    })),
    ...card.collection.map((owned) => ({
      kind: 'item' as const,
      id: owned.item.id,
      name: t(`catalog.${owned.item.key}`),
      preview: <ItemPreview item={owned.item} avatar={draft.avatar} size={48} />,
    })),
  ];

  // Only the reference is kept: a candidate also carries its preview, which is no payload.
  const toggle = ({ kind, id }: Ref) => {
    const ref: Ref = { kind, id };
    setDraft((current) => ({
      ...current,
      showcase: current.showcase.some(same(ref))
        ? current.showcase.filter((chosen) => !same(ref)(chosen))
        : current.showcase.length < SHOWCASE_MAX
          ? [...current.showcase, ref]
          : current.showcase,
    }));
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!dirty || update.isPending) return;
    const next = { ...draft, pseudo: draft.pseudo.trim() };
    const redrawn =
      next.avatar.size !== saved.avatar.size || next.avatar.pixels !== saved.avatar.pixels;
    update.mutate(
      {
        ...(next.pseudo !== saved.pseudo ? { pseudo: next.pseudo } : {}),
        ...(redrawn ? { avatar: next.avatar } : {}),
        avatar_frame_item_id: next.frameId || null,
        avatar_animation_item_id: next.animationId || null,
        showcase: next.showcase,
      },
      {
        onSuccess: () => {
          setSaved(next);
          setDraft(next);
          toast.success(t('customize.saved'));
        },
      },
    );
  };

  const cancel = () => {
    setDraft(saved);
    setRound((value) => value + 1);
    update.reset();
  };

  return (
    <form className={styles.editorPage} onSubmit={submit} noValidate>
      <TopBar back={`/o/${orgId}/profil`} backLabel={t('backProfile')} />
      <h1 className={styles.headerTitle}>{t('customize.title')}</h1>

      <div className={styles.editorColumns}>
        <section className={styles.preview} aria-labelledby="card-preview">
          <h2 id="card-preview" className={styles.label}>
            {t('customize.preview')}
          </h2>
          <Identity card={preview} orgTitle={org.title} />
          <div className={styles.actions}>
            <Button variant="secondary" disabled={!dirty || update.isPending} onClick={cancel}>
              {t('customize.cancel')}
            </Button>
            <Button type="submit" disabled={!dirty || update.isPending}>
              {t('customize.save')}
            </Button>
          </div>
        </section>

        <div className={styles.controls}>
          <Field
            label={t('customize.pseudo')}
            value={draft.pseudo}
            maxLength={24}
            autoComplete="off"
            onChange={(event) => {
              const pseudo = event.target.value;
              setDraft((current) => ({ ...current, pseudo }));
            }}
            error={errors.field('pseudo')}
          />

          <PixelEditor
            key={round}
            layout="screen"
            initial={saved.avatar}
            unlocked={org.my_membership.unlocked_colors}
            title={t('editor.title')}
            onChange={setAvatar}
            error={errors.field('avatar')}
          />

          <WearablePicker
            kind="frame"
            orgId={orgId}
            owned={owned('frame')}
            chosen={draft.frameId}
            onChoose={(frameId) => setDraft((current) => ({ ...current, frameId }))}
            preview={(key) => <FramedAvatar image={draft.avatar} frame={key} size={48} />}
          />

          <WearablePicker
            kind="animation"
            orgId={orgId}
            owned={owned('animation')}
            chosen={draft.animationId}
            onChoose={(animationId) => setDraft((current) => ({ ...current, animationId }))}
            preview={(key) => (
              <FramedAvatar image={draft.avatar} frame={frameKey} animation={key} size={48} />
            )}
          />

          <fieldset className={styles.choices}>
            <legend className={styles.label}>
              {t('customize.showcase', { count: draft.showcase.length, max: SHOWCASE_MAX })}
            </legend>
            <p className={styles.meta}>{t('customize.showcaseHint')}</p>
            {candidates.length === 0 ? (
              <p className={styles.meta}>{t('customize.nothing')}</p>
            ) : (
              <div className={styles.choiceGrid}>
                {candidates.map((candidate) => {
                  const rank = draft.showcase.findIndex(same(candidate));
                  const chosen = rank >= 0;
                  return (
                    <button
                      key={`${candidate.kind}-${candidate.id}`}
                      type="button"
                      aria-pressed={chosen}
                      disabled={!chosen && draft.showcase.length >= SHOWCASE_MAX}
                      className={`${styles.choice} ${candidate.podium ? styles.podium : ''}`}
                      onClick={() => toggle(candidate)}
                    >
                      {chosen && (
                        <span className={styles.choiceRank} aria-hidden="true">
                          {rank + 1}
                        </span>
                      )}
                      {candidate.preview}
                      <span className={styles.choiceName}>{candidate.name}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </fieldset>
        </div>
      </div>
    </form>
  );
}

export function CardEditorPage() {
  const { t } = useTranslation('profile');
  const { orgId = '' } = useParams();
  const org = useOrg(orgId);
  const card = usePressCard(orgId, org.data?.my_membership.id);
  if (!card.data || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  return <CardEditor orgId={orgId} org={org.data} card={card.data} />;
}
