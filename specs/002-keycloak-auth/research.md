# Research: Connexion par Keycloak

Décisions de la phase 0 du plan (`plan.md`). Elles remplacent la décision R4 de
`specs/001-sibylle-v1/research.md` pour les comptes ; la session de Sibylle, elle, reste celle
de R4. Les points marqués « vérifié » l'ont été le 7 novembre 2026 sur un Keycloak 26.8.2
d'essai, avec le realm créé par `keycloak/terraform`.

### K1. Le serveur de Sibylle est le client de Keycloak

- **Decision**: le serveur fait lui-même la connexion OpenID Connect avec le client confidentiel
  `sibylle` (code d'autorisation avec PKCE `S256`), puis ouvre sa session `sibylle_session` comme
  dans R4. Le navigateur ne voit que des redirections : aucun jeton ne lui parvient.
- **Rationale**: la session de R4 reste valable telle quelle. Révocation immédiate, WebSocket
  authentifiée par le même cookie, protection contre les requêtes forgées (`X-Sibylle`,
  `Origin`) : rien ne change pour le reste du serveur ni pour l'interface hors des pages de compte.
- **Alternatives considered**: l'interface comme client (keycloak-js, jetons dans le
  navigateur) : jetons lisibles par le JavaScript, WebSocket et CSRF à refaire, CSP à ouvrir ;
  un mandataire d'authentification devant Sibylle (oauth2-proxy) : un service de plus, et ni la
  déconnexion par Keycloak ni le rattachement des comptes ne s'y règlent.

### K2. Bibliothèques : httpx et PyJWT

- **Decision**: `httpx` (déjà dans les dépendances de test) passe dans les dépendances du
  serveur pour parler à Keycloak ; `PyJWT[crypto]` vérifie les jetons signés (jeton d'identité,
  jeton de déconnexion) avec les clés publiques du realm, gardées en mémoire et rechargées quand
  une clé inconnue apparaît. `argon2-cffi` part : Sibylle ne voit plus de mot de passe.
- **Rationale**: le flux tient en quatre appels (autorisation, échange du code, clés, API
  d'admin) ; deux petites bibliothèques connues suffisent et se testent avec un
  `httpx.MockTransport`, sans serveur.
- **Alternatives considered**: Authlib (client OAuth complet, bien plus que nécessaire) ;
  python-keycloak (enveloppe de l'API d'admin, lourde pour trois appels) ; vérifier les
  signatures à la main (non).

### K3. L'aller-retour de connexion

- **Decision**: `GET /api/auth/login` tire un `state`, un `nonce` et un vérificateur PKCE, les
  garde dans une ligne `sign_in_attempts` (avec l'action et la page de retour), pose un cookie
  `sibylle_signin` (aléatoire, `HttpOnly; Secure; SameSite=Lax`, 10 minutes, `Path=/api/auth`) qui
  désigne cette ligne, et redirige vers Keycloak. `GET /api/auth/callback` n'accepte que le
  navigateur qui porte ce cookie et le `state` de la ligne, à usage unique et dans les 10
  minutes ; il échange le code, vérifie le jeton d'identité (signature, émetteur, audience
  `sibylle`, expiration, `nonce`), puis supprime la ligne.
- **Rationale**: le cookie lie le retour au navigateur qui a commencé (pas de connexion
  imposée par un tiers) ; `SameSite=Lax` passe sur la navigation de retour depuis
  `auth.sibylle.cc` ; tout reste côté serveur, sans clé de signature à gérer.
- **Alternatives considered**: tout mettre dans un cookie signé (une clé de plus en
  configuration) ; garder le `state` en base sans cookie (une connexion lancée par un tiers
  serait acceptée).

### K4. Le chemin entre le serveur et Keycloak

- **Decision**: un réseau Docker partagé `keycloak` (`internal: true`, créé par `setup.sh` de
  labnode2/docker) relie `keycloak` au service `api` de Sibylle, le seul qui lui parle : le
  `worker` n'y va pas. Le serveur appelle
  `http://keycloak:8080` pour l'échange du code, les clés et l'API d'admin ; le navigateur va sur
  `https://auth.sibylle.cc`. Réglages : `OIDC_ISSUER` (l'adresse publique du realm, pour les
  redirections et la vérification), `KEYCLOAK_INTERNAL_URL`, `OIDC_CLIENT_ID`,
  `OIDC_CLIENT_SECRET`. Pas besoin de `KC_HOSTNAME_BACKCHANNEL_DYNAMIC` : le serveur construit
  lui-même les adresses internes.
- **Rationale**: NPM bloque `/admin` sur l'adresse publique, et passer par Cloudflare pour
  parler à une machine voisine serait un détour fragile. Vérifié : demandé par `keycloak:8080`,
  le jeton porte l'émetteur public `https://auth.sibylle.cc/realms/sibylle`, et les clés comme
  l'API d'admin répondent.
- **Alternatives considered**: l'adresse publique (bloquée pour `/admin`, détour par
  Cloudflare) ; mettre l'`api` sur `proxy` (contraire aux règles de la VM : seul ce que NPM doit
  joindre y va).

