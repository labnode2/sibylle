---

description: "Liste des tâches pour implémenter Sibylle v1"
---

# Tasks: Sibylle v1, le jeu de pronostics des rédactions

**Input**: Design documents from `/specs/001-sibylle-v1/` (plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md) et `.specify/memory/constitution.md`.

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: inclus. La constitution (principe IV) exige que les règles du jeu soient testées avant d'être codées, que chaque route ait son test de contrat (isolation entre rédactions comprise) et que les parcours clés aient un test de bout en bout. Dans chaque histoire, les tâches de test passent avant l'implémentation et doivent d'abord échouer.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: parallélisable (fichiers différents, aucune dépendance sur une tâche non terminée)
- **[Story]**: histoire de spec.md (US1 à US11)
- Chaque tâche cite ses fichiers.

## Path Conventions

- Serveur : `backend/src/sibylle/`, tests dans `backend/tests/` ; interface : `frontend/src/`, tests dans `frontend/tests/` ; hébergement : `deploy/`.
- Références : routes et schémas dans `contracts/rest-api.md`, événements dans `contracts/realtime.md`, notifications dans `contracts/notifications.md`, tables et contraintes dans `data-model.md`, choix R1 à R20 et règles J1 à J5 dans `research.md`, scénarios V1 à V10 dans `quickstart.md`.
- Maquettes : canvas Gazette https://claude.ai/artifact/U1j9b9bbyqA7jMC71DLUCf, planches citées par leur nom (B-Accueil, B-Prono, B-Profil, B-Web-Accueil, B-Web-Prono, B-Web-Profil, G-Rejoindre, G-Creer, G-Designer, G-Resultat, G-Classement, G-Orga, G-Pixel, G-Style) et pages « Mobile » et « Ordinateur ».
- Conventions : code et identifiants en anglais, textes d'interface en français par les catalogues ; tout instant métier vient de `clock.now()` ; chaque route sous `/orgs/{org}` passe par `current_member` et `require(...)` ; chaque écran existe en mobile (390 px) et en ordinateur (1 024 px et plus) ; après chaque changement de route serveur, régénérer `frontend/src/api/schema.d.ts` avec `npm run gen:api` ; une seule révision Alembic à la fois, pour garder une seule tête.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: dépôt, outils et squelettes des deux projets.

