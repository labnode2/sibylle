// Crystal ball kit: draws a pixel-art crystal ball on a 16×16 grid, frame by frame, with a
// variant per season and per French holiday, and picks the variant of a date.
// No dependency: a frame is a 16×16 array of colors, null where the pixel is transparent.

export const SIZE = 16;
export const FRAME_MS = 120;

const TAU = Math.PI * 2;
const near = (a, b, w) => Math.abs((((a - b) % TAU) + TAU + Math.PI) % TAU - Math.PI) < w;
const blank = () => Array.from({ length: SIZE }, () => Array(SIZE).fill(null));
const within = (x, y) => x >= 0 && x < SIZE && y >= 0 && y < SIZE;
const pts = (draw, list, c) => list.forEach(([x, y]) => draw(x, y, c));

// ---------------------------------------------------------------------------------------------
// Particles and accessories

const SPARK = '#d9dbff';
const SPARKS = [[1, 2], [14, 4], [2, 10], [15, 9]];
const SEEDS = [[5, 0], [7, 3], [9, 6], [10, 1], [6, 5], [8, 8]];
const HEART = [[0, 0], [2, 0], [0, 1], [1, 1], [2, 1], [1, 2]];
const NOTE = [[1, 0], [2, 0], [1, 1], [1, 2], [0, 3], [1, 3]];
const LEAVES = ['#f08a3c', '#d9493a', '#e8b33a'];

// A rocket climbs for 3 frames, then bursts in a growing star for 5.
const BURST = {
  3: [[0, 0]],
  4: [[1, 0], [-1, 0], [0, 1], [0, -1]],
  5: [[2, 0], [-2, 0], [0, 2], [0, -2], [1, 1], [1, -1], [-1, 1], [-1, -1]],
  6: [[2, 2], [2, -2], [-2, 2], [-2, -2], [2, 0], [-2, 0], [0, 2], [0, -2]],
  7: [[2, 2], [2, -2], [-2, 2], [-2, -2]],
};
function fireworks(draw, f, list) {
  list.forEach(([cx, cy, offset, c]) => {
    const t = (f + offset) % 16;
    if (t < 3) draw(cx, cy + 3 - t, '#c9cbff');
    else (BURST[t] || []).forEach(([a, b]) => draw(cx + a, cy + b, c));
  });
}

// Shapes that climb from the bottom to the top once per 16-frame loop.
function rise(put, f, shape, list, span) {
  list.forEach(([x0, ph, c]) => {
    const y0 = 15 - Math.floor((((f + ph) % 16) * span) / 16);
    shape.forEach(([a, b]) => put(x0 + a, y0 + b, c));
  });
}

// The crêpe jumps from the pan, turns over in the air, and lands on its other side.
function crepe(draw, f) {
  const t = f % 8;
  const y = 9 - [0, 2, 4, 5, 5, 4, 2, 0][t];
  const shape = {
    f: [[7, y], [8, y], [9, y]],
    d: [[7, y + 1], [8, y], [9, y - 1]],
    v: [[8, y - 1], [8, y], [8, y + 1]],
    r: [[7, y - 1], [8, y], [9, y + 1]],
  }['ffdvrfff'[t]];
  pts(draw, shape, t < 3 ? '#f0c97a' : '#c8954a');
}

