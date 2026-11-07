// « Changer mon mot de passe » in the settings (specs/002-keycloak-auth, US3): the way to
// Keycloak's « Nouveau mot de passe » page, through the server, back to the settings.
import { cleanup, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, expect, it } from 'vitest';

import '../../src/i18n';
import { PasswordChange } from '../../src/features/settings/SettingsPage';

afterEach(cleanup);

it("leads to Keycloak's new password page, then back to the settings", () => {
  render(
    <MemoryRouter initialEntries={['/compte']}>
      <PasswordChange />
    </MemoryRouter>,
  );
  expect(screen.getByRole('heading', { name: 'MOT DE PASSE' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Changer mon mot de passe' })).toHaveAttribute(
    'href',
    '/api/auth/login?action=password&suite=%2Fcompte',
  );
});
