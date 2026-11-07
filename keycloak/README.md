# Sibylle's Keycloak theme

Keycloak runs Sibylle's sign-in: sign-up, sign-in, forgotten password and address check. The
theme `sibylle` (`theme/`) gives those pages and e-mails the app's Gazette look and its French
words.

- `theme/login/` holds the pages. They are FreeMarker templates on Keycloak's `base` theme.
  - `template.ftl` is the frame: the masthead, the double rule, the title, Keycloak's message
    styled as one of the app's notes.
  - `field.ftl` holds the app's fields.
  - `resources/` holds the style sheet, the fonts, the crystal ball and the icons.
- `theme/email/` holds the e-mails, in the frame of the app's own
  (`backend/src/sibylle/notify/templates/fr/`).
- `dev.sh` and `dev-realm.json` run a local Keycloak with the theme.
- `check-theme.py` shows and checks every page and e-mail.

## The pages

Rewritten, after `frontend/src/features/auth/AuthPages.tsx`:

| Page | Template |
|------|----------|
| Connexion | `login.ftl` |
| Créer un compte | `register.ftl` |
| Mot de passe oublié | `login-reset-password.ftl` |
| Nouveau mot de passe | `login-update-password.ftl` |
| The account to complete | `login-update-profile.ftl` |
| The address to confirm | `login-verify-email.ftl` |
| The words after an e-mail's link | `info.ftl` |
| Errors | `error.ftl` |
| A step left too long | `login-page-expired.ftl` |
| Te déconnecter ? | `logout-confirm.ftl` |

The other pages of the base theme (one-time codes, passkeys, other sign-in services) stay as
they are. They still get the frame, the style and the app's fields and buttons through the
classes in `theme.properties`.

A new password is typed once, as in the app. Keycloak also wants it in `password-confirm`:
`resources/js/sibylle.js` copies it there on submit. Without JavaScript, the page shows that
second field.

These are the e-mails:

- `email-verification`, the address check;
- `password-reset`, the new password;
- `executeActions`, what the app asks of an account;
- `email-update-confirmation`, a new address.

Each one has an HTML and a text version.

## Deployment

There is no image to build. Production's Keycloak (`dev-external/keycloak` in labnode2/docker)
mounts this folder from the machine's copy of the repository, read-only:

```yaml
    volumes:
      - type: bind
        source: /opt/sibylle/keycloak/theme
        target: /opt/keycloak/themes/sibylle
        read_only: true
        bind:
          create_host_path: false
```

`deploy/update.sh` moves that copy to `main` at every deployment. Keycloak keeps no cache of the
theme (`KC_SPI_THEME__CACHE_THEMES` and `KC_SPI_THEME__CACHE_TEMPLATES` are `false`), so a new
page shows at once, without a restart. Its style sheet, fonts and scripts keep a 1-hour browser
cache (`KC_SPI_THEME__STATIC_MAX_AGE=3600`). Their address follows Keycloak's version, not the
theme's, so a longer cache would keep an old style sheet. At the scale of Sibylle, reading the
templates at each page costs nothing.

The "Keycloak theme" workflow (`.github/workflows/keycloak.yml`) starts the same Keycloak with
the theme on every change under `keycloak/`, then runs `check-theme.py`. On `main`, once every
page shows, it calls `deploy.yml`. A template error would otherwise break everyone's sign-in at
the next deployment.

The mount needs `/opt/sibylle/keycloak/theme` on the machine, so the theme must be deployed
before Keycloak starts with it. `create_host_path: false` makes Compose refuse to start rather
than create the folder as root, which would break `update.sh`'s next checkout.

## What the realm sets

OpenTofu creates Sibylle's realm in production (`terraform/`, its README). `dev-realm.json` sets
the same values for the local Keycloak:

- `login_theme` and `email_theme`: `sibylle`.
- Internationalization on, French as the only and default locale. Without it, Keycloak shows
  its English texts.
- Registration allowed, e-mail as username, sign-in by e-mail, forgotten password allowed, no
  "remember me".
- No "Verify email" at sign-up: an unconfirmed account may play (spec FR-002). The app asks
  Keycloak to send the address check instead.
- The password policy `length(8)`. The page's hint, "8 CARACTÈRES AU MOINS", is written in
  `messages_fr.properties`: change both together.
- Links valid 1 hour when the person asks (forgotten password) and 24 hours when the app does
  (address check). The e-mails give the realm's duration.
- SMTP: Brevo in production, Mailpit locally.

## Working on the theme

```bash
make keycloak        # Keycloak 26.8.2 with the theme on http://localhost:8280, e-mails in Mailpit
make check-keycloak  # shows and checks every page and e-mail
make keycloak-stop
```

- **Sign-in page:** http://localhost:8280/realms/sibylle/account. Keycloak runs in dev mode, so
  an edit under `theme/` shows on the next reload.
- **Accounts:** `camille@sibylle.test` / `gazette-camille`, and `dominique@sibylle.test` /
  `gazette-dominique`, whom Keycloak asks for a new password.
- **E-mails:** they arrive in Mailpit, http://localhost:8025.
- **Admin console:** http://localhost:8280/admin/ (`admin` / `admin`).
- **Each start** creates the realm anew.

## Keeping it in step

- **The style.** `resources/css/sibylle.css` carries the app's look. It takes the tokens of
  `frontend/src/styles/tokens.css`, the base of `gazette.css`, the components of
  `frontend/src/ui/ui.module.css` and the column of `frontend/src/features/auth/auth.module.css`.
  Change them together.
- **The words.** The texts come from `frontend/src/i18n/fr/auth.json` and `common.json`, and from
  the server's errors and e-mails. Each message goes through Java's `MessageFormat`, so an
  apostrophe is written `''`. Keycloak formats the titles of the pages that an e-mail's link
  opens (`…Header`, `accountUpdatedTitle`, `confirmExecutionOfActions`) twice, which drops even a
  doubled apostrophe, so those titles have none.
- **The crystal ball.** `resources/js/crystal-ball.js` is a copy of
  `crystal-ball-kit/src/crystal-ball.js`, and `check-theme.py` fails when the two differ.
- **The fonts.** They come from the frontend's fontsource 5.3.0 packages, Latin character sets
  only. Their SIL Open Font License files sit next to them.
- **The colours.** The pages are light, the app's choice until it knows an account's. The dark
  tokens apply once something sets `data-theme` on `<html>`.
- **Keycloak's version.** `dev.sh` and labnode2/docker's compose name the same version: bump
  both together. A bump of `dev.sh` runs the workflow. Read the release notes for changes to the
  base theme's templates that this theme rewrites, listed above.
