// The grid of the Wordle: six rows of five squares. The tries sent back by the server show their
// colours (green in place, yellow elsewhere, grey absent), the row being typed shows its letters,
// the rest is empty. The colours come with a word for screen readers, not by colour alone.
import { useTranslation } from 'react-i18next';

import type { WordleStatus } from '../api';
import { MAX_TRIES, WORD_LENGTH } from './letters';
import styles from './wordle.module.css';

export function WordleGrid({
  tries,
  typing,
  over,
}: {
  tries: WordleStatus['tries'];
  typing: string;
  over: boolean;
}) {
  const { t } = useTranslation('games');
  return (
    <div className={styles.grid} role="grid" aria-label={t('wordle.grid')}>
      {Array.from({ length: MAX_TRIES }, (_, row) => {
        const tried = tries[row];
        const current = !tried && !over && row === tries.length;
        return (
          <div key={row} className={styles.row} role="row">
            {Array.from({ length: WORD_LENGTH }, (_, col) => {
              const letter = tried ? tried.word[col] : current ? typing[col] : undefined;
              const mark = tried?.marks[col];
              return (
                <span
                  key={col}
                  role="gridcell"
                  className={`${styles.cell} ${mark ? styles[mark] : letter ? styles.filled : ''}`}
                  data-mark={mark}
                  aria-label={
                    letter && mark
                      ? `${letter.toUpperCase()}, ${t(`wordle.mark.${mark}`)}`
                      : undefined
                  }
                >
                  {letter?.toUpperCase()}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
