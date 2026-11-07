---

description: "Liste des tâches pour passer la connexion de Sibylle à Keycloak"
---

# Tasks: Connexion par Keycloak

**Input**: Design documents from `/specs/002-keycloak-auth/` (plan.md, spec.md, research.md, data-model.md, contracts/auth.md, quickstart.md) et `.specify/memory/constitution.md`.

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: inclus. Le principe IV veut les contrats testés avant le code : dans chaque histoire, les tâches de test passent avant l'implémentation et doivent d'abord échouer. Les tests de contrat simulent Keycloak (`backend/tests/keycloak_fake.py`) ; les parcours Playwright passent par les vraies pages du thème, avec `make keycloak`.

**Organisation**: par histoire de la spécification (US1 à US6), dans l'ordre des jalons du plan. Le travail se fait sur `main`, sans branche. Les tâches du dépôt voisin labnode2/docker (`/home/dev/Documents/github/docker`) y font leurs propres commits.

## Format: `[ID] [P?] [Story] Description`

- **[P]** : peut se faire en parallèle (autres fichiers, pas de dépendance à une tâche en cours)
- **[Story]** : l'histoire servie (US1 à US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: les dépendances et le Keycloak local dont toutes les histoires ont besoin.

- [ ] T001 Dans `backend/pyproject.toml`, passer `httpx>=0.28` des dépendances de développement à celles du serveur et ajouter `PyJWT[crypto]>=2.10` (research.md K2) ; régénérer `backend/uv.lock` avec `uv lock`. `argon2-cffi` reste jusqu'à T048.
- [ ] T002 [P] Dans `keycloak/dev-realm.json`, ajouter deux clients confidentiels (research.md K12), en gardant `sibylle-dev` pour la vérification du thème : `sibylle` pour `make dev` (secret `sibylle-dev-secret`, retours `http://localhost:5173/api/auth/callback` et `http://localhost:5173/api/auth/login*`, déconnexion back-channel `http://localhost:8000/api/auth/backchannel-logout`) et `sibylle-e2e` pour Playwright (secret `sibylle-e2e-secret`, mêmes chemins sur `http://localhost:5180` et la déconnexion vers `http://localhost:8001`). Chacun : `standardFlowEnabled`, `serviceAccountsEnabled`, `directAccessGrantsEnabled: false`, attribut `pkce.code.challenge.method` = `S256`, `backchannel.logout.session.required` = `true`, `defaultClientScopes` = `web-origins`, `service_account`, `acr`, `profile`, `roles`, `basic`, `email`, `kc-admin-api`. Leur compte de service (`service-account-<client>`) reçoit `manage-users` de `realm-management`. Donner aux comptes de démo des `id` fixes : camille `7c1e0c55-5b1a-4c37-9a0e-3d1f0c9e0001`, dominique `7c1e0c55-5b1a-4c37-9a0e-3d1f0c9e0002`. Les deux secrets sont des valeurs de développement, qui ne valent que pour ce Keycloak local, comme son `admin` / `admin` (research.md K12) : le dire dans un commentaire de `keycloak/README.md`. Vérifier avec `make keycloak` puis `make check-keycloak`.
- [ ] T003 [P] Dans `deploy/.env.example` (commentaires en français), ajouter `OIDC_ISSUER=http://localhost:8280/realms/sibylle`, `KEYCLOAK_INTERNAL_URL=` (vide : l'adresse d'`OIDC_ISSUER`), `OIDC_CLIENT_ID=sibylle`, `OIDC_CLIENT_SECRET=sibylle-dev-secret`, avec leur rôle (contracts/auth.md, « Configuration du serveur ») ; la cible `env` du `Makefile` les écrit pour le développement.
- [ ] T004 [P] Dans `frontend/playwright.config.ts`, donner au serveur d'API `OIDC_ISSUER=http://localhost:8280/realms/sibylle`, `OIDC_CLIENT_ID=sibylle-e2e`, `OIDC_CLIENT_SECRET=sibylle-e2e-secret` ; dans le `Makefile`, la cible `e2e` rappelle que `make keycloak` doit tourner.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: la configuration, le client Keycloak du serveur, son double de test et la migration.

**⚠️ CRITICAL**: aucune histoire ne commence avant la fin de cette phase.

