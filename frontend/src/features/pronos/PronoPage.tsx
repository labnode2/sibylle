// A prono's page (canvas B-Prono, B-Web-Prono): the question, the countdown, the ballot with who
// played what, the stake and the reactions; beside them, the players, the rules, what was edited
// and, under them, the discussion. Bets and messages of the others arrive live through
// `prono:<id>`. Once settled, the special edition (canvas G-Résultat) heads the page. Opening it
// reads its notifications: its bubbles leave the menus. Its author and the editor find
// « Modifier » under the question until its result; once it is cancelled, the editor finds
// « Supprimer le prono » there. A deleted prono's page says it is not to be found.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router';

import { ApiError } from '../../api/client';
import { formatDate, formatNumber, parisDay, parseDecimal } from '../../i18n';
import {
  Button,
  ButtonLink,
  Card,
  ExternalLink,
  Icon,
  KeyPhrase,
  SectionHead,
  Stepper,
  Tip,
  TopBar,
} from '../../ui/components';
import { Countdown } from '../../ui/Countdown';
import { AvatarStack, PixelImage } from '../../ui/PixelImage';
import { toast } from '../../ui/Toaster';
import { useFormErrors } from '../forms';
import { useReadProno } from '../notifications/api';
import { PushPrompt } from '../notifications/PushPrompt';
import { useOrg } from '../orgs/api';
import { DesignatePanel } from '../results/DesignatePanel';
import { MyReports } from '../results/MyReports';
import { ReportForm } from '../results/ReportForm';
import { cancelledResult, ResultCancelled } from '../results/ResultCancelled';
import { SpecialEdition, SpecialEditionHead } from '../results/SpecialEdition';
import { usePlaceBet, useProno, type Bet, type PronoDetail } from './api';
import { DeleteProno } from './DeleteProno';
import { Discussion } from './Discussion';
import { PronoHistory } from './PronoHistory';
import { ProposalDecision } from './ProposalsPanel';
import { ReactionBar } from './ReactionBar';
import { Voters, votersFor } from './WhoVoted';
import styles from './pronos.module.css';

// Every bet stakes at least one laurel and at most the balance (FR-041): typed to the laurel,
// or moved by 5 with − and +.
const MIN_STAKE = 1;
const STAKE_STEP = 5;
const SHOWN_AVATARS = 3;
// « Les pronostiqueurs »: the first six, then « Et 25 autres ».
const SHOWN_PEOPLE = 6;

const longDate = (value: string) =>
  formatDate(value, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  });

/** The moment the newsroom closed the bets, when it did so before their planned time
 *  (« Clore les paris maintenant »): that closing noted the one planned until then. */
function closedEarlyAt(prono: PronoDetail): string | null {
  const closing = prono.events.findLast((event) => event.kind === 'closed');
  const planned = closing?.data.previous_closes_at;
  const closesAt = prono.closes_at;
  return typeof planned === 'string' && closesAt && Date.parse(closesAt) < Date.parse(planned)
    ? closesAt
    : null;
}

function StateNotice({ prono, newsroom }: { prono: PronoDetail; newsroom: boolean }) {
  const { t } = useTranslation('pronos');
  // Its result taken back: waiting again for one, the stakes still in play.
  const takenBack = cancelledResult(prono);
  if (takenBack) return <ResultCancelled event={takenBack} className={styles.alert} />;
  switch (prono.state) {
    case 'proposed':
      return (
        <p className={styles.alert}>
          {newsroom
            ? t('detail.proposedNewsroom', { author: prono.created_by.pseudo })
            : t('detail.proposed')}
        </p>
      );
    case 'rejected':
      return (
        <p className={styles.alert}>
          {prono.rejected_reason
            ? t('detail.rejected', { reason: prono.rejected_reason })
            : t('detail.rejectedNoReason')}
        </p>
      );
    case 'scheduled':
      return (
        <p className={styles.alert}>{t('detail.opensAt', { date: longDate(prono.opens_at!) })}</p>
      );
    case 'closed': {
      // Closed by hand before the countdown ran out: the members see when.
      const early = closedEarlyAt(prono);
      const when = prono.result_expected_at && longDate(prono.result_expected_at);
      if (early) {
        const date = longDate(early);
        return (
          <p className={styles.alert}>
            {when
              ? t('detail.closedEarly', { date, when })
              : t('detail.closedEarlyNoDate', { date })}
          </p>
        );
      }
      return (
        <p className={styles.alert}>
          {when ? t('detail.closed', { when }) : t('detail.closedNoDate')}
        </p>
      );
    }
    case 'resolved':
      return <p className={styles.alert}>{t('detail.resolved')}</p>;
    case 'cancelled':
      return <p className={styles.alert}>{t('detail.cancelled')}</p>;
    default:
      return null;
  }
}

