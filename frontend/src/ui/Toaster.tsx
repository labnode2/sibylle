// Short notes after an action, at the top right of the screen (across its top on a phone): what
// was done, or what went wrong. The page itself does not change to say so. A bar runs out under
// each note before it goes; it waits while its cross has the focus, and the cross closes it at
// once. A note never stands in the way: a click goes through it to the page, except on the cross.
// Notes come from anywhere, outside React too (the mutations' cache), through `toast`.
import { useEffect, useRef, useState, useSyncExternalStore, type CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';

import { Icon } from './components';
import styles from './toaster.module.css';

type Tone = 'success' | 'error';
type Note = { id: number; message: string; tone: Tone };

// How long a note stays: an error longer, to be read to the end.
const DURATION: Record<Tone, number> = { success: 4000, error: 6500 };
// The newest notes shown at once; an older one gives way.
const SHOWN = 3;

let notes: Note[] = [];
let lastId = 0;
const listeners = new Set<() => void>();

function publish(next: Note[]) {
  notes = next;
  for (const listener of listeners) listener();
}

function show(message: string, tone: Tone) {
  lastId += 1;
  // The same note again (a second click) replaces the first, so that it is not shown twice.
  const others = notes.filter((note) => note.message !== message);
  publish([...others, { id: lastId, message, tone }].slice(-SHOWN));
}

function dismiss(id: number) {
  publish(notes.filter((note) => note.id !== id));
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const toast = {
  success: (message: string) => show(message, 'success'),
  error: (message: string) => show(message, 'error'),
};

function NoteItem({ note }: { note: Note }) {
  const { t } = useTranslation();
  const [paused, setPaused] = useState(false);
  const duration = DURATION[note.tone];
  const remaining = useRef(duration);

  // A timer, not the bar's animation, decides when the note goes: without animations (« couper
  // les animations »), the bar stays still and the note still goes.
  useEffect(() => {
    if (paused) return;
    const started = Date.now();
    const timer = window.setTimeout(() => dismiss(note.id), remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current -= Date.now() - started;
    };
  }, [paused, note.id]);

  return (
    <div
      role={note.tone === 'error' ? 'alert' : 'status'}
      className={`${styles.note} ${note.tone === 'error' ? styles.error : ''}`}
      style={{ '--note-duration': `${duration}ms` } as CSSProperties}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <span className={styles.mark} aria-hidden="true">
        <Icon name={note.tone === 'error' ? 'cross' : 'check'} size={12} />
      </span>
      <p className={styles.message}>{note.message}</p>
      <button
        type="button"
        className={styles.close}
        aria-label={t('toasts.close')}
        onClick={() => dismiss(note.id)}
      >
        <Icon name="cross" size={12} />
      </button>
      <span className={`${styles.bar} ${paused ? styles.barPaused : ''}`} aria-hidden="true" />
    </div>
  );
}

export function Toaster() {
  const { t } = useTranslation();
  const shown = useSyncExternalStore(subscribe, () => notes);
  return (
    <section className={styles.toaster} aria-label={t('toasts.label')} aria-live="polite">
      {shown.map((note) => (
        <NoteItem key={note.id} note={note} />
      ))}
    </section>
  );
}