### K5. L'accès du serveur à l'API d'admin

- **Decision**: le compte de service du client `sibylle` (rôle `manage-users` de
  `realm-management`, déjà donné) reçoit aussi la portée `kc-admin-api` par défaut ; OpenTofu
  la déclare avec les portées par défaut que Keycloak donne déjà au client (`web-origins`,
  `service_account`, `acr`, `profile`, `roles`, `basic`, `email`). Le serveur prend un jeton
  par `client_credentials`, gardé jusqu'à peu avant son expiration.
- **Rationale**: vérifié : sans cette portée, Keycloak 26.8 répond 401 à l'API d'admin ; avec
  elle, 200, par l'adresse interne comme par la publique (le jeton porte alors l'audience
  `https://auth.sibylle.cc/admin/realms/sibylle`).
- **Alternatives considered**: un second client réservé à l'admin (un secret de plus pour le
  même compte de service).

### K6. Rattacher les comptes

- **Decision**: un compte Sibylle porte `keycloak_id`, le `sub` de son compte Keycloak. Au
  retour d'une connexion, un `sub` connu ouvre la session de ce compte ; un `sub` inconnu crée un
  compte (e-mail, prénom, nom, adresse confirmée ou non recopiés). Une adresse déjà prise par un
  autre compte vivant arrête la connexion sur une page d'erreur : on ne rattache jamais par
  l'adresse. À chaque connexion, e-mail, prénom, nom et confirmation sont recopiés.
- **Rationale**: FR-006. La production repart de zéro (clarification du 7 novembre) : aucun
  compte n'est à importer, et Keycloak refuse deux comptes de même adresse.
- **Alternatives considered**: rattacher par l'adresse (prise de compte possible avec une
  adresse non confirmée) ; importer les comptes (sans objet).

### K7. Se déconnecter

- **Decision**: `POST /api/auth/logout` supprime la session Sibylle puis ferme la session
  Keycloak par l'API d'admin (`DELETE /admin/realms/sibylle/sessions/{sid}`), le `sid` venant du
  jeton d'identité et gardé dans `sessions.keycloak_sid`. Si Keycloak ne répond pas dans les 3
  secondes, la session Sibylle est fermée quand même et l'échec est journalisé : la session
  Keycloak expire d'elle-même (30 minutes d'inactivité). Vérifié : fermer ainsi la session fait
  envoyer par Keycloak une déconnexion back-channel pour cette session, que Sibylle a déjà
  fermée ; elle reste sans effet.
- **Rationale**: FR-011 sans redirection ni page de confirmation, depuis la boîte de dialogue
  actuelle. Le reste de risque (Keycloak injoignable au moment précis de la déconnexion) est
  borné par l'expiration de sa session.
- **Alternatives considered**: la déconnexion par redirection (`end_session` avec
  `id_token_hint`) : il faudrait garder le jeton d'identité de chaque session, et la page
  « Te déconnecter ? » du thème s'afficherait sans lui.

### K8. Quand Keycloak ferme une session ailleurs

- **Decision**: le client `sibylle` déclare une déconnexion « back-channel » vers
  `http://sibylle:8443/api/auth/backchannel-logout` : Keycloak passe par le réseau `proxy` et le
  nginx de Sibylle, sans Cloudflare. Le serveur vérifie le jeton de déconnexion (signature,
  émetteur, audience, événement de déconnexion, `sid` ou `sub`, pas de `nonce`, récent), supprime
  les sessions de ce `sid` (ou toutes celles du compte), et publie un événement sur
  `sibylle_events` pour que les WebSocket de ces sessions se ferment (code 4401). La route
  échappe à la protection CSRF : le jeton signé est sa preuve.
