# Research: Sibylle v1

**Feature**: `001-sibylle-v1` | **Date**: 2026-11-01 | **Plan**: [plan.md](plan.md)

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

- **Decision**: sessions côté serveur. Un jeton aléatoire de 256 bits dans un cookie `HttpOnly; Secure; SameSite=Lax`, stocké haché en base, valable 30 jours et prolongé à l'usage. Mots de passe hachés en Argon2id. Contre le CSRF : `SameSite=Lax`, contrôle de l'en-tête `Origin` et en-tête maison `X-Sibylle: 1` exigé sur toute requête qui modifie. Limitation de débit sur connexion, inscription et réinitialisation, dans le processus API : stricte par e-mail (10 échecs de connexion en 15 min, 5 demandes de réinitialisation par heure), beaucoup plus lâche par IP (100 et 50), car tout un bureau se connecte derrière une seule adresse.
- **Rationale**: la révocation est immédiate (déconnexion, suppression de compte), sans jeton lisible par le JavaScript ; la WebSocket s'authentifie avec le même cookie.
- **Alternatives considered**: JWT (révocation compliquée, jeton exposé au JavaScript s'il n'est pas en cookie) ; connexion par lien magique (écartée : le cahier des charges veut e-mail et mot de passe uniquement).

### R5. Temps réel : une WebSocket et `LISTEN/NOTIFY`

- **Decision**: chaque client ouvre une seule WebSocket (`/api/ws`) et s'abonne à des sujets (`org:{id}`, `prono:{id}`). Après chaque transaction qui change l'état visible, le service publie un événement par `NOTIFY sibylle_events` ; le processus API écoute ce canal et diffuse aux abonnés autorisés. Le processus de tâches publie de la même façon. Les événements portent des identifiants et les agrégats qui changent (répartition, cagnotte), jamais de données privées ; l'interface met à jour son cache TanStack Query ou recharge la ressource. À la reconnexion, le client recharge les vues ouvertes.
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

