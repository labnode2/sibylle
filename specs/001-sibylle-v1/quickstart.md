# Quickstart : lancer et valider Sibylle v1

**Feature**: `001-sibylle-v1` | **Plan**: [plan.md](plan.md)

Ce guide sert à vérifier, de bout en bout, que l'implémentation tient la spécification. Les commandes ci-dessous sont celles que l'implémentation doit fournir ; elles n'existent pas encore.

## Prérequis

- Docker 29 et Docker Compose (présents sur la machine).
- Python 3.14 et uv (présents).
- Node.js LTS 24 ou plus, avec npm : **absent de la machine**, à installer avant la première semaine.
- Pour tester les notifications push sur téléphone : le domaine en HTTPS (les navigateurs refusent le push sur une adresse locale autre que `localhost`).

## Démarrer en local

1. Copier `deploy/.env.example` en `deploy/.env` et générer les secrets : `uv run --directory backend sibylle gen-secrets` (clé de session, clés VAPID).
2. Base de données et faux serveur d'e-mails : `docker compose -f deploy/docker-compose.yml --profile dev up -d db mailpit`.
3. Serveur, dans `backend/` : `uv sync`, `uv run alembic upgrade head`, `uv run sibylle seed-demo`, puis `uv run uvicorn sibylle.main:app --reload` (port 8000) et, dans un autre terminal, `uv run sibylle worker`.
4. Interface, dans `frontend/` : `npm install`, puis `npm run dev` (port 5173, `/api` redirigé vers le port 8000).
5. Ouvrir `http://localhost:5173`. `seed-demo` crée la rédaction « Sophia Office » avec Inès (rédaction en chef), Hugo (journaliste), Cami, Léo et Manon (lecteur·rice·s), un mot de passe commun indiqué dans `backend/seed/README.md`, et quelques pronos dans chaque état.

Les e-mails partent en local vers Mailpit, un faux serveur SMTP (profil `dev` du Compose, interface sur le port 8025) ; Brevo n'est utilisé qu'en production.

## Vérifications automatiques

- Tout d'un coup : `make check` à la racine (formatage, analyse, types, tests serveur et interface, types d'API à jour).
- Règles du jeu seules : `uv run pytest tests/unit` dans `backend/`.
- Parcours de bout en bout : `npx playwright test` dans `frontend/` (lance l'API avec une horloge simulée ; les tests avancent l'horloge avec `sibylle clock` et exécutent les tâches du `worker` avec `sibylle jobs run`).
  Les tests ont leurs propres ports (API 8001, interface 5180, modifiables par `SIBYLLE_API_PORT` et `SIBYLLE_WEB_PORT`) : ils ne croisent jamais un `make dev` ouvert à côté.

Attendu : tout passe, dont les propriétés Hypothesis de la cagnotte (voir [research.md](research.md), J1).

## Horloge simulée

En développement, `SIBYLLE_CLOCK=fake` permet d'avancer le temps : `uv run sibylle clock set 2026-12-20T23:59:00+01:00` ou `uv run sibylle clock advance 2h`. Le `worker` réagit à la minute suivante.

## Scénarios de validation

Chaque scénario renvoie à une histoire de [spec.md](spec.md). Utiliser deux navigateurs (ou une fenêtre privée) pour voir deux membres à la fois.

### V1. Entrer dans une rédaction (US1, SC-001)

1. Créer un compte neuf, créer une rédaction : on en est la rédaction en chef, avec le solde de départ.
2. Créer un lien d'invitation à 2 places ; l'ouvrir avec un second compte, choisir un pseudo déjà pris (refusé), puis un pseudo libre, un avatar, accepter la charte.
3. Chronométrer depuis l'ouverture du lien jusqu'au premier pari : moins de 2 minutes.
4. Ouvrir le lien avec un troisième et un quatrième compte : le quatrième est refusé (`invitation_invalid`).
5. Vérifier dans les réponses de l'API qu'aucun nom, prénom ni e-mail d'un autre membre n'apparaît.

### V2. Parier en direct (US2, SC-002)

1. Hugo publie un prono à trois choix, gain de base 20, clôture dans 1 h.
2. Cami et Léo ouvrent le prono. Cami mise 20 sur « Nice » : chez Léo, la répartition, la cagnotte et la ligne de Cami apparaissent en moins de 2 secondes, sans recharger.
3. Cami tente de rejouer : refusé (`already_bet`). Léo tente de miser plus que son solde : refusé (`insufficient_balance`).
4. Avancer l'horloge de 1 h : le prono passe « clos », un pari est refusé.

### V3. L'exemple du cahier des charges (US3, SC-003)

1. Un prono à gain de base 20 ; quatre membres misent 10, un seul sur la bonne réponse.
2. Hugo désigne la bonne réponse. Attendu : le gagnant reçoit 20 + 40 lauriers et son score monte de 50 ; les trois autres ont perdu 10 au solde (au moment du pari) et 10 au score ; l'édition spéciale paraît ; les quatre reçoivent la notification `result`.
3. Bonus lève-tôt à 20 % pour les 5 premiers : si le gagnant était parmi les 5 premiers, il reçoit aussi 4 lauriers.
4. Inès corrige le résultat vers une autre réponse : les écritures précédentes sont inversées, le nouveau règlement est appliqué, et la somme des parts de cagnotte vaut toujours 40.
5. Inès annule un autre prono : chaque mise est rendue.

### V4. Relance et date « sans fin » (US2, US3)

