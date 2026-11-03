// « Mon pixel art » (canvas G-Pixel): the avatar editor on a page of its own, without the tabs;
// « Annuler » and « Enregistrer » lead back to the press card.
import { useTranslation } from 'react-i18next';
import { useNavigate, useParams } from 'react-router';

import { useFormErrors } from '../forms';
import { useOrg } from '../orgs/api';
import { PixelEditor } from '../pixel-editor/PixelEditor';
import { usePressCard, useUpdateProfile } from './api';

export function AvatarEditorPage() {
  const { t } = useTranslation('profile');
  const { orgId = '' } = useParams();
  const navigate = useNavigate();
  const org = useOrg(orgId);
  const me = org.data?.my_membership;
  const card = usePressCard(orgId, me?.id);
  const update = useUpdateProfile(orgId);
  const errors = useFormErrors(update.error);
  if (!card.data || !me) return <p role="status">{t('common:shell.loading')}</p>;
  const back = () => void navigate(`/o/${orgId}/profil`);

  return (
    <PixelEditor
      layout="screen"
      initial={card.data.avatar}
      unlocked={me.unlocked_colors}
      title={t('editor.title')}
      saveLabel={t('editor.save')}
      busy={update.isPending}
      error={errors.field('avatar') ?? errors.message}
      onCancel={back}
      onSave={(avatar) => update.mutate({ avatar }, { onSuccess: back })}
    />
  );
}
