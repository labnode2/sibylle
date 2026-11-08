# Contrat REST : Sibylle v1

**Feature**: `001-sibylle-v1` | **Plan**: [../plan.md](../plan.md) | **Modèle**: [../data-model.md](../data-model.md)

Ce document fixe les routes, les droits et les charges utiles. L'OpenAPI généré par FastAPI (`/api/openapi.json`) en est la forme exécutable ; l'interface en tire ses types (`frontend/src/api/schema.d.ts`), vérifiés à jour en CI.

## Conventions

- Base : `https://<domaine>/api`. JSON en UTF-8, champs en `snake_case`, instants en ISO 8601 UTC, dates en `AAAA-MM-JJ`.
- Authentification : cookie de session `sibylle_session` (`HttpOnly; Secure; SameSite=Lax`). Toute requête qui modifie (`POST`, `PUT`, `PATCH`, `DELETE`) exige l'en-tête `X-Sibylle: 1` et un `Origin` égal au domaine.
- Droits : colonne **Qui**. `Public` = sans session ; `Compte` = session valide ; `Membre` = membre actif de `{org}` ; `Journaliste` = rôle `journalist` ou `editor` ; `Réd. chef` = rôle `editor`.
- Isolation : une ressource d'une autre organisation répond `404`, jamais `403`, pour ne pas révéler son existence.
- Pagination : `?cursor=<opaque>&limit=<1..100>` ; réponse `{ "items": [...], "next_cursor": "..." | null }`.
- Erreurs : `{ "error": { "code": "<code>", "message": "<texte traduit>", "fields": { "<champ>": "<code>" } } }`.

| HTTP | code | Quand |
|---|---|---|
| 401 | `not_authenticated` | pas de session valide |
| 401 | `invalid_credentials` | e-mail ou mot de passe incorrect à la connexion |
| 403 | `forbidden` | rôle insuffisant dans l'organisation |
| 404 | `not_found` | absent ou hors de l'organisation |
| 409 | `invalid_state` | transition interdite (prono non ouvert, déjà résolu…) |
| 409 | `already_bet`, `insufficient_balance`, `insufficient_coins`, `pseudo_taken`, `email_taken`, `invitation_invalid`, `token_invalid`, `last_editor`, `attempts_exhausted`, `game_not_scheduled` | règles métier (`token_invalid` : lien de vérification ou de réinitialisation expiré ou déjà utilisé ; `game_not_scheduled` : jeu absent du programme de la semaine) |
| 413 | `too_large` | image > 5 Mo |
| 422 | `validation_error` | champs invalides (`fields`) |
| 429 | `rate_limited` | trop de tentatives |

## Comptes et session