- [ ] T005 Dans `backend/src/sibylle/config.py`, ajouter `oidc_issuer` (défaut `http://localhost:8280/realms/sibylle`), `keycloak_internal_url` (`None` : l'origine d'`oidc_issuer`), `oidc_client_id` (défaut `sibylle`) et `oidc_client_secret` (défaut vide), plus une propriété qui donne l'adresse interne du realm ; en production, `oidc_client_secret` vide est refusé, comme `SIBYLLE_CLOCK=fake`.
- [ ] T006 [P] Créer `backend/tests/keycloak_fake.py` : un faux Keycloak en `httpx.MockTransport`. Il a une paire de clés RSA et sert `…/protocol/openid-connect/certs` et `…/token`, en `authorization_code` (vérifie le secret, le `code_verifier` PKCE et le `redirect_uri`) et en `client_credentials`. Il sert l'API d'admin : `GET` et `DELETE /admin/realms/sibylle/users/{id}`, `PUT …/users/{id}/send-verify-email`, `DELETE /admin/realms/sibylle/sessions/{sid}`. Il offre des aides : `issue_code(claims)` pour un code dont le jeton d'identité porte ces champs, `logout_token(sid=…, sub=…, **écarts)`, `down = True` pour lever `httpx.ConnectError`, et le journal des appels. Une fixture de `backend/tests/conftest.py` le branche sur `services/keycloak.py`.
- [ ] T007 [P] Écrire `backend/tests/unit/test_keycloak.py` (doit échouer avant T008). Le jeton d'identité est refusé s'il vient d'un autre émetteur, d'une autre audience, avec un autre `nonce`, s'il a expiré, s'il est signé par une clé inconnue ou en `none`/`HS256`. Le jeton de déconnexion est refusé s'il n'a pas l'événement `http://schemas.openid.net/event/backchannel-logout`, s'il n'a ni `sid` ni `sub`, s'il porte un `nonce` ou si son `iat` a plus de 5 minutes. Une clé inconnue fait recharger les clés une fois. Le jeton du compte de service est gardé jusqu'à peu avant son expiration. Un appel sans réponse en 3 s lève `IdentityUnavailable`.
- [ ] T008 Créer `backend/src/sibylle/services/keycloak.py` (research.md K2 à K5, K7) : `authorization_url(action, state, nonce, code_challenge)`, sur l'adresse publique, avec `prompt=create` pour `signup` et `kc_action=UPDATE_PASSWORD` pour `password` ; `exchange_code`, `verify_id_token`, `verify_logout_token` ; `realm_is_up()` (2 s) ; et, avec le jeton du compte de service, `get_user`, `delete_user` (un 404 compte comme supprimé), `send_verify_email(user_id, redirect_uri)` et `delete_session(sid)`. Ces appels passent par l'adresse interne, avec 3 s de délai ; toute panne lève `IdentityUnavailable`. Le transport est injectable. T007 doit passer.
- [ ] T009 Dans `backend/src/sibylle/db/models/accounts.py` et une migration `backend/src/sibylle/db/migrations/versions/0022_keycloak.py`, suivre data-model.md :
  - `accounts.keycloak_id` uuid, « unique ; le `sub` du compte Keycloak ; posée à la création par le retour de connexion ; `NULL` après suppression », sans `NOT NULL` ;
  - `accounts.identity_checked_at` timestamptz ;
  - retrait d'`accounts.password_hash` ;
  - `sessions.keycloak_sid` text indexé ;
  - retrait de la table `email_tokens` et du modèle `EmailToken` ;
  - nouvelle table `sign_in_attempts` et son modèle `SignInAttempt` : `id` uuid PK, `token_hash` text unique, `state`, `nonce`, `code_verifier`, `action` text « `login`, `signup` ou `password` » (contrainte CHECK), `next_path` text, `created_at`, `expires_at` (« 10 minutes »).

  Le `downgrade` recrée, vides, ce qu'il retire. Exporter les modèles dans `backend/src/sibylle/db/models/__init__.py`.

**Checkpoint**: `make migrate` passe ; `test_keycloak.py` passe.

---

## Phase 3: User Story 1 - S'inscrire et se connecter sur les pages de la Gazette (Priority: P1) 🎯 MVP

**Goal**: s'inscrire et se connecter par les pages du thème, et revenir connecté là où l'on allait.

**Independent Test**: depuis un lien d'invitation, créer un compte sur les pages de Keycloak, revenir connecté sur l'invitation et rejoindre la rédaction ; se reconnecter depuis une page protégée et y revenir (quickstart.md, lignes US1).

### Tests for User Story 1 ⚠️

