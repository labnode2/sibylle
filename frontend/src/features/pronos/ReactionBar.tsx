// Quick reactions under a prono: one press adds yours, a second takes it back. Counts follow
// `reaction.changed` through the prono's topic.
import { useTranslation } from 'react-i18next';

import { REACTION_ICONS } from '../../ui/reactions';
import { useProno, useReact, type ReactionKind } from './api';
import styles from './pronos.module.css';

const KINDS = Object.keys(REACTION_ICONS) as ReactionKind[];

export function ReactionBar({ orgId, pronoId }: { orgId: string; pronoId: string }) {
  const { t } = useTranslation('pronos');
  const prono = useProno(orgId, pronoId);
  const react = useReact(orgId, pronoId);
  if (!prono.data) return null;
  const counts = prono.data.reactions;
  const mine = new Set(prono.data.my_reactions);

  return (
    <div className={styles.reactions} role="group" aria-label={t('reactions.label')}>
      {KINDS.map((kind) => {
        const count = counts[kind] ?? 0;
        const pressed = mine.has(kind);
        return (
          <button
            key={kind}
            type="button"
            className={styles.reaction}
            aria-pressed={pressed}
            aria-label={t('reactions.button', { name: t(`reactions.${kind}`), count })}
            title={t(`reactions.${kind}`)}
            disabled={react.isPending}
            onClick={() => react.mutate({ kind, on: !pressed })}
          >
            <svg
              width={16}
              height={16}
              viewBox="0 0 16 16"
              shapeRendering="crispEdges"
              aria-hidden="true"
            >
              <path fill="currentColor" d={REACTION_ICONS[kind]} />
            </svg>
            {count > 0 && <span aria-hidden="true">{count}</span>}
          </button>
        );
      })}
    </div>
  );
}
