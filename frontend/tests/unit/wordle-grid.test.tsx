// The Wordle's grid: the colours of each try, the row being typed, and the keyboard's best marks.
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import '../../src/i18n';
import type { WordleStatus } from '../../src/features/games/api';
import { keyMarks, plainLetter } from '../../src/features/games/wordle/letters';
import { WordleGrid } from '../../src/features/games/wordle/WordleGrid';

afterEach(cleanup);

const tries: WordleStatus['tries'] = [
  { word: 'livre', marks: ['absent', 'absent', 'absent', 'present', 'correct'] },
  { word: 'eerie', marks: ['correct', 'present', 'absent', 'absent', 'correct'] },
];

describe('WordleGrid', () => {
  it('shows six rows of five squares, each try with its colours', () => {
    render(<WordleGrid tries={tries} typing="" over={false} />);
    const rows = screen.getAllByRole('row');
    expect(rows).toHaveLength(6);
    const cells = within(rows[0]!).getAllByRole('gridcell');
    expect(cells.map((c) => c.textContent)).toEqual(['L', 'I', 'V', 'R', 'E']);
    expect(cells.map((c) => c.getAttribute('data-mark'))).toEqual([
      'absent',
      'absent',
      'absent',
      'present',
      'correct',
    ]);
    // Said in words too, not by colour alone.
    expect(cells[4]).toHaveAccessibleName('E, bien placée');
    expect(cells[3]).toHaveAccessibleName('R, mal placée');
    expect(
      within(rows[5]!)
        .getAllByRole('gridcell')
        .map((c) => c.textContent),
    ).toEqual(['', '', '', '', '']);
  });

  it('types the letters on the first free row, without a colour', () => {
    render(<WordleGrid tries={tries} typing="ar" over={false} />);
    const cells = within(screen.getAllByRole('row')[2]!).getAllByRole('gridcell');
    expect(cells.map((c) => c.textContent)).toEqual(['A', 'R', '', '', '']);
    expect(cells[0]).not.toHaveAttribute('data-mark');
  });

  it('shows no typing once the game is over', () => {
    render(<WordleGrid tries={tries} typing="ar" over />);
    expect(screen.queryByText('A')).toBeNull();
  });
});

describe('keyMarks', () => {
  it('keeps the best mark of each letter over the tries', () => {
    const marks = keyMarks(tries);
    expect(marks.e).toBe('correct');
    expect(marks.r).toBe('present');
    expect(marks.l).toBe('absent');
    expect(marks.z).toBeUndefined();
  });
});

describe('plainLetter', () => {
  it('takes letters, accents off, and nothing else', () => {
    expect(plainLetter('é')).toBe('e');
    expect(plainLetter('Ç')).toBe('c');
    expect(plainLetter('A')).toBe('a');
    expect(plainLetter('Enter')).toBeNull();
    expect(plainLetter('1')).toBeNull();
  });
});
