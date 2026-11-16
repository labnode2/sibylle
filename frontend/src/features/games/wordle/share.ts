// A finished Wordle as it is pasted elsewhere, a chat of the newsroom for one: the word's number
// and the tries it took (« X » when lost), then a row of squares per try in the grid's colours.
// Not a letter: it gives nothing of the word away to whoever has not played yet.
import type { TFunction } from 'i18next';

import type { WordleStatus } from '../api';
import type { Mark } from './letters';

// Number 1: the first word of Sibylle's Wordle, on 15 November 2026 (Paris).
const FIRST_DAY = Date.UTC(2026, 10, 15);
const DAY_MS = 86_400_000;

const SQUARES: Record<Mark, string> = { correct: '🟩', present: '🟨', absent: '⬛' };

/** The number of a day's word (`AAAA-MM-JJ`): 1 for the first one, then one more each day. */
export function wordleNumber(day: string): number {
  return Math.round((Date.parse(day) - FIRST_DAY) / DAY_MS) + 1;
}

/** The text that sharing a finished game copies. */
export function shareText(t: TFunction<'games'>, game: WordleStatus): string {
  const head = t('wordle.share.head', {
    number: wordleNumber(game.day),
    score: game.state === 'won' ? game.tries.length : 'X',
  });
  const rows = game.tries.map(({ marks }) => marks.map((mark) => SQUARES[mark]).join(''));
  return [head, '', ...rows].join('\n');
}
