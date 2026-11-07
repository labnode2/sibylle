# Implementation Plan: Connexion par Keycloak

**Branch**: `002-keycloak-auth` (le travail se fait sur `main`, sans branche) | **Date**: 2026-11-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-keycloak-auth/spec.md`

## Summary

Sibylle confie l'inscription, la connexion, les mots de passe et la confirmation d'adresse au
realm `sibylle` de Keycloak, déjà en production (`keycloak/terraform`, thème `keycloak/theme`).
Le serveur devient le client OpenID Connect (research.md K1) : `/api/auth/login` envoie vers
Keycloak (code d'autorisation, PKCE), `/api/auth/callback` échange le code par le réseau
Docker interne, vérifie le jeton d'identité, rattache le compte par son `sub` et ouvre la
session `sibylle_session` de R4, inchangée. Se déconnecter ferme aussi la session Keycloak ;
Keycloak prévient Sibylle des sessions fermées ailleurs (déconnexion back-channel) ; supprimer
son compte le supprime dans Keycloak. L'interface remplace ses cinq pages de compte par des
passages vers Keycloak et gagne « Changer mon mot de passe ». En production : un réseau
`keycloak` partagé entre Keycloak et le serveur, les secrets du client dans `deploy/.env`, une
base qui repart de zéro, et la base de Keycloak dans la sauvegarde de chaque nuit.

## Technical Context

**Language/Version**: inchangé : Python 3.14 (serveur) ; TypeScript 5 et React 19 (interface).

**Primary Dependencies**: serveur : ajout de `httpx` (passe des dépendances de test à celles du
serveur) et de `PyJWT[crypto]` (research.md K2) ; retrait d'`argon2-cffi`. Keycloak 26.8.2
(labnode2/docker, `dev-external/keycloak`), realm et client par OpenTofu 1.13
(`keycloak/terraform`), pages et e-mails par le thème `keycloak/theme`.

**Storage**: PostgreSQL 18 de Sibylle, migration `0023_keycloak` (data-model.md :
`accounts.keycloak_id`, `accounts.identity_checked_at`, `sessions.keycloak_sid`, table
`sign_in_attempts` ; retrait de `accounts.password_hash` et d'`email_tokens`). Les identités
vivent dans la base de Keycloak (`keycloak-db`, PostgreSQL 18.6).

**Testing**: contrats pytest contre un faux Keycloak branché par `httpx.MockTransport` (clés
RSA de test, jetons signés) ; la fixture `client_for` ouvre toujours ses sessions en base ;
Playwright par les pages du thème, avec le Keycloak de `keycloak/dev.sh` ; Vitest pour les
passages vers Keycloak ; `tofu.sh plan` pour le realm ; `check-theme.py` pour le thème.

**Target Platform**: inchangé, plus Keycloak sur dev-external, joint par le navigateur à
`https://auth.sibylle.cc` et par le serveur à `http://keycloak:8080`.

**Project Type**: application web (serveur + interface), plus la configuration de Keycloak
(`keycloak/`, labnode2/docker).

**Performance Goals**: une connexion fait l'aller-retour vers Keycloak en moins de 2 s hors
saisie ; une session fermée dans Keycloak l'est dans Sibylle en moins d'une minute (SC-003) ;
aucune requête à Keycloak sur le chemin des requêtes ordinaires, sauf pour un compte non
confirmé (une par minute au plus) et à la prolongation horaire d'une session (research.md K15).

**Constraints**: aucun jeton dans le navigateur ; CSP inchangée (on navigue vers
`auth.sibylle.cc`, on n'en charge rien) ; l'API d'admin de Keycloak reste fermée à Internet (NPM
la bloque) : appels du serveur par le réseau Docker interne ; Keycloak 26.8 exige la portée
`kc-admin-api` pour son API d'admin (vérifié, research.md K5) ; la production repart de zéro
(clarification du 7 novembre).

**Scale/Scope**: comme la v1 ; 4 routes de connexion, 3 de compte modifiées, 6 retirées ; 5 pages
d'interface remplacées, 1 page et 1 réglage ajoutés.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution 1.0.0 (`.specify/memory/constitution.md`).

