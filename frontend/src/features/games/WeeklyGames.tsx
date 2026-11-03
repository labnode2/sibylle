// « Les jeux de la semaine » on la une (B-Accueil, B-Web-Accueil): the ball's race, with my record
// and my attempts left, the week's leader and the way in; then Pixel mystère and its word's length.
import { useTranslation } from 'react-i18next';

import { formatNumber } from '../../i18n';
import { ButtonLink } from '../../ui/components';
import { useGames, type Games } from './api';
import styles from './games.module.css';

function PixelLine({ orgId, pixel }: { orgId: string; pixel: Games['pixel'] }) {
  const { t } = useTranslation('games');
  const line = !pixel
    ? t('box.pixelNone')
    : pixel.state === 'finished'
      ? t('box.pixelFinished', { word: pixel.word })
      : pixel.found_by_me && pixel.word
        ? t('box.pixelFound', { word: pixel.word })
        : t('box.pixelLine', { count: pixel.letters });
  return (
    <div className={styles.box}>
      <div className={styles.boxText}>
        <span className={styles.boxTitle}>{t('box.pixel')}</span>
        <span className={styles.label}>{line}</span>
      </div>
      <ButtonLink to={`/o/${orgId}/jeux/pixel`} variant="secondary">
        {pixel?.state === 'active' ? t('box.play') : t('box.see')}
      </ButtonLink>
    </div>
  );
}

export function WeeklyGames({ orgId }: { orgId: string }) {
  const { t } = useTranslation('games');
  const games = useGames(orgId);
  const runner = games.data?.runner;
  if (!games.data || !runner) return null;
  const leader = runner.top[0];
  return (
    <div className={styles.boxes}>
      <div className={styles.box}>
        <div className={styles.boxText}>
          <span className={styles.boxTitle}>{t('box.runner')}</span>
          <span className={styles.label}>
            {t('box.runnerLine', {
              context: runner.my_best === null ? 'none' : undefined,
              record: runner.my_best === null ? '' : formatNumber(runner.my_best),
              left: runner.attempts_left,
            })}
          </span>
          {leader && (
            <span className={styles.note}>
              {t('box.leader', { pseudo: leader.member.pseudo, score: formatNumber(leader.score) })}
            </span>
          )}
        </div>
        <ButtonLink to={`/o/${orgId}/jeux/course`} variant="secondary">
          {t('box.play')}
        </ButtonLink>
      </div>
      <PixelLine orgId={orgId} pixel={games.data.pixel} />
    </div>
  );
}
