import { MutationCache, QueryClient } from '@tanstack/react-query';

import { ApiError } from '../api/client';
import i18n from '../i18n';
import { toast } from '../ui/Toaster';

declare module '@tanstack/react-query' {
  interface Register {
    mutationMeta: {
      /** The note once it is done (an i18n key), for an action whose words do not depend on the
       *  screen; the others say it themselves with `toast`. */
      success?: string;
      /** Error codes the screen explains itself, with more than a note can hold. */
      shown?: readonly string[];
      /** No note when it fails: nobody asked for it, it runs on its own. */
      quiet?: boolean;
    };
  }
}

/** What went wrong, in one sentence: the server's own words, or why it could not answer. */
export function errorNote(error: unknown): string {
  if (error instanceof ApiError && error.code !== 'error') {
    return error.code === 'validation_error' ? i18n.t('toasts.fields') : error.message;
  }
  return i18n.t(navigator.onLine ? 'shell.error' : 'toasts.offline');
}

export const queryClient = new QueryClient({
  // Every action says how it went in a note at the top right (ui/Toaster), not in the page.
  mutationCache: new MutationCache({
    onSuccess: (_data, _variables, _result, mutation) => {
      const key = mutation.meta?.success;
      if (key) toast.success(i18n.t(key));
    },
    onError: (error, _variables, _result, mutation) => {
      const meta = mutation.meta;
      if (meta?.quiet) return;
      if (error instanceof ApiError && meta?.shown?.includes(error.code)) return;
      toast.error(errorNote(error));
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      // A refusal from the server (403, 404, 409…) will not change by asking again.
      retry: (failures, error) =>
        !(error instanceof ApiError && error.status < 500) && failures < 2,
    },
  },
});