1. Un prono clos sans pari : Hugo le relance avec une nouvelle date ; il rouvre.
2. Un prono de date « sans fin » : Cami parie une date proche ; avancer l'horloge au-delà ; Cami parie une nouvelle date, et sa première mise reste dans la cagnotte.
3. Désigner la date de l'événement : le pari actif le plus proche gagne ; la première mise de Cami compte comme perdue.

### V5. Saison et classements (US4)

1. Avec des pronos réglés, vérifier les six vues du classement et qu'un achat dans la collection baisse le solde sans toucher au score.
2. `uv run sibylle clock set 2026-12-21T00:00:30+01:00` : à la minute suivante, chaque membre qui a parié reçoit un trophée gravé de son score, les trois premiers ont un cadre doré, chaque solde repart au solde de départ.
3. Relancer le `worker` et forcer une seconde exécution : rien n'est versé deux fois.

### V6. La une, propositions, réglages (US5, US6)

1. La une de Cami montre le prono dont la clôture est la plus proche en premier, puis les blocs dans l'ordre de la spec ; celle d'Hugo montre en plus « à désigner ».
2. Cami propose un prono : il n'est visible que d'elle et des journalistes ; Hugo le valide, il est publié.
3. Inès fixe le plafond du gain à 30 : Hugo ne peut plus créer de prono à 40. Inès retire 15 lauriers à Léo avec un motif : solde −15, score inchangé, ligne dans le relevé de Léo.
4. Avec le compte de Cami, appeler les routes de la rédaction en chef : `403` partout.

### V7. Profil, avatar, collection (US7)

1. Dessiner un avatar 32×32, l'enregistrer : il apparaît dans les listes et chez les autres membres en direct.
2. Débloquer une couleur, l'utiliser ; tenter d'enregistrer un avatar avec une couleur non débloquée : refusé.
3. Saisir un code secret de démonstration : la surprise est débloquée une seule fois.

### V8. Notifications (US8, SC-006)

Sur le domaine en HTTPS, avec l'appli installée sur Android, iOS 16.4+ et un ordinateur :

1. Ouvrir l'appli installée depuis son icône : la fenêtre « Activer les notifications ? » s'ouvre sur la rédaction ; l'accepter, puis publier un prono : notification push et e-mail. À l'ouverture suivante, la fenêtre ne revient pas.
2. Un prono qui ferme dans 2 h : seuls les membres sans pari sont prévenus, une seule fois.
3. Couper l'e-mail pour `new_prono` : seule la notification push arrive.

### V9. Jeux de la semaine (US9, US10, US12)

1. Jouer 5 parties de course ; la 6ᵉ est refusée. Avancer au lundi 00:30 (`sibylle clock advance 7d`, puis `sibylle games pay-runner`) : 10, 7, 5 lauriers aux trois premiers, 2 aux autres, au solde seulement.
2. Hugo dépose un Pixel mystère ; un premier lot de pixels apparaît ; Cami trouve en premier (10), Léo ensuite (7) ; un essai sans accents ni majuscules est accepté ; un 4ᵉ essai dans la journée est refusé.
3. Quand tous les membres sauf Hugo ont trouvé, le jeu se termine ; un autre dessin attend le lendemain 08:00 ; avancer 7 jours (`sibylle clock advance 7d`, puis `sibylle games reveal-pixel`) : tous les pixels sont dévoilés et le jeu se termine.
4. Dans l'onglet « Jeux » des réglages, Inès retire la course de la semaine en cours (après confirmation) : Cami ne la voit plus sur la une et sa partie est refusée (`game_not_scheduled`). Elle retire Pixel mystère en plein dessin : le dessin s'arrête, son mot est donné, et la une n'a plus d'encadré des jeux. Elle décoche Pixel mystère dans « Une semaine ordinaire » : la semaine en cours garde ses jeux ; après `sibylle clock advance 7d`, la une ne propose que la course.

### V10. Données et préférences (US11, SC-005, SC-007)

1. Exporter ses données : le fichier contient compte, rédactions, paris, relevé, collection.
2. Supprimer un compte : il ne peut plus se connecter ; ses paris passés apparaissent sous « Ancien membre » ; les cagnottes réglées n'ont pas bougé.
3. Seule rédaction en chef d'une rédaction avec d'autres membres : la suppression est refusée (`last_editor`).
4. Dans les outils du navigateur, onglet réseau, parcourir toute l'appli : aucune requête vers un autre domaine.
5. `npx playwright test --grep @a11y` : aucune erreur axe-core bloquante ; le thème sombre et « couper les animations » s'appliquent partout.

## Mise en production (aperçu)

Le détail est dans `deploy/README.md`.

1. Chez Cloudflare : enregistrement DNS A du domaine vers l'adresse IPv4 publique de la box (celle des autres sites de la VM), par le proxy (sans AAAA) ; mode Full (strict) ; certificat d'origine ; Authenticated Origin Pulls. SPF, DKIM et DMARC de Brevo.
2. Sur la VM dev-external : `deploy/README.md` (dossiers de données et règle ufw dans le `setup.sh` de la VM, clone dans `/opt/sibylle`, réglages, `deploy/update.sh`, crochets de déploiement, sauvegardes), puis, dans Nginx Proxy Manager, l'hôte du domaine vers `http://sibylle:8443`, avec le certificat d'origine.
3. Vérifier : `https://<domaine>/api/health` répond `ok` ; une sauvegarde est produite la nuit suivante, puis restaurée sur une base de test.