- **Decision**: Web Push avec clés VAPID via pywebpush ; abonnement enregistré par appareil, seulement vers le service push d'un navigateur (le `worker` envoie à l'adresse donnée par le membre : sans cette liste, on pourrait le faire écrire n'importe où) ; un abonnement qui répond 404 ou 410 est supprimé. E-mails par le relais SMTP de Brevo avec aiosmtplib et des modèles Jinja2 en français ; le domaine publie SPF, DKIM et DMARC. Chaque notification est d'abord écrite dans une table `notifications` dans la même transaction que l'événement, puis envoyée par le `worker` avec reprises progressives.
- **Rationale**: une notification n'est jamais perdue si l'envoi échoue, et jamais envoyée pour un événement annulé ; SMTP garde Brevo remplaçable sans changer le code.
- **Alternatives considered**: API HTTP de Brevo (plus riche, mais lie le code au fournisseur) ; notifications envoyées directement dans la requête (perdues en cas d'erreur, ralentissent la réponse).
- **Note iOS**: Safari n'accepte les notifications push que pour une appli ajoutée à l'écran d'accueil (iOS 16.4 ou plus). L'interface l'explique au moment d'activer les notifications.

### R8. Interface : Vite, React, TypeScript

- **Decision**: application monopage construite par Vite, servie en fichiers statiques par nginx. React Router pour la navigation, TanStack Query pour les données serveur (pas de magasin global), CSS Modules et variables CSS pour les jetons Gazette (thèmes clair et sombre), i18next pour les textes, vite-plugin-pwa en mode `injectManifest` pour un service worker sur mesure (push, coque hors ligne). Client d'API typé généré par openapi-typescript à partir de l'OpenAPI de FastAPI, appelé avec openapi-fetch.
- **Rationale**: pas besoin de rendu serveur pour une appli derrière connexion ; un build statique est le plus simple à héberger ; les types générés empêchent l'interface et l'API de diverger.
- **Alternatives considered**: Next.js (rendu serveur inutile ici, hébergement plus lourd) ; Redux ou Zustand (inutile, l'état est surtout serveur) ; Tailwind (les maquettes reposent déjà sur une poignée de jetons et de styles propres à la Gazette).

### R9. Pixel art : avatars, logos, dessins

- **Decision**: un dessin est stocké comme sa taille (16 ou 32), une liste d'indices de palette (un octet par pixel, 0 = transparent) encodée en base64 dans l'API, et la référence de palette. Le serveur valide la taille et vérifie que chaque couleur utilisée est dans la palette de base ou débloquée par le membre. Le rendu se fait sur `<canvas>` avec `image-rendering: pixelated`. Pillow produit au besoin une image PNG (icône de notification).
- **Rationale**: validation simple des couleurs débloquées, stockage minuscule, rendu net à toutes les tailles.
- **Alternatives considered**: envoi d'images PNG (impossible de vérifier la palette, plus lourd) ; SVG (inutile pour une grille).

### R10. Images jointes aux pronos

- **Decision**: envoi limité à 5 Mo ; Pillow réencode en WebP de 1 200 px de côté au plus et retire les métadonnées (EXIF) ; fichier nommé par un identifiant aléatoire ; servi par l'API après contrôle d'appartenance à l'organisation, avec cache privé.
- **Rationale**: principe II (une image d'une rédaction n'est pas lisible par une autre) et principe I (pas de données de localisation dans les photos).
- **Alternatives considered**: fichiers publics servis par nginx (adresse devinable impossible, mais l'isolation ne serait plus vérifiée).

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

- **Decision**: Docker Compose sur la machine à domicile, qui est aussi le PC de développement : un projet à part (`sibylle-prod`, `deploy/compose.prod.yml`) avec `nginx`, `api`, `worker` et `db`, lancé depuis un clone du dépôt dans `/opt/sibylle` (J15). Le domaine, `sibylle.cc`, passe par le proxy de Cloudflare (choix d'Emile du 5 novembre 2026), dont l'enregistrement A pointe sur l'adresse IPv4 publique de la box ; la box transfère son port 443 au port 8443 de la machine, où nginx est publié (choix d'Emile du 6 novembre 2026, à la place d'un tunnel frp par le VPS). Pas d'enregistrement AAAA : IPv6 n'a pas de NAT. Cloudflare ne parle au site qu'en HTTPS, en mode Full (strict) : nginx termine le TLS avec un certificat d'origine de Cloudflare (valable 15 ans, donc sans certbot), et un certificat autosigné provisoire lui permet de démarrer tant que celui-ci n'est pas posé. L'adresse des visiteurs est l'en-tête `CF-Connecting-IP` quand la connexion vient d'une plage d'adresses de Cloudflare (module realip), et sinon l'adresse qui s'est connectée (quelqu'un qui joint la box sans passer par Cloudflare) ; nginx la transmet à l'API dans `X-Forwarded-For` (utile à la limitation de débit). L'adresse de la box devient l'origine du site : nginx refuse à la poignée de main TLS une connexion qui ne nomme pas le site, et, en option, Authenticated Origin Pulls ne laisse entrer que Cloudflare. Sauvegarde chaque nuit (timer systemd) et avant chaque mise à jour : `pg_dump` au format personnalisé et archive des images, 14 jours gardés sur la machine, copie chiffrée (age) de celle de la nuit sur le VPS. La restauration est répétée avant le lancement.
- **Rationale**: un seul point d'entrée, sans service en plus sur la machine ni détour par le VPS. Cloudflare termine le TLS à sa bordure et voit le trafic en clair : c'est un écart au principe I, accepté par Emile (plan.md, Complexity Tracking).
- **Alternatives considered**: le DNS seul, sans le proxy de Cloudflare, avec un certificat Let's Encrypt obtenu par certbot (le premier choix de ce plan, écarté par Emile le 5 novembre 2026) ; un tunnel frp depuis le VPS, où frps tourne déjà (le premier choix aussi, écarté par Emile le 6 novembre 2026 : un détour et un service de plus) ; un tunnel Cloudflare (cloudflared, écarté par Emile le 6 novembre 2026) ; Caddy, qui gère seul ses certificats (premier choix, remplacé par nginx).

### R15. En-têtes de sécurité

- **Decision**: nginx envoie `Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; connect-src 'self' wss://<domaine>; style-src 'self'; font-src 'self'; frame-ancestors 'none'`, HSTS, `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff` et une `Permissions-Policy` restrictive (tout ce que l'appli n'utilise pas ; `clipboard-write` et `web-share` gardent leur valeur par défaut, le site lui-même). Ces en-têtes sont posés avec `add_header … always` dans chaque bloc `location` : dès qu'un bloc déclare son propre `add_header` (le `Cache-Control` des fichiers, par exemple), nginx n'hérite plus de ceux du bloc parent. Seule exception : `/carte/`, la carte de presse publique, qu'un autre site peut afficher dans une iframe (J11).
- **Rationale**: la CSP rend impossible l'ajout involontaire d'une ressource tierce (SC-005).

### R16. Polices et ressources graphiques

- **Decision**: Jacquard 12, Bricolage Grotesque et Geist Mono (licence OFL) installées via les paquets Fontsource et servies par Sibylle, limitées aux jeux de caractères latins. Les sprites de la boule (`crystal-ball-kit/`) sont copiés dans `frontend/public/`.
- **Rationale**: les maquettes chargent ces polices depuis Google Fonts, ce que le principe I interdit en production.

### R17. Traduction

- **Decision**: i18next côté interface, un fichier JSON par fonctionnalité dans `src/i18n/fr/` ; côté serveur, les e-mails et les notifications push passent par des modèles Jinja2 et un catalogue JSON ; la langue est enregistrée sur le compte (`fr` par défaut). Dates et nombres formatés par `Intl` avec le fuseau `Europe/Paris`.
- **Rationale**: l'anglais arrive juste après le lancement sans réécriture (principe VI).

### R18. Tests et vérifications

- **Decision**: `make check` lance ruff (format et analyse), mypy, pytest, puis côté interface Prettier, ESLint, `tsc --noEmit`, Vitest, et vérifie que `schema.d.ts` correspond à l'OpenAPI. Playwright couvre les parcours clés avec deux navigateurs simultanés (temps réel) et axe-core. Les tests d'intégration utilisent un vrai PostgreSQL via testcontainers. Une horloge injectable permet de simuler clôtures, semaines et saisons. En développement, les e-mails sont capturés par Mailpit (profil `dev` du Compose, absent en production). Sur GitHub, le workflow « Frontend » (`.github/workflows/frontend.yml`) rejoue les vérifications de l'interface à chaque push sur `main` et à chaque pull request qui touche `frontend/` ou `deploy/nginx/`, puis construit l'appli, garde `frontend/dist` 14 jours et construit l'image du site (J16). Le contrat d'API a son workflow, « API contract » (`.github/workflows/api.yml`), avec uv et Python 3.14, déclenché par `backend/` et les types de l'interface (l'OpenAPI vient du serveur). Le workflow « Backend » (`.github/workflows/backend.yml`) rejoue `make check-backend`, puis construit l'image du serveur (J14) ; Playwright viendra avec le déploiement.
- **Rationale**: principe IV ; la CI lance les mêmes commandes que `make check`, si bien qu'un `make check` vert annonce une CI verte.
- **Alternatives considered**: lancer `make check-frontend` d'un bloc (une seule étape, des journaux moins lisibles, et uv aurait été nécessaire pour tout le reste) ; Playwright dès maintenant (il lui faut la base et le serveur).

### R19. Course de la boule : contrôle des scores

- **Decision**: le serveur ouvre une partie (`run_id`, graine des obstacles, heure de début) et compte les essais de la semaine ; à la fin, l'interface envoie le score et la durée ; le serveur refuse une partie déjà terminée, une partie de plus de 30 minutes, ou un score supérieur au maximum atteignable pour la durée. Le jeu tourne entièrement dans le navigateur (canvas, 60 images par seconde).
- **Rationale**: assez pour décourager la triche facile ; sans enjeu réel, une anti-triche plus lourde ne se justifie pas.

### R20. Suppression de compte

- **Decision**: la suppression efface l'e-mail, les nom et prénom, le mot de passe, les sessions, les abonnements push et les préférences ; chaque appartenance passe à l'état `anonymized` avec le pseudo « Ancien membre » et l'avatar par défaut. Les paris et les écritures du registre restent, pour que les cagnottes et les éditions passées restent justes. Si le compte est la seule rédaction en chef d'une organisation qui a d'autres membres, il doit d'abord en nommer une autre ; s'il en est le seul membre, l'organisation est supprimée avec lui. De même, la dernière personne qui quitte une rédaction la ferme : personne ne pourrait plus y revenir. Le compte supprimé n'apparaît plus dans les invitations par e-mail qui lui étaient adressées.
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

5 essais par semaine et par membre (une partie ouverte compte, même abandonnée) ; le meilleur score compte. Le lundi, pour la semaine écoulée et par rédaction : 10 lauriers au 1er, 7 au 2e, 5 au 3e, 2 à chaque autre joueur (membre actif avec au moins une partie finie et un score positif) ; à égalité de score, la partie la plus ancienne passe devant. Versé au solde (écriture `minigame`), à partir de 00:30 plutôt que 00:00 : une partie commencée le dimanche soir peut encore finir pendant 30 min. Une rédaction dont la clôture de saison est due attend celle-ci, pour que la remise à zéro du solde n'efface pas les gains. Score : un point par 10 pixels parcourus, à une vitesse de 300 à 900 pixels par seconde, donc au plus 90 points par seconde (R19).

### J4. Pixel mystère

Un·e journaliste ou la rédaction en chef dépose un dessin (16×16 ou 32×32) et son mot ; un seul jeu actif par rédaction, les suivants attendent. À la création, l'ordre de révélation des pixels est tiré au hasard et enregistré ; chaque jour à 08:00 (Paris), `ceil(nombre de pixels / 7)` pixels se dévoilent, le premier lot à l'ouverture. 3 essais par jour et par membre ; la comparaison ignore majuscules, accents et espaces en trop. Gains par ordre d'arrivée : 10, 7, 5, puis 3 ; l'auteur·rice ne joue pas (mais voit le dessin entier et le mot). Le jeu se termine quand tous les autres membres actifs ont trouvé ou quand tous les pixels sont dévoilés ; le suivant démarre le lendemain à 08:00, ou tout de suite au dépôt si le précédent s'est terminé avant ce matin. Tous les pixels comptent, transparents compris : le 7ᵉ lot dévoile donc tout. Les pixels cachés valent 255 dans le dessin envoyé. Dans la file d'attente, un·e journaliste ne voit le mot et le dessin que des siens, pour pouvoir jouer ceux des autres. La tâche tourne chaque minute (rattrapage après un redémarrage).

### J5. Rappels et alertes

- « Ferme dans 2 h » : une seule fois par prono et par membre, à la clôture moins 2 h, seulement s'il n'a pas parié ; jamais pour un prono de date « sans fin ».
- Rappel de désignation : au créateur journaliste, ou au ou à la journaliste qui a validé la proposition ; à la date de résultat attendu (ou le lendemain de la clôture sans cette date), puis à J+1, J+3, J+7, puis chaque semaine, jusqu'à la désignation, la relance ou l'annulation.

### J6. Pièces

Les lauriers servent à miser et à se classer ; les pièces servent à acheter dans la collection, pour ne plus mélanger les deux. Lauriers verts = solde (ce qu'on peut miser) ; lauriers en or = solde plus mises des paris actifs pas encore réglés (une mise remplacée sur un prono de date « sans fin » ne compte plus). Chaque lundi à 00:00 (Paris), la tâche `grant_weekly_coins` donne à chaque membre actif arrivé avant ce moment autant de pièces que ses lauriers en or (0 s'ils sont négatifs) ; les lauriers restent. Elle tourne chaque minute et ne verse qu'une fois par membre et par semaine (unique (`membership_id`, `week_start`)), comme la clôture de saison : un `worker` arrêté le lundi rattrape la semaine à son retour, avec les lauriers en or de ce moment-là. Elle verrouille les membres avec `SKIP LOCKED` et ne les attend jamais : un membre occupé par un règlement passe à la minute suivante. Une correction ou une annulation postérieure ne reprend pas les pièces déjà versées. Les pièces ne repartent pas à zéro en fin de saison. Prix : couleur 400, cadre 600 pièces (les prix en lauriers multipliés par 10, pour garder environ un objet toutes les 1 à 4 semaines). Les boules ne s'achètent plus (révision `0016_showcase`) : on les gagne en fin de saison (le trophée gravé) ou par code secret, pour qu'une boule garde sa valeur de souvenir. La fenêtre « Bonne nouvelle » s'affiche à la première ouverture après la conversion ; `memberships.coins_seen_week` retient le dernier lundi annoncé.

### J7. Programme des jeux

Tranché par Emile le 4 novembre 2026. La rédaction en chef choisit les jeux de la semaine en cours et des 3 suivantes (`game_weeks`). Une semaine sans programme propre prend ceux d'une semaine ordinaire (`game_defaults`), les deux jeux au départ ; une semaine peut n'avoir aucun jeu. La semaine ordinaire est datée : un changement vaut à partir du lundi suivant. Ainsi la semaine en cours, et la semaine passée que le lundi n'a pas encore payée, ne changent jamais de jeux sans que la rédaction en chef les touche une à une.

Retirer un jeu de la semaine en cours annule sa semaine. La course n'ouvre ni ne termine plus de partie, et le lundi ne la paie pas : `pay_runner_week` lit le programme de la semaine payée, figé puisqu'elle est passée. Pixel mystère arrête aussitôt le dessin en cours : il passe à `finished` et donne son mot, sans reprendre les lauriers gagnés. Une semaine qui commence sans Pixel mystère arrête de même le dessin en cours, à la première minute du lundi (tâche `reveal_pixel_puzzles`) ; d'ici là, les propositions sont déjà refusées. Les dessins déposés attendent une semaine avec Pixel mystère, puis démarrent selon J4 (le lendemain à 08:00 de la fin du précédent, ou tout de suite).

Un jeu remis dans la semaine en cours reprend : la course avec les essais déjà joués (5 en tout), Pixel mystère avec le dessin suivant. Une partie commencée le dimanche soir compte pour sa semaine, même si la suivante n'a pas la course. Hors programme, `GET …/games` rend `runner: null` et, pour Pixel mystère, seulement le dernier dessin terminé : le mot d'un dessin arrêté reste lisible sur sa page.

### J10. Promotion de la semaine

Choix par défaut du 4 novembre 2026, à la demande d'Emile. Chaque rédaction a, chaque semaine (du lundi 00:00 au dimanche 23:59, heure de Paris), une promotion : un objet à vendre (une couleur ou un cadre, jamais une boule) et un pourcentage parmi 20, 30, 40 et 50 %, tirés au hasard. Le tirage est gardé dans `weekly_deals` dès la première lecture de la collection ou le premier achat de la semaine (`INSERT … ON CONFLICT DO NOTHING`, donc un seul tirage même à plusieurs) : la promotion ne bouge plus de la semaine, même si le catalogue change, et le `worker` n'a rien à faire. Le prix réduit est arrondi à la pièce inférieure (`prix × (100 − %) ÷ 100`, au moins 1). L'achat envoie le prix affiché ; s'il ne correspond plus (la semaine a changé entre-temps), le serveur répond `409 price_changed` et l'écran recharge la collection.

### J8. Chaîne de victoires

Choix par défaut du 4 novembre 2026, à la demande d'Emile. La chaîne se calcule à la demande, sans colonne à tenir à jour : on prend les paris actifs (`superseded_at IS NULL`) du membre dont l'issue est `won` ou `lost`, rangés selon le premier règlement de leur prono (`settlements` de `seq = 1`, dont l'identifiant UUIDv7 suit l'ordre de création, même quand deux règlements tombent au même instant de l'horloge simulée). La chaîne en cours compte les `won` qui suivent le dernier `lost` ; le record est la plus longue suite de `won`. Un remboursement (`refunded`) n'est ni une victoire ni une défaite. Une correction change l'issue des paris sans déplacer le prono dans l'ordre, puisque le premier règlement reste le même. Pour les listes (classement, une, membres), une seule requête par rédaction calcule la chaîne en cours de chacun avec `row_number()` ; la carte de presse lit les issues d'un seul membre et calcule aussi son record.

La flamme s'allume à partir de 2 victoires d'affilée : une victoire seule n'est pas une chaîne. C'est un dessin de 8 × 10 pixels en trois images, que l'interface fait défiler en CSS (`steps`), immobile sous `.reduce-motion` comme toutes les animations.

### J9. Discussion d'un prono

Choix par défaut du 4 novembre 2026, à la demande d'Emile. Une discussion par prono, sans fils de réponses : des messages de 1 à 500 caractères, du plus ancien au plus récent, servis par pages de 20 à partir du plus récent (`before` = l'identifiant du plus ancien message déjà affiché ; les UUIDv7 suivent l'ordre d'écriture). Aimer est une bascule, comme les réactions (`message_likes`, une ligne par membre et par message ; aimer son propre message est permis). Un message supprimé l'est pour de bon, avec ses « J'aime » : par son auteur·rice, ou par la rédaction en chef qui modère selon la charte (`MODERATE_MESSAGES`). Les écrans suivent la discussion par le sujet `prono:<id>` : les événements `message.*` portent des identifiants, et chaque écran recharge la discussion, puisque `liked` et `can_delete` dépendent de qui regarde. La suppression d'un compte efface ses messages (le texte peut dire qui l'a écrit) et garde ses « J'aime », comptés sous « Ancien membre ».

### J11. Carte de presse publique

Choix par défaut du 5 novembre 2026, à la demande d'Emile. Une carte se rend publique rédaction par rédaction (`memberships.card_public`, faux par défaut). Son adresse est `/carte/<jeton>`, un jeton aléatoire de 16 caractères (`secrets.token_urlsafe(12)`, 96 bits) tiré à la première mise en public puis gardé : un lien partagé ou une iframe remarche quand la carte redevient publique. Le jeton n'est pas un secret, l'interrupteur seul décide. Quitter la rédaction remet la carte en privé ; un compte supprimé rend ses appartenances `anonymized`, donc sans carte. `GET /api/public/cards/{token}` répond sans session, et `404 not_found` pour une carte privée comme pour un jeton inconnu. Il est limité à 600 lectures par IP en 10 minutes, assez pour un bureau entier qui ouvre une page en montrant plusieurs. La réponse ne contient que la carte elle-même : ni l'identifiant du membre, ni ses trophées et sa collection en dehors des objets mis en avant.

La page publique est une route de l'application monopage, hors de la session et du cadre de l'appli : elle ne lit pas `/api/me`, n'ouvre pas de WebSocket et n'enregistre pas de service worker (dans l'iframe d'un autre site, il téléchargerait toute l'appli dans le stockage de ce site). Le service worker de l'appli laisse `/carte/` aller au serveur au lieu de servir l'`index.html` en cache, dont les en-têtes interdisent l'affichage dans un cadre. nginx sert `/carte/` avec les en-têtes de R15, sauf `frame-ancestors *` au lieu de `'none'`, plus `X-Robots-Tag: noindex` ; la page pose aussi `<meta name="robots" content="noindex">`. Le code d'intégration proposé est une iframe de 400 × 470 pixels, assez pour la carte et trois objets mis en avant à la largeur d'un téléphone.

### J12. Notifications après une action

Choix par défaut du 5 novembre 2026, à la demande d'Emile. Une action dit son résultat dans une notification en haut à droite (`frontend/src/ui/Toaster.tsx`), pas dans la page. Le cache des mutations de TanStack Query (`frontend/src/app/queryClient.ts`) en est le point unique : chaque mutation dit son succès par `meta.success` (une clé de traduction), ou l'écran le dit lui-même avec `toast` quand les mots dépendent de l'action (« Rôle de Hugo : journaliste ») ; toute erreur devient une notification d'erreur avec le message traduit du serveur, sauf les codes que l'écran explique lui-même (`meta.shown`, comme `last_editor`, avec son lien) et les appels que personne n'a demandés (`meta.quiet`). Les erreurs d'un champ restent sous ce champ ; une erreur `validation_error` dit seulement « Vérifie les champs signalés ».

La pile est une région `aria-live="polite"` nommée « Infos » (« Notifications » est déjà le nom des réglages des notifications) ; une réussite est un `status`, une erreur une `alert`. Trois notes au plus, la même jamais deux fois. Un minuteur décide du départ (4 s, 6,5 s pour une erreur), pas l'animation de la barre : sous « couper les animations », la barre reste immobile et la note part quand même. Elle attend tant que sa croix a le focus. Les notes laissent passer les clics vers la page (`pointer-events: none`), sauf leur croix : une note ne cache jamais un bouton, ni pour une personne ni pour les tests.

### J13. Logo par défaut

Choix par défaut du 5 novembre 2026, à la demande d'Emile. `organisations.logo` devient obligatoire : une rédaction créée sans logo prend le premier modèle (`DEFAULT_LOGO` de `backend/src/sibylle/domain/content.py`, l'île de Sophia Office), la révision 0021 le donne aux rédactions qui n'en avaient pas, et retirer un logo le remet. L'initiale qui en tenait lieu disparaît de l'interface. Dans les réglages, le bouton s'appelle « Modifier le logo » : on part du logo en place.

### J14. Image du serveur et registre

Choix du 5 novembre 2026, à la demande d'Emile. Une seule image sert l'API et le worker. `backend/Dockerfile` installe le serveur avec uv 0.13.5 dans une étape de construction (environnement `/app`, paquet installé sans mode éditable : migrations, modèles d'e-mails et catalogues viennent du paquet), sur Python 3.14 slim, sous un utilisateur `sibylle` sans droits qui n'écrit que dans `/data/uploads`. `sibylle serve`, la commande par défaut, applique les migrations puis lance uvicorn ; le worker est `sibylle worker`.

Le workflow « Backend » construit l'image à chaque pull request. Depuis `main`, une fois ruff, mypy et pytest passés, il l'envoie dans le registre du projet, `registry.labnode.ovh/sibylle/backend`, taguée `main` et `sha-<commit court>` (de quoi revenir à une version précise). Les identifiants du registre sont des secrets du dépôt (`REGISTRY_USERNAME`, `REGISTRY_PASSWORD`), qu'une pull request venue d'un fork ne voit pas ; les actions qui les voient sont figées par leur commit. Le registre passe par le proxy de Cloudflare, qui refuse les envois de plus de 100 Mo : la plus grosse couche de l'image en fait 45 une fois compressée. La machine de production est un PC x86_64, pour lequel les runners de GitHub construisent directement.

Écartés : une image par processus (tout serait en double) ; ghcr.io (le projet a son registre) ; construire sur la machine de production (rien n'y arriverait testé) ; le tag `latest` (il ne dit pas de quel commit vient l'image).

### J15. Déploiement par crochet

Choix du 5 novembre 2026, à la demande d'Emile. La machine de production est le PC de développement : la production vit dans `/opt/sibylle`, un clone du dépôt public, sous un utilisateur système `sibylle` (groupe `docker`), et son projet Compose `sibylle-prod` a ses propres volumes et aucun port publié ; la base de développement n'est jamais touchée.

Après l'envoi de l'image, le job « Deploy » de la CI appelle `https://sibylle.cc/hooks/deploy`, que nginx relaie à webhook (adnanh/webhook, paquet Debian) : il tourne sur la machine et n'écoute que sur le pont Docker. La requête porte le commit et sa signature HMAC-SHA256 avec un secret partagé (`DEPLOY_WEBHOOK_SECRET` côté GitHub, `/etc/sibylle/webhook.env` côté machine). webhook lance un seul script, `deploy/update.sh` : le clone passe sur `main` (le commit doit y être), l'image est tirée, la base et les images envoyées sont sauvegardées, puis les services redémarrent et doivent se dire en bonne santé ; sinon, c'est le retour à la version précédente (dépôt et image), avec la commande qui restaure la base d'avant. Le journal revient à GitHub, dont le job échoue avec la mise à jour. Qui volerait le secret ne pourrait que redéployer ce qui est déjà sur `main`, ou lire le journal d'une mise à jour.

Cloudflare, gardé devant `sibylle.cc`, coupe une réponse qui tarde plus de 100 s (erreur 524), et une mise à jour dure plus longtemps (sauvegarde, puis jusqu'à 5 min pour la santé des services) ; aucune version de webhook (2.8.3 en février 2026) ne renvoie la sortie d'une commande au fil de l'eau. Le crochet `deploy` répond donc tout de suite (202) et lance la mise à jour en arrière-plan (`deploy/webhook/deploy.sh`), sous un identifiant propre à l'essai du job (`<run>-<essai>`) : son journal et son issue restent dans `deploy-logs/`, 30 jours. La CI interroge toutes les 10 s un second crochet signé, `deploy-status`, qui rend l'état et le journal. Chaque mise à jour faite ou manquée est aussi postée sur un salon Discord (`DISCORD_WEBHOOK_URL`), aussi quand `update.sh` est lancé à la main.

Les sauvegardes passent par `deploy/backup/backup.sh`, chaque nuit (un timer systemd remplace la tâche `backup` du Compose prévue d'abord) et avant chaque mise à jour.

Écartés : interroger le registre à intervalles réguliers (un délai à chaque mise à jour, et rien dans GitHub) ; Watchtower (projet d'origine archivé en décembre 2025 ; mise à jour conteneur par conteneur, sans sauvegarde ni retour arrière) ; un runner GitHub sur la machine (un dépôt public l'exposerait aux pull requests venues de forks) ; SSH depuis GitHub (un accès de plus à ouvrir par le VPS).

### J16. Image du site et nginx

Choix du 5 novembre 2026, à la demande d'Emile. L'interface et nginx forment une seule image, `registry.labnode.ovh/sibylle/web` (`deploy/nginx/Dockerfile`) : l'interface est construite avec le Node de `frontend/.nvmrc`, sur Debian comme les runners, puis servie par nginx 1.30 sur Alpine avec sa configuration de production (`deploy/nginx/templates/`). L'image se construit depuis la racine du dépôt, que `deploy/nginx/Dockerfile.dockerignore` réduit à `frontend/` et `deploy/nginx/`. Au démarrage, l'entrée de l'image tire le domaine de `PUBLIC_ORIGIN` (l'adresse que le serveur compare déjà à l'en-tête `Origin`), remplit les modèles avec envsubst (les seules variables `SIBYLLE_*` : celles de nginx restent intactes) et pose le certificat (R14).

Le workflow « Frontend » la construit à chaque pull request et, depuis `main`, l'envoie taguée `main` et `sha-<commit court>`, comme l'image du serveur. Le contrat d'API quitte ce workflow pour le sien : un changement du seul serveur ne reconstruit ni ne redéploie l'image du site. Les deux workflows appellent le même workflow « Deploy » (`.github/workflows/deploy.yml`), qu'on lance aussi à la main pour redéployer `main`. Quand un push touche les deux, la machine enchaîne deux mises à jour (une à la fois) ; la seconde apporte ce que la première n'a pas encore trouvé. `deploy/update.sh` suit les deux images ensemble : tirées, gardées en `previous`, remises en cas d'échec. L'image d'avant est lue sur le conteneur en service plutôt que sur le tag, qu'un `pull` a pu déplacer (une mise à jour arrêtée après avoir tiré, ou un `pull` à la main) : sinon la mise à jour suivante se croirait à jour et redémarrerait sans sauvegarde ni retour arrière possible. Le job « Deploy » interroge l'état à travers nginx, que la mise à jour peut redémarrer : il patiente 6 minutes sans réponse avant d'abandonner, de quoi couvrir le retour arrière d'un nginx cassé.

nginx résout `api` par le DNS de Docker (`resolve`, nginx 1.27.3 et plus) : un redéploiement recrée le conteneur de l'API sans qu'il faille redémarrer nginx. Un écouteur interne sur 8080, non publié, sert au contrôle de santé du conteneur. La carte de presse publique (`/carte/`, J11) est servie sur place, sans redirection interne, pour garder ses propres en-têtes.

Écartés : une image nginx qui monterait l'interface construite par la CI (la machine devrait recevoir des fichiers en plus de l'image) ; certbot (Cloudflare garde son proxy, R14) ; une redirection du port 80 (Cloudflare ne joint le site qu'en HTTPS) ; un seul workflow pour l'interface et le serveur, qui ne déploierait qu'une fois par push (il faudrait détecter à la main ce qui a changé dans chaque job).

## Contenus à produire pendant l'implémentation

Ils ne bloquent pas la conception : la charte par défaut, les textes des e-mails, le jeu de réactions rapides (une poignée d'icônes en pixel art), le catalogue de la collection et ses prix (couleurs, cadres ; les boules se gagnent), les codes secrets, les modèles d'avatars et les fonds de carte d'organisation.
