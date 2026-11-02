# Research: Sybille v1

**Feature**: `001-sybille-v1` | **Date**: 2026-11-01 | **Plan**: [plan.md](plan.md)

Le contexte technique du plan ne contient aucun « NEEDS CLARIFICATION » : les choix ouverts ont été tranchés ici, ou par Emile le 1ᵉʳ novembre 2026 (section « Règles de jeu précisées »).

## Pile technique

### R1. Framework serveur : FastAPI

- **Decision**: FastAPI sur Uvicorn, Python 3.14, dépendances gérées par uv.
- **Rationale**: déjà proposé dans le cahier des charges ; asynchrone de bout en bout, ce qui convient à la WebSocket et à `LISTEN/NOTIFY` ; génère l'OpenAPI qui sert de contrat à l'interface ; Python 3.14 et uv sont déjà installés sur la machine.
- **Alternatives considered**: Django avec Channels (admin intégrée utile, mais deux modèles de concurrence et plus lourd pour une API pure) ; Litestar (proche de FastAPI, communauté plus petite).

### R2. Base de données : PostgreSQL 18

- **Decision**: PostgreSQL 18 dans Docker, un seul schéma, migrations Alembic.
- **Rationale**: verrous de ligne pour les paris concurrents, index partiels, `LISTEN/NOTIFY` pour le bus temps réel, `FOR UPDATE SKIP LOCKED` pour la file de notifications ; tout cela sans service supplémentaire (principe V).
- **Alternatives considered**: SQLite (pas de `LISTEN/NOTIFY`, écritures concurrentes limitées) ; MariaDB (pas d'équivalent simple à `LISTEN/NOTIFY`).

### R3. Accès aux données : SQLAlchemy 2 asynchrone

- **Decision**: SQLAlchemy 2 en mode asynchrone avec asyncpg ; modèles déclaratifs typés ; Alembic pour les migrations, générées puis relues à la main.
- **Rationale**: standard de fait, transactions explicites (indispensables au registre), bon support des verrous et des index partiels.
- **Alternatives considered**: SQLModel (couche en plus, moins de contrôle sur les verrous) ; SQL brut (plus de code répétitif, pas de migrations intégrées).

### R4. Authentification et sessions

- **Decision**: sessions côté serveur. Un jeton aléatoire de 256 bits dans un cookie `HttpOnly; Secure; SameSite=Lax`, stocké haché en base, valable 30 jours et prolongé à l'usage. Mots de passe hachés en Argon2id. Contre le CSRF : `SameSite=Lax`, contrôle de l'en-tête `Origin` et en-tête maison `X-Sybille: 1` exigé sur toute requête qui modifie. Limitation de débit sur connexion, inscription et réinitialisation (par IP et par e-mail), dans le processus API.
- **Rationale**: la révocation est immédiate (déconnexion, suppression de compte), sans jeton lisible par le JavaScript ; la WebSocket s'authentifie avec le même cookie.
- **Alternatives considered**: JWT (révocation compliquée, jeton exposé au JavaScript s'il n'est pas en cookie) ; connexion par lien magique (écartée : le cahier des charges veut e-mail et mot de passe uniquement).

### R5. Temps réel : une WebSocket et `LISTEN/NOTIFY`

- **Decision**: chaque client ouvre une seule WebSocket (`/api/ws`) et s'abonne à des sujets (`org:{id}`, `prono:{id}`). Après chaque transaction qui change l'état visible, le service publie un événement par `NOTIFY sybille_events` ; le processus API écoute ce canal et diffuse aux abonnés autorisés. Le processus de tâches publie de la même façon. Les événements portent des identifiants et les agrégats qui changent (répartition, cagnotte), jamais de données privées ; l'interface met à jour son cache TanStack Query ou recharge la ressource. À la reconnexion, le client recharge les vues ouvertes.
- **Rationale**: le cahier des charges fixe la WebSocket ; `LISTEN/NOTIFY` relie l'API et le processus de tâches sans Redis ; les charges utiles restent bien sous la limite de 8 000 octets.
- **Alternatives considered**: Server-Sent Events (suffiraient, mais le cahier des charges fixe la WebSocket) ; Redis pub/sub (service en plus, principe V) ; interrogation périodique (latence et charge).

### R6. Tâches planifiées : un processus `worker` avec APScheduler

- **Decision**: un processus séparé, même image que l'API, lance APScheduler (planificateur asyncio) avec :
  - toutes les minutes : ouvrir les pronos programmés, clore les pronos échus, envoyer les alertes « ferme dans 2 h », les rappels de désignation, et vider la file des notifications ;
  - chaque jour à 08:00 (Paris) : révélations de Pixel mystère ;
  - chaque lundi à 00:00 (Paris) : gains de la course de la boule de la semaine écoulée ;
  - chaque jour à 00:00 (Paris) : clôture de saison si une saison vient de finir ;
  - chaque nuit : vérification que les soldes en cache égalent le registre.

  Chaque tâche est idempotente : elle lit l'état en base et le fait avancer (par exemple une ligne `season_closures` unique par organisation et saison), si bien qu'un redémarrage ou une exécution en double ne verse rien deux fois.
- **Rationale**: aucune infrastructure en plus ; l'état vit en base, le planificateur n'a pas besoin de mémoire persistante.
- **Alternatives considered**: Celery ou RQ (exigent Redis) ; Procrastinate (file sur PostgreSQL, bonne option mais dépendance de plus pour peu de tâches) ; planificateur dans le processus API (doublons si l'API redémarre ou passe à plusieurs processus).

### R7. Notifications push et e-mails

- **Decision**: Web Push avec clés VAPID via pywebpush ; abonnement enregistré par appareil ; un abonnement qui répond 404 ou 410 est supprimé. E-mails par le relais SMTP de Brevo avec aiosmtplib et des modèles Jinja2 en français ; le domaine publie SPF, DKIM et DMARC. Chaque notification est d'abord écrite dans une table `notifications` dans la même transaction que l'événement, puis envoyée par le `worker` avec reprises progressives.
- **Rationale**: une notification n'est jamais perdue si l'envoi échoue, et jamais envoyée pour un événement annulé ; SMTP garde Brevo remplaçable sans changer le code.
- **Alternatives considered**: API HTTP de Brevo (plus riche, mais lie le code au fournisseur) ; notifications envoyées directement dans la requête (perdues en cas d'erreur, ralentissent la réponse).
- **Note iOS**: Safari n'accepte les notifications push que pour une appli ajoutée à l'écran d'accueil (iOS 16.4 ou plus). L'interface l'explique au moment d'activer les notifications.

### R8. Interface : Vite, React, TypeScript

- **Decision**: application monopage construite par Vite, servie en fichiers statiques par Caddy. React Router pour la navigation, TanStack Query pour les données serveur (pas de magasin global), CSS Modules et variables CSS pour les jetons Gazette (thèmes clair et sombre), i18next pour les textes, vite-plugin-pwa en mode `injectManifest` pour un service worker sur mesure (push, coque hors ligne). Client d'API typé généré par openapi-typescript à partir de l'OpenAPI de FastAPI, appelé avec openapi-fetch.
- **Rationale**: pas besoin de rendu serveur pour une appli derrière connexion ; un build statique est le plus simple à héberger ; les types générés empêchent l'interface et l'API de diverger.
- **Alternatives considered**: Next.js (rendu serveur inutile ici, hébergement plus lourd) ; Redux ou Zustand (inutile, l'état est surtout serveur) ; Tailwind (les maquettes reposent déjà sur une poignée de jetons et de styles propres à la Gazette).

### R9. Pixel art : avatars, logos, dessins

- **Decision**: un dessin est stocké comme sa taille (16 ou 32), une liste d'indices de palette (un octet par pixel, 0 = transparent) encodée en base64 dans l'API, et la référence de palette. Le serveur valide la taille et vérifie que chaque couleur utilisée est dans la palette de base ou débloquée par le membre. Le rendu se fait sur `<canvas>` avec `image-rendering: pixelated`. Pillow produit au besoin une image PNG (icône de notification).
- **Rationale**: validation simple des couleurs débloquées, stockage minuscule, rendu net à toutes les tailles.
- **Alternatives considered**: envoi d'images PNG (impossible de vérifier la palette, plus lourd) ; SVG (inutile pour une grille).

### R10. Images jointes aux pronos

- **Decision**: envoi limité à 5 Mo ; Pillow réencode en WebP de 1 200 px de côté au plus et retire les métadonnées (EXIF) ; fichier nommé par un identifiant aléatoire ; servi par l'API après contrôle d'appartenance à l'organisation, avec cache privé.
- **Rationale**: principe II (une image d'une rédaction n'est pas lisible par une autre) et principe I (pas de données de localisation dans les photos).
- **Alternatives considered**: fichiers publics servis par Caddy (adresse devinable impossible, mais l'isolation ne serait plus vérifiée).

### R11. Concurrence des paris et des invitations

- **Decision**: un pari verrouille dans l'ordre la ligne du prono puis celle du membre (`SELECT … FOR UPDATE`) ; il vérifie l'état ouvert, l'heure du serveur et le solde, attribue le rang d'arrivée (`bet_count + 1`), écrit la mise au registre et met à jour les compteurs. Un index unique partiel `(prono_id, membership_id) WHERE superseded_at IS NULL` garantit un seul pari actif. L'utilisation d'une invitation verrouille la ligne de l'invitation.
- **Rationale**: aucun solde négatif par une mise, aucun double pari, rang lève-tôt exact, même sous des clics simultanés.
- **Alternatives considered**: isolation `SERIALIZABLE` avec reprise (plus coûteux, plus complexe à tester).

### R12. Heure, semaines et saisons

- **Decision**: tous les instants sont stockés en UTC (`timestamptz`) ; le domaine calcule les bornes en `Europe/Paris` avec `zoneinfo`, puis les convertit en UTC, ce qui gère les changements d'heure. Une table `seasons` liste les saisons (année, saison, début, fin) jusqu'en 2030 et se complète automatiquement. La semaine des mini-jeux va du lundi 00:00 au dimanche 23:59:59, heure de Paris. Un pari réglé compte dans la saison de sa résolution.
- **Rationale**: les saisons et les semaines sont définies en heure de Paris dans le cahier des charges ; une table explicite rend les classements et les trophées faciles à requêter.
- **Alternatives considered**: calculer les saisons à la volée partout (requêtes de classement plus complexes).

### R13. Classements

- **Decision**: calculés à la demande par SQL : score du mois = somme des `score_delta` du mois ; score de la saison = compteur en cache ; depuis toujours = somme des scores gravés sur les trophées plus le score de la saison en cours ; pronos gagnés = nombre de paris gagnants réglés dans la période. Égalités : même rang, rang suivant sauté (1, 1, 3). Les membres partis n'apparaissent pas ; les comptes supprimés apparaissent dans les éditions passées sous « Ancien membre », pas dans les classements.
- **Rationale**: à 50 membres, les agrégats indexés répondent en quelques millisecondes ; pas de table dérivée à maintenir.
- **Alternatives considered**: vues matérialisées (rafraîchissement à gérer pour un gain inutile à cette échelle).

### R14. Hébergement, HTTPS et sauvegardes

- **Decision**: Docker Compose sur la machine à domicile avec `caddy`, `api`, `worker`, `db` et une tâche `backup`. frpc, sur la machine, ouvre vers le frps du VPS deux tunnels TCP (80 et 443) avec le PROXY protocol v2 ; le DNS du domaine pointe sur le VPS. Caddy, à domicile, obtient le certificat (ACME) et termine le TLS : le VPS ne voit que du trafic chiffré, et Caddy récupère l'IP réelle des visiteurs grâce au PROXY protocol (utile à la limitation de débit). Sauvegarde nocturne : `pg_dump` au format personnalisé et archive des images, 14 jours gardés sur la machine, copie chiffrée (age) sur le VPS. La restauration est répétée avant le lancement.
- **Rationale**: chiffrement jusqu'à la machine (principe I), un seul point d'entrée, et frps déjà en place sur le VPS.
- **Alternatives considered**: terminer le TLS sur le VPS (le VPS verrait le trafic en clair) ; tunnel Cloudflare (tiers non européen qui voit le trafic).

### R15. En-têtes de sécurité

- **Decision**: Caddy envoie `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; connect-src 'self' wss://<domaine>; style-src 'self'; font-src 'self'; frame-ancestors 'none'`, HSTS, `Referrer-Policy: no-referrer`, et une `Permissions-Policy` restrictive.
- **Rationale**: la CSP rend impossible l'ajout involontaire d'une ressource tierce (SC-005).

### R16. Polices et ressources graphiques

- **Decision**: Jacquard 12, Bricolage Grotesque et Geist Mono (licence OFL) installées via les paquets Fontsource et servies par Sybille, limitées aux jeux de caractères latins. Les sprites de la boule (`crystal-ball-kit/`) sont copiés dans `frontend/public/`.
- **Rationale**: les maquettes chargent ces polices depuis Google Fonts, ce que le principe I interdit en production.

### R17. Traduction

- **Decision**: i18next côté interface, un fichier JSON par fonctionnalité dans `src/i18n/fr/` ; côté serveur, les e-mails et les notifications push passent par des modèles Jinja2 et un catalogue JSON ; la langue est enregistrée sur le compte (`fr` par défaut). Dates et nombres formatés par `Intl` avec le fuseau `Europe/Paris`.
- **Rationale**: l'anglais arrive juste après le lancement sans réécriture (principe VI).

### R18. Tests et vérifications

- **Decision**: `make check` lance ruff (format et analyse), mypy, pytest, puis côté interface ESLint, `tsc --noEmit`, Vitest, et vérifie que `schema.d.ts` correspond à l'OpenAPI. Playwright couvre les parcours clés avec deux navigateurs simultanés (temps réel) et axe-core. Les tests d'intégration utilisent un vrai PostgreSQL via testcontainers. Une horloge injectable permet de simuler clôtures, semaines et saisons. En développement, les e-mails sont capturés par Mailpit (profil `dev` du Compose, absent en production).
- **Rationale**: principe IV ; le dépôt n'a pas encore de dépôt distant, `make check` servira de base à une CI GitHub Actions quand il en aura un.

### R19. Course de la boule : contrôle des scores

- **Decision**: le serveur ouvre une partie (`run_id`, graine des obstacles, heure de début) et compte les essais de la semaine ; à la fin, l'interface envoie le score et la durée ; le serveur refuse une partie déjà terminée, une partie de plus de 30 minutes, ou un score supérieur au maximum atteignable pour la durée. Le jeu tourne entièrement dans le navigateur (canvas, 60 images par seconde).
- **Rationale**: assez pour décourager la triche facile ; sans enjeu réel, une anti-triche plus lourde ne se justifie pas.

### R20. Suppression de compte

- **Decision**: la suppression efface l'e-mail, les nom et prénom, le mot de passe, les sessions, les abonnements push et les préférences ; chaque appartenance passe à l'état `anonymized` avec le pseudo « Ancien membre » et l'avatar par défaut. Les paris et les écritures du registre restent, pour que les cagnottes et les éditions passées restent justes. Si le compte est la seule rédaction en chef d'une organisation qui a d'autres membres, il doit d'abord en nommer une autre ; s'il en est le seul membre, l'organisation est supprimée avec lui.
- **Rationale**: principe I, sans casser l'historique des autres.

## Règles de jeu précisées

Tranchées par Emile le 1ᵉʳ novembre 2026, ou découlant du cahier des charges.

### J1. Règlement d'un prono

Notations : `G` gain de base du prono, `P` cagnotte (somme de toutes les mises du prono, y compris les mises remplacées d'un prono de date « sans fin »), `W` les paris gagnants, `s_i` la mise du pari `i`, `S_W` la somme des mises gagnantes, `N` et `p` le nombre de premiers joueurs et le pourcentage du bonus lève-tôt.

1. **Gagnants** : choix et oui/non, les paris dont la réponse est parmi les bonnes réponses ; nombre et date, les paris actifs dont l'écart à la valeur réelle est minimal (tous les ex aequo).
2. **Gain de base** : chaque gagnant reçoit `G`.
3. **Lève-tôt** : un gagnant dont le rang d'arrivée est au plus `N` reçoit `floor(G × p / 100)`.
4. **Cagnotte** : si `W` est vide ou si `S_W = 0`, la cagnotte est perdue. Sinon chaque gagnant reçoit `floor(P × s_i / S_W)` ; le reste est distribué un laurier à la fois aux gagnants classés par mise décroissante puis par rang d'arrivée.
5. **Registre** : au pari, une écriture `stake` retire `s_i` du solde (score inchangé). Au règlement : `base_gain` (+G au solde et au score), `early_bird` (idem), `pot_share` (+part au solde, +(part − s_i) au score) pour chaque gagnant ; `stake_lost` (0 au solde, −s_i au score) pour chaque perdant et pour chaque mise remplacée.
6. **Correction** : écritures inverses de tout le règlement précédent, puis nouveau règlement ; les deux sont rattachés à une ligne `settlements`.
7. **Annulation** : écritures `refund` qui rendent chaque mise, et inverses d'un éventuel règlement.

Propriétés testées avec Hypothesis : la somme des `pot_share` vaut `P` ou 0 ; aucun solde ne devient négatif par une mise ; règlement puis correction vers le même résultat laisse les soldes inchangés ; le résultat ne dépend pas de l'ordre de lecture des paris.

### J2. Score

Seuls les pronos font bouger le score (`base_gain`, `early_bird`, `pot_share`, `stake_lost` et leurs inverses). Les achats, les gains de mini-jeux et les ajustements de la rédaction en chef ne changent que le solde. Le trophée grave le score de la saison.

### J3. Course de la boule

5 essais par semaine et par membre ; le meilleur score compte. Le lundi à 00:00, pour la semaine écoulée et par rédaction : 10 lauriers au 1er, 7 au 2e, 5 au 3e, 2 à chaque autre joueur ; à égalité de score, la partie la plus ancienne passe devant. Versé au solde (écriture `minigame`).

### J4. Pixel mystère

Un·e journaliste ou la rédaction en chef dépose un dessin (16×16 ou 32×32) et son mot ; un seul jeu actif par rédaction, les suivants attendent. À la création, l'ordre de révélation des pixels est tiré au hasard et enregistré ; chaque jour à 08:00 (Paris), `ceil(nombre de pixels / 7)` pixels se dévoilent, le premier lot à l'ouverture. 3 essais par jour et par membre ; la comparaison ignore majuscules, accents et espaces en trop. Gains par ordre d'arrivée : 10, 7, 5, puis 3 ; l'auteur·rice ne joue pas. Le jeu se termine quand tous les autres membres actifs ont trouvé ou quand tous les pixels sont dévoilés ; le suivant démarre le lendemain à 08:00.

### J5. Rappels et alertes

- « Ferme dans 2 h » : une seule fois par prono et par membre, à la clôture moins 2 h, seulement s'il n'a pas parié ; jamais pour un prono de date « sans fin ».
- Rappel de désignation : au créateur journaliste, ou au ou à la journaliste qui a validé la proposition ; à la date de résultat attendu (ou le lendemain de la clôture sans cette date), puis à J+1, J+3, J+7, puis chaque semaine, jusqu'à la désignation, la relance ou l'annulation.

## Contenus à produire pendant l'implémentation

Ils ne bloquent pas la conception : la charte par défaut, les textes des e-mails, le jeu de réactions rapides (une poignée d'icônes en pixel art), le catalogue de la collection et ses prix (boules saisonnières, couleurs, cadres), les codes secrets, les modèles d'avatars et les fonds de carte d'organisation.
