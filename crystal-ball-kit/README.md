# Crystal ball kit

A pixel-art crystal ball on a 16×16 grid, drawn by code: a glass sphere on a gold stand, its
reflection at the top left, a mist that turns in a spiral and a core that glows. It has a still
version for favicons, an animated one, and a variant per season and per French holiday, where
the season or the holiday happens inside the glass.

Open `preview.html` in a browser to see every variant play, and which one a date gets.

## Contents

```
src/crystal-ball.js          the drawings, the calendar, SVG/canvas/RGBA output, the player (ES module, no dependency)
src/crystal-ball.d.ts        its types
dist/crystal-ball.global.js  the same as a classic script: window.CrystalBall (generated)
assets/favicon/              the still ball: favicon.svg, favicon.ico (16, 32, 48), PNGs 16 to 512, apple-touch-icon.png
assets/svg/                  the first frame of every variant, as SVG
assets/png/                  the same as PNG, 128×128 (8 px per ball pixel)
assets/sprites/              every frame of an animated variant side by side: <id>.png (16 px frames), <id>@4x.png (64 px)
examples/react/              a React component
tools/build.mjs              rebuilds dist/ and assets/ from src/ (node tools/build.mjs)
tools/test.mjs               checks the drawings and the calendar (node tools/test.mjs)
preview.html                 every variant, playing
```

Variants:

| Variant | What it shows |
|---|---|
| `fixed` | the still ball, with its four sparks: the favicon |
| `base` | the mist turns, the core glows, sparks twinkle around |
| `vision` | 2 s of mist, then 2 s of a portal inside the ball (32 frames) |
| `spring` | pink petals fall inside; a flower grows by the stand |
| `summer` | a sun pulses at the core, the mist turns gold; fireflies around |
| `autumn` | orange, red and yellow leaves flutter inside |
| `winter` | a snow globe: flakes fall and pile up at the bottom |
| `epiphany` | the kings' crown on the ball |
| `candlemas` | a crêpe jumps from a pan inside the ball |
| `valentines` | pink glass; a heart beats at the core; hearts rise around |
| `april-fools` | a paper fish stuck on the glass, wagging its tail |
| `easter` | two eggs hop beside the stand |
| `may-day` | a sprig of lily of the valley leans on the ball |
| `remembrance` | a cornflower (the French flower of remembrance), no animation at all |
| `music-day` | the core pulses twice as fast; notes rise around |
| `bastille-day` | blue, white and red glass; fireworks around |
| `pink-october` | pink glass and a pink ribbon |
| `halloween` | purple glass, green witch's mist, a jack-o'-lantern |
| `beaujolais` | wine-red glass, wine sloshing at the bottom, a bunch of grapes |
| `christmas` | green glass under a Santa hat; a snow globe inside |
| `new-year` | fireworks burst inside the ball |

## Use

### The favicon

The browser tab keeps the still ball, whatever the date. Copy `assets/favicon/` to your public
folder:

```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="16x16 32x32 48x48">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
```

`icon-192.png` and `icon-512.png` are for a web app manifest.

### The animated ball, in JavaScript

Copy `src/crystal-ball.js` and `src/crystal-ball.d.ts` into your project.

```js
import { animate, variantFor } from './crystal-ball.js';

const canvas = document.querySelector('#logo'); // style: width/height 16px (or 32, 64…), image-rendering: pixelated
const player = animate(canvas, variantFor(new Date()));
canvas.addEventListener('mouseenter', () => player.play());
```

`animate` plays 2 loops (about 4 s), then rests on the first frame; `play()` plays again, and
`animate(canvas, id, { loops: Infinity })` plays until `stop()` (a loading indicator, for
example). It never moves when the system asks for reduced motion, and draws nothing while the
tab is hidden.

Without a bundler, use the classic script: `<script src="crystal-ball.global.js"></script>`, then
`CrystalBall.animate(…)`.

Other functions: `frame(id, f)` gives a frame as a 16×16 array of colors, `toSVG(grid)` an SVG,
`paint(ctx, grid)` draws it on a canvas, `toRGBA(grid, scale)` gives its bytes.

### React

`examples/react/CrystalBall.tsx`:

```tsx
<a href="/" className="brand"><CrystalBall /> my-app</a>
<CrystalBall size={64} loops={Infinity} />   {/* while loading */}
<CrystalBall variant="vision" size={32} />
```

### CSS only, with a sprite sheet

```css
.ball {
  width: 16px; height: 16px; image-rendering: pixelated;
  background: url(assets/sprites/base.png) 0 0 / 256px 16px;
  animation: ball 1.92s steps(16) 2; /* 16 frames × 120 ms, 2 loops */
}
@keyframes ball { to { background-position: -256px 0; } }
@media (prefers-reduced-motion: reduce) { .ball { animation: none; } }
```

For the 64 px sheet (`@4x`), use 64px, 1024px and -1024px. `vision` has 32 frames: 3.84s,
steps(32).

## Calendar

`variantFor(date)` gives the variant of a date, in the local time zone.

| Variant | Days |
|---|---|
| `epiphany` | 6 January |
| `candlemas` | 2 February |
| `valentines` | 14 February |
| `april-fools` | 1 April |
| `easter` | Easter Sunday and Monday (Gregorian computus) |
| `may-day` | 1 May |
| `remembrance` | 8 May and 11 November |
| `music-day` | 21 June |
| `bastille-day` | 14 July |
| `pink-october` | all of October |
| `halloween` | 31 October |
| `beaujolais` | the third Thursday of November |
| `christmas` | 24 and 25 December |
| `new-year` | 31 December and 1 January |

A holiday wins over the season. When two holidays meet, the shorter one wins: Halloween over Pink
October, April Fools' Day over Easter (1 April 2024 and 2029). The other days get their season:
spring 21 March–20 June, summer 21 June–22 September, autumn 23 September–20 December, winter
21 December–20 March (the northern hemisphere).

## Design rules

To add a variant that belongs with the others:

- **The grid**: 16×16. Show it at whole multiples only (16, 32, 64 px…), with
  `image-rendering: pixelated` or `shape-rendering="crispEdges"`, or the pixels blur.
- **The palette**: glass `#6e74ff` (shadow side `#4a50d0`), inside `#3a3fae`, mist `#6267e8` and
  `#8f94ff`, core `#d9dbff`, reflection `#f4f6fb` and `#c9cbff`, sparks `#d9dbff`, stand
  `#f2c230`, `#c99a18`, `#8a6a12`. A variant changes the mist and core colors, and a holiday may
  recolor the glass.
- **The light** comes from the top left: the reflection. No black outline.
- **The motion**: frames of 120 ms, loops of 16 frames (32 at most). Particles inside the ball
  stay inside the glass; accessories go in front of everything. A variant never changes the
  ball's shape or its stand.
- **At 16 px**, only colors and big accessories read (the snow pile, the Santa hat, the crown);
  particles start to show at 32 px.

## Change a design

Edit `src/crystal-ball.js`, then:

```sh
node tools/build.mjs   # dist/ and assets/
node tools/test.mjs    # the drawings and the calendar
```

The kit needs Node 18 or later for these two scripts, and nothing else.
