# Contrat des notifications : Sybille v1

**Feature**: `001-sybille-v1` | **Plan**: [../plan.md](../plan.md) | **Choix**: [../research.md](../research.md) (R7, J5)

## Types

| type | Déclencheur | Destinataires | Déduplication (`dedupe_key`) |
|---|---|---|---|
| `new_prono` | un prono passe à l'état `open` | membres actifs de la rédaction, sauf son créateur | `new_prono:{prono}:{account}` |
| `closing_soon` | clôture moins 2 h (vérifié chaque minute) | membres actifs sans pari actif ; jamais pour un prono de date « sans fin » | `closing_soon:{prono}:{account}` |
| `result` | règlement (`resolution`, `correction`, `cancellation`) | membres qui ont parié | `result:{prono}:{settlement_seq}:{account}` |
| `designation_reminder` | date de résultat attendu, puis J+1, J+3, J+7, puis chaque semaine | créateur journaliste, ou journaliste qui a validé la proposition | `designation:{prono}:{étape}` |

En plus, hors préférences (toujours envoyés par e-mail) : vérification de l'adresse, réinitialisation du mot de passe, invitation nominative.

Un membre de plusieurs rédactions reçoit les notifications de chacune ; le nom de la rédaction figure dans le titre.

## Préférences

Huit interrupteurs par compte : 4 types × 2 canaux (`push`, `email`), tous actifs par défaut (routes `/me/notification-prefs` dans [rest-api.md](rest-api.md)). Un compte dont l'e-mail n'est pas vérifié ne reçoit aucun e-mail de notification.

## Notification push

Envoyée en Web Push (VAPID), chiffrée, durée de vie 12 h (`TTL`), urgence `normal` (`high` pour `closing_soon`). Charge utile lue par le service worker :

```json
{
  "type": "closing_soon",
  "title": "Sophia Office · ferme dans 2 h",
  "body": "Nice ou Monaco samedi ? Tu n'as pas encore joué.",
  "url": "/o/<org_id>/pronos/<prono_id>",
  "tag": "closing_soon:<prono_id>",
  "icon": "/icons/ball-192.png"
}
```

`tag` remplace une notification plus ancienne du même prono sur l'appareil. Au clic, le service worker ouvre ou met au premier plan l'appli sur `url`. Textes produits par le serveur dans la langue du compte.

## E-mails

Envoyés par le relais SMTP de Brevo depuis `Sybille <ne-pas-repondre@<domaine>>`, en texte et en HTML (style Gazette, sans image distante ni pixel de suivi, suivi des clics désactivé chez Brevo). Chaque e-mail de notification contient un lien direct vers ses préférences.

| Modèle | Objet (fr) |
|---|---|
| `verify_email` | Confirme ton adresse pour Sybille |
| `reset_password` | Ton lien pour changer de mot de passe |
| `invitation` | {pseudo} t'invite dans la rédaction {organisation} |
| `new_prono` | {organisation} · Nouveau prono : {question} |
| `closing_soon` | {organisation} · Plus que 2 h pour jouer |
| `result` | {organisation} · Édition spéciale : {question} |
| `designation_reminder` | {organisation} · Résultat à désigner : {question} |

## Envoi et reprises

Le `worker` lit la table `notifications` (`state = pending`, `next_attempt_at` passé) avec `FOR UPDATE SKIP LOCKED`, envoie sur les canaux actifs, puis marque `sent`. En cas d'échec : nouvelle tentative après 1 min, 5 min, 30 min, 2 h, puis `failed`. Une notification devenue sans objet à l'envoi (prono annulé, pari fait entre-temps pour `closing_soon`) passe à `skipped`.

## Tests attendus

- Chaque type est créé une seule fois par destinataire, même si le `worker` tourne deux fois.
- Couper un canal pour un type n'empêche pas l'autre canal.
- Un abonnement push qui répond 410 est supprimé.
- Aucun e-mail ne contient d'image ni de lien vers un domaine tiers.