function pumpkin(set, f) {
  const O = '#ef7a1a';
  const o = '#b8520f';
  const Y = f % 4 < 2 ? '#ffd84d' : '#ffa21a';
  set(13, 12, '#3f9a50');
  [[o, O, O, O, o], [o, Y, O, Y, o], [o, O, Y, O, o]].forEach((row, j) =>
    row.forEach((c, i) => set(11 + i, 13 + j, c)),
  );
}
function cornflower(set) {
  set(13, 12, '#24318a');
  pts(set, [[13, 11], [12, 12], [14, 12], [13, 13]], '#4f7be0');
  pts(set, [[12, 11], [14, 11], [12, 13], [14, 13]], '#8fb0ff');
  pts(set, [[13, 14], [13, 15], [14, 15]], '#3f9a50');
}
function eggs(set, f) {
  const egg = (x0, hop, c, stripe) => {
    const y0 = 11 - hop;
    set(x0 + 1, y0, c);
    for (let r = 1; r < 5; r++) for (let i = 0; i < 3; i++) set(x0 + i, y0 + r, r === 2 ? stripe : c);
  };
  egg(13, f % 8 < 2 ? 1 : 0, '#ff9cc2', '#ffd84d');
  egg(0, (f + 4) % 8 < 2 ? 1 : 0, '#7cc4ff', '#f4f6fb');
}
function crown(set) {
  pts(set, [[5, 0], [7, 0], [8, 0], [10, 0]], '#f2c230');
  for (let x = 5; x <= 10; x++) {
    set(x, 1, '#f2c230');
    set(x, 2, '#c99a18');
  }
  pts(set, [[7, 2], [8, 2]], '#e0333a');
}
// The paper fish of April Fools' Day, stuck on the glass; its tail wags.
function fish(set, f) {
  pts(set, [[10, 7], [11, 7], [12, 7], [9, 8], [11, 8], [12, 8], [13, 8], [10, 9], [11, 9], [12, 9]], '#4fb3ff');
  set(10, 8, '#0c0d1c');
  pts(set, f % 4 < 2 ? [[14, 7], [14, 8], [14, 9]] : [[14, 8], [15, 7], [15, 9]], '#2f86d1');
}
function lilyOfTheValley(set) {
  for (let y = 6; y <= 15; y++) set(1, y, '#3f9a50');
  pts(set, [[2, 5], [3, 5]], '#3f9a50');
  for (let y = 10; y <= 15; y++) set(0, y, '#57c26a');
  pts(set, [[3, 6], [2, 8], [2, 10], [2, 12]], '#f6f8f2');
}
function grapes(set) {
  set(14, 10, '#7a5128');
  pts(set, [[15, 9], [15, 10]], '#3f9a50');
  pts(set, [[13, 11], [15, 11], [14, 12], [14, 13]], '#a45bbf');
  pts(set, [[14, 11], [13, 12], [15, 12]], '#6b2a7a');
}

// ---------------------------------------------------------------------------------------------
// The variants: a glass sphere on a gold stand, its reflection at the top left, a mist that turns
// in a spiral, and a core that glows. Seasons and holidays happen inside the glass, or around it.

const BASE = {
  rim: '#6e74ff',
  dark: '#4a50d0',
  I: '#3a3fae',
  far: '#6267e8',
  near: '#8f94ff',
  core: ['#d9dbff', '#a9adff'],
  sp: SPARK,
};

