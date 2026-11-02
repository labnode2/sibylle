// The special edition (canvas G-Résultat): the result, what you won or lost, the final split of
// the answers, who saw it right, and whether the pot was lost. A cancellation says the stakes
// went back. The mockup's « SÉRIE » line is left out: the spec has no streaks.
import { useTranslation } from 'react-i18next';

import { formatDate, formatNumber } from '../../i18n';
import { Card, Icon, Laurel, Rule } from '../../ui/components';
import { AvatarStack, PixelImage } from '../../ui/PixelImage';
import type { PronoDetail } from '../pronos/api';
import type { SpecialEdition as Edition } from './api';
import { ReportForm } from './ReportForm';
import styles from './results.module.css';

const SHOWN_WINNERS = 8;

function MyResult({ prono, edition }: { prono: PronoDetail; edition: Edition }) {
  const { t } = useTranslation('results');
  const mine = prono.my_bet;
  if (!mine) return null;
  const won = edition.winners.find((w) => w.bet_id === mine.id);
  const cancelled = edition.kind === 'cancellation';

  let stamp = t('edition.lost');
  let amount = mine.stake ? `−${formatNumber(mine.stake)}` : '0';
  let detail = mine.stake ? t('edition.lostStake', { stake: mine.stake }) : t('edition.noStake');
  if (cancelled) {
    stamp = t('edition.refunded');
    amount = formatNumber(mine.stake);
    detail = mine.stake ? '' : t('edition.noStake');
  } else if (won) {
    stamp = t('edition.won');
    amount = `+${formatNumber(won.payout)}`;
    detail = [
      t('edition.breakdownBase', { base: won.base_gain }),
      won.early_bird ? t('edition.breakdownEarly', { early: won.early_bird }) : null,
      won.pot_share ? t('edition.breakdownPot', { pot: won.pot_share }) : null,
    ]
      .filter(Boolean)
      .join(' + ');
  }

  return (
    <Card className={styles.mine} aria-label={t('edition.mine')}>
      <PixelImage image={mine.member.avatar} size={48} />
      <div className={styles.mineText}>
        <span className={styles.mineAnswer}>{t('edition.vision', { answer: mine.answer })}</span>
        {detail && <span className={styles.small}>{detail}</span>}
      </div>
      <div className={styles.mineScore}>
        <span className={`${styles.stamp} ${won || cancelled ? '' : styles.stampLost}`}>
          {stamp}
        </span>
        <span className={styles.amount}>
          {amount} <Laurel />
        </span>
      </div>
    </Card>
  );
}

function FinalSplit({ prono }: { prono: PronoDetail }) {
  const { t } = useTranslation('results');
  if (prono.kind !== 'choice' && prono.kind !== 'yes_no') return null;
  return (
    <section aria-label={t('edition.final')} className={styles.panel}>
      <span className={styles.small}>{t('edition.final')}</span>
      <ul className={styles.bars}>
        {prono.options.map((option) => (
          <li key={option.id} className={styles.bar}>
            <span className={`${styles.barLabel} ${option.is_correct ? styles.barLabelWin : ''}`}>
              {option.is_correct && <Icon name="check" size={12} />}
              {option.label}
              {option.is_correct && (
                <span className="visually-hidden"> ({t('edition.rightAnswer')})</span>
              )}
            </span>
            <span className={styles.barRail} aria-hidden="true">
              <span
                className={`${styles.barFill} ${option.is_correct ? styles.barFillWin : ''}`}
                style={{ width: `${option.share_pct}%` }}
              />
            </span>
            <span className={styles.barPct}>{option.share_pct} %</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SpecialEdition({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('results');
  const edition = prono.special_edition;
  if (!edition) return null;
  const cancelled = edition.kind === 'cancellation';
  const result =
    prono.kind === 'date' && edition.result
      ? formatDate(`${edition.result}T12:00:00Z`, {
          day: 'numeric',
          month: 'long',
          year: 'numeric',
        })
      : edition.result;
  const when = formatDate(edition.settled_at, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();

  return (
    <section aria-label={t('edition.title')} className={styles.edition}>
      <div className={styles.editionHead}>
        <p className={styles.editionTitle}>{t('edition.title')}</p>
        <p className={styles.small}>
          {t('edition.meta', { date: when, seq: edition.settlement_seq })}
          {edition.kind === 'correction' && ` · ${t('edition.corrected')}`}
        </p>
      </div>
      <Rule variant="double" />
      {cancelled ? (
        <p className={styles.notice}>{t('edition.cancelled')}</p>
      ) : (
        <p className={styles.result}>
          {t('edition.result')} <mark>{result}</mark>
        </p>
      )}
      <MyResult prono={prono} edition={edition} />
      {!cancelled && (
        <>
          <FinalSplit prono={prono} />
          <section aria-label={t('edition.winners', { count: edition.winners.length })}>
            <span className={styles.small}>
              {t('edition.winners', { count: edition.winners.length })}
            </span>
            {edition.winners.length ? (
              <div className={styles.winners}>
                <AvatarStack
                  avatars={edition.winners.slice(0, SHOWN_WINNERS).map((w) => w.member.avatar)}
                  more={edition.winners.length - SHOWN_WINNERS}
                  size={32}
                />
              </div>
            ) : (
              <p>{t('edition.nobody')}</p>
            )}
          </section>
          {edition.pot_lost && (
            <p className={styles.notice}>
              {edition.winners.length
                ? t('edition.potLost', { pot: formatNumber(edition.pot) })
                : t('edition.potLostNobody', { pot: formatNumber(edition.pot) })}
            </p>
          )}
          <ReportForm orgId={orgId} pronoId={prono.id} initialKind="result_error" />
        </>
      )}
    </section>
  );
}