/** An answer, and under it its share of the laurels staked on the prono and how many played it
 *  (FR-042): « 75 % DES LAURIERS · 3 PERSONNES ». */
function Answer({ label, pct, count }: { label: string; pct: number; count: number }) {
  const { t } = useTranslation('pronos');
  return (
    <span className={styles.choiceText}>
      <span className={styles.choiceLabel}>{label}</span>
      <span className={styles.share}>
        <span className={styles.pct}>{t('detail.share', { pct })}</span>
        {' · '}
        {t('detail.shareCount', { count })}
      </span>
    </span>
  );
}

function Ballot({
  prono,
  selected,
  onSelect,
  disabled,
}: {
  prono: PronoDetail;
  selected: string | null;
  onSelect: (optionId: string) => void;
  disabled: boolean;
}) {
  const active = prono.bets.filter((bet) => !bet.superseded);
  return (
    <div className={styles.ballot}>
      {prono.options.map((option) => {
        const bettors = active.filter((bet) => bet.option_id === option.id);
        const isMine = prono.my_bet?.option_id === option.id;
        return (
          <div key={option.id}>
            <button
              type="button"
              className={styles.choice}
              aria-pressed={selected === option.id || isMine}
              onClick={() => onSelect(option.id)}
              disabled={disabled}
            >
              <span className={styles.box} aria-hidden="true">
                {(selected === option.id || isMine) && <Icon name="check" size={12} />}
              </span>
              <Answer label={option.label} pct={option.share_pct} count={option.count} />
              <AvatarStack
                avatars={bettors.slice(0, SHOWN_AVATARS).map((bet) => bet.member.avatar)}
                more={bettors.length - SHOWN_AVATARS}
                size={20}
              />
            </button>
          </div>
        );
      })}
    </div>
  );
}

