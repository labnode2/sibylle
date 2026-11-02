# Data Model: Sybille v1

**Feature**: `001-sybille-v1` | **Date**: 2026-11-01 | **Plan**: [plan.md](plan.md)

PostgreSQL 18. Identifiants `uuid` (v7, triables par date) sauf mention contraire ; instants en `timestamptz` (UTC) ; lauriers en `integer`. Les noms de tables et de colonnes sont en anglais, comme le code ; le vocabulaire de l'interface (prono, pari, rédaction…) est donné entre parenthèses.

## Types communs

- **PixelImage** (`jsonb`) : `{ "size": 16 | 32, "palette": "base-v1", "pixels": "<base64>" }`. `pixels` contient `size × size` octets, un indice de palette par pixel, 0 = transparent. Validé par le serveur : taille exacte, indices connus, couleurs hors palette de base possédées par le membre (voir `owned_items`).
- **Role** : `reader` (lecteur·rice), `journalist` (journaliste), `editor` (rédaction en chef).
- **PronoKind** : `choice`, `yes_no`, `number`, `date`.

## Comptes

### accounts (compte)

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| email | citext | unique ; `NULL` après suppression |
| password_hash | text | Argon2id ; `NULL` après suppression |
| first_name, last_name | text | privés, jamais exposés à un autre compte |
| email_verified_at | timestamptz | `NULL` tant que non vérifié |
| locale | text | `fr` par défaut |
| theme | text | `auto`, `light`, `dark` |
| reduce_motion | boolean | `false` |
| created_at, deleted_at | timestamptz | `deleted_at` posé à la suppression |

### sessions

`id`, `account_id` → accounts, `token_hash` (unique, SHA-256 du jeton du cookie), `created_at`, `last_seen_at`, `expires_at` (30 jours glissants), `user_agent`. Supprimées à la déconnexion, au changement de mot de passe (sauf la session courante) et à la suppression du compte.

### email_tokens

`id`, `account_id`, `purpose` (`verify_email`, `reset_password`), `token_hash` (unique), `expires_at` (24 h pour la vérification, 1 h pour la réinitialisation), `used_at`. Usage unique.

### notification_prefs (préférences de notification)

PK (`account_id`, `type`, `channel`) ; `type` ∈ `new_prono`, `closing_soon`, `result`, `designation_reminder` ; `channel` ∈ `push`, `email` ; `enabled` (vrai par défaut, ligne créée à la première modification).

### push_subscriptions

`id`, `account_id`, `endpoint` (unique), `p256dh`, `auth`, `user_agent`, `created_at`, `last_success_at`. Supprimée quand le service push répond 404 ou 410.

## Organisations

### organisations (rédaction)

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| title | text | 1 à 40 caractères |
| logo | PixelImage | facultatif |
| background_key | text | une clé de la liste de fonds de la plateforme |
| access_code | text | unique, `NULL` si désactivé ; régénérable |
| starting_balance | integer | ≥ 0, défaut 100 |
| max_base_gain | integer | ≥ 0, défaut 50 |
| early_bird_pct | integer | 0 à 100, défaut 20 |
| early_bird_count | integer | ≥ 0, défaut 5 |
| editor_note | text | « le mot de la rédaction en chef », facultatif |
| charter | text | charte acceptée en rejoignant, texte par défaut fourni |
| created_at, deleted_at | timestamptz | |

### memberships (membre)

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| org_id, account_id | uuid | unique (`org_id`, `account_id`) |
| role | Role | `reader` à l'arrivée ; `editor` pour le créateur |
| status | text | `active`, `left`, `anonymized` |
| pseudo | text | 2 à 24 caractères ; unique par organisation (insensible à la casse) parmi les statuts `active` et `left` |
| avatar | PixelImage | choisi parmi les modèles à l'arrivée |
| avatar_frame_item_id | uuid | → catalog_items (cadre), facultatif |
| balance | integer | cache du solde (somme du registre depuis la dernière remise au solde) |
| season_score | integer | cache du score de la saison en cours |
| joined_at, charter_accepted_at, left_at | timestamptz | |

