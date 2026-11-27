import type { WordleStatus } from '../api';

export type Mark = WordleStatus['tries'][number]['marks'][number];

export const WORD_LENGTH = 5;
// The tries of a game; a seventh, the last chance, only when the server gives it.
export const MAX_TRIES = 6;

/** The keys of the on-screen keyboard, as on a French keyboard. */
export const KEY_ROWS = ['azertyuiop', 'qsdfghjklm', 'wxcvbn'] as const;

const RANK: Record<Mark, number> = { absent: 0, present: 1, correct: 2 };

/** What each letter tried shows on the keyboard: its best mark so far. */
export function keyMarks(tries: WordleStatus['tries']): Record<string, Mark> {
  const best: Record<string, Mark> = {};
  for (const { word, marks } of tries) {
    [...word].forEach((letter, i) => {
      const mark = marks[i];
      if (mark && (!best[letter] || RANK[mark] > RANK[best[letter]])) best[letter] = mark;
    });
  }
  return best;
}

/** A letter typed, without its accent, or null for a key that is not a letter. */
export function plainLetter(key: string): string | null {
  const plain = key.normalize('NFD').replace(/\p{M}/gu, '').toLowerCase();
  return /^[a-z]$/.test(plain) ? plain : null;
}