- **Rationale**: FR-012 et SC-003. Vérifié : Keycloak envoie la déconnexion back-channel quand
  l'administrateur ferme les sessions d'un compte (« Sign out ») ou l'une d'elles, mais **pas**
  quand il désactive ou supprime le compte (K15). Le nouveau mot de passe avec « déconnecter mes
  autres appareils » ferme les autres sessions du compte. Le nginx de Sibylle répond sur `8443` à
  tout nom d'hôte (un seul serveur sur ce port).
- **Alternatives considered**: passer par `https://sibylle.cc` (détour par Cloudflare, dont les
  protections anti-robots peuvent refuser un appel de serveur) ; vérifier la session Keycloak à
  chaque requête (un appel de plus partout).

### K9. Confirmer l'adresse

- **Decision**: à la création d'un compte dont l'adresse n'est pas confirmée, le serveur fait
  envoyer l'e-mail de confirmation par l'API d'admin (`send-verify-email`, retour vers les
  réglages par une nouvelle connexion silencieuse). `POST /api/auth/verify-email/resend` reste,
  limité à 3 par heure. Sibylle apprend la confirmation par le jeton d'identité à chaque
  connexion et, pour un compte non confirmé, en relisant l'utilisateur dans Keycloak au plus une
  fois par minute quand l'interface lit `GET /api/me`. Si Keycloak ne répond pas, `GET /api/me`
  renvoie l'état connu, sans erreur : une panne ne bloque personne (SC-006).
- **Rationale**: FR-008 : un compte non confirmé joue, et sa confirmation se voit au plus tard à
  la visite suivante, même faite depuis un autre appareil. Les liens valent 24 h (jetons
  d'action envoyés par l'admin) et 1 h pour le mot de passe oublié (réglages du realm).
- **Alternatives considered**: l'action « Verify email » de Keycloak à l'inscription (elle
  bloque la connexion, contraire à FR-002 de la v1).

### K10. Changer son mot de passe, s'inscrire

- **Decision**: `GET /api/auth/login?action=password` envoie à Keycloak avec
  `kc_action=UPDATE_PASSWORD` : sa page propose de déconnecter les autres appareils, puis le
  retour ouvre une session neuve qui remplace l'ancienne. `action=signup` utilise
  `prompt=create`, qui ouvre « Créer un compte ». `action=forgot` mène directement à
  `…/login-actions/reset-credentials?client_id=sibylle`, la page « Mot de passe oublié » de
  Keycloak, sans tentative ni cookie ; après le nouveau mot de passe, le retour sur Sibylle passe
  par une connexion ordinaire.
- **Rationale**: vérifié : `prompt=create` affiche « Créer un compte · Sibylle »,
  `kc_action=UPDATE_PASSWORD` passe par la connexion quand il le faut, et la page de mot de passe
  oublié s'ouvre seule (« Mot de passe oublié · Sibylle »).
- **Alternatives considered**: le point d'entrée `/registrations` (propre à Keycloak, même
  résultat) ; la console de compte de Keycloak (hors du parcours de Sibylle).

### K11. Les pages de compte de l'interface

- **Decision**: `/connexion`, `/inscription` et une page protégée sans session mènent, par une
  navigation complète, à `/api/auth/login` (avec `action` et `suite`). `/mot-de-passe/oubli` mène à
  `/api/auth/login?action=forgot`, donc à la page « Mot de passe oublié » de Keycloak (K10).
  `/mot-de-passe/nouveau` et `/verifier-email`, ouvertes depuis un
  ancien e-mail, expliquent que le lien ne marche plus et proposent la bonne page (FR-018). Une
  page `/connexion-indisponible` dit quand Keycloak ne répond pas : `/api/auth/login` vérifie en
  moins de 2 secondes que le realm répond avant de rediriger, et le retour y mène aussi en cas
  d'échec (FR-017). Les réglages gagnent « Changer mon mot de passe ».
- **Rationale**: FR-001, FR-003, FR-004 ; `suite` garde les règles de `nextPath` (un chemin de
  Sibylle, jamais `//`).
- **Alternatives considered**: garder des formulaires dans Sibylle qui postent vers Keycloak
  (le mot de passe passerait par Sibylle).

### K12. Développement et tests

