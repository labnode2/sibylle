// « Profil public » under one's own press card (US15): a switch, what the public card shows and
// to whom, and once it is public, its link and the code that puts it in another site's iframe.
import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import type { MemberSelf } from '../../api/types';
import { ExternalLink, Field, Switch } from '../../ui/components';
import { CopyButton } from '../../ui/CopyButton';
import { toast } from '../../ui/Toaster';
import { publicCardUrl, useUpdateProfile } from './api';
import styles from './profile.module.css';

// The iframe's size, made for the card at a phone's width.
const FRAME_WIDTH = 400;
const FRAME_HEIGHT = 470;

/** A value inside a double-quoted HTML attribute: the pseudo may hold quotes or brackets. */
const attribute = (value: string) =>
  value
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');

export function PublicCardSetting({
  orgId,
  orgTitle,
  member,
}: {
  orgId: string;
  orgTitle: string;
  member: MemberSelf;
}) {
  const { t } = useTranslation('profile');
  const id = useId();
  const update = useUpdateProfile(orgId);
  // The switch follows the touch at once; the server's answer then confirms it.
  const isPublic = update.isPending
    ? update.variables?.card_public === true
    : Boolean(member.card_public);
  const url = member.card_token ? publicCardUrl(member.card_token) : null;
  const title = attribute(t('public.frameTitle', { pseudo: member.pseudo }));
  const embed =
    url &&
    `<iframe src="${url}" title="${title}" width="${FRAME_WIDTH}" height="${FRAME_HEIGHT}" ` +
      `style="border:0;max-width:100%" loading="lazy"></iframe>`;

  return (
    <section className={styles.publicSetting} aria-labelledby={`${id}-title`}>
      <div className={styles.publicSettingHead}>
        <h2 id={`${id}-title`} className={styles.intertitle}>
          {t('public.title')}
        </h2>
        <Switch
          checked={isPublic}
          label={t('public.title')}
          onChange={(next) =>
            update.mutate(
              { card_public: next },
              {
                onSuccess: () =>
                  toast.success(t(next ? 'public.madePublic' : 'public.madePrivate')),
              },
            )
          }
        />
      </div>
      <p className={styles.publicSettingText}>{t('public.intro')}</p>
      <p className={styles.label}>
        {isPublic ? t('public.on') : t('public.off', { org: orgTitle.toUpperCase() })}
      </p>
      {isPublic && url && embed && (
        <>
          <div className={styles.publicSettingCopy}>
            <Field label={t('public.link')} value={url} readOnly />
            <CopyButton text={url} label={t('public.copyLink')} done={t('public.linkCopied')} />
          </div>
          <div className={styles.publicSettingCopy}>
            <label htmlFor={`${id}-embed`} className={styles.label}>
              {t('public.embed')}
            </label>
            <textarea
              id={`${id}-embed`}
              className={styles.publicSettingCode}
              value={embed}
              rows={4}
              readOnly
            />
            <CopyButton text={embed} label={t('public.copyEmbed')} done={t('public.embedCopied')} />
          </div>
          <ExternalLink href={url} className={styles.editLink}>
            {t('public.open')}
          </ExternalLink>
          <p className={styles.meta}>{t('public.again')}</p>
        </>
      )}
    </section>
  );
}