- [ ] T010 [P] [US1] Réécrire `backend/tests/contract/test_auth.py` d'après contracts/auth.md.
  - `GET /api/auth/login` répond `303` vers l'autorisation publique, avec `client_id`, `response_type=code`, `scope=openid`, `state`, `nonce`, `code_challenge` (`S256`) et `redirect_uri` = `PUBLIC_ORIGIN/api/auth/callback`. Avec `action=signup`, il ajoute `prompt=create`. Il pose le cookie `sibylle_signin` (`HttpOnly`, `SameSite=Lax`, `Path=/api/auth`) et crée une ligne `sign_in_attempts`. `suite=//exemple.org` ramène sur `/`. Un realm qui ne répond pas mène à `303 /connexion-indisponible`. `?action=forgot` répond `303` vers `…/login-actions/reset-credentials?client_id=sibylle`, sans cookie ni tentative.
  - `GET /api/auth/callback` réussi pose `sibylle_session`, supprime la tentative et redirige vers la `suite`. Un `sub` inconnu crée un compte avec e-mail, prénom, nom et confirmation recopiés ; un `sub` connu reprend son compte et recopie ces champs.
  - Les échecs du retour : une adresse prise par un autre compte vivant donne `erreur=email_taken`, sans session. Un cookie absent, un `state` différent, une tentative expirée ou déjà servie donnent `erreur=expired`. `error=access_denied` donne `erreur=denied`. Une mauvaise signature, une mauvaise audience ou un mauvais `nonce` donnent `erreur=failed`. Keycloak injoignable à l'échange du code mène à `/connexion-indisponible`.
  - Les anciennes routes `POST /api/auth/signup`, `/auth/login`, `/auth/password-reset`, `/auth/password-reset/confirm`, `/auth/verify-email` et `/me/password` répondent 404 ou 405.
- [ ] T011 [P] [US1] Adapter `backend/tests/integration/test_commit_before_response.py` et les tests qui créaient des comptes par `/api/auth/signup` : ils ouvrent leurs sessions par `client_for`, ou par le faux Keycloak quand le parcours de connexion est l'objet du test.
- [ ] T012 [P] [US1] Écrire `frontend/tests/unit/auth.test.tsx`. Sur un 401, `RequireAuth` navigue vers `/api/auth/login?suite=<chemin courant>`. `/connexion` et `/inscription` naviguent vers `/api/auth/login` (`action=signup` pour la seconde) en gardant `suite`. `/connexion?erreur=expired` affiche l'explication et le lien pour recommencer.
- [ ] T013 [P] [US1] Dans `frontend/tests/e2e/helpers.ts`, faire passer `newPerson` par les pages du thème sur `localhost:8280` : « Créer un compte », champs « Prénom », « Nom », « E-mail », « Mot de passe », bouton « Créer un compte », puis attente du retour sur Sibylle ; ajuster les sélecteurs des parcours qui en dépendent, `frontend/tests/e2e/join.spec.ts` d'abord, qui est le parcours de US1.

### Implementation for User Story 1

- [ ] T014 [US1] Dans `backend/src/sibylle/services/accounts.py` (research.md K6), ajouter `sign_in(session, claims, keycloak_sid, user_agent)`. Il rattache par `keycloak_id` ou crée le compte, recopie e-mail, prénom, nom et confirmation (`email_verified_at` posée ou remise à `NULL`), et refuse avec `email_taken` une adresse d'un autre compte vivant. `open_session` garde le `keycloak_sid`. Retirer `signup`, `login`, `change_password`, `request_password_reset`, `reset_password`, `verify_email` et `_email_token` ; `update_account` ne touche plus aux noms.
- [ ] T015 [US1] Dans `backend/src/sibylle/api/routes/auth.py`, écrire `GET /auth/login`, `action=forgot` compris, et `GET /auth/callback` d'après contracts/auth.md (tentative en base, cookie `sibylle_signin`, `suite` validée comme `nextPath`, `303` et codes `erreur`), et retirer les anciennes routes `POST`. Dans `backend/src/sibylle/api/schemas.py`, retirer `SignupIn`, `LoginIn`, `ResetRequest`, `ResetConfirm`, `TokenIn` et `PasswordChange`, et sortir `first_name` et `last_name` de `MePatch`. Dans `backend/src/sibylle/api/deps.py`, retirer les limiteurs `login`, `login_ip`, `password_reset` et `password_reset_ip`. Dans `backend/src/sibylle/api/routes/me.py`, retirer `POST /me/password`. T010 doit passer.
- [ ] T016 [P] [US1] Dans `backend/src/sibylle/worker/jobs.py`, supprimer chaque jour les `sign_in_attempts` expirées, et programmer la tâche dans `backend/src/sibylle/worker/main.py`.
- [ ] T017 [P] [US1] Dans `backend/src/sibylle/seed.py`, rattacher les comptes de démo aux `id` fixes de `keycloak/dev-realm.json` (T002) par `keycloak_id`, sans mot de passe.
- [ ] T018 [US1] Interface dans `frontend/src/features/auth/`, d'après contracts/auth.md (« Pages de l'interface ») :
  - dans `frontend/src/features/auth/AuthPages.tsx`, remplacer les formulaires par des passages vers `/api/auth/login` : connexion, inscription, et page d'erreur pour `?erreur=…` ;
  - ajouter une page `/connexion-indisponible` ;
  - `frontend/src/features/auth/RequireAuth.tsx` navigue (`window.location.assign`) au lieu de rendre `/connexion` ;
  - retirer de `frontend/src/features/auth/api.ts` `useLogin`, `useSignup`, `useRequestReset`, `useConfirmReset` et `useVerifyEmail` ;
  - les routes vont dans `frontend/src/app/router.tsx`, les textes dans `frontend/src/i18n/fr/auth.json`, avec l'écriture inclusive et le ton de la Gazette.

  T012 doit passer.
