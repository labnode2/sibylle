// « Les jeux de la semaine » on la une (canvas B-Accueil, B-Web-Accueil): each game is a line to
// tap, its picture on the left (the season's ball for the race, the drawing as far as it shows
// for Pixel mystère), my record and attempts left, or the word's length.
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatNumber } from '../../i18n';
import { CrystalBall } from '../../ui/CrystalBall';
import { useGames, type Games } from './api';
import styles from './games.module.css';
import { MysteryDrawing } from './pixel-mystere/MysteryDrawing';

function pixelLine(t: TFunction<'games'>, pixel: Games['pixel']): string {
  if (!pixel) return t('box.pixelNone');
  if (pixel.state === 'finished') return t('box.pixelFinished', { word: pixel.word });
  if (pixel.found_by_me && pixel.word) return t('box.pixelFound', { word: pixel.word });
  return t('box.pixelLine', { count: pixel.letters });
}

export function WeeklyGames({ orgId, size = 32 }: { orgId: string; size?: 32 | 48 }) {
  const { t } = useTranslation('games');
  const games = useGames(orgId);
  const runner = games.data?.runner;
  if (!games.data || !runner) return null;
  const pixel = games.data.pixel;
  const thumb = { width: size, height: size };

  return (
    <ul className={`${styles.gameList} ${size === 48 ? styles.gameListLarge : ''}`}>
      <li>
        <Link to={`/o/${orgId}/jeux/course`} className={styles.gameLink}>
          <CrystalBall size={size} loops={0} />
          <span className={styles.gameText}>
            <span className={styles.gameTitle}>{t('box.runner')}</span>
            <span className={styles.gameLine}>
              {t('box.runnerLine', {
                context: runner.my_best === null ? 'none' : undefined,
                record: runner.my_best === null ? '' : formatNumber(runner.my_best),
                left: runner.attempts_left,
              })}
            </span>
          </span>
        </Link>
      </li>
      <li>
        <Link to={`/o/${orgId}/jeux/pixel`} className={styles.gameLink}>
          {pixel ? (
            <span className={styles.gameThumb} style={thumb}>
              <MysteryDrawing
                size={pixel.size as 16 | 32}
                revealed={pixel.revealed}
                className={styles.gameDrawing}
              />
            </span>
          ) : (
            <span className={`${styles.gameThumb} ${styles.gameThumbEmpty}`} style={thumb} />
          )}
          <span className={styles.gameText}>
            <span className={styles.gameTitle}>{t('box.pixel')}</span>
            <span className={styles.gameLine}>{pixelLine(t, pixel)}</span>
          </span>
        </Link>
      </li>
    </ul>
  );
}
