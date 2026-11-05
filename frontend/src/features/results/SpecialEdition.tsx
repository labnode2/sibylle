// The special edition (canvas G-Résultat): the result, what you won or lost, the final split of
// the answers, who saw it right, and whether the pot was lost. A cancellation says the stakes
// went back. The mockup's « SÉRIE » line is left out: the spec has no streaks.
// The head (« Édition spéciale », when and by whom) opens the prono's page; the rest follows the
// question, then « Voir le classement » and « Partager ».
import { useTranslation } from 'react-i18next';

import { formatDate, formatNumber } from '../../i18n';
import { Button, ButtonLink, Card, Icon, Laurel, Rule } from '../../ui/components';
import { AvatarStack, PixelImage } from '../../ui/PixelImage';
import { copyText } from '../../ui/CopyButton';
import { toast } from '../../ui/Toaster';
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

/** « Édition spéciale », then « SAM. 31 OCT., 19:12 · VALIDÉ PAR INÈS » and the double rule. */
export function SpecialEditionHead({ prono }: { prono: PronoDetail }) {
  const { t } = useTranslation('results');
  const edition = prono.special_edition;
  if (!edition) return null;
  const when = formatDate(edition.settled_at, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).toUpperCase();
  return (
    <div className={styles.editionTop}>
      <div className={styles.editionHead}>
        <p className={styles.editionTitle}>{t('edition.title')}</p>
        <p className={styles.small}>
          {t(`edition.by.${edition.kind}`, {
            date: when,
            pseudo: edition.settled_by.pseudo.toUpperCase(),
          })}
        </p>
      </div>
      <Rule variant="double" />
    </div>
  );
}

/** « Partager »: the share sheet of the phone, or the link copied elsewhere. */
function Share({ question }: { question: string }) {
  const { t } = useTranslation('results');
  const share = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: question, url });
      } catch {
        // The sheet was closed: nothing to say.
      }
      return;
    }
    if (await copyText(url)) toast.success(t('edition.copied'));
    else toast.error(t('common:toasts.copyFailed'));
  };
  return (
    <Button variant="secondary" className={styles.share} onClick={() => void share()}>
      {t('edition.share')}
    </Button>
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

  return (
    <section aria-label={t('edition.title')} className={styles.edition}>
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
          <div className={styles.editionActions}>
            <ButtonLink to={`/o/${orgId}/classement`} className={styles.ranking}>
              {t('edition.ranking')}
            </ButtonLink>
            <Share question={prono.question} />
          </div>
          <ReportForm orgId={orgId} pronoId={prono.id} initialKind="result_error" />
        </>
      )}
    </section>
  );
}
