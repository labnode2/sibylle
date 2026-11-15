// « Qui a voté quoi »: next to each line of the distribution, the avatars of the members who chose
// it. Only the bets in force; the whole newsroom sees it, the ballot open or closed.
import { Link } from 'react-router';

import { PixelImage } from '../../ui/PixelImage';
import type { Bet, PronoDetail } from './api';
import styles from './pronos.module.css';

/** The bets in force that fall in distribution line `index`. Choice bets match the option label;
 *  number and date bets match the value, or the range « low – high » when values are grouped. */
export function votersFor(prono: PronoDetail, index: number): Bet[] {
  const bucket = prono.distribution[index];
  if (!bucket) return [];
  const active = prono.bets.filter((bet) => !bet.superseded);
  if (prono.kind === 'choice' || prono.kind === 'yes_no') {
    return active.filter((bet) => bet.answer === bucket.label);
  }
  const isDate = prono.kind === 'date';
  const raw = (bet: Bet) => (isDate ? bet.date_value : bet.number_value);
  const num = (value: string) => (isDate ? value : Number(value));
  const range = bucket.label.split(' – ');
  if (range.length === 2) {
    const [low, high] = [num(range[0] ?? ''), num(range[1] ?? '')];
    const last = index === prono.distribution.length - 1;
    return active.filter((bet) => {
      const value = raw(bet);
      if (value == null) return false;
      const v = num(value);
      return (v >= low && v < high) || (last && v === high);
    });
  }
  return active.filter((bet) => {
    const value = raw(bet);
    return value != null && num(value) === num(bucket.label);
  });
}

export function Voters({ orgId, bets }: { orgId: string; bets: Bet[] }) {
  if (!bets.length) return null;
  return (
    <ul className={styles.voterList}>
      {bets.map((bet) => (
        <li key={bet.id} className={styles.voter}>
          <Link
            to={`/o/${orgId}/membres/${bet.member.id}`}
            title={bet.member.pseudo}
            aria-label={bet.member.pseudo}
          >
            <PixelImage image={bet.member.avatar} size={24} />
          </Link>
        </li>
      ))}
    </ul>
  );
}
