// What a form says under a field the server refused: the code's own text, or a generic one.
import { renderHook } from '@testing-library/react';
import { expect, it } from 'vitest';

import '../../src/i18n';
import { ApiError } from '../../src/api/client';
import { useFormErrors } from '../../src/features/forms';

function errorsFor(fields: Record<string, string>) {
  const error = new ApiError(422, {
    error: { code: 'validation_error', message: 'Certains champs sont invalides.', fields },
  });
  return renderHook(() => useFormErrors(error)).result.current;
}

it('says why a date of the prono form is refused', () => {
  const errors = errorsFor({
    result_expected_at: 'before_closing',
    opens_at: 'after_closing',
    closes_at: 'past',
  });
  expect(errors.field('result_expected_at')).toBe(
    'Le résultat ne peut pas être attendu avant la clôture des pronos.',
  );
  expect(errors.field('opens_at')).toBe("L'ouverture doit venir avant la clôture des pronos.");
  expect(errors.field('closes_at')).toBe('Cette date est déjà passée.');
  expect(errors.message).toBeUndefined();
});

it('falls back on a generic text for a code it does not know', () => {
  expect(errorsFor({ link: 'whatever' }).field('link')).toBe("Ce champ n'est pas valide.");
});
