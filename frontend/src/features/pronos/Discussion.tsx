// « La discussion » under a prono (US14): the messages, oldest first, with the author's avatar,
// pseudo and time; « Messages précédents » for older ones; « J'aime » with who liked; the author
// deletes their own message, the editor removes anyone's, once confirmed. Messages and likes of
// the others arrive live through `prono:<id>`. Typing « @ » in the composer proposes the active
// members to tag; the tagged names are highlighted in the messages.
import { Fragment, useRef, useState, type FormEvent, type KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { formatDate, parisDay } from '../../i18n';
import { Button, SectionHead } from '../../ui/components';
import { PixelImage } from '../../ui/PixelImage';
import { toast } from '../../ui/Toaster';
import { useMembers } from '../admin/api';
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

type Mentioned = { id: string; pseudo: string };

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/** The text of a message, with each « @pseudo » of a tagged member highlighted. */
export function MessageBody({ body, mentions }: { body: string; mentions: Mentioned[] }) {
  if (mentions.length === 0) return <>{body}</>;
  const pseudos = mentions.map((m) => m.pseudo).sort((a, b) => b.length - a.length);
  const parts = body.split(new RegExp(`(@(?:${pseudos.map(escape).join('|')}))`, 'u'));
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          {index % 2 === 1 ? <strong className={styles.mention}>{part}</strong> : part}
        </Fragment>
      ))}
    </>
  );
}

/** The word being typed after an « @ » just before the caret, if any. */
function typedMention(text: string, caret: number): { start: number; query: string } | null {
  const found = /(?:^|\s)@([^@\n]{0,30})$/u.exec(text.slice(0, caret));
  if (!found) return null;
  const query = found[1] ?? '';
  return { start: caret - query.length - 1, query };
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
        <p className={styles.messageText}>
          <MessageBody body={message.body} mentions={message.mentions} />
        </p>
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
              <Button
                disabled={remove.isPending}
                onClick={() =>
                  remove.mutate(message.id, {
                    onSuccess: () =>
                      toast.success(t(mine ? 'toast.messageRemoved' : 'toast.messageWithdrawn')),
                  })
                }
              >
                {mine ? t('discussion.delete') : t('discussion.remove')}
              </Button>
            </div>
          </div>
        )}
      </div>
    </li>
  );
}

export function Composer({ orgId, pronoId, me }: { orgId: string; pronoId: string; me: string }) {
  const { t } = useTranslation('pronos');
  const { write } = useDiscussion(orgId, pronoId);
  const members = useMembers(orgId);
  const errors = useFormErrors(write.error);
  const input = useRef<HTMLTextAreaElement>(null);
  const [body, setBody] = useState('');
  const [caret, setCaret] = useState(0);
  const [picked, setPicked] = useState<Mentioned[]>([]);
  const [active, setActive] = useState(0);
  const [dismissed, setDismissed] = useState(false);
  const empty = body.trim().length === 0;
  const listId = `mentions-${pronoId}`;

  const typed = typedMention(body, caret);
  const query = typed?.query.toLowerCase() ?? '';
  const choices =
    typed && !dismissed
      ? (members.data ?? [])
          .filter((m) => m.id !== me && m.pseudo.toLowerCase().startsWith(query))
          .slice(0, 6)
      : [];
  const open = choices.length > 0;

  const choose = (member: Mentioned) => {
    if (!typed) return;
    const inserted = `@${member.pseudo} `;
    const next = body.slice(0, typed.start) + inserted + body.slice(caret);
    const position = typed.start + inserted.length;
    setBody(next.slice(0, BODY_MAX));
    setPicked((list) => (list.some((m) => m.id === member.id) ? list : [...list, member]));
    setCaret(position);
    setActive(0);
    requestAnimationFrame(() => {
      input.current?.focus();
      input.current?.setSelectionRange(position, position);
    });
  };

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (empty || write.isPending) return;
    // Only the names still written in the message stay tagged.
    const mentions = picked.filter((m) => body.includes(`@${m.pseudo}`)).map((m) => m.id);
    write.mutate(
      { body, mentions },
      {
        onSuccess: () => {
          setBody('');
          setPicked([]);
          toast.success(t('toast.messagePosted'));
        },
      },
    );
  };
  // Ctrl or ⌘ + Entrée sends; Entrée alone goes to the line, or picks the member proposed.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (open) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const step = event.key === 'ArrowDown' ? 1 : choices.length - 1;
        setActive((active + step) % choices.length);
        return;
      }
      if ((event.key === 'Enter' && !event.ctrlKey && !event.metaKey) || event.key === 'Tab') {
        event.preventDefault();
        const chosen = choices[Math.min(active, choices.length - 1)];
        if (chosen) choose(chosen);
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        setDismissed(true);
        return;
      }
    }
    if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) submit();
  };

  return (
    <form className={styles.composer} onSubmit={submit} noValidate>
      <label className={styles.label} htmlFor={`message-${pronoId}`}>
        {t('discussion.yours')}
      </label>
      <div className={styles.composerField}>
        <textarea
          ref={input}
          id={`message-${pronoId}`}
          className={styles.composerInput}
          value={body}
          maxLength={BODY_MAX}
          rows={2}
          placeholder={t('discussion.placeholder')}
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={open ? listId : undefined}
          aria-activedescendant={open ? `${listId}-${active}` : undefined}
          aria-describedby={`${listId}-hint`}
          onChange={(event) => {
            setBody(event.target.value);
            setCaret(event.target.selectionStart);
            setActive(0);
            setDismissed(false);
          }}
          onSelect={(event) => setCaret(event.currentTarget.selectionStart)}
          onKeyDown={onKeyDown}
        />
        {open && (
          <ul
            id={listId}
            role="listbox"
            className={styles.mentionList}
            aria-label={t('discussion.mentionList')}
          >
            {choices.map((member, index) => (
              <li
                key={member.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                className={`${styles.mentionOption} ${index === active ? styles.mentionActive : ''}`}
                onMouseDown={(event) => {
                  event.preventDefault();
                  choose(member);
                }}
              >
                <PixelImage image={member.avatar} size={20} />
                {member.pseudo}
              </li>
            ))}
          </ul>
        )}
      </div>
      <span id={`${listId}-hint`} className="visually-hidden">
        {t('discussion.mentionHint')}
      </span>
      <div className={styles.composerFoot}>
        <span className={styles.meta} aria-live="polite">
          {t('discussion.left', { count: BODY_MAX - body.length })}
        </span>
        <Button type="submit" disabled={empty || write.isPending}>
          {t('discussion.send')}
        </Button>
      </div>
      {errors.field('body') && (
        <p role="alert" className={styles.alert}>
          {errors.field('body')}
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
      <Composer orgId={orgId} pronoId={pronoId} me={me} />
    </section>
  );
}
