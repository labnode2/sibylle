// « Qui a voté quoi »: for each option (or each number or date), the members who chose it, with
// their avatar and their pseudo side by side. Only the bets in force; the whole newsroom sees it,
// the ballot open or closed.
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { PixelImage } from '../../ui/PixelImage';
import type { Bet, PronoDetail } from './api';
import styles from './pronos.module.css';

type Group = { key: string; label: string; bets: Bet[] };

export function groupBets(prono: PronoDetail): Group[] {
  const active = prono.bets.filter((bet) => !bet.superseded);
  if (prono.kind === 'choice' || prono.kind === 'yes_no') {
    return prono.options
      .map((option) => ({
        key: option.id,
        label: option.label,
        bets: active.filter((bet) => bet.option_id === option.id),
      }))
      .filter((group) => group.bets.length > 0);
  }
  const groups = new Map<string, Group>();
  for (const bet of active) {
    const group = groups.get(bet.answer) ?? { key: bet.answer, label: bet.answer, bets: [] };
    group.bets.push(bet);
    groups.set(bet.answer, group);
  }
  return [...groups.values()];
}

export function WhoVoted({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  const groups = groupBets(prono);
  if (!groups.length) return null;
  return (
    <section className={styles.page} aria-label={t('detail.whoVoted')}>
      <span className={styles.label}>{t('detail.whoVoted')}</span>
      {groups.map((group) => (
        <div key={group.key} role="group" aria-label={group.label}>
          <p className={styles.voteHead}>
            <span>{group.label}</span>
            <span className={styles.meta}>{group.bets.length}</span>
          </p>
          <ul className={styles.voterList}>
            {group.bets.map((bet) => (
              <li key={bet.id} className={styles.voter}>
                <PixelImage image={bet.member.avatar} size={24} />
                <Link to={`/o/${orgId}/membres/${bet.member.id}`} className={styles.personName}>
                  {bet.member.pseudo}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
