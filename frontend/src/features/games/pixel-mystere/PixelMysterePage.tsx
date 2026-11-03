// Pixel mystère: the drawing as far as it shows, its number of letters, my guesses left today,
// who found and in what order, the word at the end; and for journalists, a drawing to post with
// the pixel editor and the drawings waiting their turn.
import { useState, type FormEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useParams } from 'react-router';

import { formatNumber } from '../../../i18n';
import { Button, Field, Icon } from '../../../ui/components';
import { PixelImage } from '../../../ui/PixelImage';
import { useFormErrors } from '../../forms';
import { useOrg } from '../../orgs/api';
import { PixelEditor } from '../../pixel-editor/PixelEditor';
import { useGames, useGuess, usePixelQueue, usePostPuzzle, type PixelStatus } from '../api';
import styles from '../games.module.css';
import { MysteryDrawing } from './MysteryDrawing';

function GuessForm({ guess, status }: { guess: ReturnType<typeof useGuess>; status: PixelStatus }) {
  const { t } = useTranslation('games');
  const errors = useFormErrors(guess.error);
  const [word, setWord] = useState('');
  const [tried, setTried] = useState('');
  const left = status.guesses_left_today;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!word.trim()) return;
    setTried(word.trim());
    guess.mutate(word, { onSuccess: () => setWord('') });
  };

  return (
    <form className={styles.guess} onSubmit={submit} noValidate>
      {left > 0 && (
        <>
          <Field
            label={t('pixel.guess')}
            value={word}
            maxLength={60}
            autoComplete="off"
            onChange={(event) => setWord(event.target.value)}
            error={errors.field('word') ?? errors.message ?? undefined}
          />
          <Button type="submit" disabled={guess.isPending}>
            {t('pixel.submit')}
          </Button>
        </>
      )}
      <p role="status" className={styles.text}>
        {guess.data && !guess.data.correct && `${t('pixel.wrong', { word: tried })} `}
        {left > 0 ? t('pixel.left', { count: left }) : t('pixel.noneLeft')}
      </p>
    </form>
  );
}

function Puzzle({ orgId, status }: { orgId: string; status: PixelStatus }) {
  const { t } = useTranslation('games');
  const guess = useGuess(orgId);
  const total = status.size * status.size;
  const message =
    status.state === 'finished'
      ? t('pixel.finished')
      : status.mine
        ? t('pixel.mine')
        : status.found_by_me
          ? t('pixel.found')
          : null;
  return (
    <div className={styles.pixel}>
      <MysteryDrawing
        size={status.size}
        revealed={status.revealed}
        label={t('pixel.drawing', { shown: status.revealed_count, total })}
      />
      <div className={styles.pixelSide}>
        <p className={styles.label}>
          {t('pixel.letters', { count: status.letters })}
          <br />
          {t('pixel.shown', {
            shown: formatNumber(status.revealed_count),
            total: formatNumber(total),
          })}
        </p>
        {status.word && <p className={styles.word}>{t('pixel.word', { word: status.word })}</p>}
        {guess.data?.correct && (
          <p role="status" className={styles.text}>
            {guess.data.rank === 1
              ? t('pixel.rightFirst', { laurels: guess.data.laurels })
              : t('pixel.right', { rank: guess.data.rank, laurels: guess.data.laurels })}
          </p>
        )}
        {message && <p className={styles.text}>{message}</p>}
        {status.state === 'active' && !status.mine && !status.found_by_me && (
          <GuessForm guess={guess} status={status} />
        )}
        <section className={styles.section} aria-labelledby="pixel-finds">
          <h2 id="pixel-finds" className={styles.sectionTitle}>
            {t('pixel.finds')}
          </h2>
          {status.finds.length === 0 ? (
            <p className={styles.note}>{t('pixel.nobody')}</p>
          ) : (
            <ol className={styles.top}>
              {status.finds.map((find) => (
                <li key={find.member.id}>
                  <span className={styles.rank}>{find.rank}</span>
                  <PixelImage image={find.member.avatar} size={24} />
                  <span className={styles.name}>{find.member.pseudo}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}

function PostPuzzle({ orgId, unlocked }: { orgId: string; unlocked: number[] }) {
  const { t } = useTranslation('games');
  const post = usePostPuzzle(orgId);
  const queue = usePixelQueue(orgId, true);
  const errors = useFormErrors(post.error);
  const [open, setOpen] = useState(false);
  const [word, setWord] = useState('');

  return (
    <section className={styles.section} aria-labelledby="pixel-post">
      <h2 id="pixel-post" className={styles.sectionTitle}>
        {t('pixel.post.title')}
      </h2>
      <p className={styles.text}>{t('pixel.post.text')}</p>
      {post.data && !open && (
        <p role="status" className={styles.text}>
          {post.data.state === 'active' ? t('pixel.post.started') : t('pixel.post.queued')}
        </p>
      )}
      {open ? (
        <>
          <Field
            label={t('pixel.post.word')}
            hint={t('pixel.post.wordHint')}
            value={word}
            maxLength={24}
            autoComplete="off"
            onChange={(event) => setWord(event.target.value)}
            error={errors.field('word') ?? undefined}
          />
          <PixelEditor
            sizes={[16, 32]}
            unlocked={unlocked}
            title={t('pixel.post.editor')}
            saveLabel={t('pixel.post.save')}
            busy={post.isPending}
            error={errors.field('drawing') ?? errors.message}
            onCancel={() => setOpen(false)}
            onSave={(drawing) =>
              post.mutate(
                { drawing, word },
                {
                  onSuccess: () => {
                    setOpen(false);
                    setWord('');
                  },
                },
              )
            }
          />
        </>
      ) : (
        <Button
          variant="secondary"
          onClick={() => {
            post.reset();
            setOpen(true);
          }}
        >
          {t('pixel.post.open')}
        </Button>
      )}
      {queue.data && queue.data.length > 0 && (
        <>
          <h3 className={styles.label}>{t('pixel.queue.title')}</h3>
          <ul className={styles.queue}>
            {queue.data.map((item) => (
              <li key={item.puzzle_id}>
                {item.drawing ? (
                  <PixelImage image={item.drawing} size={32} avatar={false} />
                ) : (
                  <span className={styles.secret} aria-hidden="true">
                    ?
                  </span>
                )}
                <span>
                  <span className={styles.label}>
                    {t(`pixel.queue.${item.state}`)} ·{' '}
                    {t('pixel.queue.item', { size: item.size, count: item.letters })}
                  </span>
                  <span className={styles.text}>
                    {item.word
                      ? t('pixel.queue.mine', { word: item.word })
                      : t('pixel.queue.other')}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}

export function PixelMysterePage() {
  const { t } = useTranslation('games');
  const { orgId = '' } = useParams();
  const games = useGames(orgId);
  const org = useOrg(orgId);
  if (!games.data || !org.data) return <p role="status">{t('common:shell.loading')}</p>;
  const me = org.data.my_membership;
  const status = games.data.pixel;

  return (
    <article className={styles.page}>
      <Link to={`/o/${orgId}`} className={styles.back}>
        <Icon name="chevronLeft" size={12} />
        {t('pixel.back')}
      </Link>
      <h1 className={styles.title}>{t('pixel.title')}</h1>
      <p className={styles.text}>{t('pixel.intro')}</p>
      {status ? (
        <Puzzle orgId={orgId} status={status} />
      ) : (
        <p className={styles.note}>{t('pixel.none')}</p>
      )}
      {me.role !== 'reader' && <PostPuzzle orgId={orgId} unlocked={me.unlocked_colors} />}
    </article>
  );
}
