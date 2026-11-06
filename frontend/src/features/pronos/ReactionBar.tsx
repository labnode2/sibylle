// Quick reactions under a prono: one press adds yours, a second takes it back. Counts follow
// `reaction.changed` through the prono's topic.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { REACTIONS, ReactionEmoji } from '../../ui/reactions';
import { useProno, useReact, type ReactionKind } from './api';
import styles from './pronos.module.css';

const KINDS = Object.keys(REACTIONS) as ReactionKind[];

export function ReactionBar({ orgId, pronoId }: { orgId: string; pronoId: string }) {
  const { t } = useTranslation('pronos');
  const prono = useProno(orgId, pronoId);
  const react = useReact(orgId, pronoId);
  // The emoji of the reaction you just gave plays once.
  const [played, setPlayed] = useState<ReactionKind | null>(null);
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
            onClick={() => {
              react.mutate({ kind, on: !pressed });
              setPlayed(pressed ? null : kind);
            }}
          >
            <ReactionEmoji kind={kind} playing={played === kind} onPlayed={() => setPlayed(null)} />
            {count > 0 && <span aria-hidden="true">{count}</span>}
          </button>
        );
      })}
    </div>
  );
}