Règles : au moins un `editor` actif par organisation qui a des membres actifs ; un retour après départ réactive la même ligne (`status = active`) ; l'anonymisation remplace le pseudo par « Ancien membre » et l'avatar par le modèle par défaut.

### invitations

`id`, `org_id`, `kind` (`link`, `email`), `token_hash` (unique), `email` (pour `email` seulement), `max_uses` (≥ 1 ; 1 pour `email`), `use_count`, `expires_at` (obligatoire ; 7 jours par défaut pour `email`), `created_by` → memberships, `revoked_at`, `created_at`. Valide si non révoquée, non expirée et `use_count < max_uses` ; l'utilisation verrouille la ligne.

### sections (rubrique)

`id`, `org_id`, `name` (unique par organisation, insensible à la casse), `position`, `archived_at`. Une rubrique utilisée est archivée plutôt que supprimée.

## Pronos et paris

### pronos

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| org_id, section_id | uuid | la rubrique appartient à la même organisation |
| kind | PronoKind | non modifiable après le premier pari |
| question | text | 5 à 200 caractères |
| link_url | text | `https` seulement, facultatif |
| image_id | uuid | → uploads, facultatif |
| base_gain | integer | 0 ≤ `base_gain` ≤ `organisations.max_base_gain` au moment de la création |
| state | text | voir les transitions ci-dessous |
| open_ended | boolean | vrai seulement pour `date` ; alors `closes_at` est `NULL` |
| opens_at | timestamptz | facultatif ; si futur, état `scheduled` |
| closes_at | timestamptz | obligatoire sauf `open_ended` ; > maintenant à la publication |
| result_expected_at | timestamptz | facultatif, ≥ `closes_at` |
| number_unit | text | facultatif, pour `number` (« buts », « °C »…) |
| created_by, validated_by | uuid | → memberships |
| rejected_reason | text | pour une proposition refusée |
| bet_count | integer | nombre de paris (y compris remplacés) ; sert au rang d'arrivée |
| pot | integer | somme des mises ; cache |
| relaunch_count | integer | |
| result_number | numeric(14,2) | pour `number` |
| result_date | date | pour `date` |
| resolved_at, resolved_by, cancelled_at, cancelled_by | | |
| created_at, updated_at | timestamptz | |

Index : (`org_id`, `state`, `closes_at`) pour la une et le `worker` ; (`org_id`, `section_id`).

### prono_options (choix)

`id`, `prono_id`, `label` (1 à 80 caractères), `position`, `is_correct` (`NULL` avant la désignation). Au moins 2 pour `choice` ; exactement « Oui » et « Non » créés automatiquement pour `yes_no` ; aucune pour `number` et `date`.

### prono_events (historique d'un prono)

`id`, `prono_id`, `kind` (`created`, `proposed`, `validated`, `rejected`, `edited`, `opened`, `closed`, `relaunched`, `resolved`, `corrected`, `cancelled`), `actor_membership_id`, `data` (jsonb : anciennes et nouvelles dates, résultat…), `created_at`. Sert à l'édition spéciale et à l'audit.

### bets (pari)

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| prono_id, membership_id | uuid | |
| option_id | uuid | pour `choice` et `yes_no` ; option du même prono |
| number_value | numeric(14,2) | pour `number` |
| date_value | date | pour `date` ; strictement après le jour du pari si `open_ended` |
| stake | integer | 0 ≤ `stake` ≤ solde au moment du pari |
| rank | integer | rang d'arrivée, ≥ 1, unique par prono |
| placed_at | timestamptz | heure du serveur |
| superseded_at, superseded_by_id | | pari remplacé (prono de date « sans fin ») |
| outcome | text | `pending`, `won`, `lost`, `refunded` |
| payout | integer | total versé au règlement (gain de base + lève-tôt + part de cagnotte) |
| settled_at | timestamptz | |

Contraintes : un seul pari actif par membre et par prono (index unique partiel `WHERE superseded_at IS NULL`) ; un pari ne se modifie jamais (seuls `superseded_*`, `outcome`, `payout`, `settled_at` évoluent) ; un nouveau pari d'un prono `open_ended` n'est permis que si la `date_value` du pari actif est passée.

### settlements (règlement)