| Principe | Comment le plan le respecte | Avant | Après conception |
|---|---|---|---|
| I. Vie privée d'abord | Keycloak tourne sur la machine du projet ; pas de nouveau tiers (Brevo, déjà admis, envoie ses e-mails). `auth.sibylle.cc` est un sous-domaine de Sibylle dont les pages servent leurs propres polices et scripts. Noms et e-mail ne sont jamais montrés à un autre membre ; l'export garde l'identité ; supprimer son compte le supprime aussi dans Keycloak (FR-013). Le proxy de Cloudflare devant `auth.sibylle.cc` reprend l'écart déjà accepté pour `sibylle.cc`. | ⚠️ | ⚠️ |
| II. Rédactions étanches | Inchangé : Keycloak ne connaît ni rédactions ni rôles ; les routes de jeu et leurs tests d'accès ne bougent pas. | ✅ | ✅ |
| III. Les lauriers sont un registre | Inchangé. La remise à zéro de la production (FR-007) se fait par une base neuve, pas par des écritures retirées. | ✅ | ✅ |
| IV. Règles testées d'abord | Les contrats de `contracts/auth.md` sont écrits avant le code, contre le faux Keycloak ; les parcours clés de bout en bout repassent par les pages du thème (SC-005). | ✅ | ✅ |
| V. Simple à héberger | Un service de plus, Keycloak et sa base, dans labnode2/docker : écart justifié ci-dessous. Sa base entre dans la sauvegarde de chaque nuit, avec la copie chiffrée hors de la machine, et sa restauration est documentée et répétée (research.md K14). | ⚠️ | ⚠️ |
| VI. Français d'abord, accessible, Gazette | Pages et e-mails de Keycloak au thème de la Gazette, en français seul ; `check-theme.py` vérifie chaque page et e-mail, et les parcours Playwright passent axe-core sur les pages du thème. | ✅ | ✅ |

Les deux écarts sont justifiés dans le Complexity Tracking, ainsi que celui du flux de travail
(sur `main`, sans branche). La conception ne fait apparaître aucun autre écart.

## Project Structure

### Documentation (this feature)

```text
specs/002-keycloak-auth/
├── spec.md              # La spécification (clarifiée le 7 novembre)
├── plan.md              # Ce fichier
├── research.md          # Phase 0 : décisions K1 à K15
├── data-model.md        # Phase 1 : comptes, sessions, aller-retour de connexion
├── quickstart.md        # Phase 1 : vérifications en local et en production
├── contracts/
│   └── auth.md          # Phase 1 : routes, jetons, réglages, pages
├── checklists/
│   └── requirements.md  # Qualité de la spécification
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml                         # + httpx, PyJWT[crypto] ; − argon2-cffi
├── src/sibylle/
│   ├── config.py                          # OIDC_ISSUER, KEYCLOAK_INTERNAL_URL, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET
│   ├── services/keycloak.py               # nouveau : autorisation, échange du code, clés, jetons, API d'admin
│   ├── services/accounts.py               # rattachement par sub, recopie, suppression (Keycloak d'abord)
│   ├── services/security.py               # − Argon2 ; garde new_token et token_hash
│   ├── api/routes/auth.py                 # login, callback, logout, backchannel-logout, verify-email/resend
│   ├── api/routes/me.py                   # − /me/password ; GET /me relit Keycloak ; DELETE /me
│   ├── api/deps.py                        # − limiteurs de connexion et de mot de passe
│   ├── api/schemas.py                     # − SignupIn, LoginIn, ResetRequest, ResetConfirm, PasswordChange, TokenIn
│   ├── realtime/hub.py, realtime/ws.py    # fermer les WebSocket d'une session supprimée
│   ├── db/models/accounts.py              # keycloak_id, identity_checked_at, keycloak_sid, SignInAttempt ; − EmailToken
│   ├── db/migrations/versions/0023_keycloak.py
│   ├── worker/jobs.py                     # purge des tentatives expirées
│   ├── seed.py                            # comptes de démo rattachés à ceux de dev-realm.json
│   └── notify/templates/fr/               # − verify_email.*, reset_password.*
└── tests/
    ├── keycloak_fake.py                   # nouveau : le faux Keycloak (MockTransport)
    └── contract/test_auth.py              # réécrit d'après contracts/auth.md

frontend/
├── src/features/auth/                     # AuthPages → passages ; RequireAuth ; page « connexion indisponible »
├── src/features/settings/SettingsPage.tsx # « Changer mon mot de passe »
├── src/i18n/fr/auth.json
├── src/api/schema.d.ts                    # régénéré depuis l'OpenAPI
└── tests/e2e/helpers.ts                   # newPerson par les pages du thème

keycloak/
├── dev-realm.json                         # + client confidentiel `sibylle`, compte de service, kc-admin-api ; ids fixes des comptes de démo
└── terraform/main.tf                      # + portées par défaut (kc-admin-api), adresse back-channel interne, retour de confirmation

deploy/
├── compose.prod.yml                       # api sur le réseau externe `keycloak`
├── .env.example                           # OIDC_*
├── backup/backup.sh, backup/restore.sh    # + keycloak-db
└── README.md                              # la bascule (research.md K13)

labnode2/docker (dépôt voisin)
├── dev-external/keycloak/docker-compose.yaml  # + réseau externe `keycloak`
├── setup.sh                                   # crée le réseau `keycloak` (--internal)
└── CLAUDE.md, NETWORK.md

specs/001-sibylle-v1/
├── research.md                            # R4 réécrite : renvoie à ce dossier
└── contracts/rest-api.md                  # section « Comptes et session » → contracts/auth.md
```