- **Decision**: le Keycloak local de `keycloak/dev.sh` (port 8280, Mailpit) importe dans
  `dev-realm.json` deux clients confidentiels, chacun avec son compte de service et la portée
  `kc-admin-api` : `sibylle` pour `make dev` (retours vers `http://localhost:5173`, déconnexion
  back-channel vers `http://localhost:8000`) et `sibylle-e2e` pour Playwright (ports 5180 et
  8001), car un client n'a qu'une adresse de déconnexion back-channel. Leurs secrets sont des
  valeurs de développement, écrites dans le dépôt comme le `admin` / `admin` de ce Keycloak
  local : ils ne valent que pour lui. Les comptes de démo y ont des identifiants fixes que
  `seed.py` reprend comme `keycloak_id`. Les tests de contrat simulent
  Keycloak par un `httpx.MockTransport` (clés RSA de test, jetons signés) ; la fixture
  `client_for` ouvre toujours ses sessions en base. Les parcours Playwright passent par les pages
  du thème, dont les libellés (« Prénom », « Nom », « E-mail », « Mot de passe », « Créer un
  compte ») remplacent ceux des anciennes pages dans les helpers.
- **Rationale**: tests rapides et sans réseau en CI ; les parcours de bout en bout voient les
  vraies pages.
- **Alternatives considered**: un Keycloak en conteneur dans les tests de contrat (lent, et la
  CI devrait le lancer).

### K13. La bascule en production

- **Decision**: dans l'ordre :
  1. sauvegarde ;
  2. labnode2/docker : réseau `keycloak`, rejoint par `keycloak` ;
  3. OpenTofu : portée `kc-admin-api` et adresse back-channel interne du client `sibylle` ;
  4. `deploy/.env` : `OIDC_*`, le secret par `tofu.sh output -raw client_secret` ;
  5. la base de Sibylle et ses images envoyées repartent de zéro, et `update.sh` déploie la
     version qui rejoint le réseau `keycloak` ;
  6. les comptes d'essai du realm `sibylle` sont supprimés ;
  7. vérifications des parcours.
- **Rationale**: FR-007 et la clarification du 7 novembre ; la migration de base retire les
  mots de passe sans rien importer.
- **Alternatives considered**: une migration qui viderait les tables (elle viderait aussi les
  bases de développement).

### K14. Sauvegarder les comptes

- **Decision**: `deploy/backup/backup.sh` ajoute chaque nuit un `pg_dump` de `keycloak-db`
  (`docker exec`, format custom), chiffré par age et copié au VPS avec le reste ;
  `restore.sh` sait le restaurer. Une restauration est répétée sur une machine d'essai avant le
  lancement.
- **Rationale**: FR-019 et le principe V, avec le mécanisme qui existe déjà (copie chiffrée,
  rétention de 14 jours).
- **Alternatives considered**: un script de sauvegarde dans labnode2/docker (un second
  mécanisme de copie au VPS) ; la seule sauvegarde Proxmox de la VM (pas hors de la machine).

### K15. Un compte désactivé ou supprimé dans Keycloak

- **Decision**: quand une session Sibylle se prolonge (au plus une fois par heure, comme dans
  R4), le serveur relit son compte dans Keycloak. Si le compte a disparu ou est désactivé, il
  supprime les sessions Sibylle de ce compte et répond comme sans session ; si Keycloak ne répond
  pas, la session continue et l'échec est journalisé. La consigne des administrateurs (dans
  `keycloak/README.md`) : avant de désactiver ou de supprimer un compte dans la console, fermer
  ses sessions (« Sign out »), ce qui fait déconnecter Sibylle aussitôt (K8).
- **Rationale**: vérifié le 7 novembre : Keycloak n'envoie aucune déconnexion back-channel quand
  l'administrateur désactive ou supprime un compte, et la session Sibylle dure 30 jours. Cette
  relecture borne le retard à une heure, sans appel à Keycloak sur les autres requêtes, et une
  panne de Keycloak ne déconnecte personne (FR-021, SC-006).
- **Alternatives considered**: relire le compte à chaque requête (un appel à Keycloak sur le
  chemin de toutes les requêtes) ; une tâche planifiée qui parcourt tous les comptes (des appels
  pour des sessions qui ne servent plus) ; une session Sibylle courte rafraîchie par Keycloak (la
  session de R4 changerait).