const VARIANTS = {
  fixed: { name: 'Fixed ball', still: true, sparks: 'all' },
  base: { name: 'Crystal ball' },
  vision: { name: 'The ball sees a portal', vision: true, frames: 32 },
  spring: {
    name: 'Spring',
    near: '#ffc2dc',
    core: ['#ffd0e4', '#ff9cc2'],
    inside: () => '#ff8cc0',
    out: ({ set }) => {
      pts(set, [[13, 13], [13, 14]], '#3fae6a');
      set(13, 12, '#ffd84d');
      pts(set, [[12, 12], [14, 12], [13, 11]], '#ff9cc2');
    },
  },
  summer: {
    name: 'Summer',
    near: '#ffe28a',
    core: ['#ffd84d', '#ffb020'],
    sun: true,
    sp: null,
    out: ({ put }, f) =>
      [[1, 2], [14, 3], [0, 7], [15, 8], [2, 11], [13, 10]].forEach(([x, y], i) => {
        if ((f + i * 3) % 8 < 4) put(x, y, '#ffd84d');
      }),
  },
  autumn: { name: 'Autumn', near: '#ffb066', core: ['#ffd8a8', '#ffb066'], inside: (i) => LEAVES[i % 3], flutter: true },
  winter: { name: 'Winter', rim: '#7d8bff', near: '#e6f0ff', core: ['#f4f8ff', '#c8d6ee'], inside: () => '#f4f8ff', drift: true },
  halloween: {
    name: 'Halloween',
    rim: '#8a4fd0',
    dark: '#5e2f96',
    I: '#3b1a5e',
    far: '#6a35a8',
    near: '#8cff6b',
    core: ['#b6ff9c', '#8cff6b'],
    sp: '#8cff6b',
    out: ({ set }, f) => pumpkin(set, f),
  },
  'pink-october': {
    name: 'Pink October',
    rim: '#ff7eb6',
    dark: '#c23b7d',
    I: '#8a2457',
    far: '#c23b7d',
    near: '#ffd0e4',
    core: ['#ffd0e4', '#ff9cc2'],
    sp: '#ffd0e4',
    out: ({ set }) => pts(set, [[13, 10], [14, 10], [12, 11], [15, 11], [12, 12], [15, 12], [13, 13], [14, 13], [12, 14], [15, 14]], '#ff3d8b'),
  },
  christmas: {
    name: 'Christmas',
    rim: '#2f9e5b',
    dark: '#22804a',
    I: '#145a32',
    far: '#22804a',
    near: '#9be3b4',
    core: ['#ffd84d', '#f4f6fb'],
    hat: true,
    drift: true,
    inside: () => '#f4f8ff',
    out: ({ set }) => {
      pts(set, [[11, 0], [12, 0], [13, 1]], '#e0333a');
      pts(set, [[14, 1], [14, 2], [13, 2]], '#f4f6fb');
    },
  },
  'new-year': {
    name: 'New Year',
    near: '#ffe28a',
    core: ['#ffd84d', '#ffb020'],
    inFx: (inn, f) => fireworks(inn, f, [[8, 4, 0, '#ffd84d'], [6, 7, 5, '#ff8cc0'], [10, 7, 10, '#f4f6fb']]),
  },
  'bastille-day': {
    name: 'Bastille Day',
    rim: (dx) => (dx < -0.33 ? '#3b5bdb' : dx > 0.33 ? '#e03a3e' : '#f4f6fb'),
    I: '#2a2f7a',
    near: '#f4f6fb',
    core: ['#f4f6fb', '#c9cbff'],
    sp: null,
    out: ({ put }, f) => fireworks(put, f, [[2, 2, 0, '#5a7cff'], [13, 2, 5, '#f4f6fb'], [13, 13, 10, '#ff4a4f']]),
  },
  remembrance: { name: 'Remembrance', still: true, sp: null, out: ({ set }) => cornflower(set) },
  easter: { name: 'Easter', near: '#ffe28a', core: ['#ffe28a', '#ffd0e4'], out: ({ set }, f) => eggs(set, f) },
  epiphany: { name: 'Epiphany', near: '#ffe28a', core: ['#ffd84d', '#f2c230'], sp: '#ffe28a', out: ({ set }) => crown(set) },
  valentines: {
    name: "Valentine's Day",
    rim: '#ff5c7a',
    dark: '#b8304f',
    I: '#7a1f35',
    far: '#b8304f',
    near: '#ffc2cc',
    inFx: (inn, f, beat) => HEART.forEach(([a, b]) => inn(7 + a, 5 + b, beat ? '#ff3d6e' : '#ffb3c6')),
    out: ({ put }, f) => rise(put, f, HEART, [[0, 0, '#ff3d6e'], [13, 9, '#ffb3c6']], 18),
  },
  candlemas: {
    name: 'Candlemas',
    near: '#ffe0a3',
    core: ['#ffe0a3', '#f0c97a'],
    inFx: (inn, f) => {
      crepe(inn, f);
      for (let x = 6; x <= 10; x++) inn(x, 10, '#3a3d45');
      pts(inn, [[6, 9], [10, 9]], '#3a3d45');
    },
  },
  'april-fools': { name: "April Fools' Day", out: ({ set }, f) => fish(set, f) },
  'may-day': { name: 'May Day', out: ({ set }) => lilyOfTheValley(set) },
  'music-day': {
    name: 'Music Day',
    near: '#ffe28a',
    core: ['#ffd84d', '#ff8cc0'],
    fast: true,
    out: ({ put }, f) => rise(put, f, NOTE, [[0, 0, '#ffd84d'], [13, 7, '#ff8cc0']], 20),
  },
  beaujolais: {
    name: 'Beaujolais Nouveau',
    rim: '#9b2242',
    dark: '#7a1a3a',
    I: '#4a0f22',
    far: '#7a1a3a',
    near: '#e87a9a',
    core: ['#e87a9a', '#c0305a'],
    wine: true,
    out: ({ set }) => grapes(set),
  },
};

