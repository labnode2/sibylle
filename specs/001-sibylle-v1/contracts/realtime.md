# Contrat temps réel : Sibylle v1

**Feature**: `001-sibylle-v1` | **Plan**: [../plan.md](../plan.md) | **Choix**: [../research.md](../research.md) (R5)

## Connexion

- URL : `wss://<domaine>/api/ws`. Authentifiée par le cookie de session ; l'en-tête `Origin` doit être le domaine.
- Une seule connexion par onglet. Le serveur envoie `{"type": "ping"}` toutes les 25 s ; le client répond `{"type": "pong"}`. Sans pong pendant 60 s, le serveur ferme.
- Codes de fermeture : `4401` session absente ou expirée (le client renvoie vers la connexion) ; `4403` sujet refusé ; `1012` redémarrage du serveur.
- Reconnexion : délai croissant de 1 s à 30 s avec un peu d'aléa ; après reconnexion, le client se réabonne et recharge les données des écrans ouverts (invalidation TanStack Query).

## Messages du client

```json
{ "type": "subscribe", "topics": ["org:<org_id>", "prono:<prono_id>"] }
{ "type": "unsubscribe", "topics": ["prono:<prono_id>"] }
{ "type": "pong" }
```

Sujets autorisés :

| Sujet | Condition | Usage |
|---|---|---|
| `org:<id>` | membre actif | la une, les listes, le classement |
| `prono:<id>` | membre actif de l'organisation du prono | l'écran du prono |
| `me` | toujours (abonnement automatique) | solde, score, notifications dans l'appli |

Le serveur répond `{"type": "subscribed", "topics": [...]}` ou `{"type": "error", "code": "forbidden_topic", "topic": "..."}`. Un membre qui quitte une organisation ou qui en est retiré est désabonné immédiatement.

## Événements du serveur

Enveloppe commune : `{"type": "event", "topic": "<sujet>", "event": "<nom>", "at": "<ISO 8601>", "data": {...}}`. Les événements sont publiés après la validation de la transaction. Ils ne contiennent jamais d'e-mail, de nom ni de prénom ; un membre y apparaît par `MemberPublic` (voir [rest-api.md](rest-api.md)).

| Événement | Sujets | data |
|---|---|---|
| `prono.created` | `org` | `{prono: PronoSummary}` (publié ou proposé ; un prono proposé n'est envoyé qu'aux journalistes et à son auteur·rice) |
| `prono.state_changed` | `org`, `prono` | `{prono_id, state, closes_at, relaunch_count}` (ouverture, clôture, relance, refus, annulation) |
| `prono.edited` | `org`, `prono` | `{prono: PronoSummary}` |
| `bet.placed` | `prono` | `{bet: Bet, pot, bet_count}` ; le client recharge le détail pour la répartition |
| `bet.placed` | `org` | `{prono_id, pot, bet_count}` (version courte pour les listes) |
| `prono.resolved` | `org`, `prono` | `{prono_id, settlement_seq, kind: "resolution" \| "correction" \| "cancellation"}` ; le client recharge l'édition spéciale |
| `report.created` | `me` (rédaction en chef) | `{report_id, prono_id, kind}` |
| `report.handled` | `me` (auteur·rice du signalement) | `{report_id, prono_id, state}` ; le client recharge le prono, où `my_reports` donne la note de la rédaction en chef |
| `reaction.changed` | `prono` | `{prono_id, reactions: {kind: count}}` |
| `leaderboard.changed` | `org` | `{}` ; le client recharge le classement affiché |
| `member.updated` | `org` | `{member: MemberPublic}` (pseudo, avatar, rôle) |
| `member.joined`, `member.left` | `org` | `{member: MemberPublic}` |
| `balance.changed` | `me` | `{org_id, balance, season_score}` |
| `games.runner.updated` | `org` | `{week_start, top}` |
| `games.pixel.revealed` | `org` | `{puzzle_id, revealed_count}` |
| `games.pixel.found` | `org` | `{puzzle_id, member, rank}` |
| `games.pixel.finished` | `org` | `{puzzle_id, word}` |
| `season.closed` | `org` | `{season: {year, name}}` ; le client recharge profil, collection et classements |

## Bus interne

L'API et le `worker` publient par `NOTIFY sibylle_events, '<json>'` avec `{"topics": [...], "event": "...", "data": {...}, "audience": "all" | "journalists" | ["<membership_id>", ...]}`. Seul le processus API, qui écoute ce canal, parle aux navigateurs. Une charge utile de plus de 7 500 octets est remplacée par un événement réduit qui demande au client de recharger.

## Tests attendus

- Deux clients abonnés au même prono : un pari de l'un arrive à l'autre en moins de 2 s (SC-002).
- Un client d'une autre organisation ne peut pas s'abonner (`forbidden_topic`) et ne reçoit rien.
- Un prono proposé n'est pas diffusé aux lecteur·rice·s autres que son auteur·rice.
- Après un redémarrage de l'API, le client se reconnecte et affiche l'état à jour.
