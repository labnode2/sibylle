import { describe, expect, it } from 'vitest';

import { REACTIONS } from '../../src/ui/reactions';
import { COLORS, EMOJIS } from '../../src/ui/reactions/frames';

const ROW = new RegExp(`^[.${Object.keys(COLORS).join('')}]{16}$`);

describe('reaction emojis', () => {
  it.each(Object.entries(EMOJIS))('%s: drawings of 16 × 16 known colours', (_, emoji) => {
    for (const frame of emoji.frames) {
      expect(frame).toHaveLength(16);
      for (const row of frame) expect(row).toMatch(ROW);
    }
  });

  it.each(Object.entries(EMOJIS))(
    '%s: every step shows a drawing, every drawing shows',
    (_, emoji) => {
      expect(emoji.sequence.every((index) => index in emoji.frames)).toBe(true);
      expect(new Set(emoji.sequence).size).toBe(emoji.frames.length);
    },
  );

  it.each(Object.entries(REACTIONS))(
    '%s: a strip of well-formed SVG, one copy per step',
    (kind, reaction) => {
      const emoji = EMOJIS[kind as keyof typeof EMOJIS];
      const svg = decodeURIComponent(reaction.src.replace('data:image/svg+xml,', ''));
      const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
      expect(doc.querySelector('parsererror')).toBeNull();
      expect(doc.querySelectorAll('defs > g')).toHaveLength(emoji.frames.length);
      expect(doc.querySelectorAll('svg > use')).toHaveLength(emoji.sequence.length);
      expect(reaction.steps).toBe(emoji.sequence.length);
      expect(reaction.duration).toBe(emoji.step * emoji.sequence.length);
    },
  );
});
