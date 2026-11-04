// A prono's page (canvas B-Prono, B-Web-Prono): the question, the countdown, the ballot with who
// played what, the stake and the rules. Bets of the others arrive live through `prono:<id>`.
// Once settled, the special edition (canvas G-Résultat) heads the page.
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation, useParams } from 'react-router';

import { formatDate, formatNumber, parisDay, parseDecimal } from '../../i18n';
import {
  Button,
  Card,
  ExternalLink,
  Icon,
  KeyPhrase,
  SectionHead,
  Stepper,
  Tip,
  TopBar,
} from '../../ui/components';
import { AvatarStack, PixelImage } from '../../ui/PixelImage';
import { useFormErrors } from '../forms';
import { PushPrompt } from '../notifications/PushPrompt';
import { useOrg } from '../orgs/api';
import { DesignatePanel } from '../results/DesignatePanel';
import { MyReports } from '../results/MyReports';
import { ReportForm } from '../results/ReportForm';
import { SpecialEdition, SpecialEditionHead } from '../results/SpecialEdition';
import { usePlaceBet, useProno, type Bet, type PronoDetail } from './api';
import { ProposalDecision } from './ProposalsPanel';
import { ReactionBar } from './ReactionBar';
import styles from './pronos.module.css';

const STAKE_STEP = 10;
const SHOWN_AVATARS = 3;
// « Les pronostiqueurs »: the first six, then « Et 25 autres ».
const SHOWN_PEOPLE = 6;

function useNow(every: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(timer);
  }, [every]);
  return now;
}

const longDate = (value: string) =>
  formatDate(value, {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  });

function Countdown({ closesAt }: { closesAt: string }) {
  const { t } = useTranslation('pronos');
  const now = useNow(15_000);
  const left = Math.max(0, new Date(closesAt).getTime() - now);
  const units = [
    { value: Math.floor(left / 86_400_000), label: t('detail.days') },
    { value: Math.floor(left / 3_600_000) % 24, label: t('detail.hours') },
    { value: Math.floor(left / 60_000) % 60, label: t('detail.minutes') },
  ];
  return (
    <div role="timer" aria-label={t('detail.countdown')}>
      <Card as="div" className={styles.countdown}>
        {units.map((unit) => (
          <div key={unit.label}>
            <span className={styles.countdownValue}>{String(unit.value).padStart(2, '0')}</span>
            <span className={styles.countdownUnit}>{unit.label}</span>
          </div>
        ))}
      </Card>
    </div>
  );
}

function StateNotice({ prono, newsroom }: { prono: PronoDetail; newsroom: boolean }) {
  const { t } = useTranslation('pronos');
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
    case 'closed':
      return (
        <p className={styles.alert}>
          {prono.result_expected_at
            ? t('detail.closed', { when: longDate(prono.result_expected_at) })
            : t('detail.closedNoDate')}
        </p>
      );
    case 'resolved':
      return <p className={styles.alert}>{t('detail.resolved')}</p>;
    case 'cancelled':
      return <p className={styles.alert}>{t('detail.cancelled')}</p>;
    default:
      return null;
  }
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
  const { t } = useTranslation('pronos');
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
              <span className={styles.choiceLabel}>{option.label}</span>
              <AvatarStack
                avatars={bettors.slice(0, SHOWN_AVATARS).map((bet) => bet.member.avatar)}
                more={bettors.length - SHOWN_AVATARS}
                size={20}
              />
              <span className={styles.pct}>{t('detail.share', { pct: option.share_pct })}</span>
            </button>
          </div>
        );
      })}
    </div>
  );
}

