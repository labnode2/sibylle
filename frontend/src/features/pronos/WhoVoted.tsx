// « Qui a voté quoi »: next to each line of the distribution, the avatars of the members who chose
// it. Only the bets in force; the whole newsroom sees it, the ballot open or closed. The mouse over
// an avatar frames it in ink, as if selected, and opens the member's press card under it; a click
// closes the card. A touch screen has no mouse over: a tap opens the card, another one closes it.
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../../api/client';
import { Card } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useOrg } from '../orgs/api';
import { usePressCard } from '../profile/api';
import { Identity } from '../profile/PressCardPage';
import type { Bet, PronoDetail } from './api';
import styles from './pronos.module.css';

type Member = Bet['member'];

// The avatar on the opened press card: a whole multiple of the 16 and 32 pixel grids.
const CARD_AVATAR = 64;
// The press card keeps this far from the edges of the screen.
const EDGE = 8;

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
        <Voter key={bet.id} orgId={orgId} member={bet.member} />
      ))}
    </ul>
  );
}

/** One avatar. The mouse over it opens the press card, which stays while the pointer is on the
 *  avatar or on the card; a click on either closes it. A tap, Enter or Space opens and closes it;
 *  Escape, a tap elsewhere or the focus moving on closes it too. */
function Voter({ orgId, member }: { orgId: string; member: Member }) {
  const spot = useRef<HTMLLIElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    const onPointer = (event: PointerEvent) => {
      if (!spot.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('pointerdown', onPointer);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('pointerdown', onPointer);
    };
  }, [open]);

  return (
    <li
      ref={spot}
      className={styles.voter}
      // Only a mouse hovers: a tap would open the card on entering and close it with its click.
      onPointerEnter={(event) => {
        if (event.pointerType === 'mouse') setOpen(true);
      }}
      onPointerLeave={(event) => {
        if (event.pointerType === 'mouse') setOpen(false);
      }}
      onBlur={(event) => {
        if (!spot.current?.contains(event.relatedTarget)) setOpen(false);
      }}
    >
      <button
        type="button"
        className={styles.voterAvatar}
        aria-label={member.pseudo}
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <PixelImage image={member.avatar} size={24} />
      </button>
      {open && <VoterCard orgId={orgId} member={member} onClose={() => setOpen(false)} />}
    </li>
  );
}

/** The member's press card, as their profile shows it: under the avatar, or over it when the
 *  screen ends below, and moved back inside the screen at its sides. A member who left the
 *  newsroom has no card any more. */
function VoterCard({
  orgId,
  member,
  onClose,
}: {
  orgId: string;
  member: Member;
  onClose: () => void;
}) {
  const { t } = useTranslation('pronos');
  const card = usePressCard(orgId, member.id);
  const org = useOrg(orgId);
  const box = useRef<HTMLDivElement>(null);
  const face = card.data && org.data ? { card: card.data, orgTitle: org.data.title } : null;
  const ready = face !== null;

  // Placed again once the card arrives, which makes it taller.
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    element.style.transform = '';
    element.removeAttribute('data-above');
    let rect = element.getBoundingClientRect();
    // Over the avatar when the screen ends below, if it fits there. It keeps farther from the
    // avatar over it than under it (see the CSS), so it is measured there before it stays.
    if (rect.bottom > window.innerHeight - EDGE) {
      element.setAttribute('data-above', '');
      const above = element.getBoundingClientRect();
      if (above.top < EDGE) element.removeAttribute('data-above');
      else rect = above;
    }
    const shift =
      rect.left < EDGE
        ? EDGE - rect.left
        : rect.right > window.innerWidth - EDGE
          ? window.innerWidth - EDGE - rect.right
          : 0;
    element.style.transform = shift ? `translateX(${Math.round(shift)}px)` : '';
  }, [ready, card.isError]);

  const gone = card.error instanceof ApiError && card.error.status === 404;
  return (
    <div ref={box} className={styles.voterCard} onClick={onClose}>
      {face ? (
        <Identity card={face.card} orgTitle={face.orgTitle} avatarSize={CARD_AVATAR} />
      ) : (
        <Card as="div" shadow={6}>
          {card.isError ? (
            <p className={styles.voterNote}>
              {gone ? t('detail.voterGone', { pseudo: member.pseudo }) : t('common:shell.error')}
            </p>
          ) : (
            <p role="status" className={styles.voterNote}>
              {t('common:shell.loading')}
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
