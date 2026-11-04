// « La discussion » under a prono (US14): the messages, oldest first, with the author's avatar,
// pseudo and time; « Messages précédents » for older ones; « J'aime » with who liked; the author
// deletes their own message, the editor removes anyone's, once confirmed. Messages and likes of
// the others arrive live through `prono:<id>`.
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDate, parisDay } from '../../i18n';
import { Button, SectionHead } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { useFormErrors } from '../forms';
import { useDiscussion, useMessages, type Message } from './api';
import styles from './pronos.module.css';

const BODY_MAX = 500;
const SHOWN_LIKERS = 3;

// A heart of 7 × 6 pixels: outlined, or filled once liked.
const HEART = 'M1 0h2v1h-2zM4 0h2v1h-2zM0 1h7v2h-7zM1 3h5v1h-5zM2 4h3v1h-3zM3 5h1v1h-1z';
const HEART_OUTLINE =
  'M1 0h2v1h-2zM4 0h2v1h-2zM0 1h1v2h-1zM3 1h1v1h-1zM6 1h1v2h-1zM1 3h1v1h-1zM5 3h1v1h-1zM2 4h1v1h-1zM4 4h1v1h-1zM3 5h1v1h-1z';

/** « 14:32 », « hier, 14:32 » or « lun. 2 nov., 14:32 ». */
function useWhen() {
  const { t } = useTranslation('pronos');
  return (value: string) => {
    const time = formatDate(value, { hour: '2-digit', minute: '2-digit' });
    const day = parisDay(new Date(value));
    if (day === parisDay(new Date())) return time;
    if (day === parisDay(new Date(Date.now() - 86_400_000))) {
      return t('discussion.yesterday', { time });
    }
    return formatDate(value, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  };
}

/** « Léo », « Léo et Hugo », « Léo, Hugo et Cami », « Léo, Hugo, Cami et 2 autres ». */
function useLikedBy() {
  const { t } = useTranslation('pronos');
  return (likers: string[]) => {
    const shown = likers.slice(0, SHOWN_LIKERS);
    const others = likers.length - shown.length;
    if (others > 0) {
      return t('discussion.likedByMore', { names: shown.join(', '), count: others });
    }
    if (shown.length === 1) return t('discussion.likedBy', { names: shown[0] });
    return t('discussion.likedBy', {
      names: t('discussion.and', { first: shown.slice(0, -1).join(', '), last: shown.at(-1) }),
    });
  };
}

function MessageItem({
  orgId,
  pronoId,
  message,
  mine,
}: {
  orgId: string;
  pronoId: string;
  message: Message;
  mine: boolean;
}) {
  const { t } = useTranslation('pronos');
  const when = useWhen();
  const likedBy = useLikedBy();
  const { like, remove } = useDiscussion(orgId, pronoId);
  const [confirming, setConfirming] = useState(false);
  const errors = useFormErrors(remove.error ?? like.error);

  return (
    <li className={styles.message}>
      <PixelImage image={message.author.avatar} size={28} />
      <div className={styles.messageMain}>
        <p className={styles.messageHead}>
          <Link to={`/o/${orgId}/membres/${message.author.id}`} className={styles.messageAuthor}>
            {message.author.pseudo}
          </Link>
          <time dateTime={message.created_at} className={styles.meta}>
            {when(message.created_at)}
          </time>
        </p>
        <p className={styles.messageText}>{message.body}</p>
        <div className={styles.messageActions}>
          <button
            type="button"
            className={styles.like}
            aria-pressed={message.liked}
            disabled={like.isPending}
            onClick={() => like.mutate({ id: message.id, on: !message.liked })}
          >
            <svg
              width={14}
              height={12}
              viewBox="0 0 7 6"
              shapeRendering="crispEdges"
              aria-hidden="true"
            >
              <path fill="currentColor" d={message.liked ? HEART : HEART_OUTLINE} />
            </svg>
            <span className="visually-hidden">{t('discussion.like')}</span>
            {message.likes > 0 && <span>{message.likes}</span>}
          </button>
          {message.likers.length > 0 && (
            <span className={styles.likers}>{likedBy(message.likers)}</span>
          )}
          {message.can_delete && !confirming && (
            <Button
              variant="link"
              className={styles.messageDelete}
              onClick={() => setConfirming(true)}
            >
              {mine ? t('discussion.delete') : t('discussion.remove')}
            </Button>
          )}
        </div>
        {confirming && (
          <div className={styles.confirmDelete}>
            <p>{mine ? t('discussion.deleteConfirm') : t('discussion.removeConfirm')}</p>
            <div className={styles.confirmActions}>
              <Button variant="secondary" onClick={() => setConfirming(false)}>
                {t('discussion.keep')}
              </Button>
              <Button disabled={remove.isPending} onClick={() => remove.mutate(message.id)}>
                {mine ? t('discussion.delete') : t('discussion.remove')}
              </Button>
            </div>
          </div>
        )}
        {errors.message && (
          <p role="alert" className={styles.alert}>
            {errors.message}
          </p>
        )}
      </div>
    </li>
  );
}

function Composer({ orgId, pronoId }: { orgId: string; pronoId: string }) {
  const { t } = useTranslation('pronos');
  const { write } = useDiscussion(orgId, pronoId);
  const errors = useFormErrors(write.error);
  const [body, setBody] = useState('');
  const empty = body.trim().length === 0;

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (empty || write.isPending) return;
    write.mutate(body, { onSuccess: () => setBody('') });
  };
  // Ctrl or ⌘ + Entrée sends; Entrée alone goes to the line.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) submit();
  };
  const problem = errors.message ?? errors.field('body');

  return (
    <form className={styles.composer} onSubmit={submit} noValidate>
      <label className={styles.label} htmlFor={`message-${pronoId}`}>
        {t('discussion.yours')}
      </label>
      <textarea
        id={`message-${pronoId}`}
        className={styles.composerInput}
        value={body}
        maxLength={BODY_MAX}
        rows={2}
        placeholder={t('discussion.placeholder')}
        onChange={(event) => setBody(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className={styles.composerFoot}>
        <span className={styles.meta} aria-live="polite">
          {t('discussion.left', { count: BODY_MAX - body.length })}
        </span>
        <Button type="submit" disabled={empty || write.isPending}>
          {t('discussion.send')}
        </Button>
      </div>
      {problem && (
        <p role="alert" className={styles.alert}>
          {problem}
        </p>
      )}
    </form>
  );
}

export function Discussion({
  orgId,
  pronoId,
  count,
  me,
}: {
  orgId: string;
  pronoId: string;
  count: number;
  me: string;
}) {
  const { t } = useTranslation('pronos');
  const messages = useMessages(orgId, pronoId);
  // The pages come newest first; each one is in reading order.
  const shown = [...(messages.data?.pages ?? [])].reverse().flatMap((page) => page.items);

  return (
    <section className={styles.discussion} aria-labelledby="prono-discussion">
      <SectionHead id="prono-discussion" title={t('discussion.title')} meta={String(count)} />
      {messages.hasNextPage && (
        <Button
          variant="link"
          className={styles.older}
          disabled={messages.isFetchingNextPage}
          onClick={() => void messages.fetchNextPage()}
        >
          {t('discussion.older')}
        </Button>
      )}
      {messages.isPending ? (
        <p role="status">{t('common:shell.loading')}</p>
      ) : shown.length === 0 ? (
        <p className={styles.empty}>{t('discussion.empty')}</p>
      ) : (
        <ol className={styles.messages} aria-label={t('discussion.title')}>
          {shown.map((message) => (
            <MessageItem
              key={message.id}
              orgId={orgId}
              pronoId={pronoId}
              message={message}
              mine={message.author.id === me}
            />
          ))}
        </ol>
      )}
      <Composer orgId={orgId} pronoId={pronoId} />
    </section>
  );
}
