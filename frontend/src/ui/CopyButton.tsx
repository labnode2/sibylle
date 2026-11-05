// Copying a link or a code: the button keeps its words, and a note says it is copied.
import { useTranslation } from 'react-i18next';

import { Button, Icon } from './components';
import { toast } from './Toaster';

/** Puts `text` in the clipboard. The clipboard API needs a secure page: in plain http (the app
 *  opened from another machine of the local network), the old command still copies. */
export async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    // refused: the old way may still work
  }
  const area = document.createElement('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.append(area);
  area.select();
  const copied = document.execCommand('copy');
  area.remove();
  return copied;
}

/** A button that copies `text`; `done` is the note once it is copied. */
export function CopyButton({ text, label, done }: { text: string; label: string; done?: string }) {
  const { t } = useTranslation();
  const copy = async () => {
    if (await copyText(text)) toast.success(done ?? t('toasts.copied'));
    else toast.error(t('toasts.copyFailed'));
  };
  return (
    <Button variant="secondary" onClick={() => void copy()}>
      <Icon name="copy" />
      {label}
    </Button>
  );
}