**Structure Decision**: la structure web de la v1 (`backend/`, `frontend/`) ne change pas ; le
nouveau code tient dans un service (`services/keycloak.py`) et les routes existantes. Ce qui
configure Keycloak reste dans `keycloak/` (thème, realm), et ce qui le fait tourner dans
labnode2/docker.

## Jalons

1. **Keycloak prêt pour le serveur** : `dev-realm.json` et `keycloak/terraform` donnent au client
   `sibylle` la portée `kc-admin-api`, son adresse back-channel et le retour de confirmation ;
   `tofu.sh plan` en production ne change que cela.
2. **Le serveur** : contrats d'abord, contre le faux Keycloak ; puis l'aller-retour de connexion,
   le rattachement, la déconnexion et la déconnexion back-channel, la confirmation, la
   suppression, la migration.
3. **L'interface** : passages vers Keycloak, pages d'erreur et d'indisponibilité, « Changer mon
   mot de passe », types régénérés, parcours Playwright par les pages du thème.
4. **La sauvegarde** de `keycloak-db`, et sa restauration répétée sur une machine d'essai.
5. **La bascule** en production (research.md K13), puis les vérifications de `quickstart.md`.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Écart | Pourquoi | Alternative plus simple écartée |
|---|---|---|
| Principe V : un service de plus, Keycloak et sa base (`keycloak`, `keycloak-db` dans labnode2/docker), et un réseau partagé avec Sibylle | Choix d'Emile des 6 et 7 novembre 2026 : confier comptes, mots de passe, liens envoyés par e-mail et freinage des attaques à un outil éprouvé, administrable, et réutilisable par d'autres applis (un realm par appli) | Garder la connexion maison de la v1 (R4), qui couvrait déjà la spécification, écartée par Emile |
| Principe I : le proxy de Cloudflare devant `auth.sibylle.cc` voit les pages de connexion en clair | Le même choix que pour `sibylle.cc` (001, research.md R14), pour le même domaine | Le DNS seul pour ce sous-domaine, avec un certificat Let's Encrypt, écarté avec celui de `sibylle.cc` |
| Flux de travail : la fonctionnalité se fait sur `main`, sans branche `002-keycloak-auth` | Choix d'Emile : tout va sur `main` | Une branche par fonctionnalité, écartée par Emile |
