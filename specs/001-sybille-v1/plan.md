# Implementation Plan: Sybille v1, le jeu de pronostics des rédactions

**Branch**: `001-sybille-v1` | **Date**: 2026-11-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-sybille-v1/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Sybille v1 est une appli web installable (PWA) où des rédactions fermées de 10 à 50 personnes pronostiquent des événements, misent des lauriers et se classent par saison. Elle comprend les comptes, les organisations et leurs invitations, les quatre types de pronos avec mises et cagnotte, la désignation des résultats et les relances, les classements et les saisons, la carte de presse avec avatar en pixel art et collection, les notifications push et e-mail, et deux mini-jeux.

Approche technique : une API **FastAPI** (Python 3.14) sur **PostgreSQL**, un processus de tâches pour tout ce qui dépend de l'heure (clôtures, rappels, saisons, mini-jeux, envoi des notifications), et une interface **React + TypeScript** construite avec Vite. Le temps réel passe par **une WebSocket par client**, alimentée par `LISTEN/NOTIFY` de PostgreSQL, ce qui évite d'ajouter Redis. Les règles du jeu (cycle de vie, gains, cagnotte, saisons, classements, mini-jeux) vivent dans un module de domaine pur, testé d'abord. Chaque mouvement de lauriers est une écriture d'un registre en ajout seul. Le tout tourne en Docker Compose sur la machine à domicile, derrière Caddy, exposée par frp depuis le VPS qui porte le domaine. Les e-mails partent par Brevo et les notifications push par Web Push (VAPID). Le détail des choix est dans [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.14 (serveur) ; TypeScript 5 et React 19 (interface) ; Node.js LTS 24 ou plus pour construire l'interface.

**Primary Dependencies**: serveur : FastAPI, Uvicorn, SQLAlchemy 2 (asynchrone) avec asyncpg, Alembic, Pydantic 2 et pydantic-settings, argon2-cffi, APScheduler, pywebpush, aiosmtplib et Jinja2, Pillow. Interface : Vite, React Router, TanStack Query, i18next et react-i18next, vite-plugin-pwa (service worker sur mesure), openapi-typescript et openapi-fetch, polices auto-hébergées via Fontsource.

**Storage**: PostgreSQL 18 (données, registre des lauriers, file des notifications, bus d'événements `LISTEN/NOTIFY`) ; volume disque pour les images envoyées (prono), réencodées et servies par l'API après contrôle des droits.

**Testing**: serveur : pytest, pytest-asyncio, httpx (client ASGI), Hypothesis (propriétés de la cagnotte et du registre), testcontainers (vrai PostgreSQL). Interface : Vitest et Testing Library. Bout en bout : Playwright, avec axe-core pour l'accessibilité. Contrat : types TypeScript générés depuis l'OpenAPI de FastAPI, vérifiés à jour en CI.

**Target Platform**: serveur Linux à domicile avec Docker Compose ; navigateurs récents (Chrome, Edge, Firefox, Safari), Android, iOS 16.4 ou plus pour les notifications push (appli installée).

**Project Type**: application web (serveur + interface).

**Performance Goals**: un pari visible chez les autres en moins de 2 s (SC-002), viser moins de 500 ms ; API p95 < 200 ms ; écran affiché en moins de 1,5 s en 4G (SC-004), avec un JavaScript initial < 250 Ko compressé ; jusqu'à 1 000 connexions WebSocket simultanées sur un seul processus.

**Constraints**: aucune requête tierce depuis le navigateur (CSP `self`) ; données sur la machine à domicile ; lauriers en entiers ; heures et saisons en Europe/Paris ; un seul processus API (le bus d'événements passe par PostgreSQL) ; coque de l'appli disponible hors ligne, paris uniquement en ligne ; respect de « réduire les animations ».

**Scale/Scope**: au lancement, quelques rédactions et moins de 1 000 comptes ; conçu pour 10 à 50 membres par rédaction, fluide jusqu'à 100 ; environ 25 écrans (version mobile et ordinateur) ; 11 histoires utilisateur.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution 1.0.0 (`.specify/memory/constitution.md`).

| Principe | Comment le plan le respecte | Avant | Après conception |
|---|---|---|---|
| I. Vie privée d'abord | Polices, icônes et scripts servis par Sybille ; CSP limitée à `self` ; seuls tiers : Brevo (UE) et les services push des navigateurs (contenu chiffré). Le pseudo est la seule identité visible ; export JSON et suppression avec anonymisation (data-model : `accounts.deleted_at`, `memberships.status = anonymized`). | ✅ | ✅ |
| II. Rédactions étanches | Toutes les routes de jeu sont sous `/api/orgs/{org_id}/…` ; une dépendance FastAPI charge le membre et son rôle et refuse sinon ; les sujets temps réel sont filtrés par appartenance ; une suite de tests d'accès parcourt toutes les routes (contracts/rest-api.md). | ✅ | ✅ |
| III. Les lauriers sont un registre | Table `ledger_entries` en ajout seul ; solde et score mis en cache sur `memberships` dans la même transaction ; corrections par écritures inverses rattachées à un `settlement` ; vérification nocturne cache = somme. | ✅ | ✅ |
| IV. Règles testées d'abord | Paquet `sybille.domain` sans FastAPI ni SQLAlchemy ; tests unitaires et Hypothesis écrits avant le code ; tests de contrat et parcours Playwright pour rejoindre, parier, désigner, être payé. | ✅ | ✅ |
| V. Simple à héberger | Quatre services Compose : `caddy`, `api`, `worker`, `db` (plus une tâche de sauvegarde) ; pas de Redis ni de file de messages : `LISTEN/NOTIFY` et une table de notifications suffisent. | ✅ | ✅ |
| VI. Français d'abord, accessible, Gazette | i18next côté interface, catalogue Jinja2 côté e-mails, `fr` seul livré ; fuseau `Europe/Paris` dans le domaine ; jetons de couleur et polices de la Gazette dans `tokens.css` ; axe-core en CI ; `prefers-reduced-motion` et réglage « couper les animations ». | ✅ | ✅ |

Aucun écart : la section Complexity Tracking reste vide.

## Project Structure

### Documentation (this feature)

```text
specs/001-sybille-v1/
├── plan.md              # Ce fichier
├── research.md          # Phase 0 : choix techniques et règles précisées
├── data-model.md        # Phase 1 : tables, contraintes, transitions d'état
├── quickstart.md        # Phase 1 : lancer et valider de bout en bout
├── contracts/
│   ├── rest-api.md      # Routes HTTP, droits, charges utiles
│   ├── realtime.md      # Protocole WebSocket et événements
│   └── notifications.md # Push, e-mails et préférences
└── tasks.md             # Phase 2 (/speckit-tasks), pas encore créé
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml               # géré par uv
├── alembic.ini
├── src/sybille/
│   ├── main.py                  # fabrique de l'app FastAPI
│   ├── config.py                # réglages par variables d'environnement
│   ├── clock.py                 # horloge réelle ou simulée
│   ├── cli.py                   # commande `sybille` (worker, openapi, seed-demo…)
│   ├── i18n/fr.json             # messages d'erreur et textes serveur
│   ├── domain/                  # règles pures, sans web ni base
│   │   ├── lifecycle.py         # états et transitions d'un prono
│   │   ├── betting.py           # règles de saisie d'un prono et des paris
│   │   ├── settlement.py        # gains, lève-tôt, cagnotte, arrondis
│   │   ├── closest.py           # gagnants des pronos nombre et date
│   │   ├── ledger.py            # types d'écritures et leurs effets
│   │   ├── seasons.py           # calendrier des saisons, semaines (Europe/Paris)
│   │   ├── leaderboard.py       # classements mois, saison, depuis toujours
│   │   ├── minigames.py         # course de la boule, Pixel mystère
│   │   ├── pixels.py            # PixelImage et palettes
│   │   ├── content.py           # modèles d'avatars, fonds, charte, réactions
│   │   └── permissions.py       # matrice des droits par rôle
│   ├── db/
│   │   ├── models/              # modèles SQLAlchemy (voir data-model.md)
│   │   ├── session.py
│   │   └── migrations/          # Alembic
│   ├── services/                # cas d'usage transactionnels
│   │   ├── accounts.py  orgs.py  invitations.py  pronos.py  bets.py
│   │   ├── results.py  ledger.py  seasons.py  leaderboard.py  front_page.py
│   │   ├── collection.py  minigames.py  reports.py  uploads.py  export.py
│   │   ├── notifications.py  security.py
│   ├── api/
│   │   ├── deps.py              # session, membre courant, contrôle des rôles
│   │   ├── errors.py
│   │   └── routes/              # health, auth, me, orgs, members, invitations,
│   │                            # pronos, bets, results, front_page, leaderboard,
│   │                            # profile, collection, uploads, minigames,
│   │                            # reports, notifications
│   ├── realtime/
│   │   ├── hub.py               # abonnements par sujet, diffusion locale
│   │   ├── bus.py               # LISTEN/NOTIFY PostgreSQL
│   │   └── ws.py                # point d'entrée WebSocket
│   ├── worker/
│   │   ├── main.py              # APScheduler, boucle du processus de tâches
│   │   └── jobs.py              # clôtures, rappels, saisons, mini-jeux, envois
│   └── notify/
│       ├── email.py  push.py
│       └── templates/fr/        # e-mails Jinja2
└── tests/
    ├── unit/                    # domaine (dont Hypothesis)
    ├── integration/             # services sur vrai PostgreSQL
    └── contract/                # routes, droits, isolation des rédactions

frontend/
├── package.json  vite.config.ts  index.html
├── public/                      # icônes, manifeste, sprites de la boule
├── src/
│   ├── app/                     # routes, fournisseurs (Query, i18n, thème)
│   ├── api/                     # schema.d.ts généré, client.ts, realtime.ts
│   ├── ui/                      # composants Gazette : bandeau, filets, cartes,
│   │                            # boutons, compteur de mise, piles d'avatars, sprites
│   ├── features/
│   │   ├── auth/  orgs/  une/  pronos/  results/  leaderboard/
│   │   ├── profile/  pixel-editor/  collection/  notifications/
│   │   ├── settings/  admin/
│   │   └── games/runner/  games/pixel-mystere/
│   ├── styles/                  # tokens.css (clair, sombre), gazette.css
│   ├── i18n/fr/                 # catalogues de textes
│   └── sw.ts                    # service worker : push, coque hors ligne
└── tests/
    ├── unit/                    # Vitest
    └── e2e/                     # Playwright + axe-core

deploy/
├── docker-compose.yml           # caddy, api, worker, db, backup ; profil dev : mailpit
├── Caddyfile                    # HTTPS, proxy protocol, CSP, fichiers statiques
├── frpc.toml.example            # tunnel 80/443 vers Caddy
├── .env.example
└── backup/                      # pg_dump quotidien et restauration

crystal-ball-kit/                # existant : sprites et logo, copiés dans frontend/public
```

**Structure Decision**: application web en deux projets, `backend/` (Python, géré par uv) et `frontend/` (React, géré par npm), plus `deploy/` pour l'hébergement. Le domaine du serveur est isolé dans `sybille.domain` pour être testé sans base (principe IV). L'interface est rangée par fonctionnalité, avec une bibliothèque de composants Gazette commune.

## Jalons

Calqués sur le découpage du cahier des charges ; chaque semaine se termine par une version déployée sur la machine.

| Semaine | Histoires | Contenu |
|---|---|---|
| 2 – 8 nov. | US1, US6 (en partie), US11 (thème) | Dépôt, Compose, CI ; comptes, sessions, organisations, invitations, rôles, rubriques ; jetons Gazette, polices, i18n, coque PWA ; premier déploiement derrière frp. |
| 9 – 15 nov. | US2, US3 | Domaine d'abord (cycle de vie, cagnotte, lève-tôt, plus proche) ; création, paris, mises, clôture automatique, désignation, édition spéciale, relance, correction, annulation ; temps réel des paris. |
| 16 – 22 nov. | US4, US5, US6 (fin), US7 | Registre et relevé, classements, saisons et trophées ; la une complète, propositions, réactions ; carte de presse, éditeur pixel art, réglages de la rédaction, signalements. |
| 23 – 29 nov. | US8, US9, US10, US11, US7 (collection) | Notifications push et e-mail ; collection et codes secrets ; course de la boule ; Pixel mystère (peut glisser en décembre) ; export et suppression ; version ordinateur ; parcours Playwright. |
| 30 nov. | — | Répétition générale : sauvegarde et restauration, test de charge à 100 membres, audit réseau et accessibilité. |
| 1ᵉʳ déc. | — | Lancement ; la saison d'automne dure jusqu'au 20 décembre. |

**Risques suivis** : calendrier serré (Pixel mystère est la variable d'ajustement) ; notifications push sur iOS, qui exigent l'appli installée ; disponibilité de la machine à domicile (sauvegardes hors site sur le VPS) ; triche à la course de la boule, limitée par des contrôles de vraisemblance côté serveur et acceptée faute d'enjeu.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

Aucun écart à justifier.
