// Wordle: guess the word of the day, the same for the whole newsroom, in six tries. The grid and
// the keyboard (on screen or the device's own) type five letters, the server checks the word and
// sends the colours back; the solution only comes once the game is over. One game a day: the
// state is kept by the server, so a reload shows the same grid. Once over, the result can be
// copied to be pasted elsewhere, in colours only. The try that finds the word plays the burst of a
// win; a reload of a game already won does not. Before and after the game, the word's difficulty
// shows as squares, and the member's chain of wins with its joker from two wins in a row; under
// the game, the ranking of the day and the chain's rules, then the credit of Lexique, where the
// words come from. A word of level 4 or more missed six times gives a last chance: a seventh row,
// and the word's letters in alphabetical order above the keyboard; found there, it is a win
// without laurels nor bonus, which the chain counts all the same.
import { useCallback, useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { useCelebration } from '../../../ui/Celebration';
import { ExternalLink, Icon } from '../../../ui/components';
import { Flame, Streak, STREAK_SHOWN_FROM } from '../../../ui/Flame';
import { PixelImage } from '../../../ui/PixelImage';
import { useFormErrors } from '../../forms';
import { useWordle, useWordleGuess, type WordleStatus } from '../api';
import styles from '../games.module.css';
import { KEY_ROWS, keyMarks, MAX_TRIES, plainLetter, WORD_LENGTH } from './letters';
import { triesTaken } from './share';
import { WordleGrid } from './WordleGrid';
import wordle from './wordle.module.css';
import { WordleShare } from './WordleShare';

type RankingRow = WordleStatus['ranking'][number];

const LEXIQUE = 'http://www.lexique.org';
// A word's difficulty, the rank of its tier in the word file, goes from 1 (the most common words)
// to this.
const DIFFICULTIES = 6;
// The chain's bonus and its joker start at three wins in a row (backend `wordle_stage`).
const JOKER_FROM = 3;

/** The word's difficulty: as many squares filled, of six. */
function Difficulty({ level }: { level: number }) {
  const { t } = useTranslation('games');
  const of = { level, levels: DIFFICULTIES };
  return (
    <p className={wordle.difficulty} role="img" aria-label={t('wordle.levelLabel', of)}>
      {t('wordle.level', of)}
      <span className={wordle.squares}>
        {Array.from({ length: DIFFICULTIES }, (_, index) => (
          <span
            key={index}
            className={index < level ? `${wordle.square} ${wordle.squareOn}` : wordle.square}
          />
        ))}
      </span>
    </p>
  );
}

/** The last chance's hint: the word's letters in alphabetical order, kept on one line. */
function LastChance({ letters }: { letters: string }) {
  const { t } = useTranslation('games');
  return (
    <Trans
      t={t}
      i18nKey="wordle.lastChance"
      values={{ letters }}
      components={{ letters: <span className={wordle.hint} /> }}
    />
  );
}

/** The member's chain of wins and its joker, from two wins in a row like the flame. */
function Chain({ streak }: { streak: WordleStatus['streak'] }) {
  const { t } = useTranslation('games');
  if (streak.current < STREAK_SHOWN_FROM) return null;
  const line = streak.current < JOKER_FROM ? 'start' : streak.joker ? 'joker' : 'used';
  return (
    <p className={wordle.chain}>
      <Flame size={12} />
      {t(`wordle.chain.${line}`, { days: streak.current })}
    </p>
  );
}

/** What a win paid: the tries' gain, then the chain's bonus when there is one; nothing at the last
 *  chance. */
function Won({ game }: { game: WordleStatus }) {
  const { t } = useTranslation('games');
  const count = game.tries.length;
  if (count > MAX_TRIES) return <>{t('wordle.wonLastChance')}</>;
  const gain = t('wordle.gain', { count: game.laurels ?? 0 });
  const bonus = game.streak_bonus ?? 0;
  return (
    <>
      {bonus > 0
        ? t('wordle.wonBonus', { count, gain, bonus, days: game.streak.current })
        : t('wordle.won', { count, gain })}
    </>
  );
}

/** How a game of the ranking went: « 3/6 », « 6+1/6 » at the last chance, or « perdu ». */
function Result({ row }: { row: RankingRow }) {
  const { t } = useTranslation('games');
  if (row.state === 'lost') {
    return <span className={styles.score}>{t('wordle.ranking.lost')}</span>;
  }
  return (
    <span className={styles.score}>
      <span aria-hidden="true">{t('wordle.ranking.score', { score: triesTaken(row.tries) })}</span>
      <span className="visually-hidden">
        {row.tries > MAX_TRIES
          ? t('wordle.ranking.lastChance')
          : t('wordle.ranking.found', { count: row.tries })}
      </span>
    </span>
  );
}

/** The ranking of the day, before and after one's own game: whoever finished, those who found
 *  first, with their chain from two wins in a row; never a letter of their tries. Under it, the
 *  rules of the chain, as the race's gains under its ranking: below the game, which they would
 *  push under the fold of a phone. */
function Ranking({ rows }: { rows: RankingRow[] }) {
  const { t } = useTranslation('games');
  return (
    <section className={styles.section} aria-labelledby="wordle-day">
      <h2 id="wordle-day" className={styles.sectionTitle}>
        {t('wordle.ranking.title')}
      </h2>
      {rows.length === 0 ? (
        <p className={styles.note}>{t('wordle.ranking.nobody')}</p>
      ) : (
        <ol className={styles.top}>
          {rows.map((row) => (
            <li
              key={row.member.id}
              className={row.is_me ? styles.me : undefined}
              aria-current={row.is_me ? 'true' : undefined}
            >
              <span className={styles.rank}>{row.rank}</span>
              <PixelImage image={row.member.avatar} size={24} />
              <span className={wordle.player}>
                {row.member.pseudo}
                <Streak value={row.streak} label={t('wordle.streak', { days: row.streak })} />
              </span>
              <Result row={row} />
            </li>
          ))}
        </ol>
      )}
      <p className={styles.note}>{t('wordle.chain.rules')}</p>
    </section>
  );
}

export function WordlePage() {
  const { t } = useTranslation('games');
  const { orgId = '' } = useParams();
  const status = useWordle(orgId);
  const guess = useWordleGuess(orgId);
  const errors = useFormErrors(guess.error);
  const [typing, setTyping] = useState('');
  const [celebration, celebrate] = useCelebration();
  const over = status.data ? status.data.state !== 'playing' : true;
  const { mutate, reset, isPending } = guess;

  const type = useCallback(
    (letter: string) => {
      reset();
      setTyping((word) => (word.length < WORD_LENGTH ? word + letter : word));
    },
    [reset],
  );
  const erase = useCallback(() => {
    reset();
    setTyping((word) => word.slice(0, -1));
  }, [reset]);
  const submit = useCallback(() => {
    if (typing.length !== WORD_LENGTH || isPending) return;
    mutate(typing, {
      onSuccess: (game) => {
        setTyping('');
        if (game.state === 'won') celebrate();
      },
    });
  }, [typing, isPending, mutate, celebrate]);

  useEffect(() => {
    if (over) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      const target = event.target as HTMLElement | null;
      // Enter on a focused on-screen key presses it: only handle it elsewhere.
      if (event.key === 'Enter') {
        if (target?.tagName === 'BUTTON') return;
        event.preventDefault();
        submit();
      } else if (event.key === 'Backspace') erase();
      else {
        const letter = plainLetter(event.key);
        if (letter && event.key.length === 1) type(letter);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [over, type, erase, submit]);

  if (!status.data) return <p role="status">{t('common:shell.loading')}</p>;
  const { tries, state, solution, tries_left: left, level, hint } = status.data;
  const marks = keyMarks(tries);
  const problem = errors.field('word') ?? errors.message;

  return (
    <article className={styles.page}>
      <Link to={`/o/${orgId}`} className={styles.back}>
        <Icon name="chevronLeft" size={12} />
        {t('wordle.back')}
      </Link>
      <h1 className={styles.title}>{t('wordle.title')}</h1>
      <p className={styles.text}>{t('wordle.intro')}</p>
      {level !== null && <Difficulty level={level} />}
      <Chain streak={status.data.streak} />
      <WordleGrid tries={tries} typing={typing} over={over} />
      <p className={styles.text} role="status">
        {state === 'won' && <Won game={status.data} />}
        {state === 'lost' && t('wordle.lost', { word: solution?.toUpperCase() })}
        {state === 'playing' &&
          (problem ??
            (hint !== null ? <LastChance letters={hint} /> : t('wordle.left', { count: left })))}
      </p>
      {over ? (
        <>
          <p className={styles.note}>{t('wordle.tomorrow')}</p>
          <WordleShare game={status.data} />
        </>
      ) : (
        <div className={wordle.keyboard}>
          {KEY_ROWS.map((row, index) => (
            <div key={row} className={wordle.keyRow}>
              {index === 2 && (
                <button
                  type="button"
                  className={`${wordle.key} ${wordle.keyWide}`}
                  onClick={submit}
                  disabled={typing.length !== WORD_LENGTH || isPending}
                >
                  {t('wordle.enter')}
                </button>
              )}
              {[...row].map((letter) => (
                <button
                  key={letter}
                  type="button"
                  className={`${wordle.key} ${marks[letter] ? wordle[marks[letter]] : ''}`}
                  onClick={() => type(letter)}
                >
                  {letter.toUpperCase()}
                </button>
              ))}
              {index === 2 && (
                <button
                  type="button"
                  className={`${wordle.key} ${wordle.keyWide}`}
                  onClick={erase}
                  aria-label={t('wordle.erase')}
                >
                  ⌫
                </button>
              )}
            </div>
          ))}
        </div>
      )}
      <Ranking rows={status.data.ranking} />
      <p className={`${styles.note} ${wordle.credit}`}>
        <Trans
          t={t}
          i18nKey="wordle.credit"
          components={{ site: <ExternalLink href={LEXIQUE} /> }}
        />
      </p>
      {celebration}
    </article>
  );
}
