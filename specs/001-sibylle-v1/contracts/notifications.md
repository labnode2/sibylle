# Contrat des notifications : Sibylle v1

**Feature**: `001-sibylle-v1` | **Plan**: [../plan.md](../plan.md) | **Choix**: [../research.md](../research.md) (R7, J5)

## Types

| type | Déclencheur | Destinataires | Déduplication (`dedupe_key`) |
|---|---|---|---|
| `new_prono` | un prono passe à l'état `open` | membres actifs de la rédaction, sauf son créateur et la personne qui l'a validé | `new_prono:{prono}:{account}` |
| `closing_soon` | clôture moins 2 h (vérifié chaque minute) | membres actifs sans pari actif ; jamais pour un prono de date « sans fin » | `closing_soon:{prono}:{account}` |
| `result` | règlement (`resolution`, `correction`, `cancellation`, `result_cancellation`) | membres qui ont parié | `result:{prono}:{settlement_seq}:{account}` |
| `designation_reminder` | date de résultat attendu (sinon lendemain de la clôture), puis J+1, J+3, J+7, puis chaque semaine ; une relance repart de zéro | créateur journaliste, ou journaliste qui a validé la proposition | `designation:{prono}:{relance}-{étape}` |
| `report` | un membre signale un prono (résultat erroné ou contenu) | membres actifs qui traitent les signalements (`handle_reports` : rédaction en chef), sauf l'auteur du signalement et le créateur du prono signalé ; lien vers `/o/<org_id>/reglages/signalements` ; sans objet si le signalement est déjà traité | `report:{report}:{account}` |
| `mention` | un message de la discussion d'un prono tague un membre (`@pseudo`, membres actifs de la rédaction) | le membre tagué, jamais l'auteur du message ; au plus une notification non lue par membre et par prono (`mention` ou `discussion`) ; sans objet si le message est supprimé | `mention:{message}:{account}` |
| `discussion` | un message arrive dans la discussion d'un prono | membres actifs qui y ont écrit ou y ont été tagués, sauf l'auteur du message et les membres tagués par lui (déjà prévenus par `mention`) ; au plus une notification non lue par membre et par prono | `discussion:{message}:{account}` |

En plus, hors préférences (toujours envoyés par e-mail) : vérification de l'adresse, réinitialisation du mot de passe, invitation nominative.

Un membre de plusieurs rédactions reçoit les notifications de chacune ; le nom de la rédaction figure dans le titre.

## Dans l'appli

Pas d'onglet ni de liste à part : de petites bulles (le compteur en encre des signalements ouverts) mènent jusqu'au prono concerné. Le nombre de notifications non lues est à côté de « Pronos », dans la barre d'onglets du téléphone comme dans la navigation de l'ordinateur. Dans la liste des pronos, il est ensuite sur chaque filtre (« Ouverts », « Clos », « Résolus », selon l'état du prono), puis sur chaque prono. Le nom accessible du menu porte le nombre (`aria-label` « PRONOS, 3 notifications non lues »).

Une bulle ne s'arrête jamais en chemin : chaque bulle se retrouve en dessous, jusqu'à ce qui la fait partir. Au-dessus des menus, la bulle d'une rédaction, dans le menu des rédactions (sa petite carte, dans la navigation de l'ordinateur et sur la une du téléphone) et sur la page d'accueil, additionne les bulles de ses menus : les notifications de « Pronos » et, pour la rédaction en chef, les signalements ouverts de « La rédaction » (`waiting` de chaque rédaction dans `GET /me`). La petite carte elle-même porte la somme des autres rédactions, les menus montrant déjà celle-ci. Dans la liste, le choix d'une rubrique montre aussi le nombre de chaque rubrique sous le filtre choisi (« Sport (2) »), et « Voir plus » celui des pronos plus bas, pas encore affichés. Les signalements mènent de « La rédaction » à « Réglages de la rédaction », puis à « Signalements ».

Ouvrir le prono marque lues toutes les notifications du membre sur ce prono (`read_at`), y compris celles qui arrivent pendant qu'il est ouvert. Les bulles suivent sans recharger sur tous les appareils du membre, celles des autres rédactions comprises, grâce aux événements `notification.created`, `notification.read` et `notification.changed` (son prono a changé d'état) sur son sujet `me`, et `report.created` et `report.handled` pour la rédaction en chef.