- [X] T001 Créer l'arborescence de plan.md : `backend/src/sibylle/__init__.py`, `backend/tests/unit/`, `backend/tests/integration/`, `backend/tests/contract/`, `frontend/`, `deploy/backup/`, un `.gitignore` racine (`.venv/`, `__pycache__/`, `node_modules/`, `frontend/dist/`, `.env`, `deploy/.env`, `data/`, `.fake-clock`, `playwright-report/`, `test-results/`) et un `README.md` racine de quelques lignes qui renvoie à `specs/001-sibylle-v1/quickstart.md`.
- [X] T002 [P] Vérifier que Node.js LTS 24 ou plus et npm sont installés (ils manquaient sur la machine le 1ᵉʳ novembre 2026) ; s'ils manquent, demander à l'utilisateur avant de les installer pour son compte (par exemple avec fnm), puis écrire la version dans `frontend/.nvmrc`.
- [X] T003 [P] Initialiser le projet Python avec uv dans `backend/pyproject.toml` : nom `sibylle`, `requires-python = ">=3.14"`, disposition `src/`, script `sibylle = "sibylle.cli:main"` ; dépendances fastapi, uvicorn[standard], sqlalchemy[asyncio] 2.x, asyncpg, alembic, pydantic 2, pydantic-settings, argon2-cffi, apscheduler (>=3.11,<4), pywebpush, aiosmtplib, jinja2, pillow, python-multipart ; dépendances de développement pytest, pytest-asyncio, httpx, hypothesis, testcontainers[postgres], ruff, mypy ; générer `backend/uv.lock`.
- [X] T004 Configurer dans `backend/pyproject.toml` ruff (format et règles E, F, I, B, UP, ASYNC, longueur 100), mypy strict sur le paquet `sibylle`, et pytest (`asyncio_mode = "auto"`, marqueurs `unit`, `integration`, `contract`).
- [X] T005 Initialiser l'interface Vite + React + TypeScript dans `frontend/package.json` (paquet `sibylle-web`) : react et react-dom 19, react-router 8, @tanstack/react-query 5, i18next, react-i18next, openapi-fetch, workbox-precaching, workbox-routing, workbox-strategies ; en développement typescript 5.9 (typescript-eslint et openapi-typescript n'acceptent pas encore TypeScript 7), vite, @vitejs/plugin-react, vite-plugin-pwa, openapi-typescript, vitest, jsdom, @testing-library/react, @testing-library/user-event, @playwright/test, @axe-core/playwright, eslint, typescript-eslint, eslint-plugin-react-hooks, prettier ; polices @fontsource/jacquard-12, @fontsource-variable/bricolage-grotesque et @fontsource/geist-mono (si un paquet n'existe pas, placer les fichiers WOFF2 sous licence OFL dans `frontend/src/assets/fonts/`).
- [X] T006 Configurer `frontend/tsconfig.json` (strict), `frontend/eslint.config.js`, `frontend/.prettierrc`, `frontend/vite.config.ts` (proxy `/api` vers `http://localhost:8000` avec `ws: true`), `frontend/vitest.config.ts` (jsdom) et `frontend/playwright.config.ts` (lance l'API avec `SIBYLLE_CLOCK=fake` et le serveur Vite ; les tests déclenchent les tâches du `worker` avec `sibylle jobs run`), plus les scripts `dev`, `build`, `lint`, `typecheck`, `test`, `e2e`, `gen:api` et `check:api` de `frontend/package.json`.
- [X] T007 [P] Écrire `deploy/docker-compose.yml` avec `db` (postgres:18, volume `pgdata`, contrôle `pg_isready`, port 5432 lié à 127.0.0.1) et `mailpit` (profil `dev`, ports 1025 et 8025 liés à 127.0.0.1), et `deploy/.env.example`, qui documente sans valeur réelle `ENVIRONMENT`, `DATABASE_URL`, `PUBLIC_ORIGIN`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`, `UPLOAD_DIR`, `SIBYLLE_CLOCK`, `SIBYLLE_FAKE_CLOCK_FILE` et `LOG_LEVEL`.
- [X] T008 [P] Écrire `./Makefile` à la racine du dépôt : cible `check` (serveur : `uv run ruff format --check`, `uv run ruff check`, `uv run mypy src`, `uv run pytest` ; interface : `npm run lint`, `npm run typecheck`, `npm run test`, `npm run check:api`) et cibles `db`, `api`, `worker`, `web` et `e2e`.
- [X] T009 Copier `crystal-ball-kit/assets/favicon/*` dans `frontend/public/`, `crystal-ball-kit/src/crystal-ball.js` et `crystal-ball-kit/src/crystal-ball.d.ts` dans `frontend/src/vendor/crystal-ball/` (avec une note d'origine), et adapter `crystal-ball-kit/examples/react/CrystalBall.tsx` en `frontend/src/ui/CrystalBall.tsx` (props `variant`, `size` multiple de 16, `loops`).

**Checkpoint**: `uv sync` et `npm install` passent ; `docker compose -f deploy/docker-compose.yml --profile dev up -d db mailpit` démarre la base et Mailpit.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: socle commun : configuration, horloge, base de données, droits, registre des lauriers, sessions, temps réel, file des notifications, processus de tâches, coque de l'interface.

**⚠️ CRITICAL**: aucune histoire ne commence avant la fin de cette phase.

- [X] T010 Implémenter `backend/src/sibylle/config.py` : réglages pydantic-settings pour toutes les variables de `deploy/.env.example`, `ENVIRONMENT` ∈ `development`, `test`, `production`, et refus de `SIBYLLE_CLOCK=fake` en production.
- [X] T011 Implémenter `backend/src/sibylle/clock.py` : `now()` renvoie un instant UTC avec fuseau ; horloge système par défaut ; horloge simulée (`SIBYLLE_CLOCK=fake`) qui lit dans `SIBYLLE_FAKE_CLOCK_FILE` l'instant simulé et l'heure réelle à laquelle il a été posé, pour que le temps continue de s'écouler ; `set_fake_now(instant)` et `advance_fake(delta)`. Règle du projet : tout instant métier vient de `clock.now()`, jamais du `now()` de PostgreSQL.
- [X] T012 [P] Écrire d'abord `backend/tests/unit/test_seasons.py` (il doit échouer) : bornes « printemps du 21 mars au 20 juin, été du 21 juin au 22 septembre, automne du 23 septembre au 20 décembre, hiver du 21 décembre au 20 mars (heure de Paris) », chaque saison commençant à 00:00, et « l'hiver porte l'année de son début » ; conversions autour des changements d'heure ; début de semaine (lundi 00:00, Paris) ; bornes du mois ; le 1ᵉʳ décembre 2026 tombe dans l'automne 2026, qui finit le 21 décembre 2026 à 00:00 (Paris).
- [X] T013 Implémenter `backend/src/sibylle/domain/seasons.py` pour faire passer T012 : `season_of(instant)`, `season_bounds(year, name)`, `week_start(instant)`, `month_bounds(instant)` et `seasons_between(start, end)`, avec `zoneinfo.ZoneInfo("Europe/Paris")`.
- [X] T014 Implémenter `backend/src/sibylle/db/base.py` (DeclarativeBase, convention de nommage des contraintes, clé primaire `uuid` par défaut `uuid.uuid7()`) et `backend/src/sibylle/db/session.py` (moteur asyncpg, fabrique de sessions, une transaction par requête, `transaction()` pour le `worker` et la ligne de commande).
- [X] T015 Configurer Alembic : `backend/alembic.ini`, `backend/src/sibylle/db/migrations/env.py` (asynchrone, métadonnées de `backend/src/sibylle/db/models/__init__.py`, qui importe tous les modèles) et une première révision `backend/src/sibylle/db/migrations/versions/<rev>_base.py` : extension `citext` et table `seasons` (`id` smallserial, `year`, `name` ∈ `spring`, `summer`, `autumn`, `winter`, `starts_at`, `ends_at`, unique (`year`, `name`)), remplie de l'automne 2026 à 2030 avec `domain/seasons.py` ; modèle dans `backend/src/sibylle/db/models/seasons.py`.
- [X] T016 [P] Écrire d'abord `backend/tests/unit/test_permissions.py` : matrice des droits du cahier des charges. Tous les rôles : pronostiquer, réagir, voir qui a choisi quoi. `reader` seul : proposer un prono, publié après validation. `journalist` et `editor` : créer et publier, valider les propositions, modifier tant que personne n'a joué, désigner le résultat, relancer. `editor` seul : gérer membres, rôles, invitations et code ; personnaliser la carte ; régler les lauriers ; corriger un résultat ; annuler un prono ; ajouter ou retirer des lauriers à un membre ; traiter les signalements.
- [X] T017 Implémenter `backend/src/sibylle/domain/permissions.py` (`Role`, `Action`, `can(role, action)`) pour faire passer T016.
- [X] T018 [P] Écrire d'abord `backend/tests/unit/test_security.py`, puis implémenter `backend/src/sibylle/services/security.py` : hachage Argon2id (argon2-cffi), jetons aléatoires de 256 bits (`secrets.token_urlsafe(32)`) et leur empreinte SHA-256 ; seule l'empreinte est stockée (`sessions.token_hash`, `email_tokens.token_hash`, `invitations.token_hash`).
- [X] T019 [P] Implémenter `backend/src/sibylle/api/errors.py` et le catalogue `backend/src/sibylle/i18n/fr.json` : enveloppe `{ "error": { "code", "message", "fields" } }`, exception `AppError`, codes et statuts de contracts/rest-api.md (`not_authenticated` et `invalid_credentials` 401 ; `forbidden` 403 ; `not_found` 404 ; `invalid_state`, `already_bet`, `insufficient_balance`, `pseudo_taken`, `email_taken`, `invitation_invalid`, `token_invalid`, `last_editor` et `attempts_exhausted` 409 ; `too_large` 413 ; `validation_error` 422 avec `fields` ; `rate_limited` 429), messages en français.
- [X] T020 Implémenter `backend/src/sibylle/main.py` (`create_app()`, préfixe `/api`, erreurs de T019, journaux JSON sur la sortie standard, middleware qui exige `X-Sibylle: 1` et un `Origin` égal à `PUBLIC_ORIGIN` sur `POST`, `PUT`, `PATCH` et `DELETE`, sinon 403 `forbidden`), `backend/src/sibylle/api/routes/health.py` (`GET /api/health` renvoie `{status, db}`) et `backend/src/sibylle/cli.py` (`sibylle openapi` écrit l'OpenAPI sur la sortie standard ; `sibylle clock set <instant>` et `sibylle clock advance <durée>`).
- [X] T021 Créer `backend/src/sibylle/db/models/accounts.py` (`accounts`, `sessions`, `email_tokens`), `backend/src/sibylle/db/models/orgs.py` (`organisations`, `memberships`) et `backend/src/sibylle/db/models/ledger.py` (`ledger_entries`) avec toutes les colonnes de data-model.md et ses règles : `accounts.email` citext « unique ; NULL après suppression », `theme` ∈ `auto`, `light`, `dark`, `reduce_motion` faux par défaut, `locale` `fr` ; `sessions.token_hash` unique ; `email_tokens.purpose` ∈ `verify_email`, `reset_password` ; `organisations.title` « 1 à 40 caractères », `access_code` « unique, NULL si désactivé », `starting_balance` « ≥ 0, défaut 100 », `max_base_gain` « ≥ 0, défaut 50 », `early_bird_pct` « 0 à 100, défaut 20 », `early_bird_count` « ≥ 0, défaut 5 », plus `logo`, `background_key`, `editor_note`, `charter` ; `memberships` unique (`org_id`, `account_id`), `role` ∈ `reader`, `journalist`, `editor`, `status` ∈ `active`, `left`, `anonymized`, `pseudo` « 2 à 24 caractères ; unique par organisation (insensible à la casse) parmi les statuts active et left » (index unique partiel sur `lower(pseudo)`), plus `avatar`, `avatar_frame_item_id`, `balance`, `season_score`, `joined_at`, `charter_accepted_at`, `left_at` ; `ledger_entries` (`id` bigint identité, `org_id`, `membership_id`, `season_id`, `kind`, `amount`, `score_delta`, `prono_id`, `bet_id`, `settlement_id`, `reverses_entry_id`, `reason`, `actor_membership_id`, `created_at`) avec les index (`membership_id`, `created_at`), (`org_id`, `season_id`, `kind`) et (`settlement_id`) ; `prono_id`, `bet_id` et `settlement_id` restent sans clé étrangère jusqu'à US2 et US3.
- [X] T022 Générer et relire la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_accounts_orgs_ledger.py` pour T021, avec `REVOKE UPDATE, DELETE ON ledger_entries` pour le rôle de l'application (registre en ajout seul, principe III).
- [X] T023 Écrire `backend/tests/conftest.py` : PostgreSQL 18 via testcontainers avec migrations appliquées, horloge simulée remise à zéro à chaque test, client httpx ASGI qui envoie `X-Sibylle: 1` et l'`Origin` attendu, fabriques `make_account`, `make_org`, `make_member(org, role)` et `client_for(member)` déjà connecté.
- [X] T024 [P] Écrire d'abord `backend/tests/unit/test_ledger_effects.py` : effet de chaque type d'écriture sur le solde et sur le score selon data-model.md — `starting_balance` (+ solde de départ, 0), `stake` (− mise, 0), `base_gain` et `early_bird` (+ gain, + gain), `pot_share` (+ part, + (part − mise)), `stake_lost` (0, − mise), `refund` (+ mise, 0), `reversal` (− montant et − score de l'écriture inversée), `purchase` (− prix, 0), `minigame` (+ gain, 0), `adjustment` (± montant, 0), `season_reset` (solde de départ − solde courant, 0).
- [X] T025 Implémenter `backend/src/sibylle/realtime/bus.py` (publication `NOTIFY sibylle_events` après validation de la transaction, écoute `LISTEN` sur une connexion asyncpg dédiée, charge de plus de 7 500 octets remplacée par un événement réduit qui demande au client de recharger) et `backend/src/sibylle/realtime/hub.py` (abonnements par sujet `org:<id>`, `prono:<id>` et `me` ; audience `all`, `journalists` ou liste de `membership_id`), avec le test `backend/tests/integration/test_bus.py`.
- [X] T026 Implémenter `backend/src/sibylle/domain/ledger.py` (`LedgerKind` et effets, pour faire passer T024) et `backend/src/sibylle/services/ledger.py` : `append(...)` verrouille la ligne du membre (`FOR UPDATE`), écrit l'écriture avec la saison courante, met à jour `memberships.balance` et `memberships.season_score` dans la même transaction et publie `balance.changed` sur `me` après validation ; `reverse(entry)` ; `check_caches(org_id)` compare les caches aux sommes du registre.
- [X] T027 Implémenter `backend/src/sibylle/api/deps.py` : session de base par requête ; `current_account` (cookie `sibylle_session`, session valide, prolongée de 30 jours à l'usage, sinon 401 `not_authenticated`) ; `current_member(org_id)` (membre `active` de la rédaction, sinon 404 `not_found`) ; `require(action)` qui applique `domain/permissions.py` (sinon 403 `forbidden`) ; limiteur de débit en mémoire par IP et par clé (429 `rate_limited`).
- [X] T028 Implémenter `backend/src/sibylle/realtime/ws.py` selon contracts/realtime.md : `GET /api/ws`, cookie de session et contrôle de l'`Origin`, messages `subscribe`, `unsubscribe` et `pong`, `ping` toutes les 25 s et fermeture sans `pong` pendant 60 s, codes `4401`, `4403` et `1012`, réponses `subscribed` ou `error` `forbidden_topic`, abonnement automatique à `me`, sujet `org:<id>` réservé aux membres actifs (le sujet `prono:<id>` arrive avec US2), désabonnement immédiat d'un membre qui quitte ou est retiré.
- [X] T029 Créer `backend/src/sibylle/db/models/notifications.py` (`notifications` : `account_id`, `org_id`, `type`, `payload`, `dedupe_key` unique, `state` ∈ `pending`, `sent`, `skipped`, `failed`, `attempts`, `next_attempt_at`, `sent_at`, `created_at`), sa révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_notifications.py`, et `backend/src/sibylle/services/notifications.py` : `enqueue(session, account_id, type, payload, dedupe_key, scheduled_at)`, qui ignore un doublon de `dedupe_key`.
- [X] T030 [P] Implémenter `backend/src/sibylle/notify/email.py` : rendu Jinja2 en texte et en HTML depuis `backend/src/sibylle/notify/templates/fr/`, mise en page commune `base.html` au style Gazette (aucune image distante, aucun pixel de suivi), envoi SMTP par aiosmtplib depuis `MAIL_FROM` (Mailpit en développement, relais Brevo en production), émetteur injectable pour les tests.
- [X] T031 Implémenter `backend/src/sibylle/worker/main.py` (APScheduler `AsyncIOScheduler`, fuseau Europe/Paris, lancé par `sibylle worker` ; `sibylle jobs run <tâche>` exécute une tâche une fois, pour les tests) et `backend/src/sibylle/worker/jobs.py` (registre des tâches) avec une première tâche, `dispatch_notifications` : chaque minute, lignes `pending` échues lues avec `FOR UPDATE SKIP LOCKED`, envoi, reprises après 1 min, 5 min, 30 min et 2 h, puis `failed` ; test `backend/tests/integration/test_dispatch.py` avec l'émetteur factice.
- [X] T032 [P] Écrire `frontend/src/styles/tokens.css` et `frontend/src/styles/gazette.css` : papier `#f3f4fa`, blanc `#ffffff`, encre `#15162d`, encre secondaire `#4a4d6a`, filet `#c9cbe4`, gris clair `#e3e4eb` (sélections, rails, codes, ligne « toi »), indigo `#4a50d0` ; or `#f2c230` réservé au logo et aux lauriers, soulignement fin `#c99a18` sous la phrase clé, une fois par écran ; thème clair par défaut, sombre sous `[data-theme="dark"]`, et sous `prefers-color-scheme` seulement avec `[data-theme="auto"]` ; angles droits, filets de 1 et 2 px, ombres décalées dures (`4px 4px 0` couleur encre) ; pixel art à l'échelle entière avec `image-rendering: pixelated` ; animations coupées par `prefers-reduced-motion` ou par la classe `.reduce-motion` ; polices Jacquard 12 (titre « Sibylle », multiples de 12 px), Bricolage Grotesque (titres et texte) et Geist Mono (surtitres, chiffres, capitales).
- [X] T033 [P] Créer les composants de `frontend/src/ui/` d'après la planche G-Style, regroupés dans `frontend/src/ui/components.tsx` (`Masthead` avec « LA GAZETTE DE », « Sibylle » et la boule de `CrystalBall.tsx` ; `Rule`, `Card`, `Button`, `ButtonLink`, `Field`, `Chip`, `Stepper`, `Kicker`, `TabBar` avec l'onglet actif souligné à l'encre, `Laurel` avec le laurier extrait de l'atlas du canvas, `Switch`, `Icon` et les icônes 12 × 12 de `icons.ts`) et `frontend/src/ui/PixelImage.tsx` (`PixelImage` dessinée sur `<canvas>` à l'échelle entière, `AvatarStack`), plus la palette `frontend/src/ui/palette.ts`.
- [X] T034 [P] Configurer i18next dans `frontend/src/i18n/index.ts` : `fr` seul, un fichier JSON par fonctionnalité dans `frontend/src/i18n/fr/`, dates et nombres formatés par `Intl` dans le fuseau `Europe/Paris`.
- [X] T035 Créer `frontend/src/api/client.ts` (openapi-fetch, `credentials: "include"`, en-tête `X-Sibylle: 1` sur les requêtes qui modifient, erreurs `{error}` converties en exceptions typées) et les scripts `gen:api` (`uv run --directory ../backend sibylle openapi`, puis openapi-typescript vers `frontend/src/api/schema.d.ts`) et `check:api` (échoue si le fichier régénéré diffère).
- [X] T036 [P] Créer `frontend/src/api/realtime.ts` : une WebSocket par onglet sur `/api/ws`, réponse aux `ping`, reconnexion avec un délai de 1 s à 30 s et un peu d'aléa, réabonnement et invalidation des requêtes TanStack Query après reconnexion, renvoi vers `/connexion` sur `4401`, crochet `useTopic(topic, onEvent)` ; test `frontend/tests/unit/realtime.test.ts`.
- [X] T037 Créer `frontend/src/main.tsx`, `frontend/src/app/providers.tsx` (QueryClient, i18n, thème clair, sombre ou automatique et « couper les animations » posés sur `<html>`), `frontend/src/app/router.tsx` (React Router : routes publiques `/connexion`, `/inscription`, `/rejoindre/:token`, routes de rédaction `/o/:orgId/…`) et `frontend/src/app/AppShell.tsx` (mobile à 390 px avec la barre d'onglets Accueil, Pronos, Profil ; ordinateur à partir de 1 024 px d'après la page « Ordinateur » du canvas).
- [X] T038 [P] Configurer la PWA : vite-plugin-pwa en mode `injectManifest` dans `frontend/vite.config.ts`, manifeste (nom « Sibylle », icônes `icon-192.png` et `icon-512.png` du kit, couleurs du papier et de l'encre) et `frontend/src/sw.ts` (précache de la coque, page hors ligne qui explique que parier demande une connexion ; les gestionnaires `push` et `notificationclick` viennent avec US8).

**Checkpoint**: `make check` passe ; `GET /api/health` répond ; la coque de l'interface s'affiche en clair et en sombre ; le `worker` démarre.

---

## Phase 3: User Story 1 - Entrer dans une rédaction (Priority: P1) 🎯 MVP

**Goal**: s'inscrire, créer une rédaction, inviter, rejoindre par lien, code ou invitation nominative, avec un pseudo, un avatar et la charte ; un même compte vit dans plusieurs rédactions.

**Independent Test**: créer un compte, créer une organisation, générer un lien d'invitation et le faire utiliser par un second compte ; le second compte voit la rédaction avec son pseudo et le rôle lecteur·rice, et un troisième compte sans invitation ne voit rien.

### Tests for User Story 1 ⚠️

> Écrits d'abord ; ils doivent échouer avant l'implémentation.

- [X] T039 [P] [US1] Écrire `backend/tests/contract/test_auth.py` : `POST /auth/signup` (201, cookie `sibylle_session` `HttpOnly; Secure; SameSite=Lax`, e-mail `verify_email` mis en file ; adresse déjà prise → `email_taken` ; mot de passe de moins de 8 caractères → 422), `POST /auth/login` (mauvais mot de passe → `invalid_credentials` ; 429 après 10 essais en 15 minutes par IP et par adresse), `POST /auth/logout`, `GET /me`, `PATCH /me`, `POST /me/password` (ferme les autres sessions), `POST /auth/verify-email` (jeton valable 24 h, à usage unique, sinon `token_invalid`), `POST /auth/verify-email/resend`, `POST /auth/password-reset` (toujours 202), `POST /auth/password-reset/confirm` (jeton valable 1 h, à usage unique, ferme les autres sessions) ; seule `/me` contient `email`, `first_name` et `last_name` ; une requête qui modifie sans `X-Sibylle` ou avec un autre `Origin` reçoit 403.
- [X] T040 [P] [US1] Écrire `backend/tests/contract/test_orgs_join.py` : `POST /orgs` (le créateur est `editor`, reçoit une écriture `starting_balance` de 100 par défaut, un code d'accès est généré), `GET /orgs/{org}`, `POST /orgs/{org}/invitations` (lien : `url` montrée une fois, `max_uses`, `expires_at` ; e-mail : une place, 7 jours, e-mail `invitation` en file ; réservé à `editor`), `POST /join/preview` (`places_left`, `member_count`, `invited_by_pseudo`, charte), `POST /join` par lien, par code et par invitation nominative (pseudo déjà pris, sans tenir compte de la casse → `pseudo_taken` ; lien expiré, révoqué ou complet → `invitation_invalid` ; `charter_accepted` obligatoire ; arrivée en `reader` avec le solde de départ), `GET /orgs/{org}/members`, `PATCH /orgs/{org}/members/me` ; un compte membre de deux rédactions y garde des pseudos, des avatars et des soldes distincts ; un compte d'une autre rédaction reçoit 404 sur chaque route `/orgs/{org}`.
- [X] T041 [P] [US1] Écrire `backend/tests/integration/test_invitation_race.py` : deux `POST /join` simultanés sur un lien à une seule place → une seule adhésion, l'autre reçoit `invitation_invalid`.
- [X] T042 [P] [US1] Écrire `backend/tests/unit/test_pixels.py` : une PixelImage `{ "size": 16 | 32, "palette": "base-v1", "pixels": "<base64>" }` contient exactement `size × size` octets d'indices connus (0 = transparent) ; une couleur hors palette de base n'est acceptée que si le membre l'a débloquée ; base64 invalide, mauvaise taille ou indice inconnu → erreur de validation.

### Implementation for User Story 1

- [X] T043 [US1] Implémenter `backend/src/sibylle/domain/pixels.py` pour faire passer T042 : palette `base-v1` = transparent (indice 0), puis 32 couleurs tirées des avatars de l'atlas Gazette (indices 1 à 32, ouvertes à tous ; la palette PICO-8 envisagée d'abord dénaturait les avatars des maquettes), les 16 couleurs PICO-8 débloquables avec les lauriers (indices 33 à 48) et 4 couleurs rares de la boule (`#6e74ff`, `#8f94ff`, `#6267e8`, `#8a6a12`, indices 49 à 52) réservées aux codes secrets ; `validate_pixel_image(data, unlocked_indices)` ; la même palette dans `frontend/src/ui/palette.ts`.
- [X] T044 [US1] Écrire `backend/src/sibylle/domain/content.py` et `backend/src/sibylle/domain/templates.json` : les 7 modèles d'avatars (t0 à t6) et le modèle de logo (t8) de l'atlas du canvas Gazette (fichier `4f9de3add98bcfa2e85b3c0c687c3794` de https://claude.ai/artifact/U1j9b9bbyqA7jMC71DLUCf ; t7 est le laurier), convertis en PixelImage aux couleurs `base-v1` les plus proches, et un avatar par défaut neutre pour les comptes supprimés ; `BACKGROUND_KEYS` : `mer` (`linear-gradient(#8fb0ff 0 62%, #f4f6fb 62% 66%, #4a50d0 66% 100%)`, celui de G-Rejoindre), `aube`, `nuit`, `foret`, `papier` et `brique` (dégradés dans les couleurs Gazette) ; charte par défaut en français, de moins de 1 500 caractères (jeu sans argent ni lot, respect des collègues, sujets interdits par défaut « la santé et la vie privée des collègues, la politique », modération par la rédaction en chef).
- [X] T045 [US1] Ajouter `invitations` à `backend/src/sibylle/db/models/orgs.py` avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_invitations.py` : `kind` ∈ `link`, `email` ; `token_hash` unique ; `email` pour `email` seulement ; `max_uses` « ≥ 1 ; 1 pour email » ; `use_count` ; `expires_at` « obligatoire ; 7 jours par défaut pour email » ; `created_by` ; `revoked_at` ; `created_at`.
- [X] T046 [US1] Implémenter `backend/src/sibylle/services/accounts.py` : inscription (adresse normalisée, mot de passe de 8 caractères au moins, nom et prénom obligatoires, e-mail `verify_email` en file), connexion (Argon2id, session de 30 jours), déconnexion, mise à jour du compte (`first_name`, `last_name`, `theme`, `reduce_motion`, `locale`), changement de mot de passe (ferme les autres sessions), vérification d'adresse (jeton `verify_email` valable 24 h, à usage unique) et réinitialisation (jeton `reset_password` valable 1 h, à usage unique, ferme toutes les sessions).
- [X] T047 [P] [US1] Écrire `backend/src/sibylle/notify/templates/fr/verify_email.html` et `.txt`, `reset_password.html` et `.txt`, `invitation.html` et `.txt`, avec les objets de contracts/notifications.md : « Confirme ton adresse pour Sibylle », « Ton lien pour changer de mot de passe », « {pseudo} t'invite dans la rédaction {organisation} ».
- [X] T048 [US1] Implémenter `backend/src/sibylle/services/orgs.py` : création d'une rédaction (titre de 1 à 40 caractères, fond pris dans `BACKGROUND_KEYS`, logo PixelImage facultatif, charte par défaut, code d'accès au format de la maquette `SOPHIA-7K2` : lettres du titre sans accents, 6 au plus, en majuscules, un tiret, trois caractères parmi `23456789ABCDEFGHJKMNPQRSTUVWXYZ`, nouveau tirage en cas de collision) ; le créateur devient membre `editor` avec son pseudo et son avatar et reçoit l'écriture `starting_balance` ; lecture d'une rédaction et de ses membres ; changement de son propre pseudo et de son avatar (événement `member.updated`).
- [X] T049 [US1] Implémenter `backend/src/sibylle/services/invitations.py` : lien (jeton montré une seule fois, `max_uses`, `expires_at`), invitation nominative (une place, 7 jours, e-mail `invitation` en file), aperçu pour un jeton ou un code d'accès (`places_left`, `member_count`, `invited_by_pseudo`, charte), adhésion qui verrouille l'invitation, vérifie sa validité et le pseudo, exige `charter_accepted: true`, crée le membre `reader` avec l'écriture `starting_balance` et publie `member.joined`, ou réactive un ancien membre `left` avec son profil et son historique (FR-123).
- [X] T050 [US1] Implémenter `backend/src/sibylle/api/routes/auth.py` et `backend/src/sibylle/api/routes/me.py` (comptes et session de contracts/rest-api.md ; export, suppression et notifications viennent avec US11 et US8), `backend/src/sibylle/api/routes/orgs.py` (`POST /orgs`, `GET /orgs/{org}`), `backend/src/sibylle/api/routes/members.py` (`GET /orgs/{org}/members`, `GET /orgs/{org}/members/{member}` en `MemberPublic`, `PATCH /orgs/{org}/members/me`), `backend/src/sibylle/api/routes/invitations.py` (`POST /orgs/{org}/invitations`, `POST /join/preview`, `POST /join`) et la route publique `backend/src/sibylle/api/routes/content.py` (`GET /content` : modèles d'avatars et de logo, fonds, charte), avec les schémas de `backend/src/sibylle/api/schemas.py` (`Me`, `MemberPublic` sans nom, prénom ni e-mail, `MemberSelf`) ; régénérer `frontend/src/api/schema.d.ts`.
- [X] T051 [P] [US1] Écrire `frontend/src/features/auth/AuthPages.tsx` (connexion, inscription, mot de passe oublié, nouveau mot de passe, vérification d'adresse, au style Gazette) avec ses requêtes dans `frontend/src/features/auth/api.ts`, et `frontend/src/features/auth/RequireAuth.tsx`, qui renvoie vers `/connexion` sans session puis revient à la page demandée.
- [X] T052 [P] [US1] Écrire `frontend/src/features/orgs/OrgPages.tsx` (page d'accueil sans rédaction, création d'une rédaction, adhésion d'après G-Rejoindre : carte d'invitation avec fond et logo, « INVITATION D'{PSEUDO} », « {n} MEMBRES · {k} PLACES RESTANTES », « CODE D'ACCÈS » marqué « VALIDE », « TON PSEUDO DANS CETTE RÉDACTION » et « TES NOM ET PRÉNOM RESTENT PRIVÉS », « TON AVATAR » parmi les modèles, « Dessiner le mien » inactif jusqu'à US7, charte à accepter, « Rejoindre la rédaction », « TOUT SE CHANGE ENSUITE DANS TON PROFIL »), `frontend/src/features/orgs/pickers.tsx` et `frontend/src/styles/backgrounds.css` avec les mêmes clés que `BACKGROUND_KEYS`.
- [X] T053 [P] [US1] Écrire `frontend/src/features/orgs/OrgSwitcher.tsx` (page « Mes rédactions » d'après `GET /me`, bascule vers `/o/:orgId/`, déconnexion ; lien « ÉDITION … » de la barre ordinateur), `frontend/src/app/OrgLayout.tsx` (lauriers, avatar et pseudo dans la barre ordinateur) et une première `frontend/src/features/une/UnePage.tsx` (nom de la rédaction, pseudo et solde), que US5 remplace par la une complète.
- [X] T054 [P] [US1] Écrire `frontend/src/features/admin/InvitePanel.tsx` pour la rédaction en chef : lien avec nombre de places et date d'expiration (URL montrée une seule fois, bouton « Copier »), invitation par e-mail, affichage du code d'accès.
- [X] T055 [US1] Brancher les routes de US1 dans `frontend/src/app/router.tsx` (avec `RequireAuth`) et ajouter `frontend/src/i18n/fr/auth.json` et `frontend/src/i18n/fr/orgs.json`.
- [X] T056 [US1] Ajouter `sibylle seed-demo` à `backend/src/sibylle/cli.py` et écrire `backend/seed/README.md` : rédaction « Sophia Office » avec Inès (`editor`), Hugo (`journalist`), Cami, Léo et Manon (`reader`), un mot de passe de démonstration commun indiqué dans le README ; commande idempotente, refusée en production.
- [X] T057 [US1] Écrire `frontend/tests/e2e/join.spec.ts` (quickstart V1, points 1, 2, 4 et 5) : inscription, création d'une rédaction, lien à 2 places, pseudo déjà pris refusé, deuxième et troisième comptes acceptés, quatrième refusé, aucune donnée privée d'un autre membre dans les réponses de l'API.

**Checkpoint**: on s'inscrit, on crée une rédaction et on la rejoint par lien, code ou e-mail ; chacun a son pseudo et son avatar par rédaction.

---

## Phase 4: User Story 2 - Jouer un prono (Priority: P1)

**Goal**: un·e journaliste publie un prono de l'un des quatre types ; chaque membre parie une fois, de façon définitive, mise s'il le veut et voit tout en direct ; le prono s'ouvre et se clôt tout seul.

**Independent Test**: avec une rédaction de trois membres, publier un prono de chaque type, parier depuis deux navigateurs et vérifier que l'autre navigateur voit la répartition et la cagnotte changer sans recharger ; aucun pari n'est accepté après la clôture.

### Tests for User Story 2 ⚠️

- [X] T058 [P] [US2] Écrire `backend/tests/unit/test_lifecycle.py` : transitions de data-model.md — `proposed` → `scheduled` ou `open` (validation) ; `proposed` → `rejected` ; `scheduled` → `open` à `opens_at` ; `open` → `closed` à `closes_at` ; `open` → `resolved` pour une date « sans fin » ; `closed` → `resolved` ; `closed` → `open` (relance) ; `resolved` → `resolved` (correction) ; `scheduled`, `open`, `closed` et `resolved` → `cancelled` ; toute autre transition lève `InvalidTransition` ; un prono sans aucun pari ne se résout pas (il est relancé ou annulé) ; modification permise seulement si `bet_count = 0` et l'état est `proposed`, `scheduled` ou `open`.
- [X] T059 [P] [US2] Écrire `backend/tests/unit/test_betting.py` : champs d'un prono — question « 5 à 200 caractères », `link_url` « https seulement », `0 ≤ base_gain ≤ organisations.max_base_gain`, `open_ended` seulement pour `date` et alors `closes_at` NULL, `closes_at` dans le futur à la publication, `result_expected_at ≥ closes_at`, choix de « 1 à 80 caractères », au moins 2 pour `choice`, aucun pour `number` et `date`, « Oui » et « Non » automatiques pour `yes_no` ; paris — mise entière `0 ≤ stake ≤ solde`, seule une mise de 0 quand le solde est négatif, refus hors de l'état `open` ou à partir de `closes_at` (heure du serveur), un seul pari actif, nouveau pari d'un prono `open_ended` seulement si la `date_value` du pari actif est passée, `date_value` « strictement après le jour du pari si open_ended ».
- [X] T060 [P] [US2] Écrire `backend/tests/contract/test_pronos.py` : `POST /orgs/{org}/pronos` par un·e journaliste (`open`, ou `scheduled` si `opens_at` est future), `GET /orgs/{org}/pronos` (filtres `state` et `section`, curseur), `GET /orgs/{org}/pronos/{id}` (`options` avec `count`, `stake_total` et `share_pct` ; `bets` avec membre, réponse, mise et rang ; `pot` ; `my_bet`), `PATCH` refusé dès le premier pari (`invalid_state`), `POST …/bets` (201, `already_bet`, `insufficient_balance`, `invalid_state`), `GET /orgs/{org}/sections`, `POST /orgs/{org}/uploads` (413 au-delà de 5 Mo) ; chaque route répond 404 à un membre d'une autre rédaction.
- [X] T061 [P] [US2] Écrire `backend/tests/integration/test_bet_concurrency.py` : 20 paris simultanés (d'un même membre et de membres différents) → un seul pari actif par membre, rangs de 1 à n sans trou, aucun solde négatif, `pot` égal à la somme des mises.
- [X] T062 [P] [US2] Écrire `backend/tests/integration/test_realtime_bets.py` : deux clients WebSocket abonnés à `prono:<id>` ; le pari de l'un arrive à l'autre (`bet.placed`) en moins de 2 s ; un membre d'une autre rédaction reçoit `forbidden_topic`.

### Implementation for User Story 2

- [X] T063 [US2] Créer `backend/src/sibylle/db/models/pronos.py` (`sections`, `pronos`, `prono_options`, `prono_events`, `bets`) et `backend/src/sibylle/db/models/uploads.py` (`uploads`) selon data-model.md, avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_pronos.py` : contraintes listées dans T059 ; `sections.name` unique par rédaction (insensible à la casse), `position`, `archived_at` ; `pronos.kind` ∈ `choice`, `yes_no`, `number`, `date` ; `pronos.state` ∈ `proposed`, `rejected`, `scheduled`, `open`, `closed`, `resolved`, `cancelled` ; `result_number` et `bets.number_value` en `numeric(14,2)` ; `bets.rank` unique par prono ; `bets.outcome` ∈ `pending`, `won`, `lost`, `refunded` ; index unique partiel `(prono_id, membership_id) WHERE superseded_at IS NULL` ; index (`org_id`, `state`, `closes_at`) et (`org_id`, `section_id`) ; `uploads.mime` `image/webp` ; clés étrangères `ledger_entries.prono_id` et `ledger_entries.bet_id` ; rubrique « Général » créée pour chaque rédaction existante.
- [X] T064 [US2] Implémenter `backend/src/sibylle/domain/lifecycle.py` et `backend/src/sibylle/domain/betting.py` pour faire passer T058 et T059.
- [X] T065 [US2] Implémenter `backend/src/sibylle/services/pronos.py` : création par un·e journaliste (`scheduled` si `opens_at` est future, sinon `open` ; un·e lecteur·rice reçoit 403 jusqu'à US5), options « Oui » et « Non » pour `yes_no`, modification avant le premier pari, listes paginées, détail avec la répartition par option (`count`, `stake_total`, `share_pct`) ou, pour nombre et date, une `distribution` en tranches, historique `prono_events`, événements `prono.created` et `prono.edited` ; dans `backend/src/sibylle/services/orgs.py`, créer la rubrique « Général » avec chaque nouvelle rédaction.
- [X] T066 [US2] Implémenter `backend/src/sibylle/services/bets.py` selon research.md R11 : verrou du prono puis du membre, contrôles de `domain/betting.py`, rang `bet_count + 1`, écriture `stake` au registre, mise à jour de `pot` et de `bet_count`, remplacement d'un pari de date « sans fin » (`superseded_at`, `superseded_by_id`), publication après validation de `bet.placed` sur `prono:<id>` (pari complet, `pot`, `bet_count` ; l'écran recharge le détail pour la répartition) et sur `org:<id>` (`prono_id`, `pot`, `bet_count`).
- [X] T067 [P] [US2] Implémenter `backend/src/sibylle/services/uploads.py` et `backend/src/sibylle/api/routes/uploads.py` (research.md R10) : `POST /orgs/{org}/uploads` (5 Mo au plus, sinon 413 `too_large`), réencodage Pillow en WebP de 1 200 px de côté au plus, sans métadonnées, nom aléatoire sous `UPLOAD_DIR` ; `GET /orgs/{org}/uploads/{id}` réservé aux membres, avec cache privé.
- [X] T068 [US2] Ajouter à `backend/src/sibylle/worker/jobs.py` la tâche minute `advance_pronos` : `scheduled` → `open` à `opens_at`, `open` → `closed` à `closes_at`, avec `prono_events` et l'événement `prono.state_changed` sur `org:` et `prono:`.
- [X] T069 [US2] Implémenter `backend/src/sibylle/api/routes/pronos.py` (`GET` et `POST /orgs/{org}/pronos`, `GET` et `PATCH /orgs/{org}/pronos/{id}`, `GET /orgs/{org}/sections`) et `backend/src/sibylle/api/routes/bets.py` (`POST /orgs/{org}/pronos/{id}/bets`), avec `PronoInput`, `PronoSummary`, `PronoDetail` et `Bet` de contracts/rest-api.md ; autoriser le sujet `prono:<id>` dans `backend/src/sibylle/realtime/ws.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [X] T070 [P] [US2] Écrire `frontend/src/features/pronos/CreatePronoPage.tsx` d'après G-Creer : puces de type CHOIX, OUI/NON, NOMBRE et DATE ; question ; rubrique ; choix ajoutables sans limite (100 au plus côté API) ; lien et image facultatifs (envoi par `POST /uploads`) ; ouverture programmée, clôture, résultat attendu et case « sans fin » pour le type date ; compteur « GAIN FIXE · MAX {plafond} » par pas de 5, borné au plafond de la rédaction.
- [X] T071 [P] [US2] Écrire `frontend/src/features/pronos/PronoPage.tsx` d'après B-Prono (mobile) et B-Web-Prono (ordinateur) : choix avec piles d'avatars et « +n », compteur de mise par pas de 10 entre 0 et le solde, « Cagnotte : {pot} lauriers » mise à jour pendant le réglage, bouton « MISE {n} » ou « SANS MISE », note « CHOIX DÉFINITIF · +{gain} DE BASE SI JUSTE », liste des paris (pseudo, choix, mise), règlement (clôture, résultat désigné par un·e journaliste, report, mise sans plafond perdue si l'on se trompe, gain fixe plus part de la cagnotte, cagnotte perdue si personne n'a vu juste), nouveau pari d'une date « sans fin » quand `can_rebet`, mises à jour par `useTopic("prono:<id>")` ; requêtes dans `frontend/src/features/pronos/api.ts`, styles dans `pronos.module.css`.
- [X] T072 [P] [US2] Écrire `frontend/src/features/pronos/PronoListPage.tsx` (onglet Pronos : ouverts, clos, résolus ; filtre par rubrique), avec cagnotte et nombre de paris mis à jour par `useTopic("org:<id>")`.
- [X] T073 [US2] Brancher les routes de US2 dans `frontend/src/app/router.tsx` (`/o/:orgId/pronos`, `/pronos/nouveau`, `/pronos/:pronoId`, bouton « Nouveau prono » dans `OrgLayout.tsx`) et ajouter les textes de `frontend/src/i18n/fr/pronos.json` ; dates saisies en heure de Paris (`fromParisInput`, `toParisInput` dans `frontend/src/i18n/index.ts`, test `frontend/tests/unit/paris.test.ts`).
- [X] T074 [US2] Écrire `frontend/tests/e2e/bet-live.spec.ts` (quickstart V2) : deux navigateurs, pari visible chez l'autre en moins de 2 s sans recharger, second pari et mise trop forte refusés, clôture après avance de l'horloge simulée ; mesurer aussi SC-001 (de l'ouverture du lien d'invitation au premier pari en moins de 2 minutes). Corrigé au passage : la transaction d'une requête est validée avant l'envoi de la réponse (`Depends(get_db, scope="function")` dans `backend/src/sibylle/api/deps.py`, test `backend/tests/integration/test_commit_before_response.py`) ; `SIBYLLE_WEB_PORT` change le port de l'interface pour Playwright.

**Checkpoint**: un prono se publie, se joue avec mise et se clôt tout seul ; tout se met à jour en direct.

---

## Phase 5: User Story 3 - Désigner le résultat et être payé (Priority: P1)

**Goal**: un·e journaliste désigne le résultat ; gain de base, bonus lève-tôt et part de cagnotte sont versés ; le résultat paraît dans une édition spéciale ; relance, signalement, correction et annulation fonctionnent.

**Independent Test**: reproduire l'exemple du cahier des charges (quatre membres misent 10, un seul voit juste) : il reçoit le gain de base plus 40 lauriers, les trois autres ont perdu 10, et le total versé depuis la cagnotte vaut exactement la cagnotte.

Le scénario 10 de spec.md (rappels de désignation) est livré avec US8.

### Tests for User Story 3 ⚠️

- [x] T075 [P] [US3] Écrire `backend/tests/unit/test_settlement.py` selon research.md J1 : gagnants des types choix et oui/non (réponse parmi les bonnes) ; gain de base `G` par gagnant ; lève-tôt `floor(G × p / 100)` pour un rang ≤ `N` ; cagnotte `P` = toutes les mises, mises remplacées comprises ; part `floor(P × s_i / S_W)`, le reste distribué « un laurier à la fois aux gagnants classés par mise décroissante puis par rang d'arrivée » ; cagnotte perdue sans gagnant ou quand `S_W = 0` ; écritures `base_gain`, `early_bird`, `pot_share` (score + (part − mise)) et `stake_lost` (score − mise) pour chaque perdant et chaque mise remplacée ; exemples de spec.md : quatre mises de 10, un gagnant, `G = 20` → + 20 et + 40, score + 50, perdants − 10 au score ; mises gagnantes de 30 et 10 sur une cagnotte de 100 → 75 et 25 ; lève-tôt de 20 % sur 20 → 4.
- [x] T076 [P] [US3] Écrire `backend/tests/unit/test_settlement_properties.py` (Hypothesis) : la somme des `pot_share` vaut `P` ou 0 ; aucune part ni aucun gain négatif ; régler puis corriger vers le même résultat laisse soldes et scores inchangés ; le résultat ne dépend pas de l'ordre de lecture des paris.
- [x] T077 [P] [US3] Écrire `backend/tests/unit/test_closest.py` : pour un nombre (`numeric(14,2)`) ou une date, gagnent les paris actifs dont l'écart à la valeur réelle est minimal, ex aequo compris ; une mise remplacée ne gagne jamais.
- [x] T078 [P] [US3] Écrire `backend/tests/contract/test_results.py` : `POST …/resolve` (journaliste ; état `closed`, ou `open` pour une date « sans fin » ; refusé sans aucun pari), `POST …/relaunch` (nouvelle `closes_at` future, paris et rangs conservés, `relaunch_count` + 1), `POST …/correct` et `POST …/cancel` (rédaction en chef seulement, 403 sinon ; une correction qui reprend des lauriers dépensés rend le solde négatif et empêche ensuite toute mise non nulle), `POST …/reports` (`kind` `result_error` ou `content`, message de 500 caractères au plus), `special_edition` dans `PronoDetail` ; un membre parti (`left`) est payé normalement ; 404 pour une autre rédaction.

### Implementation for User Story 3

- [x] T079 [US3] Ajouter à `backend/src/sibylle/db/models/pronos.py` les modèles `settlements` (`seq` 1, 2, … par prono ; `kind` ∈ `resolution`, `correction`, `cancellation` ; `result` jsonb ; `created_by` ; `reversed_by_id`) et `reports` (`kind` ∈ `result_error`, `content` ; `message` « ≤ 500 caractères » ; `state` ∈ `open`, `resolved`, `dismissed` ; `handled_by`, `handled_at`, `resolution_note`), avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_settlements_reports.py` et la clé étrangère `ledger_entries.settlement_id`.
- [x] T080 [US3] Implémenter `backend/src/sibylle/domain/settlement.py` et `backend/src/sibylle/domain/closest.py` (fonctions pures qui renvoient gagnants, versements et écritures à passer) pour faire passer T075, T076 et T077.
- [x] T081 [US3] Implémenter `backend/src/sibylle/services/results.py` : désignation (contrôle d'état, `is_correct` ou `result_number` / `result_date`, nouveau `settlements`, écritures passées par `services/ledger.py`, `outcome`, `payout` et `settled_at` des paris, `prono_events`, état `resolved`, événement `prono.resolved`), relance (état `open`, nouvelles `closes_at` et `result_expected_at`, `relaunch_count` + 1), correction (écritures `reversal` de tout le règlement précédent, `reversed_by_id`, puis nouveau règlement) et annulation (écritures `refund` de chaque mise, inverses d'un éventuel règlement, état `cancelled`).
- [x] T082 [US3] Implémenter `backend/src/sibylle/services/reports.py` (création d'un signalement, événement vers les rédactions en chef) et les routes `backend/src/sibylle/api/routes/results.py` (`resolve`, `relaunch`, `correct`, `cancel`) et `backend/src/sibylle/api/routes/reports.py` (`POST /orgs/{org}/pronos/{id}/reports`) ; ajouter `special_edition` (gagnants, versements, `pot_lost`, `settlement_seq`) à `PronoDetail` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T083 [P] [US3] Écrire `frontend/src/features/results/DesignatePanel.tsx` d'après G-Designer : cases carrées (`aria-pressed`) pour une ou plusieurs bonnes réponses, champ de valeur pour un nombre ou une date, « Tu es journaliste : coche la ou les bonnes réponses. », « +{G} LAURIERS CHACUN·E, PLUS UNE PART DES {P} LAURIERS DE LA CAGNOTTE », relance avec une nouvelle date ; pour la rédaction en chef, correction et annulation avec confirmation.
- [x] T084 [P] [US3] Écrire `frontend/src/features/results/SpecialEdition.tsx` d'après G-Resultat : gain du membre (par exemple « +47 » et « 15 DE BASE + 32 DE CAGNOTTE »), gagnants, « cagnotte perdue » s'il y a lieu, bouton « Signaler une erreur » (type et message de 500 caractères au plus) ; ne pas reprendre la ligne « SÉRIE » de la maquette, absente de la spec.
- [x] T085 [US3] Afficher `DesignatePanel` et `SpecialEdition` dans `frontend/src/features/pronos/PronoPage.tsx` selon l'état et le rôle, ajouter `frontend/src/i18n/fr/results.json`, et compléter `sibylle seed-demo` (`backend/src/sibylle/cli.py`) avec des pronos ouverts, clos, résolus, relancés et annulés.
- [x] T086 [US3] Écrire `frontend/tests/e2e/resolve-payout.spec.ts` (quickstart V3 et V4) : exemple du cahier des charges, bonus lève-tôt, correction (la somme des parts reste 40), annulation (mises rendues), relance d'un prono sans pari, nouveau pari sur une date « sans fin ».

**Checkpoint**: MVP jouable : rejoindre, parier, désigner, être payé (quickstart V1 à V4).

---

## Phase 6: User Story 4 - Classements, saisons et trophées (Priority: P2)

**Goal**: deux classements (lauriers, pronos gagnés) sur trois périodes (mois, saison, depuis toujours) ; à la fin de chaque saison, trophées gravés, cadre doré pour le podium et remise au solde de départ.

**Independent Test**: avec des paris réglés sur deux mois et une fin de saison simulée, vérifier les six classements, les trophées, les cadres dorés et la remise au solde de départ.

### Tests for User Story 4 ⚠️

- [x] T087 [P] [US4] Écrire `backend/tests/unit/test_leaderboard.py` : score du mois = somme des `score_delta` du mois (heure de Paris) ; score de saison ; « depuis toujours » = scores gravés sur les trophées + score de la saison en cours ; pronos gagnés = paris `won` réglés dans la période ; égalités au même rang, rang suivant sauté (1, 1, 3) ; membres `left` et `anonymized` absents ; un achat ne change pas le score.
- [x] T088 [P] [US4] Écrire `backend/tests/integration/test_season_close.py` : à la fin de la saison, un trophée (score, rang, `podium` si rang ≤ 3) pour chaque membre qui a placé au moins un pari dans la saison ; écriture `season_reset` vers le solde de départ pour tous les membres `active` et `left` ; `season_score` remis à 0 ; une seconde exécution ne fait rien (`season_closures`) ; un prono misé en saison A et réglé en saison B compte en B.
- [x] T089 [P] [US4] Écrire `backend/tests/contract/test_leaderboard.py` : `GET /orgs/{org}/leaderboard?metric=laurels|wins&period=month|season|all_time` (`rows` avec `rank`, `member`, `value`, `is_me`) et `GET /orgs/{org}/seasons/current` ; 404 pour une autre rédaction.

### Implementation for User Story 4

- [x] T090 [US4] Ajouter à `backend/src/sibylle/db/models/seasons.py` `season_closures` (PK `org_id`, `season_id` ; `closed_at`) et `trophies` (`score`, `rank`, `podium`, unique (`membership_id`, `season_id`)), avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_trophies.py`.
- [x] T091 [US4] Implémenter `backend/src/sibylle/domain/leaderboard.py` (rangs à égalité) pour faire passer T087, et `backend/src/sibylle/services/leaderboard.py` (agrégats SQL sur `ledger_entries`, `bets` et `trophies`).
- [x] T092 [US4] Implémenter `backend/src/sibylle/services/seasons.py` : clôture d'une saison pour une rédaction en une transaction (trophées, `season_reset`, `season_score` à 0, ligne `season_closures`), ajout automatique des saisons suivantes à la table `seasons`, tâche quotidienne `close_finished_seasons` à 00:00 (Paris) dans `backend/src/sibylle/worker/jobs.py`, événement `season.closed`.
- [x] T093 [US4] Implémenter `backend/src/sibylle/api/routes/leaderboard.py` (contrat de T089) et publier `leaderboard.changed` après chaque règlement dans `backend/src/sibylle/services/results.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T094 [P] [US4] Écrire `frontend/src/features/leaderboard/LeaderboardPage.tsx` d'après G-Classement : bascule Lauriers / Pronos gagnés, périodes Mois / Saison / Depuis toujours, ligne « toi » sur fond gris clair, rechargement sur `leaderboard.changed` et `season.closed`.
- [x] T095 [US4] Brancher la route dans `frontend/src/app/router.tsx`, ajouter `frontend/src/i18n/fr/leaderboard.json` et écrire `frontend/tests/e2e/season.spec.ts` (quickstart V5, horloge simulée au 21 décembre 2026 à 00:00:30, heure de Paris).

**Checkpoint**: classements justes et clôture de saison idempotente.

---

## Phase 7: User Story 5 - La une et la vie de la rédaction (Priority: P2)

**Goal**: la une complète dans l'ordre prévu, propositions des lecteur·rice·s validées par les journalistes, réactions rapides.

**Independent Test**: avec des pronos dans plusieurs états, vérifier l'ordre de la une pour un·e lecteur·rice et pour un·e journaliste, faire proposer puis valider un prono, ajouter puis retirer une réaction.

### Tests for User Story 5 ⚠️

- [x] T096 [P] [US5] Écrire `backend/tests/contract/test_front_page.py` (`GET /orgs/{org}/front-page` renvoie `headline`, le prono ouvert dont la clôture est la plus proche, puis `open`, `to_designate` réservé aux journalistes, `latest_results`, `leaderboard_top`, `games` et `editor_note`) et `backend/tests/contract/test_proposals_reactions.py` (un·e lecteur·rice crée un prono `proposed`, visible seulement de son auteur·rice et des journalistes ; `validate` avec gain ajustable sous le plafond ; `reject` avec motif ; `PUT` puis `DELETE …/reactions/{kind}` ; type de réaction inconnu → 422).

### Implementation for User Story 5

- [x] T097 [US5] Ajouter le modèle `reactions` (PK `prono_id`, `membership_id`, `kind` ; `created_at`) à `backend/src/sibylle/db/models/pronos.py`, avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_reactions.py`, et le jeu fixe de réactions à `backend/src/sibylle/domain/content.py` : `bien_vu` (« Bien vu »), `rire` (« Ha ha »), `choc` (« Oh ! »), `bravo` (« Bravo »), `doute` (« Hmm »).
- [x] T098 [US5] Dans `backend/src/sibylle/services/pronos.py` et `backend/src/sibylle/api/routes/pronos.py` : un·e lecteur·rice crée un prono `proposed` (au lieu du 403 de US2) ; `POST …/validate` (journaliste ; gain ajustable ; état `scheduled` ou `open`) ; `POST …/reject` (état `rejected`, motif, auteur·rice informé·e) ; visibilité restreinte dans les listes et le détail ; événement `prono.created` limité aux journalistes et à l'auteur·rice.
- [x] T099 [US5] Implémenter les réactions (`PUT` et `DELETE /orgs/{org}/pronos/{id}/reactions/{kind}`, événement `reaction.changed`) dans `backend/src/sibylle/services/pronos.py`, puis `backend/src/sibylle/services/front_page.py` et la route `backend/src/sibylle/api/routes/front_page.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T100 [P] [US5] Réécrire `frontend/src/features/une/UnePage.tsx` d'après B-Accueil (mobile) et B-Web-Accueil (ordinateur) : prono à la une avec la ligne « CLÔTURE {jour heure} · {n} PRONOS · CAGNOTTE {pot} », autres pronos ouverts, pronos à désigner (journalistes), derniers résultats, haut du classement, emplacement « Jeux de la semaine » (rempli par US9 et US10), mot de la rédaction en chef ; mises à jour par `useTopic("org:<id>")`.
- [x] T101 [P] [US5] Ajouter le bouton « Proposer » des lecteur·rice·s à `frontend/src/features/pronos/CreatePronoPage.tsx` et écrire `frontend/src/features/pronos/ProposalsPanel.tsx` pour les journalistes (propositions en attente, validation avec gain ajustable, refus avec motif).
- [x] T102 [P] [US5] Écrire `frontend/src/features/pronos/ReactionBar.tsx` et une icône de 16×16 en pixel art par réaction dans `frontend/src/ui/reactions/`, avec compteurs mis à jour par `reaction.changed` et retrait au second appui.
- [x] T103 [US5] Intégrer `ReactionBar` et `ProposalsPanel` dans `frontend/src/features/pronos/PronoPage.tsx` et `frontend/src/features/une/UnePage.tsx`, brancher les routes et ajouter `frontend/src/i18n/fr/une.json`.

**Checkpoint**: la une suit l'ordre de la spec ; les propositions et les réactions marchent.

---

## Phase 8: User Story 6 - Régler sa rédaction (Priority: P2)

**Goal**: la rédaction en chef règle la carte et les lauriers, gère membres, rôles, invitations et code d'accès, ajuste les lauriers d'un membre et traite les signalements.

**Independent Test**: changer chaque réglage avec le compte de la rédaction en chef et vérifier son effet ; les mêmes actions sont refusées à un·e journaliste et à un·e lecteur·rice.

### Tests for User Story 6 ⚠️

- [x] T104 [P] [US6] Écrire `backend/tests/contract/test_org_admin.py` : `PATCH /orgs/{org}` (titre « 1 à 40 caractères », `starting_balance` « ≥ 0 », `max_base_gain` « ≥ 0 », `early_bird_pct` « 0 à 100 », `early_bird_count` « ≥ 0 », fond connu, logo PixelImage valide, mot de la rédaction en chef, charte ; un plafond abaissé à 30 refuse ensuite un prono à 40) ; `POST` puis `DELETE /orgs/{org}/access-code` (l'ancien code est refusé) ; `GET` et `DELETE /orgs/{org}/invitations/{id}` ; `PATCH …/members/{member}/role` (`last_editor` quand on retire la dernière rédaction en chef) ; `DELETE …/members/{member}` ; `POST …/members/{member}/adjustments` (montant non nul, motif obligatoire, solde changé, score inchangé) ; `GET …/members/me/ledger` (paginé) ; rubriques `POST`, `PATCH`, `DELETE` (archivage si utilisée) ; `GET /orgs/{org}/reports?state=open` et `POST …/reports/{id}/handle` ; ces routes répondent 403 à `journalist` et à `reader`, sauf le relevé, que chaque membre lit pour lui-même.

### Implementation for User Story 6

- [x] T105 [US6] Compléter `backend/src/sibylle/services/orgs.py` (carte et réglages, code d'accès régénéré ou désactivé, changement de rôle avec la garde « au moins une rédaction en chef active » et l'événement `member.updated`, retrait d'un membre avec `status = left`, désabonnement temps réel et `member.left`, ajustements par écriture `adjustment` avec motif, rubriques : création, renommage, ordre, archivage) et `backend/src/sibylle/services/reports.py` (liste, traitement en `resolved` ou `dismissed` avec note, auteur·rice informé·e).
- [x] T106 [US6] Implémenter les routes correspondantes dans `backend/src/sibylle/api/routes/orgs.py`, `members.py`, `invitations.py` et `reports.py`, plus `GET /orgs/{org}/members/me/ledger` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T107 [P] [US6] Écrire `frontend/src/features/admin/OrgSettingsPage.tsx` d'après G-Orga, réservé à la rédaction en chef : carte (logo en pixel art, fond parmi la liste, titre), « Gain fixe maximum » (« CHOISI À LA CRÉATION DE CHAQUE PRONO », pas de 5), « Solde de départ » (« À L'ARRIVÉE ET À CHAQUE SAISON », pas de 10), « Bonus lève-tôt » (pourcentage par pas de 5 et nombre de premiers joueurs), mot de la rédaction en chef, charte et rubriques.
- [x] T108 [P] [US6] Écrire `frontend/src/features/admin/MembersPage.tsx` (membres, rôles, retrait, ajustement de lauriers avec motif, invitations en cours et révocation, code d'accès régénéré ou désactivé, en réutilisant `InvitePanel.tsx`) et `frontend/src/features/admin/ReportsPage.tsx` (signalements ouverts, lien vers le prono, correction ou rejet avec note).
- [x] T109 [US6] Brancher les écrans d'administration, visibles seulement de la rédaction en chef, dans `frontend/src/app/router.tsx` et `frontend/src/app/AppShell.tsx`, et ajouter `frontend/src/i18n/fr/admin.json`.

**Checkpoint**: chaque réglage marche pour la rédaction en chef et reste refusé aux autres rôles.

---

## Phase 9: User Story 7 - Carte de presse, avatar et collection (Priority: P3)

**Goal**: la carte de presse avec ses statistiques et sa collection, l'éditeur pixel art, les achats avec les lauriers et les codes secrets.

**Independent Test**: dessiner et enregistrer un avatar, acheter une couleur puis une boule, et vérifier le solde, le score inchangé, le relevé et l'avatar partout où apparaît le pseudo.

### Tests for User Story 7 ⚠️

- [x] T110 [P] [US7] Écrire `backend/tests/contract/test_profile_collection.py` : `GET /orgs/{org}/members/{member}` → `PressCard` (pseudo, avatar, cadre, rôle, arrivée, lauriers, pronos joués, taux de réussite = gagnés / réglés, trophées, collection) ; `PATCH …/members/me` avec une couleur non débloquée → 422 ; `GET /orgs/{org}/catalog` (avec `owned`) ; `POST …/catalog/{item}/purchase` (solde − prix, score inchangé, `insufficient_balance`, objet déjà possédé refusé) ; `POST …/secret-codes/redeem` (une seule fois par membre, code inconnu refusé, 429 après 5 essais par heure).

### Implementation for User Story 7

- [x] T111 [US7] Créer `backend/src/sibylle/db/models/collection.py` (`catalog_items` : `kind` ∈ `ball`, `color`, `frame`, `key` unique, `name_key`, `price` « NULL si non achetable », `season`, `data`, `active` ; `owned_items` : `source` ∈ `purchase`, `secret_code`, unique (`membership_id`, `item_id`) ; `secret_codes` : `code_hash` unique, `item_id`, `active` ; `secret_code_redemptions` : unique (`secret_code_id`, `membership_id`)) et la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_collection.py`, qui insère le catalogue : boules `spring`, `summer`, `autumn` et `winter` du kit (achetables), les 16 couleurs débloquables (indices 33 à 48 de `domain/pixels.py`), quelques cadres, les variantes de fêtes du kit (`halloween`, `christmas`, `new-year`, `bastille-day`…) et les couleurs rares (indices 49 à 52) réservées aux codes secrets ; prix proposés, à faire valider : couleur 40, cadre 60, boule 80.
- [x] T112 [US7] Implémenter `backend/src/sibylle/services/collection.py` : catalogue avec `owned`, achat (verrou du membre, écriture `purchase`, `owned_items`), code secret (empreinte, une fois par membre, limité en débit), couleurs débloquées transmises à la validation des avatars, statistiques et trophées de la carte de presse, numéro de carte = rang d'arrivée dans la rédaction, sur 4 chiffres.
- [x] T113 [US7] Implémenter `backend/src/sibylle/api/routes/profile.py` (`GET /orgs/{org}/members/{member}` en `PressCard`), `backend/src/sibylle/api/routes/collection.py` (`catalog`, `purchase`, `secret-codes/redeem`) et la commande `sibylle secret-code add <code> <item_key>` dans `backend/src/sibylle/cli.py` (les codes ne sont jamais écrits dans le dépôt) ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T114 [P] [US7] Écrire `frontend/src/features/profile/PressCardPage.tsx` d'après B-Profil et B-Web-Profil (« Carte de presse », « CARTE DE PRESSE N° {numéro} », pseudo, « MEMBRE DEPUIS {mois année} », statistiques, collection avec trophées gravés et cadre doré pour le podium) et `frontend/src/features/profile/LedgerList.tsx` (relevé avec motifs).
- [x] T115 [P] [US7] Écrire `frontend/src/features/pixel-editor/PixelEditor.tsx` d'après G-Pixel : grille de 16×16 ou 32×32, palette de base et couleurs débloquées, crayon, gomme, remplissage, annulation, aperçu à l'échelle entière, utilisable au clavier (flèches, espace) ; enregistrement par `PATCH …/members/me` ; réutilisable pour le logo de la rédaction et Pixel mystère ; test `frontend/tests/unit/pixel-editor.test.ts` (aller-retour de l'encodage base64).
- [x] T116 [P] [US7] Écrire `frontend/src/features/collection/CollectionPage.tsx` : couleurs, cadres et boules (dessinées par `frontend/src/ui/CrystalBall.tsx` avec la variante du kit), achat avec confirmation, saisie d'un code secret.
- [x] T117 [US7] Brancher les routes, activer « Dessiner le mien » dans `frontend/src/features/orgs/JoinPage.tsx` et l'édition du logo dans `frontend/src/features/admin/OrgSettingsPage.tsx`, et ajouter `frontend/src/i18n/fr/profile.json`.

**Checkpoint**: carte de presse, éditeur et collection marchent ; les achats ne touchent que le solde.

---

## Phase 9b: Évolution de US7 - Pièces et conversion du lundi

**Goal**: séparer les lauriers (miser, se classer) des pièces (acheter) : chaque lundi, les lauriers en or deviennent autant de pièces, une fenêtre l'annonce, et la collection se paie en pièces (spec FR-094 à FR-096, research.md J6).

**Independent Test**: avec l'horloge simulée, passer un lundi, vérifier les pièces reçues (solde plus mises en jeu), les lauriers inchangés, la fenêtre « Bonne nouvelle » une seule fois, puis un achat en pièces.

- [x] T152 [US7] Écrire `backend/tests/unit/test_coins.py` (lundi de la semaine en heure de Paris, montant = lauriers en or ou 0) et `backend/tests/contract/test_coins.py` : conversion d'un membre avec un pari en jeu (solde + mise), lauriers inchangés, une seule fois par semaine même lancée deux fois, rien pour un membre arrivé après le lundi 00:00 ni pour un membre parti ; `GET /orgs/{org}/coins/weekly` puis `POST …/coins/weekly/seen` ; `gold` et `coins` dans `MemberSelf` ; achat payé en pièces (`insufficient_coins`, lauriers et score inchangés) ; ajuster `backend/tests/contract/test_profile_collection.py`.
- [x] T153 [US7] Créer `coin_entries` (`kind` ∈ `weekly`, `purchase` ; unique (`membership_id`, `week_start`) ; en ajout seulement, comme `ledger_entries`), `memberships.coins` (≥ 0) et `memberships.coins_seen_week` dans `backend/src/sibylle/db/models/coins.py` et `orgs.py`, avec la révision Alembic `backend/src/sibylle/db/migrations/versions/0011_coins.py`, qui multiplie aussi les prix du catalogue par 10 (couleur 400, cadre 600, boule 800).
- [x] T154 [US7] Implémenter `backend/src/sibylle/services/coins.py` (lauriers en or, écriture de pièces avec mise à jour du cache, conversion de la semaine avec `SKIP LOCKED` et événement `coins.granted`, conversion à annoncer, annonce vue), la tâche minute `grant_weekly_coins` dans `backend/src/sibylle/worker/jobs.py` (avec `sibylle coins grant --org` pour les tests sur une base partagée, et la conversion de la semaine dans `seed-demo`), l'achat en pièces dans `backend/src/sibylle/services/collection.py`, `gold` et `coins` dans `MemberSelf`, et les routes de `backend/src/sibylle/api/routes/coins.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T155 [P] [US7] Dessiner le laurier vert et la pièce (`frontend/src/ui/assets/laurel-green.png`, `coin.png`, 16×16), ajouter `Laurel tone="green"`, `Coins` et `Wallet` (les trois compteurs) à `frontend/src/ui/components.tsx`, et afficher lauriers verts, lauriers en or et pièces dans l'en-tête (`frontend/src/app/OrgLayout.tsx`), sur la une et sur l'écran du prono (mise : lauriers verts).
- [x] T156 [P] [US7] Écrire `frontend/src/features/coins/WeeklyCoinsDialog.tsx` (fenêtre « Bonne nouvelle » : lauriers en or convertis, pièces reçues, lien vers la collection ; fermée, elle appelle `…/coins/weekly/seen`), l'ouvrir depuis `OrgLayout` et sur `coins.granted`, passer `frontend/src/features/collection/CollectionPage.tsx` aux pièces, et ajouter `frontend/src/i18n/fr/coins.json`.
- [x] T157 [US7] Écrire `frontend/tests/e2e/coins.spec.ts` : avancer l'horloge jusqu'au lundi, voir la fenêtre une seule fois (en direct puis plus au rechargement), aller à la collection en pièces ; passer l'achat de `frontend/tests/e2e/profile.spec.ts` aux pièces.

**Checkpoint**: les lauriers ne servent plus qu'à miser et à se classer ; la collection se paie en pièces.

---

## Phase 10: User Story 8 - Être prévenu (Priority: P3)

**Goal**: notifications push (appli installée) et e-mails pour quatre événements, réglables type par type et canal par canal.

**Independent Test**: s'abonner aux notifications push sur un appareil, déclencher chacun des quatre événements et vérifier la réception push et e-mail, puis couper un type et vérifier qu'il n'arrive plus.

### Tests for User Story 8 ⚠️

- [x] T118 [P] [US8] Écrire `backend/tests/integration/test_notifications.py` (contracts/notifications.md) : `new_prono` au passage à `open`, pour tous les membres actifs sauf le créateur ; `closing_soon` à la clôture moins 2 h, seulement sans pari actif, jamais pour une date « sans fin » ; `result` à chaque règlement, pour ceux qui ont parié ; `designation_reminder` au créateur journaliste, ou au ou à la journaliste qui a validé la proposition, à la date de résultat attendu (sinon le lendemain de la clôture), puis à J+1, J+3, J+7, puis chaque semaine, jusqu'à la désignation, la relance ou l'annulation ; une seule ligne par `dedupe_key`, même si le `worker` tourne deux fois ; préférences par type et par canal ; aucun e-mail de notification sans adresse vérifiée ; état `skipped` quand la notification n'a plus d'objet ; abonnement push qui répond 410 supprimé.

### Implementation for User Story 8

- [x] T119 [US8] Ajouter `notification_prefs` (PK `account_id`, `type`, `channel` ; `enabled`, vrai par défaut) et `push_subscriptions` (`endpoint` unique, `p256dh`, `auth`, `user_agent`, `created_at`, `last_success_at`) à `backend/src/sibylle/db/models/notifications.py`, avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_push.py`.
- [x] T120 [US8] Implémenter `backend/src/sibylle/notify/push.py` (pywebpush, VAPID, `TTL` de 12 h, urgence `high` pour `closing_soon`, charge `{type, title, body, url, tag, icon}` de contracts/notifications.md), le choix des canaux selon `notification_prefs` dans `dispatch_notifications` (`backend/src/sibylle/worker/jobs.py`), et les e-mails `new_prono`, `closing_soon`, `result` et `designation_reminder` dans `backend/src/sibylle/notify/templates/fr/`, avec les objets de contracts/notifications.md et un lien vers les préférences.
- [x] T121 [US8] Mettre en file `new_prono` au passage à `open` (`backend/src/sibylle/services/pronos.py` et tâche `advance_pronos`) et `result` dans `backend/src/sibylle/services/results.py`, et ajouter les tâches minute `closing_soon_alerts` et `designation_reminders` à `backend/src/sibylle/worker/jobs.py`.
- [x] T122 [US8] Implémenter `backend/src/sibylle/api/routes/notifications.py` (`GET` et `PUT /me/notification-prefs`, `GET /push/vapid-public-key`, `POST` et `DELETE /me/push-subscriptions`) et la commande `sibylle gen-secrets` (clés VAPID et mot de passe PostgreSQL) dans `backend/src/sibylle/cli.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T123 [P] [US8] Ajouter à `frontend/src/sw.ts` les gestionnaires `push` (titre, texte, icône, `tag`) et `notificationclick` (ouvre l'appli sur `url` ou la met au premier plan), et écrire `frontend/src/features/notifications/usePush.ts` (permission demandée sur un clic, abonnement envoyé au serveur, explication pour l'iPhone : iOS 16.4 ou plus et appli ajoutée à l'écran d'accueil).
- [x] T124 [P] [US8] Écrire `frontend/src/features/notifications/NotificationPrefs.tsx` : quatre types × deux canaux (push, e-mail), avec l'état de l'abonnement push de l'appareil.
- [x] T125 [US8] Afficher `NotificationPrefs` dans le profil (déplacé ensuite dans les réglages du compte `/compte` par T133, avec un lien depuis la carte de presse), proposer d'activer les notifications après le premier pari dans `frontend/src/features/pronos/PronoPage.tsx`, et ajouter `frontend/src/i18n/fr/notifications.json`.

**Checkpoint**: les quatre notifications arrivent par push et par e-mail, chacune une seule fois, selon les préférences.

---

## Phase 11: User Story 9 - Course de la boule (Priority: P3)

**Goal**: le mini-jeu de saut d'obstacles, 5 essais par semaine, avec les gains du classement hebdomadaire.

**Independent Test**: jouer 5 parties, vérifier qu'une 6ᵉ est refusée et que seul le meilleur score s'affiche, puis simuler la fin de semaine et vérifier les lauriers versés.

### Tests for User Story 9 ⚠️

- [x] T126 [P] [US9] Écrire `backend/tests/unit/test_runner.py` (research.md J3 et R19 : semaine du lundi 00:00 au dimanche 23:59:59, heure de Paris ; 5 essais par membre ; meilleur score retenu ; gains de 10, 7 et 5 aux trois premiers et de 2 aux autres joueurs ; égalité départagée par la partie la plus ancienne ; refus d'une partie de plus de 30 minutes ou d'un score supérieur au maximum atteignable pour sa durée) et `backend/tests/contract/test_runner.py` (`GET /orgs/{org}/games` ; `POST …/games/runner/runs` avec `attempts_exhausted` au 6ᵉ essai ; `POST …/runs/{run}/finish` avec 422 si le score est invraisemblable et refus d'une partie déjà terminée ; paiement hebdomadaire idempotent, versé au solde seulement).

### Implementation for User Story 9

- [x] T127 [US9] Créer `backend/src/sibylle/db/models/minigames.py` (`runner_runs` : `org_id`, `membership_id`, `week_start`, `seed`, `started_at`, `finished_at`, `score`, `duration_ms` ; `minigame_payouts` : PK `org_id`, `game`, `period_key`, `paid_at`) et la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_runner.py`.
- [x] T128 [US9] Implémenter la partie course de `backend/src/sibylle/domain/minigames.py` (pour faire passer T126) et de `backend/src/sibylle/services/minigames.py` (ouvrir et terminer une partie, classement de la semaine, gains par écriture `minigame`), la tâche du lundi 00:00 `pay_runner_week` dans `backend/src/sibylle/worker/jobs.py`, les routes de `backend/src/sibylle/api/routes/minigames.py` et l'événement `games.runner.updated` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T129 [P] [US9] Écrire `frontend/src/features/games/runner/RunnerGame.tsx` : canvas à 60 images par seconde, la boule du kit qui saute (espace, flèche du haut, toucher), obstacles tirés de la graine donnée par le serveur, vitesse croissante, score ; version sobre quand « couper les animations » est actif ; partie ouverte et terminée par l'API.
- [x] T130 [US9] Écrire `frontend/src/features/games/WeeklyGames.tsx` (encadré « Jeux de la semaine » de B-Accueil et B-Web-Accueil : « Course de la boule », « RECORD {n} · {k} ESSAIS SUR 5 »), le placer dans `frontend/src/features/une/UnePage.tsx` et ajouter `frontend/src/i18n/fr/games.json`.

**Checkpoint**: la course se joue depuis la une ; la semaine paie une seule fois.

---

## Phase 12: User Story 11 - Mes données et mes préférences (Priority: P3)

**Goal**: thème, animations, export des données, suppression du compte en un clic, départ d'une rédaction.

**Independent Test**: exporter les données d'un compte actif, puis le supprimer et vérifier que son e-mail, ses nom et prénom ont disparu et que ses anciens paris apparaissent sous « Ancien membre ».

### Tests for User Story 11 ⚠️

- [x] T131 [P] [US11] Écrire `backend/tests/contract/test_data_rights.py` : `GET /me/export` (compte, rédactions, paris, relevés de lauriers et de pièces, collections) ; `DELETE /me` avec `confirm: true` (e-mail, nom, prénom, mot de passe, sessions, abonnements push et préférences effacés ; chaque membre passe en `anonymized` avec le pseudo « Ancien membre » et l'avatar par défaut ; paris et registre conservés ; connexion impossible ensuite) ; `last_editor` pour la seule rédaction en chef d'une rédaction qui a d'autres membres ; rédaction supprimée quand son seul membre supprime son compte ; `DELETE /orgs/{org}/members/me` (quitter ; `last_editor`).

### Implementation for User Story 11

- [x] T132 [US11] Implémenter `backend/src/sibylle/services/export.py` (export JSON), la suppression avec anonymisation et le départ d'une rédaction dans `backend/src/sibylle/services/accounts.py` (research.md R20), et les routes `GET /me/export`, `DELETE /me` et `DELETE /orgs/{org}/members/me` dans `backend/src/sibylle/api/routes/me.py` et `backend/src/sibylle/api/routes/members.py` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T133 [P] [US11] Écrire `frontend/src/features/settings/SettingsPage.tsx` : thème clair, sombre ou automatique et « couper les animations » (enregistrés par `PATCH /me` et appliqués tout de suite), notifications (US8), quitter une rédaction, exporter mes données (téléchargement du fichier), supprimer mon compte (confirmation), message « nomme d'abord une autre rédaction en chef » sur `last_editor`.
- [x] T134 [US11] Brancher la route, ajouter `frontend/src/i18n/fr/settings.json` et écrire `frontend/tests/e2e/data-rights.spec.ts` (quickstart V10, points 1 à 3).

**Checkpoint**: export, suppression et départ respectent le principe I sans casser l'historique des autres.

---

## Phase 13: User Story 10 - Pixel mystère (Priority: P4)

**Goal**: un dessin en pixel art se dévoile chaque jour ; les premiers à trouver le mot gagnent des lauriers.

**Independent Test**: lancer un dessin, faire deviner plusieurs membres dans un ordre donné et vérifier les gains, puis vérifier la fin du jeu dans les deux cas.

### Tests for User Story 10 ⚠️

- [x] T135 [P] [US10] Écrire `backend/tests/unit/test_pixel_mystere.py` (research.md J4 : ordre de révélation tiré au hasard à la création ; `ceil(nombre de pixels / 7)` pixels par jour à 08:00, heure de Paris, premier lot à l'ouverture ; comparaison qui ignore majuscules, accents et espaces en trop ; 3 essais par jour et par membre ; gains de 10, 7, 5 puis 3 par ordre d'arrivée ; l'auteur·rice ne joue pas ; fin quand tous les autres membres actifs ont trouvé ou quand tous les pixels sont dévoilés ; dessin suivant le lendemain à 08:00) et `backend/tests/contract/test_pixel_mystere.py` (`GET /orgs/{org}/games/pixel` masque les pixels non dévoilés et ne donne `word` qu'à qui a trouvé ou à la fin ; `POST …/pixel/guesses` ; `GET` et `POST …/pixel/puzzles` réservés aux journalistes).

### Implementation for User Story 10

- [x] T136 [US10] Ajouter à `backend/src/sibylle/db/models/minigames.py` `pixel_puzzles` (`drawing` PixelImage, `word`, `word_normalized`, `reveal_order` bytea, `revealed_count`, `state` ∈ `queued`, `active`, `finished`, au plus un `active` par rédaction par index unique partiel), `pixel_guesses` (au plus 3 par puzzle, membre et jour) et `pixel_finds` (unique (`puzzle_id`, `membership_id`), `rank`, `laurels`), avec la révision Alembic `backend/src/sibylle/db/migrations/versions/<rev>_pixel_mystere.py`.
- [x] T137 [US10] Implémenter la partie Pixel mystère de `backend/src/sibylle/domain/minigames.py` (pour faire passer T135) et de `backend/src/sibylle/services/minigames.py` (file des dessins, activation, révélations, essais, gains par écriture `minigame`, fin du jeu), la tâche quotidienne de 08:00 `reveal_pixel_puzzles` dans `backend/src/sibylle/worker/jobs.py`, les routes de `backend/src/sibylle/api/routes/minigames.py` et les événements `games.pixel.revealed`, `games.pixel.found` et `games.pixel.finished` ; régénérer `frontend/src/api/schema.d.ts`.
- [x] T138 [P] [US10] Écrire `frontend/src/features/games/pixel-mystere/PixelMysterePage.tsx` (dessin en partie dévoilé, nombre de lettres, essais restants, ordre des trouveurs, mot donné à la fin) et le dépôt d'un dessin par un·e journaliste avec `frontend/src/features/pixel-editor/PixelEditor.tsx`.
- [x] T139 [US10] Ajouter la carte Pixel mystère à `frontend/src/features/games/WeeklyGames.tsx` (« UN MOT DE {n} LETTRES · LANCÉ PAR LA RÉDACTION »), brancher les routes et écrire `frontend/tests/e2e/games.spec.ts` (quickstart V9).

**Checkpoint**: Pixel mystère se joue depuis la une et se termine dans les deux cas prévus.

---

## Phase 14: Polish & Cross-Cutting Concerns

**Purpose**: mise en ligne, sécurité, accessibilité, performance et répétition générale.

- [ ] T140 [P] Écrire `backend/Dockerfile` (Python 3.14 slim, uv, utilisateur non root, commande `sibylle`) et `deploy/nginx/Dockerfile` (construction de l'interface avec Node, puis image nginx stable sur Alpine qui sert `frontend/dist`, avec openssl pour le certificat provisoire).
- [ ] T141 Ajouter à `deploy/docker-compose.yml` les services `nginx` (ports 80 et 443 publiés sur `127.0.0.1` seulement, où frpc les atteint), `certbot` (`certonly --webroot --keep-until-expiring` au démarrage puis toutes les 12 h), `api` (uvicorn, un seul processus, migrations Alembic au démarrage, `FORWARDED_ALLOW_IPS=*` pour lire l'IP du visiteur dans `X-Forwarded-For` posé par nginx, sans aucun port publié puisque seul nginx doit l'atteindre ; sinon toutes les requêtes semblent venir de nginx et partagent une même limite de débit par IP), `worker` et `backup`, avec contrôles de santé et volumes `uploads`, `letsencrypt` et `acme_webroot`.
- [ ] T142 [P] Écrire `deploy/nginx/sibylle.conf.template` (le domaine remplacé par envsubst au démarrage de l'image officielle) : `listen 80 proxy_protocol` et `listen 443 ssl proxy_protocol` avec `http2 on`, sans HTTP/3 puisque les tunnels ne portent que TCP ; sur le port 80, `/.well-known/acme-challenge/` servi depuis le dossier partagé avec certbot et redirection vers HTTPS pour le reste ; certificat lu dans `/etc/letsencrypt/live/<domaine>/`, avec un certificat autosigné provisoire tant que certbot n'en a pas obtenu et un rechargement de nginx quand le certificat change ; `/api/` (dont `/api/ws`, avec `Upgrade` et `Connection`) vers `api:8000` avec `X-Forwarded-For $proxy_protocol_addr` et un `client_max_body_size` au-dessus des 5 Mo des images ; fichiers de l'interface avec `try_files $uri /index.html`, `/assets/` en cache immuable et le reste en `no-cache` ; aucun journal d'accès ; un écouteur interne sans PROXY protocol pour le contrôle de santé du conteneur ; en-têtes de research.md R15 posés avec `add_header … always` dans chaque `location` (`Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; connect-src 'self' wss://<domaine>; style-src 'self'; font-src 'self'; frame-ancestors 'none'`, HSTS, `Referrer-Policy: no-referrer`, `Permissions-Policy` restrictive).
- [ ] T143 [P] Écrire `deploy/frpc.toml.example` : deux proxys TCP (80 et 443) vers nginx avec `transport.proxyProtocolVersion = "v2"`, sans aucun secret réel.
- [ ] T144 [P] Écrire `deploy/backup/backup.sh` (pg_dump au format personnalisé et archive des images, 14 jours gardés, copie chiffrée avec age vers le VPS) et `deploy/backup/restore.sh`.
- [ ] T145 Écrire `deploy/README.md` : enregistrements DNS A et AAAA vers le VPS, SPF, DKIM et DMARC de Brevo, frps existant, premier démarrage, `sibylle gen-secrets`, sauvegarde et restauration testée.
- [ ] T146 [P] Ajouter à `backend/src/sibylle/worker/jobs.py` la tâche nocturne `check_ledger_caches`, qui compare `balance` et `season_score` aux sommes du registre, et `coins` à celle de `coin_entries`, pour chaque rédaction et journalise tout écart.
- [ ] T147 [P] Écrire `frontend/tests/e2e/a11y.spec.ts` (axe-core sur la une, un prono, le classement, la carte de presse, les réglages et les préférences, en thème clair et sombre, à 390 px et à 1 280 px) et corriger dans `frontend/src/` les écarts au niveau AA des WCAG 2.2.
- [ ] T148 [P] Écrire `frontend/tests/e2e/no-third-party.spec.ts` : sur un parcours complet, aucune requête vers un autre domaine que celui de l'appli (SC-005).
- [ ] T149 [P] Écrire `backend/tests/load/run_load.py` : 100 membres, 20 pronos ouverts, paris simultanés et WebSockets ouvertes ; vérifier un p95 des routes sous 200 ms et une diffusion d'un pari en moins de 2 s (SC-002, SC-004).
- [x] T150 Relire chaque écran à 390 px et à 1 280 px en le comparant aux pages « Mobile » et « Ordinateur » du canvas, et corriger `frontend/src/app/AppShell.tsx`, `frontend/src/styles/gazette.css` et les écrans concernés.
- [ ] T151 Dérouler `specs/001-sibylle-v1/quickstart.md` de bout en bout (V1 à V10 ; V8 sur le vrai domaine avec Android, iOS 16.4 ou plus et un ordinateur), faire passer `make check`, et corriger le quickstart si une commande a changé.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance.
- **Foundational (Phase 2)** : après Setup ; bloque toutes les histoires.
- **Histoires (Phases 3 à 13)** : après Foundational, selon les dépendances ci-dessous.
- **Polish (Phase 14)** : le déploiement (T140 à T145) peut suivre US1 ; le reste vient quand les histoires voulues sont faites.

### User Story Dependencies

- **US1 (P1)** : socle des autres histoires (comptes, rédactions, membres, invitations).
- **US2 (P1)** : après US1.
- **US3 (P1)** : après US2.
- **US4 (P2)** : après US3 (classements et saisons reposent sur les règlements).
- **US5 (P2)** : après US2 ; ses blocs « derniers résultats » et « haut du classement » se remplissent avec US3 et US4.
- **US6 (P2)** : après US1 ; le traitement des signalements suppose US3.
- **US7 (P3)** : après US1 ; les trophées de la collection viennent de US4.
- **US8 (P3)** : après US2 et US3.
- **US9 (P3)** : après US1 ; son encadré sur la une suppose US5.
- **US11 (P3)** : après US1 ; le réglage des notifications suppose US8.
- **US10 (P4)** : après US7 (éditeur pixel art) et US9 (encadré « Jeux de la semaine »).

### Within Each User Story

- Tests d'abord, qui échouent ; puis modèle et révision Alembic, domaine, services, routes, régénération du schéma d'API, écrans, branchement, parcours de bout en bout.
- Fichiers partagés, à modifier par une seule tâche à la fois : `backend/src/sibylle/cli.py`, `backend/src/sibylle/worker/jobs.py`, `backend/src/sibylle/services/pronos.py`, `backend/src/sibylle/services/orgs.py`, `frontend/src/app/router.tsx`, `frontend/src/features/pronos/PronoPage.tsx`, `frontend/src/features/une/UnePage.tsx`, ainsi que les révisions Alembic.

### Parallel Opportunities

- Setup : T002, T003, T007 et T008 ensemble.
- Foundational : T012, T016, T018, T019, T024 et T030 côté serveur ; T032, T033, T034, T036 et T038 côté interface, pendant que le serveur avance.
- Dans chaque histoire : toutes les tâches de test [P] ensemble, puis les écrans [P] ensemble une fois les routes faites.
- Entre histoires, après US3 : US4, US6, US7, US9 et US11 touchent surtout des fichiers distincts et peuvent avancer en même temps, en respectant la liste des fichiers partagés.

---

## Parallel Example: User Story 1

```bash
# Tests d'abord, ensemble :
Task: "Contrats des comptes dans backend/tests/contract/test_auth.py"
Task: "Contrats des rédactions et de l'adhésion dans backend/tests/contract/test_orgs_join.py"
Task: "Course à la dernière place dans backend/tests/integration/test_invitation_race.py"
Task: "Validation des PixelImage dans backend/tests/unit/test_pixels.py"

# Une fois les routes faites, les écrans ensemble :
Task: "Inscription et connexion dans frontend/src/features/auth/"
Task: "Créer et rejoindre dans frontend/src/features/orgs/CreateOrgPage.tsx et JoinPage.tsx"
Task: "Sélecteur de rédaction dans frontend/src/features/orgs/OrgSwitcher.tsx"
Task: "Invitations dans frontend/src/features/admin/InvitePanel.tsx"
```

## Parallel Example: User Story 2

```bash
Task: "Cycle de vie dans backend/tests/unit/test_lifecycle.py"
Task: "Règles de pari dans backend/tests/unit/test_betting.py"
Task: "Contrats des pronos dans backend/tests/contract/test_pronos.py"
Task: "Concurrence des paris dans backend/tests/integration/test_bet_concurrency.py"
Task: "Temps réel des paris dans backend/tests/integration/test_realtime_bets.py"

# puis
Task: "Création dans frontend/src/features/pronos/CreatePronoPage.tsx"
Task: "Écran du prono dans frontend/src/features/pronos/PronoPage.tsx"
Task: "Liste dans frontend/src/features/pronos/PronoListPage.tsx"
```

## Parallel Example: User Story 3

```bash
Task: "Règlement dans backend/tests/unit/test_settlement.py"
Task: "Propriétés dans backend/tests/unit/test_settlement_properties.py"
Task: "Plus proche dans backend/tests/unit/test_closest.py"
Task: "Contrats des résultats dans backend/tests/contract/test_results.py"

# puis
Task: "Désignation dans frontend/src/features/results/DesignatePanel.tsx"
Task: "Édition spéciale dans frontend/src/features/results/SpecialEdition.tsx"
```

---

## Implementation Strategy

### MVP First (US1, US2 et US3)

US1 seule n'est pas jouable : le minimum utile réunit les trois histoires P1.

1. Phase 1, puis Phase 2 (bloquante).
2. US1, puis le déploiement (T140 à T145) pour une première version en ligne derrière frp.
3. US2, puis US3.
4. **STOP and VALIDATE** : quickstart V1 à V4 et `make check`. On peut rejoindre, parier, désigner et être payé.

### Incremental Delivery (jalons de plan.md)

| Semaine | Contenu |
|---|---|
| 2 – 8 nov. | Phases 1 et 2, US1, déploiement |
| 9 – 15 nov. | US2, US3 |
| 16 – 22 nov. | US4, US5, US6, US7 |
| 23 – 29 nov. | US8, US9, US11, puis US10 (peut glisser en décembre) |
| 30 nov. | T146 à T151 : répétition générale |
| 1ᵉʳ déc. | lancement ; la saison d'automne dure jusqu'au 20 décembre |

### Parallel Team Strategy

Avec plusieurs sessions de développement :

1. Phases 1 et 2 ensemble, puis US1, dont tout dépend.
2. US2, puis US3 (même cœur de jeu, mêmes fichiers).
3. Ensuite, en parallèle : US4 et US5, US6, US7, US9 et US11, chacune sur sa branche, en respectant la liste des fichiers partagés.
4. Enfin US8, puis US10 et la phase 14.

---

## Notes

- [P] = fichiers différents, aucune dépendance sur une tâche non terminée.
- Chaque tâche de test doit d'abord échouer ; aucune règle de jeu n'est codée sans son test (principe IV).
- Un commit par tâche ou par groupe logique, sur la branche `001-sibylle-v1` ; `make check` passe avant chaque fusion.
- Les contenus de plateforme (palette, modèles d'avatars, fonds de carte, charte, réactions, catalogue et prix) sont des propositions à faire valider par l'utilisateur au fil de l'eau.
- À éviter : tâches vagues, deux tâches simultanées sur un même fichier, dépendances entre histoires qui cassent leur test indépendant.
