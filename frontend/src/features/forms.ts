// Turns an API error into what a form shows: one message, and a message per invalid field.
import { useTranslation } from 'react-i18next';

import { ApiError } from '../api/client';

export function useFormErrors(error: unknown) {
  const { t } = useTranslation('common');
  const apiError = error instanceof ApiError ? error : null;
  return {
    /** The error's message, unless it is about specific fields. */
    message: error
      ? apiError?.code === 'validation_error'
        ? undefined
        : (apiError?.message ?? t('shell.error'))
      : undefined,
    field(name: string): string | undefined {
      const code = apiError?.fields[name];
      if (!code) return undefined;
      return t(`fields.${code}`, { defaultValue: t('fields.invalid') });
    },
  };
}
