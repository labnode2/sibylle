// Wordle: guess the word of the day, the same for the whole newsroom, in six tries. The grid and
// the keyboard (on screen or the device's own) type five letters, the server checks the word and
// sends the colours back; the solution only comes once the game is over. One game a day: the
// state is kept by the server, so a reload shows the same grid. Once over, the result can be
// copied to be pasted elsewhere, in colours only. The try that finds the word plays the burst of a
// win; a reload of a game already won does not. Before and after the game, the word's difficulty
// shows as squares; at the bottom, the credit of Lexique, where the words come from.
import { useCallback, useEffect, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { useCelebration } from '../../../ui/Celebration';
import { ExternalLink, Icon } from '../../../ui/components';
import { useFormErrors } from '../../forms';
import { useWordle, useWordleGuess } from '../api';
import styles from '../games.module.css';
import { KEY_ROWS, keyMarks, plainLetter, WORD_LENGTH } from './letters';
import { WordleGrid } from './WordleGrid';
import wordle from './wordle.module.css';
import { WordleShare } from './WordleShare';

const LEXIQUE = 'http://www.lexique.org';
// A word's difficulty, the rank of its tier in the word file, goes from 1 (the most common words)
// to this.
const DIFFICULTIES = 6;

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
  const { tries, state, solution, laurels, tries_left: left, level } = status.data;
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
      <WordleGrid tries={tries} typing={typing} over={over} />
      <p className={styles.text} role="status">
        {state === 'won' && t('wordle.won', { count: tries.length, laurels })}
        {state === 'lost' && t('wordle.lost', { word: solution?.toUpperCase() })}
        {state === 'playing' && (problem ?? t('wordle.left', { count: left }))}
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
