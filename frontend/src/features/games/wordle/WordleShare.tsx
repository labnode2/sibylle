// Sharing a finished game by copy and paste: the text as it will be pasted, so that one sees what
// goes out (colours, no letter) and can still copy it by hand, and a button that copies it.
import { useTranslation } from 'react-i18next';

import { CopyButton } from '../../../ui/CopyButton';
import type { WordleStatus } from '../api';
import styles from '../games.module.css';
import { shareText } from './share';
import wordle from './wordle.module.css';

export function WordleShare({ game }: { game: WordleStatus }) {
  const { t } = useTranslation('games');
  const text = shareText(t, game);
  return (
    <section className={styles.section} aria-labelledby="wordle-share">
      <h2 id="wordle-share" className={styles.sectionTitle}>
        {t('wordle.share.title')}
      </h2>
      <pre className={wordle.share}>{text}</pre>
      {/* In its own box, so that the column does not stretch it. */}
      <div>
        <CopyButton text={text} label={t('wordle.share.copy')} done={t('wordle.share.copied')} />
      </div>
    </section>
  );
}
