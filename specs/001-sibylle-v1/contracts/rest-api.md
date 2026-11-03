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
| 409 | `already_bet`, `insufficient_balance`, `insufficient_coins`, `pseudo_taken`, `email_taken`, `invitation_invalid`, `token_invalid`, `last_editor`, `attempts_exhausted` | règles métier (`token_invalid` : lien de vérification ou de réinitialisation expiré ou déjà utilisé) |
| 413 | `too_large` | image > 5 Mo |
| 422 | `validation_error` | champs invalides (`fields`) |
| 429 | `rate_limited` | trop de tentatives |

## Comptes et session

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| POST | `/auth/signup` | Public | `{email, password, first_name, last_name}` → `201 Me` + cookie ; envoie l'e-mail de vérification |
| POST | `/auth/login` | Public | `{email, password}` → `200 Me` + cookie |
| POST | `/auth/logout` | Compte | → `204` |
| POST | `/auth/verify-email` | Public | `{token}` → `204` |
| POST | `/auth/verify-email/resend` | Compte | → `204` |
| POST | `/auth/password-reset` | Public | `{email}` → `202` (toujours, que l'adresse existe ou non) |
| POST | `/auth/password-reset/confirm` | Public | `{token, password}` → `204` ; ferme les autres sessions |
| GET | `/me` | Compte | → `Me` |
| PATCH | `/me` | Compte | `{first_name?, last_name?, theme?, reduce_motion?, locale?}` → `Me` |
| POST | `/me/password` | Compte | `{current_password, new_password}` → `204` |
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
| POST | `/orgs` | Compte | `{title, background_key, logo?, pseudo, avatar}` → `201 {org: Org, membership: MemberSelf}` ; le créateur est `editor` |
| GET | `/orgs/{org}` | Membre | → `Org` (carte, réglages de lauriers, charte, mot de la rédaction en chef, `my_membership`) |
| PATCH | `/orgs/{org}` | Réd. chef | `{title?, logo?, background_key?, starting_balance?, max_base_gain?, early_bird_pct?, early_bird_count?, editor_note?, charter?}` → `Org` |
| POST | `/orgs/{org}/access-code` | Réd. chef | → `{access_code}` (nouveau code ; l'ancien ne marche plus) |
| DELETE | `/orgs/{org}/access-code` | Réd. chef | → `204` (désactive) |
| POST | `/join/preview` | Compte | `{token}` ou `{code}` → `{org: OrgCard, member_count, places_left, invited_by_pseudo, charter}` ou `409 invitation_invalid` |
| POST | `/join` | Compte | `{token \| code, pseudo, avatar, charter_accepted: true}` → `201 {org, membership}` ; un ancien membre retrouve son profil |
| GET | `/orgs/{org}/invitations` | Réd. chef | → `[Invitation]` |
| POST | `/orgs/{org}/invitations` | Réd. chef | `{kind: "link", max_uses, expires_at}` → `201 {invitation, url}` (l'URL n'est montrée qu'une fois) ; `{kind: "email", email}` → `201 {invitation}` et envoi |
| DELETE | `/orgs/{org}/invitations/{id}` | Réd. chef | → `204` (révoque) |
| GET | `/orgs/{org}/members` | Membre | → `[MemberPublic]` |
| GET | `/orgs/{org}/members/{member}` | Membre | → `PressCard` (carte de presse : pseudo, avatar, cadre, rôle, arrivée, statistiques, trophées, collection) |
| PATCH | `/orgs/{org}/members/me` | Membre | `{pseudo?, avatar?, avatar_frame_item_id?}` → `MemberSelf` |
| DELETE | `/orgs/{org}/members/me` | Membre | → `204` (quitter ; la dernière personne qui part ferme la rédaction) ; `409 last_editor` avec `fields.org_id` |
| PATCH | `/orgs/{org}/members/{member}/role` | Réd. chef | `{role}` → `MemberPublic` ; `409 last_editor` si on retire la dernière |
| DELETE | `/orgs/{org}/members/{member}` | Réd. chef | → `204` (retire un membre) |
| POST | `/orgs/{org}/members/{member}/adjustments` | Réd. chef | `{amount (≠ 0), reason}` → `201 LedgerEntry` |
| GET | `/orgs/{org}/members/me/ledger` | Membre | `?cursor=&limit=` → `{items: [LedgerEntry], next_cursor}` (relevé, du plus récent au plus ancien) |
| GET | `/orgs/{org}/sections` | Membre | → `[Section]` |
| POST | `/orgs/{org}/sections` | Réd. chef | `{name}` → `201 Section` |
| PATCH | `/orgs/{org}/sections/{id}` | Réd. chef | `{name?, position?}` → `Section` |
| DELETE | `/orgs/{org}/sections/{id}` | Réd. chef | → `204` (archive si utilisée) |

`MemberPublic` = `{id, pseudo, avatar, frame, role, joined_at}`, jamais de nom, prénom ni e-mail. `MemberSelf` ajoute `balance` (lauriers verts), `gold` (lauriers en or : solde plus mises en jeu), `season_score`, `coins`, `unlocked_colors`.

## Pronos et paris

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/front-page` | Membre | → `FrontPage` : `{headline, open, to_designate (journalistes seulement), latest_results, leaderboard_top, games, editor_note}` |
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
| POST | `/orgs/{org}/pronos/{id}/reports` | Membre | `{kind: "result_error" \| "content", message?}` → `201 Report` |
| POST | `/orgs/{org}/uploads` | Membre | `multipart/form-data` `file` → `201 {id, width, height}` |
| GET | `/orgs/{org}/uploads/{id}` | Membre | → `image/webp` |

`PronoInput` = `{kind, question, section_id, options?: [label], base_gain, link_url?, image_id?, opens_at?, closes_at?, open_ended?, result_expected_at?, number_unit?}`.

`PronoDetail` = `PronoSummary` + `{options: [{id, label, is_correct, count, stake_total, share_pct}], bets: [{member: MemberPublic, answer, stake, rank, placed_at, outcome, payout}], my_bet, can_rebet, pot, reactions: {kind: count}, my_reactions, events: [PronoEvent], special_edition?: {winners: [{member, payout}], pot_lost: bool, settlement_seq}, rejected_reason?, my_reports: [Report]}` (`my_reports` : les signalements du membre sur ce prono, avec la note de traitement). Pour un prono de nombre ou de date, `options` est remplacé par `distribution` (valeurs regroupées en tranches pour l'affichage).

`PronoSummary` = `{id, kind, question, section, state, base_gain, opens_at, closes_at, open_ended, result_expected_at, bet_count, pot, relaunch_count, created_by: MemberPublic, image_url?}`.

## Classements, signalements, collection

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/leaderboard` | Membre | `?metric=laurels\|wins&period=month\|season\|all_time` → `{period_label, rows: [{rank, member: MemberPublic, value, is_me}]}` |
| GET | `/orgs/{org}/seasons/current` | Membre | → `{year, name, starts_at, ends_at}` |
| GET | `/orgs/{org}/reports` | Réd. chef | `?state=open` → `[Report]` |
| POST | `/orgs/{org}/reports/{id}/handle` | Réd. chef | `{state: "resolved" \| "dismissed", note?}` → `Report` |
| GET | `/orgs/{org}/catalog` | Membre | → `[{item, price, owned}]` |
| POST | `/orgs/{org}/catalog/{item}/purchase` | Membre | → `201 {owned_item, coins}` ; payé en pièces ; `insufficient_coins` |
| GET | `/orgs/{org}/coins/weekly` | Membre | → `WeeklyCoins` ou `null` : la dernière conversion pas encore annoncée (montant > 0) |
| POST | `/orgs/{org}/coins/weekly/seen` | Membre | `{week_start}` → `204` ; la fenêtre ne revient plus pour cette semaine ni les précédentes |
| POST | `/orgs/{org}/secret-codes/redeem` | Membre | `{code}` → `201 {item}` ; limité en débit |

`WeeklyCoins` = `{week_start, gold, amount}` : le lundi de la conversion, les lauriers en or de ce moment-là et les pièces reçues.

## Jeux de la semaine

| Méthode | Route | Qui | Corps → Réponse |
|---|---|---|---|
| GET | `/orgs/{org}/games` | Membre | → `{runner: {week_start, attempts_left, my_best, top: [...]}, pixel: PixelStatus \| null}` |
| POST | `/orgs/{org}/games/runner/runs` | Membre | → `201 {run_id, seed}` ; `409 attempts_exhausted` |
| POST | `/orgs/{org}/games/runner/runs/{run}/finish` | Membre | `{score, duration_ms}` → `{score, my_best, rank}` ; `422` si invraisemblable |
| GET | `/orgs/{org}/games/pixel` | Membre | → `PixelStatus` : `{puzzle_id, size, revealed: "<base64 masqué>", letters, guesses_left_today, finds: [{member, rank}], found_by_me, state, word?}` (`word` seulement si trouvé ou terminé) |
| POST | `/orgs/{org}/games/pixel/guesses` | Membre | `{word}` → `{correct, rank?, laurels?, guesses_left_today}` |
| GET | `/orgs/{org}/games/pixel/puzzles` | Journaliste | → file des dessins à venir |
| POST | `/orgs/{org}/games/pixel/puzzles` | Journaliste | `{drawing: PixelImage, word}` → `201` |

## Divers

| Méthode | Route | Qui | Réponse |
|---|---|---|---|
| GET | `/health` | Public | `{status: "ok", db: "ok"}` |
| GET | `/content` | Public | `{avatars: [{key, name, image}], logos: [...], backgrounds: [clé], charter}` : modèles d'avatars et de logo, fonds de carte, charte par défaut |
| GET | `/ws` | Compte | passage en WebSocket, voir [realtime.md](realtime.md) |

## Tests de contrat attendus

- Pour chaque route : la réponse respecte le schéma OpenAPI.
- Pour chaque route sous `/orgs/{org}` : un compte d'une autre organisation reçoit `404` ; un rôle insuffisant reçoit `403`.
- Aucune réponse, hors `/me` et `/me/export`, ne contient `email`, `first_name` ou `last_name`.
- Les requêtes qui modifient sans `X-Sibylle` ou avec un autre `Origin` reçoivent `403`.