function Distribution({ prono }: { prono: PronoDetail }) {
  const { t } = useTranslation('pronos');
  if (!prono.distribution.length) return null;
  return (
    <section className={styles.page} aria-label={t('detail.distribution')}>
      <span className={styles.label}>{t('detail.distribution')}</span>
      <div className={styles.ballot}>
        {prono.distribution.map((bucket) => (
          <div key={bucket.label}>
            <div className={styles.choice}>
              <span className={styles.choiceLabel}>{bucket.label}</span>
              <span className={styles.pct}>{t('detail.share', { pct: bucket.share_pct })}</span>
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

export function PronoPage() {
  const { t } = useTranslation('pronos');
  const { orgId = '', pronoId = '' } = useParams();
  const location = useLocation();
  const org = useOrg(orgId);
  const query = useProno(orgId, pronoId);
  const placeBet = usePlaceBet(orgId, pronoId);
  const errors = useFormErrors(placeBet.error);
  const [optionId, setOptionId] = useState<string | null>(null);
  const [number, setNumber] = useState('');
  const [day, setDay] = useState('');
  const [stake, setStake] = useState(0);
  const [missing, setMissing] = useState(false);
  // Once a bet is in, the result is worth hearing about: the app offers push notifications.
  const [justBet, setJustBet] = useState(false);

  if (!query.data || !org.data) {
    return <p role="status">{t('common:shell.loading')}</p>;
  }
  const prono = query.data;
  const me = org.data.my_membership;
  const canBet = prono.state === 'open' && (!prono.my_bet || prono.can_rebet);
  const choosing = prono.kind === 'choice' || prono.kind === 'yes_no';
  // The designation panel and the special edition show the answers in their own way.
  const hideBallot =
    Boolean(prono.special_edition) ||
    (prono.state === 'closed' && me.role !== 'reader' && prono.bet_count > 0);
  const today = parisDay(new Date());

  const answer = choosing
    ? optionId && { option_id: optionId }
    : prono.kind === 'number'
      ? parseDecimal(number) && { number_value: parseDecimal(number) }
      : day && { date_value: day };

  const submit = () => {
    if (!answer) {
      setMissing(true);
      return;
    }
    setMissing(false);
    placeBet.mutate(
      { ...answer, stake },
      {
        onSuccess: () => {
          setStake(0);
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
  // From la une, the way back leads there; otherwise to the list of pronos.
  const fromUne = (location.state as { from?: string } | null)?.from === 'une';
  const numbered = t('detail.number', { number: prono.number });
  const settled = Boolean(prono.special_edition);

  return (
    <article className={styles.page}>
      <TopBar
        back={fromUne ? `/o/${orgId}` : `/o/${orgId}/pronos`}
        backLabel={fromUne ? t('detail.back') : t('detail.backList')}
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

          {prono.state === 'open' && prono.closes_at && <Countdown closesAt={prono.closes_at} />}
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
                disabled={!canBet}
              />
            </section>
          )}
          {!choosing && <Distribution prono={prono} />}

          {canBet && prono.kind === 'number' && (
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
          {canBet && prono.kind === 'date' && (
            <label className={styles.fieldset}>
              <span className={styles.label}>{t('detail.pickDate')}</span>
              <input
                className={styles.answerInput}
                type="date"
                min={prono.open_ended ? today : undefined}
                value={day}
                onChange={(event) => setDay(event.target.value)}
              />
            </label>
          )}

          {canBet && (
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
                      count: prono.pot + stake,
                      pot: formatNumber(prono.pot + stake),
                    })}
                  </span>
                </div>
                <Stepper
                  label={t('detail.stakeLabel')}
                  value={stake}
                  onChange={setStake}
                  min={0}
                  max={Math.max(0, me.balance)}
                  step={STAKE_STEP}
                  format={formatNumber}
                />
                <div className={`only-desktop ${styles.potLarge}`}>
                  <span className={styles.potValue}>
                    {t('detail.potValue', {
                      count: prono.pot + stake,
                      pot: formatNumber(prono.pot + stake),
                    })}
                  </span>
                  <span className={styles.label}>{t('detail.potShared')}</span>
                </div>
              </div>
              {(missing || errors.message || fieldError) && (
                <p role="alert" className={styles.alert}>
                  {missing ? t('detail.chooseFirst') : (errors.message ?? fieldError)}
                </p>
              )}
              <div className={styles.submitRow}>
                <Button className={styles.submit} onClick={submit} disabled={placeBet.isPending}>
                  <span>{prono.my_bet ? t('detail.rebet') : t('detail.submit')}</span>
                  <span className={styles.submitTag}>
                    {stake > 0
                      ? t('detail.submitStake', { stake: formatNumber(stake) })
                      : t('detail.submitFree')}
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
          <MyReports reports={prono.my_reports ?? []} />
          {!prono.special_edition && (
            <ReportForm orgId={orgId} pronoId={prono.id} initialKind="content" />
          )}
        </div>
      </div>
    </article>
  );
}
