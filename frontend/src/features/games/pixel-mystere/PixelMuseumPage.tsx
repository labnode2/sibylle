// Pixel mystère's museum: the newsroom's drawings whose game is over, the latest first, hung one
// at a time on a gallery wall in a gold frame drawn in pixels, with their label: the word, « par »
// their author, the day the game ended and how many found it. The slideshow moves on by itself
// every 4 s and starts again after the last, with buttons to go back, forward, pause and play.
// Without animations (« couper les animations », prefers-reduced-motion) it keeps still: only the
// buttons move it, and the drawings change without a transition.
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatDate } from '../../../i18n';
import { Button, Icon } from '../../../ui/components';
import { useMotionReduced } from '../../../ui/motion';
import { PixelImage } from '../../../ui/PixelImage';
import { usePixelMuseum, type PixelMuseumItem } from '../api';
import styles from '../games.module.css';

/** How long a drawing stays on the wall before the next one, in ms. */
export const SLIDE_MS = 4000;

/** The bench in front of the wall, as in every museum. */
function Bench() {
  return (
    <svg
      className={styles.bench}
      width={96}
      height={28}
      viewBox="0 0 24 7"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      <rect className={styles.benchTop} x={1} y={0} width={22} height={1} />
      <rect x={0} y={1} width={24} height={2} />
      <rect x={2} y={3} width={2} height={4} />
      <rect x={20} y={3} width={2} height={4} />
    </svg>
  );
}

/** A drawing in its frame, and its label. */
function Exhibit({ item }: { item: PixelMuseumItem }) {
  const { t } = useTranslation('games');
  const found = item.found_count;
  return (
    <figure className={styles.exhibit}>
      <div className={styles.frame}>
        <div className={styles.art}>
          <PixelImage
            image={item.drawing}
            size="var(--art)"
            avatar={false}
            label={t('museum.drawing', { word: item.word, pseudo: item.author.pseudo })}
          />
        </div>
      </div>
      <figcaption className={styles.cartel}>
        <span className={styles.cartelWord}>{item.word}</span>
        <span className={styles.cartelAuthor}>
          <PixelImage image={item.author.avatar} size={32} />
          {t('museum.by', { pseudo: item.author.pseudo })}
        </span>
        <time className={styles.label} dateTime={item.finished_at}>
          {formatDate(item.finished_at, {
            day: 'numeric',
            month: 'long',
            year: 'numeric',
          }).toUpperCase()}
        </time>
        <span className={styles.label}>
          {found === 0 ? t('museum.foundNone') : t('museum.found', { count: found })}
        </span>
      </figcaption>
    </figure>
  );
}

type Way = 'next' | 'previous';

/** The drawings one after the other, the first one first. */
export function MuseumSlideshow({ items }: { items: PixelMuseumItem[] }) {
  const { t } = useTranslation('games');
  const still = useMotionReduced();
  const [playing, setPlaying] = useState(true);
  // The drawing on the wall, by its id: one entering the museum meanwhile, first in the list,
  // does not take its place. `way`: where it came from, for its transition; none at first.
  const [shown, setShown] = useState<{ id?: string; way?: Way }>({});
  const count = items.length;
  const found = items.findIndex((item) => item.puzzle_id === shown.id);
  const at = found === -1 ? 0 : found;
  const item = items[at]!;
  const beside = (step: 1 | -1) => items[(at + step + count) % count]!.puzzle_id;
  const next = beside(1);
  const rolling = playing && !still && count > 1;
  const go = (way: Way) => setShown({ id: beside(way === 'next' ? 1 : -1), way });

  // A new countdown for each drawing, so that one chosen with the buttons stays its 4 s too.
  useEffect(() => {
    if (!rolling) return;
    const timer = window.setTimeout(() => setShown({ id: next, way: 'next' }), SLIDE_MS);
    return () => window.clearTimeout(timer);
  }, [rolling, next, item.puzzle_id]);

  return (
    <section
      className={styles.museum}
      aria-roledescription={t('museum.carousel')}
      aria-label={t('museum.drawings')}
    >
      <div className={styles.wall}>
        {/* Read out when someone changes the drawing, not every 4 s. */}
        <div className={styles.wallSpot} aria-live={rolling ? 'off' : 'polite'}>
          <div
            key={item.puzzle_id}
            className={styles.slide}
            data-way={shown.way}
            role="group"
            aria-roledescription={t('museum.slide')}
            aria-label={t('museum.position', { index: at + 1, count })}
          >
            <Exhibit item={item} />
          </div>
        </div>
        <Bench />
      </div>
      {count > 1 && (
        <div className={styles.museumControls}>
          <div className={styles.museumButtons}>
            <Button
              variant="secondary"
              className={styles.museumButton}
              aria-label={t('museum.previous')}
              title={t('museum.previous')}
              onClick={() => go('previous')}
            >
              <Icon name="chevronLeft" size={24} />
            </Button>
            {!still && (
              <Button
                variant="secondary"
                className={styles.museumButton}
                aria-label={t(playing ? 'museum.pause' : 'museum.play')}
                title={t(playing ? 'museum.pause' : 'museum.play')}
                onClick={() => setPlaying(!playing)}
              >
                <Icon name={playing ? 'pause' : 'play'} size={24} />
              </Button>
            )}
            <Button
              variant="secondary"
              className={styles.museumButton}
              aria-label={t('museum.next')}
              title={t('museum.next')}
              onClick={() => go('next')}
            >
              <Icon name="chevronRight" size={24} />
            </Button>
          </div>
          <span className={styles.museumCount} aria-hidden="true">
            {t('museum.count', { index: at + 1, count })}
          </span>
        </div>
      )}
    </section>
  );
}

export function PixelMuseumPage() {
  const { t } = useTranslation('games');
  const { orgId = '' } = useParams();
  const museum = usePixelMuseum(orgId);

  return (
    <article className={styles.page}>
      <Link to={`/o/${orgId}/jeux/pixel`} className={styles.back}>
        <Icon name="chevronLeft" size={12} />
        {t('museum.back')}
      </Link>
      <h1 className={styles.title}>{t('museum.title')}</h1>
      <p className={styles.text}>{t('museum.intro')}</p>
      {/* What the museum held stays up when asking again fails. */}
      {!museum.data ? (
        museum.isError ? (
          <p role="alert" className={styles.note}>
            {t('common:shell.error')}
          </p>
        ) : (
          <p role="status">{t('common:shell.loading')}</p>
        )
      ) : museum.data.length === 0 ? (
        <div className={styles.wall}>
          <p className={`${styles.cartel} ${styles.cartelEmpty}`}>{t('museum.empty')}</p>
          <Bench />
        </div>
      ) : (
        <MuseumSlideshow items={museum.data} />
      )}
    </article>
  );
}