function draw(v0, f) {
  const v = { ...BASE, ...v0 };
  const g = blank();
  const kind = blank();
  const theta = (f * TAU) / 16;
  const beat = v.fast ? f % 4 < 2 : f % 8 < 4;
  const coreR = v.sun ? (f % 8 < 4 ? 0.07 : 0.1) : 0.04;
  const vision = v.vision && f % 32 >= 16;
  for (let y = 0; y < SIZE; y++) {
    for (let x = 0; x < SIZE; x++) {
      const dx = (x + 0.5 - 8) / 5.8;
      const dy = (y + 0.5 - 6.5) / 5.8;
      const d = dx * dx + dy * dy;
      if (d > 1) {
        if (v.hat && d <= 1.3 && dy < -0.85) g[y][x] = '#e0333a';
        continue;
      }
      const rr = Math.sqrt(d);
      const reflection = (dx + 0.38) ** 2 + (dy + 0.38) ** 2;
      const level = 0.3 + 0.07 * Math.sin((f * TAU) / 8 + dx * 4);
      let c;
      let k = 'in';
      if (d > 0.75) {
        c = typeof v.rim === 'function' ? v.rim(dx) : dx + dy > 0.6 ? v.dark : v.rim;
        k = 'rim';
      } else if (reflection < 0.035) {
        c = '#f4f6fb';
        k = 'glass';
      } else if (reflection < 0.08) {
        c = '#c9cbff';
        k = 'glass';
      } else if (v.drift && dy > 0.5) {
        c = dy > 0.62 ? '#b9c8e6' : '#f4f8ff';
        k = 'snow';
      } else if (v.wine && dy > level) {
        c = dy > level + 0.12 ? '#8a1538' : '#c0305a';
        k = 'wine';
      } else if (vision) {
        const mx = (x + 0.5 - 8) / 2.2;
        const my = (y + 0.5 - 6.5) / 2.9;
        const dd = mx * mx + my * my;
        c = dd <= 0.42 ? '#0c0d1c' : dd <= 1 ? '#a9adff' : v.I;
      } else if (d < coreR) {
        c = beat ? v.core[0] : v.core[1];
      } else {
        const ph = Math.atan2(dy, dx) - rr * 3 - theta;
        const mist = rr > 0.15 && (near(ph, 0, 0.45) || near(ph, Math.PI, 0.45));
        c = mist ? (rr < 0.4 ? v.near : v.far) : v.I;
      }
      if (v.hat) {
        if (dy < -0.8) c = '#e0333a';
        else if (dy < -0.66) c = '#f4f6fb';
      }
      g[y][x] = c;
      kind[y][x] = k;
    }
  }
  // put fills an empty pixel only (behind what is there), set overwrites, inn draws inside the
  // glass only.
  const put = (x, y, c) => {
    if (within(x, y) && !g[y][x]) g[y][x] = c;
  };
  const set = (x, y, c) => {
    if (within(x, y)) g[y][x] = c;
  };
  const inn = (x, y, c) => {
    if (within(x, y) && kind[y][x] === 'in') g[y][x] = c;
  };
  if (v.inside) {
    SEEDS.forEach(([x0, ph], i) => {
      const y = 2 + ((ph + f) % 9);
      const x = x0 + [0, 1, 1, 0][(ph + f) % 4];
      inn(x, y, v.inside(i));
      if (v.flutter && (f + ph) % 4 < 2) inn(x + 1, y, v.inside(i));
    });
  }
  if (v.inFx) v.inFx(inn, f, beat);
  for (let x = 5; x <= 10; x++) set(x, 12, '#f2c230');
  for (let x = 6; x <= 9; x++) set(x, 13, '#c99a18');
  for (let x = 4; x <= 11; x++) set(x, 14, '#c99a18');
  for (let x = 3; x <= 12; x++) set(x, 15, '#8a6a12');
  set(4, 14, '#f2c230');
  if (v.sp) {
    SPARKS.forEach(([x, y], i) => {
      if (v.sparks === 'all' || (f + i * 2) % 8 < 2) put(x, y, v.sp);
    });
  }
  if (v.out) v.out({ put, set }, f);
  return g;
}

// ---------------------------------------------------------------------------------------------
// Variants and frames

function variant(id) {
  const v = VARIANTS[id];
  if (!v) throw new Error(`crystal-ball: unknown variant ${id}`);
  return v;
}

export const variants = () => Object.keys(VARIANTS);

// How many frames one loop of a variant has: 1 for a still one.
export function frameCount(id) {
  const v = variant(id);
  return v.still ? 1 : v.frames || 16;
}

export function info(id) {
  return { name: variant(id).name, frames: frameCount(id) };
}

// Frame f of a variant (f wraps around the loop).
export function frame(id, f = 0) {
  const n = frameCount(id);
  return draw(variant(id), ((f % n) + n) % n);
}

// ---------------------------------------------------------------------------------------------
// Output

// An SVG of one frame, one rect per run of same-colored pixels.
export function toSVG(grid) {
  let rects = '';
  grid.forEach((row, y) => {
    for (let x = 0; x < SIZE; ) {
      const c = row[x];
      let n = 1;
      while (x + n < SIZE && row[x + n] === c) n++;
      if (c) rects += `<rect x="${x}" y="${y}" width="${n}" height="1" fill="${c}"/>`;
      x += n;
    }
  });
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" shape-rendering="crispEdges">${rects}</svg>\n`;
}