Une notification non lue ne compte que tant qu'elle mène encore à quelque chose. `new_prono` et `closing_soon` comptent tant que le prono est ouvert. `designation_reminder` compte tant que le résultat attend d'être désigné. `result`, `mention` et `discussion` comptent jusqu'à leur lecture. `report` ne compte pas ici : les signalements ouverts ont déjà leur compteur à côté de « La rédaction ».

Le push et l'e-mail n'y changent rien : une notification qu'aucun canal n'a pu porter (`skipped`, par exemple quand les deux interrupteurs de son type sont coupés) compte quand même, et ouvrir le prono la marque lue comme les autres.

## Préférences

Quatorze interrupteurs par compte : 7 types × 2 canaux (`push`, `email`), tous actifs par défaut (routes `/me/notification-prefs` dans [rest-api.md](rest-api.md)). Un compte dont l'e-mail n'est pas vérifié ne reçoit aucun e-mail de notification.

## Notification push

Envoyée en Web Push (VAPID), chiffrée, durée de vie 12 h (`TTL`), urgence `normal` (`high` pour `closing_soon`). Charge utile lue par le service worker :

```json
{
  "type": "closing_soon",
  "title": "Sophia Office · ferme dans 2 h",
  "body": "Nice ou Monaco samedi ? Tu n'as pas encore joué.",
  "url": "/o/<org_id>/pronos/<prono_id>",
  "tag": "closing_soon:<prono_id>",
  "icon": "/icon-192.png"
}
```

Le corps est la question suivie d'une phrase propre au type (« Tu n'as pas encore joué. », « Résultat : Nice. Tu gagnes 40 lauriers. »…). `tag` remplace une notification plus ancienne du même prono sur l'appareil. Au clic, le service worker ouvre ou met au premier plan l'appli sur `url`. Textes produits par le serveur dans la langue du compte.

## E-mails

Envoyés par le relais SMTP de Brevo depuis `Sibylle <ne-pas-repondre@<domaine>>`, en texte et en HTML (style Gazette, sans image distante ni pixel de suivi, suivi des clics désactivé chez Brevo). Chaque e-mail de notification contient un lien direct vers ses préférences (`/compte#notifications`).

| Modèle | Objet (fr) |
|---|---|
| `verify_email` | Confirme ton adresse pour Sibylle |
| `reset_password` | Ton lien pour changer de mot de passe |
| `invitation` | {pseudo} t'invite dans la rédaction {organisation} |
| `new_prono` | {organisation} · Nouveau prono : {question} |
| `closing_soon` | {organisation} · Plus que 2 h pour jouer |
| `result` | {organisation} · Édition spéciale : {question} |
| `designation_reminder` | {organisation} · Résultat à désigner : {question} |
| `report` | {organisation} · Nouveau signalement : {question} |
| `mention` | {organisation} · {auteur} t'a taggé : {question} |
| `discussion` | {organisation} · Nouveau message : {question} |

## Envoi et reprises

Le `worker` lit la table `notifications` (`state = pending`, `next_attempt_at` passé) avec `FOR UPDATE SKIP LOCKED`, envoie sur les canaux actifs, puis marque `sent`. Canaux actifs : `push` si l'interrupteur est allumé, que le serveur a ses clés VAPID et que le compte a au moins un appareil abonné ; `email` si l'interrupteur est allumé et l'adresse vérifiée. En cas d'échec d'un canal : nouvelle tentative de ce seul canal (`done_channels` garde ceux déjà passés) après 1 min, 5 min, 30 min, 2 h, puis `failed`. Sans aucun canal actif, la notification passe à `skipped`. Une notification devenue sans objet à l'envoi (prono annulé, pari fait entre-temps pour `closing_soon`) passe à `skipped`.

## Tests attendus

- Chaque type est créé une seule fois par destinataire, même si le `worker` tourne deux fois.
- Couper un canal pour un type n'empêche pas l'autre canal.
- Un abonnement push qui répond 404 ou 410 est supprimé.
- Un abonnement n'est accepté que vers le service push d'un navigateur (`fcm.googleapis.com`, `*.push.services.mozilla.com`, `*.push.apple.com`, `*.notify.windows.com`, en HTTPS) : le `worker` n'écrit nulle part ailleurs.
- Aucun e-mail ne contient d'image ni de lien vers un domaine tiers.