L'inscription, la connexion, les mots de passe et la confirmation d'adresse passent par Keycloak
depuis la fonctionnalité 002 : les routes `/auth/*` et celles de `/me` qui en dépendent sont
décrites dans `specs/002-keycloak-auth/contracts/auth.md`, qui remplace ici `POST /auth/signup`,
`POST /auth/login`, `POST /auth/verify-email`, `POST /auth/password-reset`,
`POST /auth/password-reset/confirm` et `POST /me/password` (retirées).

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/auth/login`, `/auth/callback` | Public | l'aller-retour par Keycloak : `specs/002-keycloak-auth/contracts/auth.md` |
| POST | `/auth/logout` | Compte | → `204` ; ferme aussi la session Keycloak (002) |
| POST | `/auth/verify-email/resend` | Compte | → `204` ; Keycloak envoie l'e-mail (002) |
| GET | `/me` | Compte | → `Me` |
| PATCH | `/me` | Compte | `{theme?, reduce_motion?, locale?}` → `Me` ; les noms changent dans Keycloak (002) |
| GET | `/me/export` | Compte | → fichier JSON `sibylle-mes-donnees-AAAA-MM-JJ.json` (compte, rédactions, paris, relevés de lauriers et de pièces, collections, trophées, signalements, préférences, appareils sans leur adresse push) |
| DELETE | `/me` | Compte | `{confirm: true}` → `204` (cookie effacé) ; `409 last_editor` avec `fields.org_id` si seule rédaction en chef d'une rédaction qui a d'autres membres |
| GET | `/me/notification-prefs` | Compte | → `[{type, channel, enabled}]` |
| PUT | `/me/notification-prefs` | Compte | `[{type, channel, enabled}]` → idem |
| GET | `/push/vapid-public-key` | Compte | → `{key}` (`null` si le serveur n'a pas de clés VAPID) |
| POST | `/me/push-subscriptions` | Compte | `{endpoint, keys: {p256dh, auth}}` → `201 {id}` ; un appareil déjà connu revient au compte connecté ; `422` si `endpoint` n'est pas un service push de navigateur |
| DELETE | `/me/push-subscriptions/{id}` | Compte | → `204` |

`Me` = `{id, email, first_name, last_name, email_verified, theme, reduce_motion, locale, memberships: [{org: OrgCard, membership: MemberSelf}]}`. C'est la seule réponse qui contient le nom, le prénom et l'e-mail.

## Organisations, invitations, membres

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| POST | `/orgs` | Compte | `{title, background_key, logo?, pseudo, avatar}` → `201 {org: Org, membership: MemberSelf}` ; le créateur est `editor` ; sans `logo`, la rédaction prend le logo par défaut |
| GET | `/orgs/{org}` | Membre | → `Org` (carte, réglages de lauriers, charte, mot de la rédaction en chef, `member_count`, `edition_number` : le jour de la rédaction, « N° 305 », `my_membership`) |
| PATCH | `/orgs/{org}` | Réd. chef | `{title?, logo?, background_key?, starting_balance?, max_base_gain?, early_bird_pct?, early_bird_count?, editor_note?, charter?}` → `Org` ; `logo: null` remet le logo par défaut (`OrgCard.logo` n'est jamais `null`) |
| DELETE | `/orgs/{org}` | Réd. chef | → `204` ; suppression douce : la rédaction disparaît aussitôt pour tous ses membres (`404` partout), et ni ses invitations ni son code ne laissent entrer ; rien n'est effacé, et `sibylle orgs restore <org>` la rend telle qu'elle était (`sibylle orgs deleted` liste les rédactions supprimées) |
| POST | `/orgs/{org}/access-code` | Réd. chef | → `{access_code}` (nouveau code ; l'ancien ne marche plus) |
| DELETE | `/orgs/{org}/access-code` | Réd. chef | → `204` (désactive) |
| POST | `/join/preview` | Compte | `{token}` ou `{code}` → `{org: OrgCard, member_count, places_left, invited_by_pseudo, role, charter, already_member}` (`role` : celui de l'invitation, `reader` par le code) ou `409 invitation_invalid` |
| POST | `/join` | Compte | `{token \| code, pseudo, avatar, charter_accepted: true}` → `201 {org, membership}` ; chacun prend le rôle de l'invitation (`reader` par le code) ; un ancien membre retrouve son profil |
| GET | `/orgs/{org}/invitations` | Réd. chef | → `[Invitation]` |
| POST | `/orgs/{org}/invitations` | Réd. chef | `{kind: "link", max_uses, expires_at, role?}` → `201 {invitation, url}` (l'URL n'est montrée qu'une fois) ; `{kind: "email", email, role?}` → `201 {invitation}` et envoi ; `role` : `reader` (par défaut), `journalist` ou `editor` |
| DELETE | `/orgs/{org}/invitations/{id}` | Réd. chef | → `204` (révoque) |
| GET | `/orgs/{org}/members` | Membre | → `[MemberPublic + {streak, balance}]` : `streak`, la chaîne de victoires en cours (research.md J8) ; `balance`, ses lauriers verts, ceux que montre sa carte de presse (la rédaction en chef les ajuste depuis cette liste) |
| GET | `/orgs/{org}/members/{member}` | Membre | → `PressCard` (carte de presse : pseudo, avatar, cadre, rôle, arrivée, statistiques `{laurels, pronos_played, settled, wins, success_rate, streak, best_streak}` (`laurels` : les lauriers verts, le solde, le même nombre que dans l'en-tête du membre), trophées `{id, season, score, rank, podium}`, collection, `showcase`) ; tout membre de la rédaction peut la lire |
| PATCH | `/orgs/{org}/members/me` | Membre | `{pseudo?, avatar?, avatar_frame_item_id?, avatar_animation_item_id?, showcase?: [{kind: "item" \| "trophy", id}], card_public?}` → `MemberSelf` ; `showcase` remplace toute la sélection : 3 au plus (`fields.showcase` : `too_many`, `duplicate`, `not_owned`) ; `card_public` rend la carte publique ou privée (US15), et la première mise en public tire `card_token` |
| DELETE | `/orgs/{org}/members/me` | Membre | → `204` (quitter ; la dernière personne qui part ferme la rédaction) ; `409 last_editor` avec `fields.org_id` |
| PATCH | `/orgs/{org}/members/{member}/role` | Réd. chef | `{role}` → `MemberPublic` ; `409 last_editor` si on retire la dernière |
| DELETE | `/orgs/{org}/members/{member}` | Réd. chef | → `204` (retire un membre) |
| POST | `/orgs/{org}/members/{member}/adjustments` | Réd. chef | `{amount (≠ 0), reason}` → `201 LedgerEntry` |
| GET | `/orgs/{org}/members/me/ledger` | Membre | `?cursor=&limit=` → `{items: [LedgerEntry], next_cursor}` (relevé, du plus récent au plus ancien) |
| GET | `/orgs/{org}/sections` | Membre | → `[Section]` |
| POST | `/orgs/{org}/sections` | Réd. chef | `{name}` → `201 Section` |
| PATCH | `/orgs/{org}/sections/{id}` | Réd. chef | `{name?, position?}` → `Section` |
| DELETE | `/orgs/{org}/sections/{id}` | Réd. chef | → `204` (archive si utilisée) |

`PressCard.showcase` = `[{kind: "item", item} | {kind: "trophy", trophy}]`, dans l'ordre choisi ; un objet qui n'appartient plus au membre n'y figure pas.

`MemberPublic` = `{id, pseudo, avatar, frame, animation, role, joined_at}` (`frame` et `animation` : les clés du cadre et de l'animation portés, ou `null`), jamais de nom, prénom ni e-mail. `MemberSelf` ajoute `balance` (lauriers verts), `gold` (lauriers en or : solde plus mises en jeu), `season_score`, `coins`, `unlocked_colors`, `card_public` et `card_token` (l'adresse de la carte publique est `/carte/<card_token>` ; `null` tant que la carte n'a jamais été publique).

## Pronos et paris

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/front-page` | Membre | → `FrontPage` : `{headline, open, open_count, to_designate (journalistes seulement), latest_results, leaderboard_top (les cinq premiers de la saison par lauriers verts, puis la ligne du membre s'il n'en est pas ; chaque ligne avec sa streak), leaderboard_period ("2026-autumn"), editor_note}` ; `headline` et `open` sont des `FrontProno` = `PronoSummary` + `{options, distribution}` (la jauge de la une) ; l'encadré des jeux lit `GET /orgs/{org}/games` |
| GET | `/orgs/{org}/pronos` | Membre | `?state=&section=&cursor=` → `[PronoSummary]` |
| POST | `/orgs/{org}/pronos` | Membre | `PronoInput` → `201 PronoDetail` ; état `open`/`scheduled` pour un·e journaliste, `proposed` pour un·e lecteur·rice |
| GET | `/orgs/{org}/pronos/{id}` | Membre | → `PronoDetail` |
| PATCH | `/orgs/{org}/pronos/{id}` | créateur journaliste, Réd. chef | `PronoInput` partiel → `PronoDetail` ; `409 invalid_state` dès le premier pari |
| POST | `/orgs/{org}/pronos/{id}/validate` | Journaliste | `{base_gain?}` → `PronoDetail` |
| POST | `/orgs/{org}/pronos/{id}/reject` | Journaliste | `{reason?}` → `PronoDetail` |
| POST | `/orgs/{org}/pronos/{id}/bets` | Membre | `{option_id \| number_value \| date_value, stake}` → `201 Bet` ; erreurs `invalid_state`, `already_bet`, `insufficient_balance` |
| POST | `/orgs/{org}/pronos/{id}/resolve` | Journaliste | `{correct_option_ids}` ou `{result_number}` ou `{result_date}` → `PronoDetail` (avec `special_edition`) |
| POST | `/orgs/{org}/pronos/{id}/relaunch` | Journaliste | `{closes_at, result_expected_at?, reason}` → `PronoDetail` |
| POST | `/orgs/{org}/pronos/{id}/correct` | Réd. chef | même corps que `resolve` → `PronoDetail` |
| POST | `/orgs/{org}/pronos/{id}/cancel` | Réd. chef | `{reason}` → `PronoDetail` |
| PUT | `/orgs/{org}/pronos/{id}/reactions/{kind}` | Membre | → `204` (ajoute) |
| DELETE | `/orgs/{org}/pronos/{id}/reactions/{kind}` | Membre | → `204` (retire) |
| GET | `/orgs/{org}/pronos/{id}/messages` | Membre | `?before=<message>&limit=` → `{items: [Message], has_more}` : les `limit` messages (20 par défaut, 50 au plus) écrits avant `before`, ou les derniers, rangés du plus ancien au plus récent ; `has_more` dit s'il en reste de plus anciens ; `409 invalid_state` pour un prono proposé ou refusé (`404` pour qui ne le voit pas) |
| POST | `/orgs/{org}/pronos/{id}/messages` | Membre | `{body}` → `201 Message` ; `409 invalid_state` pour un prono proposé ou refusé ; `422` si `body` est vide une fois les espaces retirés, ou dépasse 500 caractères |
| DELETE | `/orgs/{org}/pronos/{id}/messages/{message}` | auteur·rice, Réd. chef | → `204` ; `403` pour le message d'un autre |
| PUT | `/orgs/{org}/pronos/{id}/messages/{message}/like` | Membre | → `204` (aime ; deux fois ne change rien) |
| DELETE | `/orgs/{org}/pronos/{id}/messages/{message}/like` | Membre | → `204` (n'aime plus) |
| POST | `/orgs/{org}/pronos/{id}/reports` | Membre | `{kind: "result_error" \| "content", message?}` → `201 Report` |
| POST | `/orgs/{org}/uploads` | Membre | `multipart/form-data` `file` → `201 {id, width, height}` |
| GET | `/orgs/{org}/uploads/{id}` | Membre | → `image/webp` |

`PronoInput` = `{kind, question, section_id, options?: [label], base_gain, link_url?, image_id?, opens_at?, closes_at?, open_ended?, result_expected_at?, number_unit?}`.

`PronoDetail` = `PronoSummary` + `{options: [{id, label, is_correct, count, stake_total, share_pct}], bets: [{member: MemberPublic, answer, stake, rank, placed_at, outcome, payout}], my_bet, can_rebet, pot, reactions: {kind: count}, my_reactions, events: [PronoEvent], special_edition?: {winners: [{member, payout}], pot_lost: bool, settlement_seq, settled_by: MemberPublic}, rejected_reason?, my_reports: [Report]}` (`my_reports` : les signalements du membre sur ce prono, avec la note de traitement). Pour un prono de nombre ou de date, `options` est remplacé par `distribution` (valeurs regroupées en tranches pour l'affichage).

`PronoSummary` = `{id, number, kind, question, section, state, base_gain, opens_at, closes_at, open_ended, result_expected_at, bet_count, pot, relaunch_count, message_count, created_by: MemberPublic, image_url?}`.

`Message` = `{id, author: MemberPublic, body, created_at, likes, liked, likers: [pseudo], can_delete}` : `liked`, si le membre qui lit l'aime ; `likers`, les pseudos de qui l'aime, dans l'ordre des « J'aime » ; `can_delete`, pour son auteur·rice et la rédaction en chef.

## Classements, signalements, collection

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/leaderboard` | Membre | `?metric=laurels\|wins&period=month\|season\|all_time` (pas de `month` pour `laurels` : `422`, `period: not_for_metric`) → `{period_label, rows: [{rank, member: MemberPublic, value, is_me, streak}]}` ; `streak` : la chaîne de victoires en cours, quelle que soit la période |
| GET | `/orgs/{org}/seasons/current` | Membre | → `{year, name, starts_at, ends_at}` |
| GET | `/orgs/{org}/reports` | Réd. chef | `?state=open` → `[Report]` |
| POST | `/orgs/{org}/reports/{id}/handle` | Réd. chef | `{state: "resolved" \| "dismissed", note?}` → `Report` |
| GET | `/orgs/{org}/catalog` | Membre | → `[{item, price, regular_price, discount_pct, discount_until, owned}]` : ce qui est à vendre (couleurs, cadres, animations), plus les objets sans prix que le membre a débloqués ; les boules ne sont jamais à vendre. `price` est le prix de cette semaine : pour la promotion de la semaine (un seul objet), `discount_pct` vaut 20, 30, 40 ou 50, `regular_price` le prix habituel et `discount_until` le lundi suivant 00:00 (Paris) ; sinon ces trois champs valent `null` |
| POST | `/orgs/{org}/catalog/{item}/purchase` | Membre | `{price?}` (le prix affiché) → `201 {owned_item, coins}` ; payé en pièces, au prix de la semaine ; `insufficient_coins` ; `409 price_changed` si `price` n'est plus le prix de la semaine |
| GET | `/orgs/{org}/coins/weekly` | Membre | → `WeeklyCoins` ou `null` : la dernière conversion pas encore annoncée (montant > 0) |
| POST | `/orgs/{org}/coins/weekly/seen` | Membre | `{week_start}` → `204` ; la fenêtre ne revient plus pour cette semaine ni les précédentes |
| POST | `/orgs/{org}/secret-codes/redeem` | Membre | `{code}` → `201 {item}` ; limité en débit |

`WeeklyCoins` = `{week_start, gold, amount}` : le lundi de la conversion, les lauriers en or de ce moment-là et les pièces reçues.

## Jeux de la semaine

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/games` | Membre | → `{scheduled, runner, pixel}`. `scheduled` : les jeux de la semaine en cours, parmi `"runner"` et `"pixel"`. `runner` : `{week_start, attempts_left, my_best, top: [{member, score, rank}] (10 premiers)}`, ou `null` si la course n'est pas au programme. `pixel` : `PixelStatus \| null` (hors programme, seulement le dernier dessin terminé, avec son mot) |
| POST | `/orgs/{org}/games/runner/runs` | Membre | → `201 {run_id, seed}` (une partie ouverte compte comme un essai, même jamais finie) ; `409 attempts_exhausted` ; `409 game_not_scheduled` si la course n'est pas au programme de la semaine |
| POST | `/orgs/{org}/games/runner/runs/{run}/finish` | Membre | `{score, duration_ms}` → `{score, my_best, rank}` ; `409 run_finished` ; `409 game_not_scheduled` si la course n'est plus au programme de la semaine de la partie ; `422` si invraisemblable (`score` au-delà de 90 points par seconde, `duration_ms` plus longue que la partie ou au-delà de 30 min) |
| GET | `/orgs/{org}/games/pixel` | Membre | → `PixelStatus \| null` : `{puzzle_id, size, revealed, revealed_count, letters, guesses_left_today, finds: [{member, rank}], found_by_me, mine, state, word, ends_at}`. `ends_at` : la fin du dessin en cours sauf si tout le monde trouve avant (le matin où ses derniers pixels se dévoilent, ou le lundi d'une semaine sans Pixel mystère s'il vient avant), `null` une fois terminé. `revealed` : le dessin en base64, un octet par pixel, 255 pour un pixel encore caché ; dessin entier et `word` seulement pour qui a trouvé, pour l'auteur·rice ou à la fin (sinon `word` vaut `null`). Le dessin actif, ou le dernier terminé tant que le suivant n'a pas démarré ; hors programme, seulement le dernier dessin terminé |
| POST | `/orgs/{org}/games/pixel/guesses` | Membre | `{word}` → `{correct, rank, laurels, guesses_left_today}` ; `403` pour l'auteur·rice ; `409 attempts_exhausted` au 4ᵉ essai du jour ; `409 invalid_state` sans dessin actif ou après avoir trouvé ; `409 game_not_scheduled` si Pixel mystère n'est pas au programme de la semaine |
| GET | `/orgs/{org}/games/pixel/puzzles` | Journaliste | → `[{puzzle_id, state, size, letters, mine, word, drawing, created_at}]` : le dessin en cours puis ceux qui attendent ; `word` et `drawing` seulement pour ses propres dessins |
| POST | `/orgs/{org}/games/pixel/puzzles` | Journaliste | `{drawing: PixelImage, word}` → `201` (même forme qu'un élément de la file : `state` dit s'il démarre tout de suite ou attend ; une semaine sans Pixel mystère, il attend) ; `422` si le mot n'est pas fait de lettres (2 au moins, 24 caractères au plus) |
| GET | `/orgs/{org}/games/schedule` | Réd. chef | → `GameSchedule` |
| PUT | `/orgs/{org}/games/schedule/default` | Réd. chef | `{games}` → `GameSchedule` : les jeux d'une semaine ordinaire, à partir de la semaine suivante |
| PUT | `/orgs/{org}/games/schedule/weeks/{week_start}` | Réd. chef | `{games}` → `GameSchedule` ; `422` avec `fields.week_start` : `not_monday`, ou `out_of_range` hors de la semaine en cours et des 3 suivantes. Pour la semaine en cours, un jeu retiré s'arrête aussitôt (research.md J7) et l'événement `games.schedule.changed` part |
| DELETE | `/orgs/{org}/games/schedule/weeks/{week_start}` | Réd. chef | → `GameSchedule` : la semaine redevient ordinaire ; `409 invalid_state` pour la semaine en cours ; `422` comme ci-dessus |

`GameSchedule` = `{default: [game], weeks: [{week_start, games: [game], planned}]}`. `default` : les jeux d'une semaine ordinaire à partir de la semaine suivante. `weeks` : la semaine en cours puis les 3 suivantes, avec leurs jeux ; `planned` est vrai si la semaine a son propre programme. Un `game` vaut `"runner"` ou `"pixel"` ; une liste `games` revient dans cet ordre, sans doublon, et peut être vide.

## Divers

| Méthode | Route | Qui | Réponse |
|---|---|---|---|
| GET | `/health` | Public | `{status: "ok", db: "ok"}` |
| GET | `/content` | Public | `{avatars: [{key, name, image}], logos: [...], backgrounds: [clé], charter}` : modèles d'avatars et de logo, fonds de carte, charte par défaut |
| GET | `/ws` | Compte | passage en WebSocket, voir [realtime.md](realtime.md) |
| GET | `/public/cards/{token}` | Public | → `PublicCard` (US15) ; `404 not_found` si la carte est privée, si son membre a quitté la rédaction ou supprimé son compte, ou si le jeton est inconnu ; `429 rate_limited` au-delà de 600 lectures par IP en 10 minutes |

`PublicCard` = `{newsroom: {title, logo}, pseudo, avatar, frame, animation, role, joined_at, card_number, stats, showcase}` : la carte seule, sans l'identifiant du membre, ses trophées ni sa collection hors des objets mis en avant.

## Tests de contrat attendus

- Pour chaque route : la réponse respecte le schéma OpenAPI.
- Pour chaque route sous `/orgs/{org}` : un compte d'une autre organisation reçoit `404` ; un rôle insuffisant reçoit `403`.
- Aucune réponse, hors `/me` et `/me/export`, ne contient `email`, `first_name` ou `last_name`.
- Les requêtes qui modifient sans `X-Sibylle` ou avec un autre `Origin` reçoivent `403`.
