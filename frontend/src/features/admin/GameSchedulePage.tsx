// « Jeux » in the editor's settings (US12, research.md J7): the games of an ordinary week, then
// this week and the three after it, a box per game. Taking a game out of the week in play asks
// first, since it cancels that game's week.
import { Fragment, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams } from 'react-router';

import { formatDate } from '../../i18n';
import { Button } from '../../ui/components';
import {
  GAMES,
  useGameSchedule,
  usePlanWeek,
  useSetOrdinaryWeek,
  useUnplanWeek,
  type Game,
  type GameSchedule,
} from '../games/api';
import styles from './admin.module.css';

type Week = GameSchedule['weeks'][number];

/** A day of the week starting on that Monday, at noon UTC so that Paris keeps the date. */
function day(monday: string, offset = 0): Date {
  const date = new Date(`${monday}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() + offset);
  return date;
}

/** The games with one of them switched on or off, in the server's order. */
function switched(games: readonly Game[], game: Game, on: boolean): Game[] {
  return GAMES.filter((each) => (each === game ? on : games.includes(each)));
}

export function GameSchedulePage() {
  const { t } = useTranslation('admin');
  const { orgId = '' } = useParams();
  const schedule = useGameSchedule(orgId);
  const ordinary = useSetOrdinaryWeek(orgId);
  const plan = usePlanWeek(orgId);
  const unplan = useUnplanWeek(orgId);
  // The game the editor is taking out of the week in play, until they confirm.
  const [removing, setRemoving] = useState<Game | null>(null);
  if (!schedule.data) return <p role="status">{t('common:shell.loading')}</p>;

  const { default: usual, weeks } = schedule.data;
  const busy = ordinary.isPending || plan.isPending || unplan.isPending;
  // A new change forgets what an earlier one failed on.
  const fresh = () => {
    ordinary.reset();
    plan.reset();
    unplan.reset();
  };
  const monday = (week: Week) =>
    formatDate(day(week.week_start), { day: 'numeric', month: 'long' });
  const shortDay = (week: Week, offset: number) =>
    formatDate(day(week.week_start, offset), { day: 'numeric', month: 'short' });

  const toggle = (week: Week, index: number, game: Game, on: boolean) => {
    if (index === 0 && !on) {
      setRemoving(game);
      return;
    }
    fresh();
    plan.mutate({ week: week.week_start, games: switched(week.games, game, on) });
  };

  const remove = (week: Week, game: Game) => {
    fresh();
    plan.mutate(
      { week: week.week_start, games: switched(week.games, game, false) },
      { onSuccess: () => setRemoving(null) },
    );
  };

  return (
    <>
      <section className={styles.panel} aria-label={t('games.ordinary.title')}>
        <h2 className={styles.heading}>{t('games.ordinary.title')}</h2>
        <p className={styles.hint}>{t('games.ordinary.hint')}</p>
        <ul className={styles.gameChoices}>
          {GAMES.map((game) => (
            <li key={game}>
              <label className={styles.check}>
                <input
                  type="checkbox"
                  checked={usual.includes(game)}
                  disabled={busy}
                  onChange={(event) => {
                    fresh();
                    ordinary.mutate(switched(usual, game, event.target.checked));
                  }}
                />
                {t(`games.names.${game}`)}
              </label>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.panel} aria-label={t('games.weeks.title')}>
        <h2 className={styles.heading}>{t('games.weeks.title')}</h2>
        <p className={styles.hint}>{t('games.weeks.hint')}</p>
        <table className={styles.weeks}>
          <thead>
            <tr>
              <th scope="col" className={styles.label}>
                {t('games.weeks.week')}
              </th>
              {GAMES.map((game) => (
                <th key={game} scope="col" className={styles.label}>
                  {t(`games.columns.${game}`)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map((week, index) => (
              <Fragment key={week.week_start}>
                <tr>
                  <th scope="row">
                    <span className={styles.weekCell}>
                      <span className={styles.rowName}>
                        {index === 0
                          ? t('games.weeks.current')
                          : t('games.weeks.next', { date: monday(week) })}
                      </span>
                      <span className={styles.hint}>
                        {t('games.weeks.range', {
                          from: shortDay(week, 0),
                          to: shortDay(week, 6),
                        }).toUpperCase()}{' '}
                        ·{' '}
                        {index === 0
                          ? t('games.weeks.inPlay')
                          : week.planned
                            ? t('games.weeks.planned')
                            : t('games.weeks.ordinary')}
                      </span>
                      {index > 0 && week.planned && (
                        <Button
                          variant="link"
                          className={styles.weekReset}
                          disabled={busy}
                          onClick={() => {
                            fresh();
                            unplan.mutate(week.week_start);
                          }}
                        >
                          {t('games.weeks.reset')}
                        </Button>
                      )}
                    </span>
                  </th>
                  {GAMES.map((game) => (
                    <td key={game}>
                      <input
                        type="checkbox"
                        className={styles.box}
                        aria-label={
                          index === 0
                            ? t('games.box.current', { game: t(`games.names.${game}`) })
                            : t('games.box.next', {
                                game: t(`games.names.${game}`),
                                date: monday(week),
                              })
                        }
                        checked={week.games.includes(game)}
                        disabled={busy}
                        onChange={(event) => toggle(week, index, game, event.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
                {index === 0 && removing && (
                  <tr>
                    <td colSpan={GAMES.length + 1}>
                      <div className={styles.confirm}>
                        <p>{t(`games.remove.${removing}`)}</p>
                        <div className={styles.actions}>
                          <Button variant="secondary" onClick={() => setRemoving(null)}>
                            {t('games.remove.no')}
                          </Button>
                          <Button disabled={busy} onClick={() => remove(week, removing)}>
                            {t('games.remove.yes')}
                          </Button>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}
