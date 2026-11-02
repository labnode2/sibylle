// Checks the drawings and the calendar: node tools/test.mjs
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as ball from '../src/crystal-ball.js';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
let checks = 0;
const check = (name, fn) => {
  fn();
  checks++;
};

check('every frame of every variant is 16×16, of colors or null', () => {
  for (const id of ball.variants()) {
    for (let f = 0; f < ball.frameCount(id); f++) {
      const g = ball.frame(id, f);
      assert.equal(g.length, 16, `${id}#${f}`);
      for (const row of g) {
        assert.equal(row.length, 16, `${id}#${f}`);
        for (const c of row) assert.ok(c === null || /^#[0-9a-f]{6}$/.test(c), `${id}#${f}: ${c}`);
      }
    }
  }
});

check('every season and holiday of the calendar has a variant', () => {
  const dated = ['spring', 'summer', 'autumn', 'winter', ...ball.holidays(2026).map(([id]) => id)];
  for (const id of dated) assert.ok(ball.variants().includes(id), id);
});

check('still variants have a single frame', () => {
  assert.equal(ball.frameCount('fixed'), 1);
  assert.equal(ball.frameCount('remembrance'), 1);
  assert.equal(ball.frameCount('base'), 16);
  assert.equal(ball.frameCount('vision'), 32);
});

check('the favicon is the fixed ball', () => {
  const svg = readFileSync(join(root, 'assets/favicon/favicon.svg'), 'utf8');
  assert.equal(svg, ball.toSVG(ball.frame('fixed')));
});

check('Easter', () => {
  const dates = { 2024: [3, 31], 2025: [4, 20], 2026: [4, 5], 2027: [3, 28], 2028: [4, 16], 2029: [4, 1], 2030: [4, 21] };
  for (const [year, date] of Object.entries(dates)) assert.deepEqual(ball.easter(Number(year)), date, year);
});

check('the variant of a date', () => {
  const v = (y, m, d) => ball.variantFor(new Date(y, m - 1, d));
  const cases = [
    [2026, 1, 6, 'epiphany'],
    [2026, 1, 1, 'new-year'],
    [2026, 12, 31, 'new-year'],
    [2026, 12, 24, 'christmas'],
    [2026, 12, 23, 'winter'],
    [2026, 2, 2, 'candlemas'],
    [2026, 2, 14, 'valentines'],
    [2026, 3, 20, 'winter'],
    [2026, 3, 21, 'spring'],
    [2026, 4, 5, 'easter'],
    [2026, 4, 6, 'easter'],
    [2024, 4, 1, 'april-fools'],
    [2029, 4, 1, 'april-fools'],
    [2029, 4, 2, 'easter'],
    [2026, 5, 1, 'may-day'],
    [2026, 5, 8, 'remembrance'],
    [2026, 6, 20, 'spring'],
    [2026, 6, 21, 'music-day'],
    [2026, 6, 22, 'summer'],
    [2026, 7, 14, 'bastille-day'],
    [2026, 9, 22, 'summer'],
    [2026, 9, 23, 'autumn'],
    [2026, 10, 1, 'pink-october'],
    [2026, 10, 30, 'pink-october'],
    [2026, 10, 31, 'halloween'],
    [2026, 11, 11, 'remembrance'],
    [2026, 11, 19, 'beaujolais'],
    [2027, 11, 18, 'beaujolais'],
    [2026, 11, 20, 'autumn'],
    [2026, 12, 21, 'winter'],
  ];
  for (const [y, m, d, id] of cases) assert.equal(v(y, m, d), id, `${y}-${m}-${d}`);
});

console.log(`${checks} checks passed`);