- [ ] T019 [US1] Régénérer `frontend/src/api/schema.d.ts` (`npm run gen:api` avec le serveur lancé), faire passer `npm run check:api` et `npm run typecheck`.
- [ ] T020 [US1] Dans `specs/001-sibylle-v1/contracts/rest-api.md`, remplacer les lignes de « Comptes et session » qui ont changé par un renvoi à `specs/002-keycloak-auth/contracts/auth.md`.

**Checkpoint**: `make check` passe ; avec `make keycloak`, `npx playwright test join` passe ; les lignes US1 de quickstart.md se vérifient à la main.

---

## Phase 4: User Story 2 - Confirmer son adresse (Priority: P2)

**Goal**: jouer sans confirmer, recevoir l'e-mail de Keycloak, et que Sibylle sache quand l'adresse est confirmée.

**Independent Test**: créer un compte, jouer, cliquer le lien reçu dans Mailpit et voir les notifications par e-mail devenir possibles (quickstart.md, lignes US2).

### Tests for User Story 2 ⚠️

- [ ] T021 [P] [US2] Dans `backend/tests/contract/test_auth.py`, tester l'envoi de l'e-mail de confirmation :
  - un premier retour avec `email_verified: false` fait envoyer l'e-mail (journal du faux Keycloak : `send-verify-email` avec `client_id=sibylle` et `redirect_uri` = `PUBLIC_ORIGIN/api/auth/login?suite=/compte`) ;
  - `POST /api/auth/verify-email/resend` l'envoie de nouveau, et la quatrième fois dans l'heure répond 429.
- [ ] T022 [P] [US2] Créer `backend/tests/contract/test_me.py` pour tester la relecture de la confirmation. Pour un compte non confirmé, `GET /api/me` relit l'utilisateur dans le faux Keycloak au plus une fois par minute (`identity_checked_at`) et pose `email_verified_at` quand il est confirmé. Pour un compte confirmé, il n'appelle jamais Keycloak. Avec le faux Keycloak injoignable, il répond 200 avec l'état connu (SC-006).

### Implementation for User Story 2

