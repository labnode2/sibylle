// « Les jeux de la semaine » on la une (B-Accueil, B-Web-Accueil): the ball's race, with my record
// and my attempts left, the week's leader and the way in.
import { useTranslation } from 'react-i18next';

import { formatNumber } from '../../i18n';
import { ButtonLink } from '../../ui/components';
import { useGames } from './api';
import styles from './games.module.css';

export function WeeklyGames({ orgId }: { orgId: string }) {
  const { t } = useTranslation('games');
  const games = useGames(orgId);
  const runner = games.data?.runner;
  if (!runner) return null;
  const leader = runner.top[0];
  return (
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
  );
}