// Draws one frame on a 2D canvas context, one canvas pixel per ball pixel.
export function paint(ctx, grid) {
  ctx.clearRect(0, 0, SIZE, SIZE);
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (c) {
        ctx.fillStyle = c;
        ctx.fillRect(x, y, 1, 1);
      }
    }),
  );
}

// The RGBA bytes of one frame, each ball pixel scale × scale (for PNG encoders).
export function toRGBA(grid, scale = 1) {
  const w = SIZE * scale;
  const out = new Uint8Array(w * w * 4);
  grid.forEach((row, y) =>
    row.forEach((c, x) => {
      if (!c) return;
      const rgb = [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
      for (let j = 0; j < scale; j++) {
        for (let i = 0; i < scale; i++) out.set([...rgb, 255], ((y * scale + j) * w + x * scale + i) * 4);
      }
    }),
  );
  return out;
}

// Plays a variant on a canvas: `loops` loops (2 by default, under the 5 s of WCAG 2.2.2), then
// rests on its first frame. Never moves when the system asks for reduced motion, and draws
// nothing while the tab is hidden. play() plays again (on hover, for example).
export function animate(canvas, id, { loops = 2 } = {}) {
  canvas.width = SIZE;
  canvas.height = SIZE;
  const ctx = canvas.getContext('2d');
  const n = frameCount(id);
  const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  let timer = null;
  let f = 0;
  let left = 0;
  const show = (i) => paint(ctx, frame(id, i));
  const halt = () => {
    clearInterval(timer);
    timer = null;
  };
  const stop = () => {
    halt();
    f = 0;
    show(0);
  };
  const tick = () => {
    if (typeof document !== 'undefined' && document.hidden) return;
    f++;
    if (f >= n) {
      f = 0;
      if (--left <= 0) return stop();
    }
    show(f);
  };
  const play = (count = loops) => {
    if (reduced || n === 1) return;
    left = count;
    if (!timer) timer = setInterval(tick, FRAME_MS);
  };
  show(0);
  play();
  return { play, stop, destroy: halt };
}

// ---------------------------------------------------------------------------------------------
// Calendar: the variant of a date

// Easter Sunday of a Gregorian year, as [month, day] (the anonymous Gregorian algorithm).
export function easter(year) {
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const n = h + l - 7 * m + 114;
  return [Math.floor(n / 31), (n % 31) + 1];
}

// The holidays of a year: each one's days, as [month, day].
export function holidays(year) {
  const day = (date) => [date.getMonth() + 1, date.getDate()];
  const [em, ed] = easter(year);
  const firstThursday = 1 + ((4 - new Date(year, 10, 1).getDay() + 7) % 7);
  return [
    ['epiphany', [[1, 6]]],
    ['candlemas', [[2, 2]]],
    ['valentines', [[2, 14]]],
    ['april-fools', [[4, 1]]],
    ['easter', [[em, ed], day(new Date(year, em - 1, ed + 1))]],
    ['may-day', [[5, 1]]],
    ['remembrance', [[5, 8], [11, 11]]],
    ['music-day', [[6, 21]]],
    ['bastille-day', [[7, 14]]],
    ['pink-october', Array.from({ length: 31 }, (_, i) => [10, i + 1])],
    ['halloween', [[10, 31]]],
    ['beaujolais', [[11, firstThursday + 14]]],
    ['christmas', [[12, 24], [12, 25]]],
    ['new-year', [[12, 31], [1, 1]]],
  ];
}

export function season(month, day) {
  const md = month * 100 + day;
  if (md >= 321 && md <= 620) return 'spring';
  if (md >= 621 && md <= 922) return 'summer';
  if (md >= 923 && md <= 1220) return 'autumn';
  return 'winter';
}

// The variant of a date, in the local time zone: the holiday of the day (the shortest one when
// two meet; each remembrance day counts as one day), or else the season.
export function variantFor(date) {
  const month = date.getMonth() + 1;
  const day = date.getDate();
  let best = null;
  for (const [id, days] of holidays(date.getFullYear())) {
    const length = id === 'remembrance' ? 1 : days.length;
    if (days.some(([m, d]) => m === month && d === day) && (!best || length < best.length)) {
      best = { id, length };
    }
  }
  return best ? best.id : season(month, day);
}