function Distribution({ orgId, prono }: { orgId: string; prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  if (!prono.distribution.length) return null;
  return (
    <section className={styles.page} aria-label={t('detail.distribution')}>
      <span className={styles.label}>{t('detail.distribution')}</span>
      <div className={styles.ballot}>
        {prono.distribution.map((bucket, index) => (
          <div key={bucket.label}>
            <div className={`${styles.choice} ${styles.distributionLine}`}>
              <Answer label={bucket.label} pct={bucket.share_pct} count={bucket.count} />
              {prono.state !== 'proposed' && prono.state !== 'rejected' && (
                <Voters orgId={orgId} bets={votersFor(prono, index)} />
              )}
            </div>
            <div className={styles.gauge} aria-hidden="true">
              <span style={{ width: `${bucket.share_pct}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** « Les pronostiqueurs »: who played what and staked how much, the first six, then the rest
 *  on demand. Everyone's choice and stake are seen by the whole newsroom. */
function People({ orgId, bets }: { orgId: string; bets: Bet[] }) {
  const { t } = useTranslation('pronos');
  const [all, setAll] = useState(false);
  const players = new Set(bets.filter((bet) => !bet.superseded).map((bet) => bet.member.id)).size;
  const shown = all ? bets : bets.slice(0, SHOWN_PEOPLE);
  const hidden = bets.length - shown.length;
  return (
    <section className={styles.people} aria-labelledby="prono-people">
      <SectionHead id="prono-people" title={t('detail.people')} meta={String(players)} />
      {bets.length === 0 && <p className={styles.empty}>{t('detail.nobody')}</p>}
      <ul className={styles.peopleList}>
        {shown.map((bet) => (
          <li key={bet.id} className={styles.person}>
            <PixelImage image={bet.member.avatar} size={28} />
            <Link to={`/o/${orgId}/membres/${bet.member.id}`} className={styles.personName}>
              {bet.member.pseudo}
            </Link>
            <span className={`${styles.personAnswer} ${bet.superseded ? styles.replaced : ''}`}>
              {bet.answer.toUpperCase()}
              {bet.superseded && <span className="visually-hidden"> ({t('detail.replaced')})</span>}
            </span>
            <span className={styles.personStake}>
              {bet.stake > 0
                ? t('detail.submitStake', { stake: formatNumber(bet.stake) })
                : t('detail.submitFree')}
            </span>
          </li>
        ))}
      </ul>
      {bets.length > 0 && (
        <p className={styles.peopleNote}>
          {hidden > 0 && `${t('detail.others', { count: hidden })} `}
          {t('detail.visible')}
        </p>
      )}
      {hidden > 0 && (
        <Button variant="link" onClick={() => setAll(true)}>
          {t('detail.showAll')}
        </Button>
      )}
    </section>
  );
}

function Rules({ prono }: { prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  const creator = prono.created_by.pseudo;
  return (
    <Card as="aside" className={styles.rules} aria-labelledby="prono-rules">
      <h2 id="prono-rules" className={styles.rulesTitle}>
        {t('detail.rules')}
      </h2>
      <dl>
        <dt>{t('detail.rulesClose')}</dt>
        <dd>
          {prono.closes_at
            ? t('detail.rulesCloseValue', { date: longDate(prono.closes_at) })
            : t('detail.rulesCloseOpenEnded')}
        </dd>
        <dt>{t('detail.rulesResult')}</dt>
        <dd>{t('detail.rulesResultValue')}</dd>
        <dt>{t('detail.rulesReport')}</dt>
        <dd>{t('detail.rulesReportValue')}</dd>
        <dt>{t('detail.rulesStake')}</dt>
        <dd>{t('detail.rulesStakeValue')}</dd>
        <dt>{t('detail.rulesGain')}</dt>
        <dd>{t('detail.rulesGainValue', { gain: prono.base_gain, creator })}</dd>
        <dt>{t('detail.rulesPot')}</dt>
        <dd>{t('detail.rulesPotValue')}</dd>
      </dl>
    </Card>
  );
}

/** A prono that does not exist, or no longer: deleted, or never seen by this member (404), as a
 *  notification's link or the history may still lead here. */
function NotFound({ orgId }: { orgId: string }) {
  const { t } = useTranslation('pronos');
  return (
    <article className={styles.page}>
      <TopBar back={`/o/${orgId}/pronos`} backLabel={t('detail.backList')} />
      <p role="alert" className={styles.alert}>
        {t('detail.notFound')}
      </p>
      <ButtonLink variant="secondary" className={styles.edit} to={`/o/${orgId}/pronos`}>
        {t('detail.notFoundBack')}
      </ButtonLink>
    </article>
  );
}

export function PronoPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '', pronoId = '' } = useParams();
  const location = useLocation();
  const org = useOrg(orgId);
  const query = useProno(orgId, pronoId);
  useReadProno(orgId, pronoId);
  const placeBet = usePlaceBet(orgId, pronoId);
  const errors = useFormErrors(placeBet.error);
  const [optionId, setOptionId] = useState<string | null>(null);
  const [number, setNumber] = useState('');
  const [day, setDay] = useState('');
  const [stake, setStake] = useState(MIN_STAKE);
  // Once a bet is in, the result is worth hearing about: the app offers push notifications.
  const [justBet, setJustBet] = useState(false);

  // Deleted while on screen too: the prono's event reloads it, and the server answers 404.
  if (query.error instanceof ApiError && query.error.status === 404) {
    return <NotFound orgId={orgId} />;
  }
  if (!query.data || !org.data) {
    return <p role="status">{t('common:shell.loading')}</p>;
  }
  const prono = query.data;
  const me = org.data.my_membership;
  const canBet = prono.state === 'open' && (!prono.my_bet || prono.can_rebet);
  // Below one laurel nothing can be staked: the page says why instead of offering a dead button.
  const broke = me.balance < MIN_STAKE;
  // What would be staked: the stake set, within one laurel and the balance (which may have moved).
  const staked = Math.max(MIN_STAKE, Math.min(stake, me.balance));
  const choosing = prono.kind === 'choice' || prono.kind === 'yes_no';
  // The designation panel and the special edition show the answers in their own way.
  const hideBallot =
    Boolean(prono.special_edition) ||
    (prono.state === 'closed' && me.role !== 'reader' && prono.bet_count > 0);
  const tomorrowDate = new Date();
  tomorrowDate.setUTCDate(tomorrowDate.getUTCDate() + 1);
  const tomorrow = parisDay(tomorrowDate);

  const answer = choosing
    ? optionId && { option_id: optionId }
    : prono.kind === 'number'
      ? parseDecimal(number) && { number_value: parseDecimal(number) }
      : day && { date_value: day };

  const submit = () => {
    if (!answer) {
      toast.error(t('detail.chooseFirst'));
      return;
    }
    placeBet.mutate(
      { ...answer, stake: staked },
      {
        onSuccess: () => {
          toast.success(t('toast.betStake', { count: staked, stake: formatNumber(staked) }));
          setStake(MIN_STAKE);
          setDay('');
          setJustBet(true);
        },
      },
    );
  };

  const fieldError =
    errors.field('option_id') ??
    errors.field('number_value') ??
    errors.field('date_value') ??
    errors.field('stake');
  // The way back leads to the page that opened the prono (la une, or a path in `state.from`,
  // e.g. the profile's ledger); otherwise to the list of pronos.
  const from = (location.state as { from?: unknown } | null)?.from;
  const fromUne = from === 'une';
  const fromPath = typeof from === 'string' && from.startsWith('/') && !from.startsWith('//');
  const numbered = t('detail.number', { number: prono.number });
  const settled = Boolean(prono.special_edition);

  return (
    <article className={styles.page}>
      <TopBar
        back={fromPath ? from : fromUne ? `/o/${orgId}` : `/o/${orgId}/pronos`}
        backLabel={
          fromPath ? t('detail.backPrevious') : fromUne ? t('detail.back') : t('detail.backList')
        }
        aside={settled ? t('detail.resultNumber', { number: prono.number }) : numbered}
        asideOnPhoneOnly
      />

      <div className={styles.columns}>
        <div className={styles.page}>
          {prono.special_edition && <SpecialEditionHead prono={prono} />}
          <span className={styles.kicker}>
            {t('detail.kicker', {
              section: prono.section.name.toUpperCase(),
              org: org.data.title.toUpperCase(),
              creator: prono.created_by.pseudo.toUpperCase(),
            })}
            <span className="only-desktop">{` · ${numbered}`}</span>
          </span>
          <h1 className={styles.question}>
            <KeyPhrase text={prono.question} />
          </h1>
          {prono.state === 'open' && (
            <p className={`only-desktop ${styles.deck}`}>
              {prono.closes_at
                ? t('detail.deck', { date: longDate(prono.closes_at) })
                : t('detail.deckOpenEnded')}
            </p>
          )}
          {prono.image_url && (
            <img src={prono.image_url} alt={t('detail.image')} className={styles.preview} />
          )}
          {prono.link_url && <ExternalLink href={prono.link_url}>{t('detail.link')}</ExternalLink>}
          {prono.can_edit && (
            <ButtonLink
              variant="secondary"
              className={styles.edit}
              to={`/o/${orgId}/pronos/${prono.id}/modifier`}
            >
              {t('detail.edit')}
            </ButtonLink>
          )}
          <DeleteProno orgId={orgId} prono={prono} />

          {prono.state === 'open' && prono.closes_at && (
            <Countdown until={prono.closes_at} label={t('detail.countdown')} large />
          )}
          {prono.state === 'open' && prono.open_ended && (
            <p className={styles.meta}>{t('detail.openEnded')}</p>
          )}
          {prono.special_edition ? (
            <SpecialEdition orgId={orgId} prono={prono} />
          ) : (
            <StateNotice prono={prono} newsroom={me.role !== 'reader'} />
          )}

          {prono.state === 'proposed' && me.role !== 'reader' && (
            <ProposalDecision orgId={orgId} prono={prono} />
          )}

          {prono.my_bet && !prono.special_edition && (
            <p className={styles.mine}>
              <span className={styles.label}>{t('detail.mine')}</span>
              <span>{prono.my_bet.answer}</span>
              <span className={styles.meta}>
                {prono.my_bet.stake > 0
                  ? t('detail.mineStake', { stake: prono.my_bet.stake })
                  : t('detail.mineFree')}
              </span>
            </p>
          )}
          {justBet && <PushPrompt />}

          {choosing && !hideBallot && (
            <section className={styles.page} aria-label={t('detail.yourPick')}>
              <span className={styles.label}>{t('detail.yourPick')}</span>
              <Ballot
                prono={prono}
                selected={optionId}
                onSelect={(id) => setOptionId(id)}
                disabled={!canBet || broke}
              />
            </section>
          )}
          {!choosing && <Distribution orgId={orgId} prono={prono} />}

          {canBet && !broke && prono.kind === 'number' && (
            <label className={styles.fieldset}>
              <span className={styles.label}>
                {t('detail.pickNumber')}
                {prono.number_unit && ` · ${t('detail.unit', { unit: prono.number_unit })}`}
              </span>
              <input
                className={styles.answerInput}
                inputMode="decimal"
                value={number}
                onChange={(event) => setNumber(event.target.value)}
              />
            </label>
          )}
          {canBet && !broke && prono.kind === 'date' && (
            <label className={styles.fieldset}>
              <span className={styles.label}>{t('detail.pickDate')}</span>
              <input
                className={styles.answerInput}
                type="date"
                min={tomorrow}
                value={day}
                onChange={(event) => setDay(event.target.value)}
              />
            </label>
          )}

          {canBet && broke && (
            <p className={styles.alert}>
              {t('detail.broke', { balance: formatNumber(me.balance) })}
            </p>
          )}
          {canBet && !broke && (
            <>
              <div className={styles.stake}>
                <div className={styles.stakeText}>
                  <span className={styles.stakeLabel}>
                    <span className={styles.label}>
                      {t('detail.stake', { balance: formatNumber(me.balance) })}
                    </span>
                    <Tip
                      label={t('detail.stakeHelpLabel')}
                      tip={t('detail.stakeHelp')}
                      align="start"
                    >
                      <span className="tip-mark" aria-hidden="true">
                        ?
                      </span>
                    </Tip>
                  </span>
                  <span className={`only-mobile ${styles.pot}`}>
                    {t('detail.pot', {
                      count: prono.pot + staked,
                      pot: formatNumber(prono.pot + staked),
                    })}
                  </span>
                </div>
                <Stepper
                  label={t('detail.stakeLabel')}
                  value={staked}
                  onChange={setStake}
                  min={MIN_STAKE}
                  max={me.balance}
                  step={STAKE_STEP}
                  format={formatNumber}
                  typed
                />
                <div className={`only-desktop ${styles.potLarge}`}>
                  <span className={styles.potValue}>
                    {t('detail.potValue', {
                      count: prono.pot + staked,
                      pot: formatNumber(prono.pot + staked),
                    })}
                  </span>
                  <span className={styles.label}>{t('detail.potShared')}</span>
                </div>
              </div>
              {fieldError && (
                <p role="alert" className={styles.alert}>
                  {fieldError}
                </p>
              )}
              <div className={styles.submitRow}>
                <Button className={styles.submit} onClick={submit} disabled={placeBet.isPending}>
                  <span>{prono.my_bet ? t('detail.rebet') : t('detail.submit')}</span>
                  <span className={styles.submitTag}>
                    {t('detail.submitStake', { stake: formatNumber(staked) })}
                  </span>
                </Button>
                <p className={styles.note}>
                  {t('detail.note', { gain: prono.base_gain })}
                  <br className="only-mobile" />
                  <span className="only-desktop"> · </span>
                  {prono.open_ended ? t('detail.noteOpenEnded') : t('detail.noteReport')}
                </p>
              </div>
            </>
          )}
          <DesignatePanel orgId={orgId} prono={prono} role={me.role} />
          {prono.state !== 'proposed' && prono.state !== 'rejected' && (
            <ReactionBar orgId={orgId} pronoId={prono.id} />
          )}
        </div>

        <div className={styles.page}>
          <People orgId={orgId} bets={prono.bets} />
          <Rules prono={prono} />
          <PronoHistory prono={prono} />
          {prono.state !== 'proposed' && prono.state !== 'rejected' && (
            <Discussion orgId={orgId} pronoId={prono.id} count={prono.message_count} me={me.id} />
          )}
          <MyReports reports={prono.my_reports ?? []} />
          {!prono.special_edition && (
            <ReportForm orgId={orgId} pronoId={prono.id} initialKind="content" />
          )}
        </div>
      </div>
    </article>
  );
}