- [ ] T023 [US2] Dans `backend/src/sibylle/services/accounts.py`, écrire `send_verification` (par `services/keycloak.py`, research.md K9, appelée par `sign_in` à la création d'un compte non confirmé) et `refresh_identity` (une relecture par minute au plus ; `IdentityUnavailable` y est rattrapée et journalisée, sans faire échouer la requête). Les brancher sur `POST /auth/verify-email/resend` dans `backend/src/sibylle/api/routes/auth.py`, limité à 3 par heure par le limiteur existant, et sur `GET /me` dans `backend/src/sibylle/api/routes/me.py`. T021 et T022 doivent passer.
- [ ] T024 [P] [US2] Retirer les e-mails que Keycloak envoie désormais : `backend/src/sibylle/notify/templates/fr/verify_email.*` et `reset_password.*`, leurs types dans `backend/src/sibylle/notify/messages.py` et leurs cas dans `backend/tests/unit/test_email_templates.py`.
- [ ] T025 [P] [US2] Écrire dans `frontend/src/features/auth/AuthPages.tsx` une page « ce lien ne marche plus » (FR-018) pour `/verifier-email` : elle explique et propose de se connecter pour redemander l'e-mail depuis le compte. Vérifier que le bouton de renvoi des réglages (`NotificationPrefs`) marche toujours.
- [ ] T026 [US2] Dans `frontend/tests/e2e/notifications.spec.ts`, confirmer l'adresse par le lien de l'e-mail de Keycloak lu dans Mailpit, puis vérifier que les notifications par e-mail sont proposées.

**Checkpoint**: lignes US2 de quickstart.md vérifiées.

---

## Phase 5: User Story 3 - Mot de passe oublié, nouveau mot de passe (Priority: P2)

**Goal**: « Changer mon mot de passe » depuis `/compte`, et le mot de passe oublié par la page de Keycloak.

**Independent Test**: changer son mot de passe depuis `/compte` et revenir connecté ; demander un nouveau mot de passe depuis la page de connexion (quickstart.md, ligne US3).

### Tests for User Story 3 ⚠️

- [ ] T027 [P] [US3] Dans `backend/tests/contract/test_auth.py`, tester le changement de mot de passe :
  - `GET /api/auth/login?action=password` porte `kc_action=UPDATE_PASSWORD` ;
  - un retour réussi alors que le navigateur a déjà une session la remplace : l'ancienne ligne de `sessions` est supprimée et un nouveau cookie est posé.
- [ ] T028 [P] [US3] Créer `frontend/tests/unit/settings.test.tsx` pour tester que la page `/compte` montre « Changer mon mot de passe » et qu'il mène à `/api/auth/login?action=password&suite=/compte`.

### Implementation for User Story 3

- [ ] T029 [US3] Dans `backend/src/sibylle/api/routes/auth.py`, accepter `action=password` et faire remplacer la session courante par le retour. T027 doit passer.
- [ ] T030 [US3] Dans `frontend/src/features/settings/SettingsPage.tsx`, ajouter « Changer mon mot de passe » (textes dans `frontend/src/i18n/fr/settings.json`). `/mot-de-passe/oubli` navigue vers `/api/auth/login?action=forgot` ; `/mot-de-passe/nouveau` montre la page « ce lien ne marche plus » de T025 (`frontend/src/app/router.tsx`). T028 doit passer.
- [ ] T031 [US3] Dans `frontend/tests/e2e/profile.spec.ts`, changer son mot de passe sur la page « Nouveau mot de passe » du thème, revenir sur `/compte` toujours connecté ; avec « déconnecter mes autres appareils », un second contexte connecté est déconnecté. Ce dernier point dépend de la déconnexion back-channel de US4 (T035).

**Checkpoint**: ligne US3 de quickstart.md vérifiée.

---

## Phase 6: User Story 4 - Se déconnecter, partout (Priority: P2)

**Goal**: la déconnexion ferme aussi la session Keycloak ; une session fermée dans Keycloak l'est dans Sibylle, et un compte désactivé ou supprimé dans Keycloak perd ses sessions Sibylle dans l'heure (FR-021).

**Independent Test**: se déconnecter et voir le mot de passe redemandé ; fermer une session dans Keycloak et voir l'appareil déconnecté, WebSocket comprise (quickstart.md, lignes US3 et US4).

### Tests for User Story 4 ⚠️

- [ ] T032 [P] [US4] Dans `backend/tests/contract/test_auth.py`, tester les deux déconnexions.
  - `POST /api/auth/logout` répond 204, supprime la session et fait fermer la session Keycloak de son `keycloak_sid` (journal du faux). Avec le faux Keycloak injoignable, il répond quand même 204.
  - `POST /api/auth/backchannel-logout`, sans `X-Sibylle` ni `Origin`, avec un jeton valable : un `sid` supprime les sessions de ce `sid` seulement, un `sub` seul supprime toutes celles du compte.
  - Il répond 400 à un jeton mal signé, d'une autre audience, sans l'événement de déconnexion, avec un `nonce`, ou dont l'`iat` a plus de 5 minutes.
- [ ] T033 [US4] Dans `backend/tests/contract/test_auth.py`, tester la relecture horaire (research.md K15, « Relecture horaire du compte » de contracts/auth.md). Une session dont la dernière prolongation date de plus d'une heure, et dont le compte est absent ou désactivé dans le faux Keycloak, répond `401` et disparaît avec les autres sessions du compte ; un compte actif continue ; le faux Keycloak injoignable laisse passer la requête et garde la session (SC-006).
- [ ] T034 [P] [US4] Écrire `backend/tests/integration/test_realtime_signout.py` : la WebSocket d'une session supprimée par une déconnexion back-channel se ferme avec le code 4401.

### Implementation for User Story 4

- [ ] T035 [US4] Dans `backend/src/sibylle/api/routes/auth.py`, écrire la déconnexion (session locale, puis `delete_session` au mieux, l'échec journalisé, research.md K7) et `POST /auth/backchannel-logout` (research.md K8). Sortir ce chemin du contrôle `X-Sibylle`/`Origin` dans `backend/src/sibylle/main.py`. Les suppressions de sessions vont dans `backend/src/sibylle/services/accounts.py`. T032 doit passer.
- [ ] T036 [US4] Fermer les WebSocket des sessions supprimées, dans `backend/src/sibylle/realtime/` :
  - dans `backend/src/sibylle/realtime/hub.py`, une connexion garde l'id de sa session ;
  - après la suppression, publier sur `sibylle_events` un événement `signed_out` portant ces ids (`backend/src/sibylle/realtime/bus.py`) ;
  - le hub ferme alors les connexions concernées avec 4401 (`backend/src/sibylle/realtime/ws.py`).

  T034 doit passer.
- [ ] T037 [US4] Dans `backend/src/sibylle/api/deps.py`, à la prolongation horaire d'`account_from_token` (`TOUCH_EVERY`), relire le compte par `get_user` de `services/keycloak.py` : absent ou désactivé, supprimer les sessions du compte et répondre comme sans session ; `IdentityUnavailable`, garder la session et journaliser. La WebSocket, qui passe par la même fonction à sa connexion (`backend/src/sibylle/realtime/ws.py`), suit sans changement. T033 doit passer.
- [ ] T038 [P] [US4] Dans `keycloak/README.md`, ajouter la consigne des administrateurs (research.md K15, FR-021) : avant de désactiver ou de supprimer un compte du realm `sibylle` dans la console, fermer ses sessions (*Sessions*, « Sign out »), pour que Sibylle le déconnecte aussitôt ; sans cela, au plus tard une heure après.
- [ ] T039 [P] [US4] Ajouter dans `specs/001-sibylle-v1/contracts/realtime.md` que le code 4401 sert aussi à une session fermée par Keycloak.
- [ ] T040 [US4] Écrire `frontend/tests/e2e/auth.spec.ts` : après « Se déconnecter », revenir sur Sibylle mène à la page de connexion du thème, mot de passe demandé. Le même fichier passe axe-core (`@axe-core/playwright`, comme les autres parcours) sur les pages « Connexion », « Créer un compte » et « Mot de passe oublié » du thème (principe VI, niveau AA).

**Checkpoint**: lignes US3 et US4 de quickstart.md vérifiées, T031 compris.

---

## Phase 7: User Story 5 - Supprimer son compte, partout (Priority: P2)

**Goal**: la suppression du compte efface aussi le compte Keycloak, ou rien du tout.

**Independent Test**: supprimer un compte, le voir disparaître de la console de Keycloak, puis se réinscrire avec la même adresse et obtenir un compte neuf (quickstart.md, ligne US5).

### Tests for User Story 5 ⚠️

- [ ] T041 [P] [US5] Dans `backend/tests/contract/test_data_rights.py`, tester la suppression et l'export :
  - `DELETE /api/me` fait supprimer l'utilisateur dans le faux Keycloak, anonymise le compte, met `keycloak_id` à `NULL` et supprime ses sessions ;
  - avec le faux Keycloak injoignable, il répond `503 identity_unavailable` et ne change rien ;
  - l'export contient e-mail, prénom, nom, `email_verified_at` et `created_at` (FR-014).

### Implementation for User Story 5

- [ ] T042 [US5] Dans `backend/src/sibylle/services/accounts.py`, faire supprimer le compte Keycloak avant l'anonymisation de `delete_account` (un 404 compte comme supprimé), puis mettre `keycloak_id` à `NULL`. Ajouter le code `identity_unavailable` (503) dans `backend/src/sibylle/api/errors.py` et son message dans `frontend/src/i18n/fr/common.json` ; le dialogue de suppression de `frontend/src/features/settings/SettingsPage.tsx` l'affiche. T041 doit passer.
- [ ] T043 [US5] Dans `frontend/tests/e2e/data-rights.spec.ts`, supprimer son compte puis se réinscrire avec la même adresse, et vérifier qu'on obtient un compte neuf, sans rédaction.

**Checkpoint**: ligne US5 de quickstart.md vérifiée.

---

## Phase 8: User Story 6 - Basculer la production (Priority: P3)

**Goal**: la production passe à Keycloak, repart de zéro, et sauvegarde ses comptes.

**Independent Test**: les vérifications « En production » de quickstart.md, et une restauration de `keycloak-db` sur une machine d'essai.

- [ ] T044 [P] [US6] Dans labnode2/docker (`/home/dev/Documents/github/docker`), mettre en place le réseau partagé `keycloak` :
  - `setup.sh` le crée (`docker network create --internal keycloak`) dans l'étape « Shared networks » ;
  - `dev-external/keycloak/docker-compose.yaml` y met le service `keycloak`, en plus de `proxy` et `internal` ;
  - le tableau des réseaux de `NETWORK.md` et les notes de `CLAUDE.md` le décrivent.

  Commit dans ce dépôt. Sur la VM, `sudo bash ~/workdir/docker/setup.sh keycloak` ne recrée que Keycloak.
- [ ] T045 [P] [US6] Dans `keycloak/terraform/main.tf`, modifier le client `sibylle` (research.md K5, K8, K9) :
  - une ressource `keycloak_openid_client_default_scopes` avec `web-origins`, `service_account`, `acr`, `profile`, `roles`, `basic`, `email` et `kc-admin-api` ;
  - une variable `backchannel_logout_url` (défaut `http://sibylle:8443/api/auth/backchannel-logout`) à la place de l'adresse publique ;
  - `${var.app_origin}/api/auth/login*` en plus dans `valid_redirect_uris`, pour le retour de la confirmation d'adresse.

  Mettre à jour `keycloak/terraform/README.md`. Essayer avec `TOFU_ELSEWHERE=1` sur un Keycloak jetable ; en production, `tofu.sh plan` ne doit montrer que ces changements.
- [ ] T046 [US6] Dans `deploy/compose.prod.yml`, faire rejoindre à `api`, et à lui seul, le réseau externe `keycloak` (le `worker` ne parle pas à Keycloak, research.md K4), et poser `KEYCLOAK_INTERNAL_URL: http://keycloak:8080` dans `x-backend-env`. Mettre à jour le test de `backend/tests/unit/test_deploy.py`. À déployer seulement après T044 sur la VM : sans le réseau, `update.sh` échoue.
- [ ] T047 [P] [US6] Dans `deploy/backup/backup.sh` (en anglais), ajouter chaque nuit et avant chaque déploiement un `pg_dump` de `keycloak-db` (`docker exec keycloak-db pg_dump --username=keycloak --dbname=keycloak --format=custom`) vers `<base>.keycloak.dump`, chiffré par age et envoyé au VPS avec les autres fichiers. Dans `deploy/backup/restore.sh`, ajouter `--keycloak <fichier>`, qui restaure dans `keycloak-db`, Keycloak arrêté.
- [ ] T048 [US6] Dans `deploy/README.md` (en anglais), écrire « Switching sign-in to Keycloak », les étapes de research.md K13 avec leurs commandes, ainsi que la sauvegarde et la restauration de Keycloak. ⚠️ Ce fichier a des modifications non commitées de l'utilisateur : regarder d'abord `git diff deploy/README.md` et lui demander de les commiter, ou écrire par-dessus sans les écraser ; ne jamais les inclure dans un commit sans son accord.
- [ ] T049 [US6] Répéter la restauration de `keycloak-db` depuis une sauvegarde sur une machine d'essai : un Keycloak jetable avec le compose de labnode2/docker, comme les essais du 7 novembre. Vérifier qu'un compte s'y connecte, puis noter le résultat dans `deploy/README.md` (SC-007).
- [ ] T050 [US6] Faire la bascule avec l'utilisateur, en suivant `deploy/README.md` :
  - sauvegarde ;
  - T044 sur la VM ;
  - `tofu.sh apply` ;
  - `OIDC_*` dans `/opt/sibylle/deploy/.env`, le secret par `tofu.sh output -raw client_secret` ;
  - base et images de Sibylle remises à zéro, puis déploiement ;
  - comptes d'essai supprimés du realm `sibylle` ;
  - vérifications de quickstart.md, « En production », dont un `tofu.sh plan` sans changement : les réglages qui portent FR-002 (e-mail et mot de passe seulement), FR-009 (liens de 1 h et 24 h) et FR-016 (10 échecs en 15 minutes) sont toujours ceux d'OpenTofu.

**Checkpoint**: SC-002 et SC-007 vérifiés ; les parcours de US1 à US5 marchent en production.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T051 [P] Retirer ce qui ne sert plus : `argon2-cffi` de `backend/pyproject.toml` (`uv lock`), `hash_password`, `verify_password` et `needs_rehash` de `backend/src/sibylle/services/security.py` et leurs tests dans `backend/tests/unit/test_security.py`, les styles et clés de traduction des anciens formulaires (`frontend/src/features/auth/auth.module.css`, `frontend/src/i18n/fr/auth.json`) ; `make check` passe.
- [ ] T052 [P] Dans `keycloak/README.md`, décrire les clients `sibylle` et `sibylle-e2e` de `dev-realm.json` et la portée `kc-admin-api` (section « What the realm sets »).
- [ ] T053 Dérouler toutes les lignes « En local » de quickstart.md, `make e2e` compris, et corriger ce qui manque.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)** : aucune dépendance ; T002 à T004 en parallèle après T001.
- **Foundational (Phase 2)** : après le Setup ; bloque toutes les histoires.
- **US1 (Phase 3)** : après la phase 2. C'est le MVP : les autres histoires supposent qu'on peut se connecter.
- **US2, US4, US5 (Phases 4, 6, 7)** : après US1, indépendantes entre elles.
- **US3 (Phase 5)** : après US1 ; son dernier parcours (T031, autres appareils) attend US4.
- **US6 (Phase 8)** : T044, T045 et T047 peuvent commencer tôt ; la bascule (T050) attend US1 à US5, T046, T048 et T049.
- **Polish (Phase 9)** : après les histoires ; T051 après US1 à US5.

### Within Each User Story

- Tests d'abord, qui échouent ; puis services, routes, interface.
- Les tâches qui touchent le même fichier (`api/routes/auth.py`, `services/accounts.py`, `tests/contract/test_auth.py`) se suivent, jamais en parallèle.

### Parallel Opportunities

- Setup : T002, T003, T004.
- Foundational : T006 et T007 en même temps, avant T008 ; T009 en parallèle de T006 à T008.
- US1 : les tests T010 à T013 ensemble ; puis T016 et T017 pendant T014 et T015.
- Après US1 : US2, US4 et US5 en parallèle (fichiers de test distincts, mais `auth.py` et `accounts.py` partagés : à enchaîner pour ces fichiers).
- US6 : T044, T045 et T047 en parallèle du reste.

---

## Parallel Example: User Story 1

```bash
# Les tests de US1 ensemble (ils doivent échouer) :
Task: "T010 Réécrire backend/tests/contract/test_auth.py d'après contracts/auth.md"
Task: "T012 Écrire frontend/tests/unit/auth.test.tsx"
Task: "T013 Faire passer newPerson par les pages du thème dans frontend/tests/e2e/helpers.ts"

# Puis, pendant T014 et T015 :
Task: "T016 Purge des sign_in_attempts dans backend/src/sibylle/worker/jobs.py"
Task: "T017 Comptes de démo rattachés dans backend/src/sibylle/seed.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 (Setup) puis Phase 2 (Foundational).
2. Phase 3 (US1) : s'inscrire et se connecter par Keycloak, en local.
3. S'arrêter et vérifier : lignes US1 de quickstart.md, `join.spec.ts`.

Le MVP reste local : la production ne bascule qu'une fois, avec tout le reste (US6), puisqu'elle repart de zéro.

### Incremental Delivery

1. Setup et Foundational, puis US1 : connexion par Keycloak en local.
2. US2, US4, US5, puis US3 : confirmation, déconnexions, suppression, mot de passe.
3. US6 : réseau, realm, sauvegarde, restauration répétée, puis la bascule.
4. Polish : nettoyage et quickstart déroulé en entier.

---

## Notes

- [P] = autres fichiers, pas de dépendance à une tâche en cours.
- Vérifier que les tests échouent avant d'écrire le code.
- Les commits se font sur `main`, quand l'utilisateur le demande ; ceux de labnode2/docker dans ce dépôt.
- `deploy/README.md` porte des modifications non commitées de l'utilisateur (T048) : ne pas les mêler à un commit.
- Le code et les commentaires de `deploy/` et des workflows sont en anglais ; l'interface, les spécifications et le `Makefile` en français.