`id`, `prono_id`, `seq` (1, 2, … par prono), `kind` (`resolution`, `correction`, `cancellation`), `result` (jsonb : options correctes ou valeur réelle), `created_by`, `created_at`, `reversed_by_id` (→ settlements, posé quand une correction ou une annulation l'annule). Toutes les écritures du registre d'un règlement y sont rattachées.

### Transitions d'état d'un prono

```text
proposed ──validation──▶ scheduled ──opens_at──▶ open ──closes_at──▶ closed ──désignation──▶ resolved
    │      (ou open si pas d'opens_at futur)          │                  │                       │
    └──refus──▶ rejected                              │                  └──relance──▶ open      └──correction──▶ resolved
                                                      └──désignation (date « sans fin »)──▶ resolved
scheduled | open | closed | resolved ──annulation (rédaction en chef)──▶ cancelled
```

| Transition | Qui | Conditions |
|---|---|---|
| validation, refus | journaliste, rédaction en chef | état `proposed` |
| ouverture, clôture | `worker` | heure atteinte |
| désignation | journaliste, rédaction en chef | état `closed`, ou `open` pour une date « sans fin » ; au moins une bonne réponse |
| relance | journaliste, rédaction en chef | état `closed` ; nouvelle `closes_at` future |
| correction | rédaction en chef | état `resolved` ; résultat différent |
| annulation | rédaction en chef | état `scheduled`, `open`, `closed` ou `resolved` |
| modification | créateur journaliste, rédaction en chef | `bet_count = 0` et état `proposed`, `scheduled` ou `open` |

Une relance remet `state = open`, change `closes_at` (et `result_expected_at`), incrémente `relaunch_count` et garde les paris et leur rang.

## Lauriers

### seasons (saison)

`id` (smallserial), `year`, `name` (`spring`, `summer`, `autumn`, `winter`), `starts_at`, `ends_at` ; unique (`year`, `name`). Bornes calculées en Europe/Paris (printemps 21 mars, été 21 juin, automne 23 septembre, hiver 21 décembre, à 00:00) ; l'hiver porte l'année de son début.

### ledger_entries (registre des lauriers)

| Colonne | Type | Règles |
|---|---|---|
| id | bigint | PK, identité |
| org_id, membership_id | uuid | |
| season_id | smallint | saison au moment de l'écriture |
| kind | text | voir ci-dessous |
| amount | integer | effet sur le solde (signé) |
| score_delta | integer | effet sur le score (signé) |
| prono_id, bet_id, settlement_id | uuid | selon le type |
| reverses_entry_id | bigint | pour une écriture inverse |
| reason | text | obligatoire pour `adjustment` |
| actor_membership_id | uuid | qui a provoqué l'écriture, si c'est une personne |
| created_at | timestamptz | |

Types et effets :

| kind | amount | score_delta |
|---|---|---|
| `starting_balance` | + solde de départ | 0 |
| `stake` | − mise | 0 |
| `base_gain`, `early_bird` | + gain | + gain |
| `pot_share` | + part | + (part − mise) |
| `stake_lost` | 0 | − mise |
| `refund` | + mise | 0 |
| `reversal` | − montant de l'écriture inversée | − score de l'écriture inversée |
| `purchase` | − prix | 0 |
| `minigame` | + gain | 0 |
| `adjustment` | ± montant | 0 |
| `season_reset` | solde de départ − solde courant | 0 |

Aucune mise à jour ni suppression (droit `INSERT` seulement pour le rôle de l'application sur cette table). `memberships.balance` et `memberships.season_score` sont mis à jour dans la même transaction. Le score de la saison se remet à zéro à la clôture de saison (par construction : le cache repart à 0, les sommes se font par `season_id`). Index : (`membership_id`, `created_at`), (`org_id`, `season_id`, `kind`), (`settlement_id`).

### season_closures

PK (`org_id`, `season_id`), `closed_at`. Écrite dans la même transaction que les trophées et les remises au solde, ce qui rend la clôture idempotente.

### trophies (trophée)

`id`, `membership_id`, `season_id`, `score`, `rank` (classement de fin de saison, ex aequo au même rang), `podium` (rang ≤ 3), `created_at` ; unique (`membership_id`, `season_id`). Créé pour chaque membre qui a au moins un pari placé dans la saison.

## Collection

### catalog_items (objet du catalogue)

`id`, `kind` (`ball`, `color`, `frame`), `key` (unique), `name_key` (clé de traduction), `price` (`NULL` si non achetable : objet de code secret), `season` (pour les boules saisonnières), `data` (jsonb : couleur, sprite), `active`.

### owned_items

`id`, `membership_id`, `item_id`, `source` (`purchase`, `secret_code`), `acquired_at` ; unique (`membership_id`, `item_id`). Un achat écrit aussi une ligne `purchase` au registre. Les trophées restent dans `trophies` et s'affichent dans la collection.

### secret_codes, secret_code_redemptions

`secret_codes` : `id`, `code_hash` (unique), `item_id`, `active`. `secret_code_redemptions` : unique (`secret_code_id`, `membership_id`), `redeemed_at`. Saisie limitée en débit pour empêcher l'essai systématique.

## Interactions

### reactions

PK (`prono_id`, `membership_id`, `kind`) ; `kind` dans le jeu fixe de la plateforme ; `created_at`. Ajout et retrait par bascule.

### reports (signalement)

`id`, `org_id`, `prono_id`, `reporter_membership_id`, `kind` (`result_error`, `content`), `message` (≤ 500 caractères), `state` (`open`, `resolved`, `dismissed`), `handled_by`, `handled_at`, `resolution_note`, `created_at`.

### uploads (image jointe)

`id`, `org_id`, `uploaded_by`, `mime` (`image/webp`), `width`, `height`, `size_bytes`, `storage_key`, `created_at`. Lecture réservée aux membres de l'organisation.

### notifications (file d'envoi)

`id`, `account_id` (NULL pour une invitation envoyée à une adresse sans compte : l'adresse est alors dans `payload.to`), `org_id`, `type`, `payload` (jsonb : identifiants et textes déjà traduits), `dedupe_key` (unique, par exemple `closing_soon:{prono}:{account}` ou `designation:{prono}:{étape}`), `state` (`pending`, `sent`, `skipped`, `failed`), `attempts`, `next_attempt_at`, `sent_at`, `created_at`. Lue par le `worker` avec `FOR UPDATE SKIP LOCKED` ; les canaux sont choisis à l'envoi selon `notification_prefs`.

## Mini-jeux

### runner_runs (partie de course)

`id`, `org_id`, `membership_id`, `week_start` (date du lundi, Paris), `seed`, `started_at`, `finished_at`, `score`, `duration_ms`. Au plus 5 parties par (`membership_id`, `week_start`) ; une partie terminée ne se modifie plus.

### minigame_payouts

PK (`org_id`, `game`, `period_key`) ; `paid_at`. Marqueur d'idempotence des gains hebdomadaires de la course (`period_key` = date du lundi).

### pixel_puzzles (Pixel mystère)

`id`, `org_id`, `author_membership_id`, `drawing` (PixelImage), `word`, `word_normalized`, `reveal_order` (bytea : permutation des pixels), `revealed_count`, `state` (`queued`, `active`, `finished`), `started_at`, `finished_at`, `created_at`. Au plus un `active` par organisation (index unique partiel).

### pixel_guesses, pixel_finds

`pixel_guesses` : `id`, `puzzle_id`, `membership_id`, `guess_normalized`, `correct`, `day` (date, Paris), `created_at` ; au plus 3 par (`puzzle_id`, `membership_id`, `day`). `pixel_finds` : unique (`puzzle_id`, `membership_id`), `rank`, `laurels` (10, 7, 5, puis 3), `found_at` ; le gain écrit une ligne `minigame` au registre.

## Relations principales

```text
accounts 1─n memberships n─1 organisations
organisations 1─n sections, invitations, pronos, uploads, pixel_puzzles
pronos 1─n prono_options, bets, settlements, prono_events, reactions, reports
memberships 1─n bets, ledger_entries, trophies, owned_items, runner_runs
settlements 1─n ledger_entries
seasons 1─n ledger_entries, trophies, season_closures
```
