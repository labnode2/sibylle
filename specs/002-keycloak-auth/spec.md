# Feature Specification: Connexion par Keycloak

**Feature Branch**: `002-keycloak-auth`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "Connexion de Sibylle par Keycloak. Le serveur de Sibylle délègue l'inscription, la connexion, le mot de passe oublié, le changement de mot de passe et la vérification d'adresse au realm `sibylle` de Keycloak (https://auth.sibylle.cc), déjà en production : créé par OpenTofu (keycloak/terraform), pages et e-mails au style Gazette (keycloak/theme). Le serveur fait lui-même la connexion OIDC (code d'autorisation avec PKCE, client confidentiel `sibylle`) puis ouvre sa propre session `sibylle_session` comme aujourd'hui : aucun jeton dans le navigateur, la WebSocket et la protection CSRF ne changent pas. Chaque compte Sibylle est rattaché à son compte Keycloak ; e-mail, prénom, nom et adresse vérifiée sont recopiés à chaque connexion. Se déconnecter ferme la session Sibylle et la session Keycloak ; Keycloak prévient Sibylle quand une session finit ailleurs (déconnexion back-channel, nouveau mot de passe). Un compte non vérifié peut jouer (FR-002) : Sibylle fait envoyer l'e-mail de vérification par Keycloak. Supprimer son compte supprime aussi le compte Keycloak. Dans l'interface, les 5 pages de compte (connexion, inscription, mot de passe oublié, nouveau mot de passe, vérifier l'e-mail) deviennent des passages vers Keycloak ; changer son mot de passe depuis les réglages passe par Keycloak. Tests : contrats avec un faux fournisseur OIDC, parcours de bout en bout par les pages Keycloak. Bascule en production : secrets du client dans deploy/.env, déploiement, sauvegarde pg_dump de keycloak-db gardée hors de la VM. La décision R4 de research.md est à réécrire, et le service en plus (Keycloak) à justifier dans Complexity Tracking."

Aujourd'hui, Sibylle gère elle-même ses comptes : formulaires de connexion et d'inscription,
mots de passe, liens envoyés par e-mail. Cette fonctionnalité confie tout cela au **service de
comptes** de Sibylle, Keycloak, qui tourne déjà sur la machine de production à
`https://auth.sibylle.cc`, avec des pages et des e-mails au style de la Gazette. Le reste de
Sibylle (rédactions, pronos, lauriers, jeux) ne change pas. Les exigences de compte de la v1
restent vraies (`specs/001-sibylle-v1/spec.md`, FR-001 à FR-004) : seul l'endroit où elles
se jouent change.

## Clarifications

### Session 2026-11-07

- Q: Que deviennent les comptes créés avant la bascule ? → A: Aucun à garder : la production
  n'a que des comptes d'essai. Elle repart de zéro à la bascule, dans Sibylle comme dans le
  service de comptes ; rien n'est importé.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - S'inscrire et se connecter sur les pages de la Gazette (Priority: P1)

Cami reçoit le lien d'invitation de « Sophia Office ». Sibylle l'envoie sur la page « Créer un
compte » du service de comptes, au style de la Gazette : e-mail, prénom, nom, mot de passe. Une
fois le compte créé, elle revient sur Sibylle, connectée, sur la page de l'invitation, et
rejoint la rédaction. Le lendemain, sur un autre appareil, « Se connecter » l'emmène sur la page
de connexion du service, puis la ramène connectée là où elle allait.

**Why this priority**: sans elle, personne n'entre dans Sibylle. C'est le cœur de la
bascule.

**Independent Test**: depuis un lien d'invitation, créer un compte sur les pages du service,
revenir sur Sibylle, rejoindre la rédaction ; se déconnecter, puis se reconnecter depuis une
page protégée et y revenir.

**Acceptance Scenarios**:

1. **Given** une personne sans compte, **When** elle ouvre un lien d'invitation puis crée son
   compte sur la page du service, **Then** elle revient connectée sur la page de l'invitation et
   peut rejoindre la rédaction.
2. **Given** une personne qui a un compte, **When** elle ouvre une page protégée sans être
   connectée, **Then** elle passe par la page de connexion du service et revient sur la page
   qu'elle visait.
3. **Given** une personne déjà connectée au service depuis peu (par exemple dans un autre
   onglet), **When** sa session Sibylle a expiré et qu'elle revient, **Then** elle retrouve
   Sibylle sans retaper son mot de passe.
4. **Given** un mauvais mot de passe, **When** la personne se connecte, **Then** la page du
   service le lui dit, sans révéler si l'adresse a un compte.
5. **Given** une adresse qui a déjà un compte, **When** quelqu'un essaie de s'inscrire avec,
   **Then** le service refuse et propose de se connecter.

---

### User Story 2 - Confirmer son adresse (Priority: P2)

Cami peut jouer tout de suite, sans avoir confirmé son adresse. Sibylle demande au service de
lui envoyer l'e-mail de confirmation dès son inscription. Tant qu'elle n'a pas cliqué, elle ne
reçoit pas d'e-mails de notification, et ses réglages lui proposent de renvoyer l'e-mail. Après
le clic, Sibylle sait que son adresse est confirmée.

**Why this priority**: elle garde la règle FR-002 de la v1 (un compte non confirmé peut jouer)
et rend les e-mails de notification possibles.

**Independent Test**: créer un compte, vérifier qu'on joue sans confirmer, recevoir l'e-mail de
confirmation, cliquer, et voir les notifications par e-mail devenir possibles.

**Acceptance Scenarios**:

1. **Given** un nouveau compte, **When** la personne arrive sur Sibylle, **Then** elle peut
   jouer et l'e-mail de confirmation est parti.
2. **Given** une adresse non confirmée, **When** la personne demande à renvoyer l'e-mail,
   **Then** un nouvel e-mail part, au plus 3 fois par heure.
3. **Given** une personne qui clique le lien de confirmation, **When** elle revient sur Sibylle,
   **Then** son adresse y est confirmée au plus tard à sa visite suivante.

---

### User Story 3 - Mot de passe oublié, nouveau mot de passe (Priority: P2)

Dominique a oublié son mot de passe. La page de connexion du service propose « Mot de passe
oublié ? » ; le lien reçu par e-mail mène à la page « Nouveau mot de passe ». Plus tard, depuis
ses réglages, « Changer mon mot de passe » l'emmène sur la même page, puis la ramène à ses
réglages ; elle peut en profiter pour déconnecter ses autres appareils.

**Why this priority**: indispensable, mais déjà fourni par les pages du service. Seuls le
passage depuis les réglages et le retour sont à faire.

**Independent Test**: demander un nouveau mot de passe, l'utiliser ; changer de mot de passe
depuis les réglages en déconnectant les autres appareils, et vérifier qu'un autre navigateur
est déconnecté.

**Acceptance Scenarios**:

1. **Given** un mot de passe oublié, **When** la personne le demande, **Then** elle reçoit un
   lien valable une seule fois et pendant une heure.
2. **Given** une personne connectée, **When** elle choisit « Changer mon mot de passe » dans ses
   réglages, **Then** elle change son mot de passe sur la page du service et revient à ses
   réglages, toujours connectée.
3. **Given** un nouveau mot de passe choisi avec « déconnecter mes autres appareils », **When**
   un autre appareil fait sa requête suivante, **Then** il n'est plus connecté.

---

### User Story 4 - Se déconnecter, partout (Priority: P2)

Cami se déconnecte sur l'ordinateur du bureau : sa session Sibylle et sa session du service se
ferment, et la personne suivante devra taper un mot de passe. Quand une session du service se
termine ailleurs (nouveau mot de passe, sessions fermées par un administrateur), Sibylle ferme
aussi les sessions qui en dépendent.

**Why this priority**: sur un ordinateur partagé, se déconnecter doit vraiment déconnecter.

**Independent Test**: se déconnecter, revenir sur Sibylle et constater que le mot de passe est
redemandé ; fermer une session depuis le service et voir l'appareil concerné déconnecté.

**Acceptance Scenarios**:

1. **Given** une personne connectée, **When** elle se déconnecte, **Then** sa visite suivante
   passe par la page de connexion du service, mot de passe compris.
2. **Given** une session du service fermée ailleurs, **When** l'appareil concerné fait sa
   requête suivante ou attend dans le temps réel, **Then** il n'est plus connecté, au plus une
   minute après.

---

### User Story 5 - Supprimer son compte, partout (Priority: P2)

Quand Cami supprime son compte depuis ses réglages, Sibylle fait ce qu'elle faisait (données
personnelles effacées, traces de jeu anonymisées) et supprime aussi son compte du service. Son
adresse peut ensuite servir à un nouveau compte, sans lien avec l'ancien.

**Why this priority**: principe I de la constitution : supprimer son compte efface les données
personnelles, où qu'elles soient.

**Independent Test**: supprimer un compte, vérifier qu'il n'existe plus ni dans Sibylle ni dans
le service, puis s'inscrire de nouveau avec la même adresse et obtenir un compte neuf.

**Acceptance Scenarios**:

1. **Given** une personne connectée, **When** elle supprime son compte, **Then** son compte du
   service est supprimé aussi et toutes ses sessions se ferment.
2. **Given** le service injoignable, **When** la personne supprime son compte, **Then** rien
   n'est supprimé et Sibylle l'invite à réessayer plus tard.
3. **Given** un compte supprimé, **When** quelqu'un s'inscrit avec la même adresse, **Then** il
   obtient un compte neuf, sans rédaction ni lauriers.

---

### User Story 6 - Basculer la production (Priority: P3)

Emile met la nouvelle connexion en production. Il sauvegarde la base, efface les comptes et les
données d'essai, dans Sibylle comme dans le service, donne à Sibylle les secrets de son client
du service, déploie, et vérifie qu'on s'inscrit, se connecte et se déconnecte. Les comptes du
service sont sauvegardés chaque nuit, avec une copie hors de la machine, comme la base de
Sibylle, et leur restauration a été répétée une fois.

**Why this priority**: elle vient après le reste, mais aucune personne ne doit dépendre du
service avant que ses comptes soient sauvegardés.

**Independent Test**: après le déploiement, constater qu'aucun compte d'essai ne reste et faire
le tour des parcours 1 à 5 en production ; restaurer les comptes du service depuis la copie hors
de la machine sur une machine d'essai.

**Acceptance Scenarios**:

1. **Given** la bascule faite, **When** on regarde les comptes, **Then** il n'en reste aucun
   d'avant la bascule, ni dans Sibylle ni dans le service.
2. **Given** la nouvelle version déployée, **When** on s'inscrit, se connecte et se déconnecte,
   **Then** chaque parcours aboutit.
3. **Given** une nuit passée, **When** on regarde les sauvegardes, **Then** celle des comptes du
   service existe sur la machine et hors de la machine.
4. **Given** cette sauvegarde, **When** on la restaure sur une machine d'essai, **Then** les
   comptes s'y connectent.

---

### Edge Cases

- Le service de comptes ne répond pas : les personnes connectées continuent de jouer ; celle qui
  veut se connecter ou s'inscrire voit une page de Sibylle qui le dit et propose de réessayer.
- Le service ne répond pas au moment où une personne se déconnecte : sa session Sibylle se ferme
  quand même ; celle du service expire d'elle-même après 30 minutes d'inactivité.
- La personne abandonne sur la page du service, ou revient avec une demande expirée ou forgée :
  aucune session ne s'ouvre, et Sibylle propose de recommencer.
- Le retour après connexion ne mène qu'à une page de Sibylle, jamais à une adresse extérieure.
- Un lien envoyé par l'ancienne connexion (confirmation d'adresse, nouveau mot de passe) est
  ouvert après la bascule : la page explique qu'il ne marche plus et mène à la bonne page.
- Une ancienne adresse de page (`/connexion`, `/inscription`, `/mot-de-passe/oubli`,
  `/mot-de-passe/nouveau`, `/verifier-email`), dans un favori ou un lien partagé : elle mène à
  la page correspondante du service.
- Le compte du service est désactivé ou supprimé par un administrateur : le service ne prévient
  pas Sibylle. Les sessions Sibylle de ce compte se ferment au plus tard une heure après, à leur
  prolongation suivante ; tout de suite si l'administrateur a d'abord fermé ses sessions. Le
  compte ne peut plus se connecter.
- Le nom ou l'adresse changent dans le service : Sibylle les recopie à la connexion suivante ;
  ils restent invisibles des autres membres.
- Trop d'échecs de connexion : le service bloque le compte pour un temps, jamais pour de bon.
- Deux comptes Sibylle ne peuvent jamais se retrouver rattachés au même compte du service, ni un
  compte à deux comptes du service.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: L'inscription, la connexion, le mot de passe oublié, le nouveau mot de passe et la
  confirmation d'adresse DOIVENT se faire sur les pages du service de comptes, au style de la
  Gazette et en français. Sibylle NE DOIT PLUS afficher de formulaire de mot de passe ni stocker
  de mot de passe.
- **FR-002**: La connexion DOIT rester par e-mail et mot de passe uniquement (FR-003 de la v1) :
  aucun autre moyen de connexion n'est proposé.
- **FR-003**: Les liens « Se connecter » et « Créer un compte », et toute page protégée ouverte
  sans session, DOIVENT mener à la bonne page du service. Les anciennes adresses des pages de
  compte DOIVENT continuer d'y mener.
- **FR-004**: Après une inscription ou une connexion réussie, la personne DOIT revenir connectée
  sur la page de Sibylle qu'elle visait, invitation et code d'accès compris, et jamais sur une
  adresse extérieure.
- **FR-005**: Sibylle DOIT garder sa propre session de navigateur, comme dans la v1 : valable 30
  jours, prolongée à l'usage. Le temps réel et la protection contre les requêtes forgées DOIVENT
  fonctionner comme avant. Le navigateur NE DOIT JAMAIS détenir de jeton du service.
- **FR-006**: Chaque compte Sibylle DOIT être rattaché à un seul compte du service, et chaque
  compte du service à un seul compte Sibylle. L'e-mail, le prénom, le nom et l'état de
  confirmation de l'adresse DOIVENT être recopiés dans Sibylle à chaque connexion. Sibylle NE
  DOIT JAMAIS rattacher un compte sur la foi de la seule adresse e-mail.
- **FR-007**: À la bascule, la production DOIT repartir de zéro, après une sauvegarde : les
  comptes d'essai et toutes les données de jeu qui en dépendent sont effacés de Sibylle, les
  comptes d'essai du service aussi, et rien n'est importé.
- **FR-008**: Un compte dont l'adresse n'est pas confirmée DOIT pouvoir jouer, sans recevoir
  d'e-mails de notification (FR-002 de la v1). À l'inscription, Sibylle DOIT faire envoyer
  l'e-mail de confirmation par le service. Ses réglages DOIVENT permettre de le renvoyer, au plus
  3 fois par heure. Une adresse confirmée DOIT être connue de Sibylle au plus tard à la visite
  suivante.
- **FR-009**: Le lien de nouveau mot de passe DOIT être à usage unique et valable 1 heure ; le
  lien de confirmation d'adresse, 24 heures, comme dans la v1.
- **FR-010**: Les réglages DOIVENT proposer « Changer mon mot de passe », qui mène à la page du
  service et ramène aux réglages. La personne DOIT pouvoir y déconnecter ses autres appareils.
- **FR-011**: Se déconnecter DOIT fermer la session Sibylle et la session du service : la visite
  suivante redemande le mot de passe. Si le service ne répond pas à ce moment, la session Sibylle
  se ferme quand même et celle du service expire d'elle-même (cas limites).
- **FR-012**: Quand une session du service se termine ailleurs (autres appareils déconnectés,
  nouveau mot de passe, sessions fermées par un administrateur), les sessions Sibylle qui en
  dépendent DOIVENT se fermer dans la minute, sans attendre leur expiration.
- **FR-013**: Supprimer son compte (US11 de la v1) DOIT aussi supprimer le compte du service. Si
  le service ne répond pas, rien NE DOIT être supprimé et la personne DOIT être invitée à
  réessayer.
- **FR-014**: L'export de ses données DOIT comprendre ce que Sibylle sait de l'identité de la
  personne : e-mail, prénom, nom, adresse confirmée ou non, date de création du compte.
- **FR-015**: Le nom, le prénom et l'e-mail NE DOIVENT JAMAIS être visibles d'un autre membre
  (FR-004 de la v1), qu'ils viennent de Sibylle ou du service.
- **FR-016**: Les échecs de connexion répétés DOIVENT être freinés : 10 échecs en 15 minutes
  bloquent le compte pour un temps, jamais pour de bon (R4 de la v1).
- **FR-017**: Si le service de comptes ne répond pas, les personnes connectées DOIVENT continuer
  de jouer, et une connexion ou une inscription DOIT afficher une page de Sibylle qui le dit et
  propose de réessayer.
- **FR-018**: Un lien envoyé par l'ancienne connexion DOIT mener à une page qui explique qu'il ne
  marche plus et propose la bonne page du service.
- **FR-019**: Les comptes du service DOIVENT être sauvegardés chaque nuit, avec une copie hors
  de la machine. Leur restauration DOIT être documentée et répétée au moins une fois avant que
  quiconque en dépende (principe V).
- **FR-020**: Le service de comptes et Sibylle DOIVENT rester sur la machine du projet ; aucune
  donnée d'identité ne doit partir chez un tiers (principe I), hors l'envoi des e-mails par
  Brevo.
- **FR-021**: Un compte désactivé ou supprimé dans le service, que le service n'annonce pas, DOIT
  perdre ses sessions Sibylle au plus tard une heure après, quand elles se prolongent. Une
  panne du service ne ferme aucune session. La consigne des administrateurs DOIT dire de fermer
  d'abord les sessions du compte, pour un effet immédiat.

### Key Entities *(include if feature involves data)*

- **Compte** (Sibylle) : une personne. Il n'a plus de mot de passe. Il est rattaché à un compte
  du service, dont il recopie l'e-mail, le prénom, le nom et l'état de confirmation de
  l'adresse. Ses préférences, rédactions et lauriers restent dans Sibylle.
- **Compte du service** : l'identité de la personne dans le service de comptes : e-mail (son
  identifiant), prénom, nom, mot de passe, adresse confirmée ou non.
- **Session Sibylle** : un navigateur connecté à Sibylle. Elle est liée à la session du service
  ouverte au même moment, pour fermer l'une quand l'autre se termine.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Depuis un lien d'invitation, une personne crée son compte et arrive dans la
  rédaction en moins de 2 minutes, sans quitter le style de la Gazette.
- **SC-002**: Après la bascule, aucun compte d'avant la bascule ne reste, ni dans Sibylle ni dans
  le service.
- **SC-003**: Après une déconnexion, ou une déconnexion des autres appareils, aucune session
  Sibylle concernée ne reste ouverte plus d'une minute.
- **SC-004**: Sibylle ne conserve plus aucun mot de passe ni aucun lien secret de compte.
- **SC-005**: Les parcours clés de bout en bout de la v1 (rejoindre, parier, désigner, être payé)
  réussissent avec la nouvelle connexion.
- **SC-006**: Une panne du service de comptes n'interrompt la partie d'aucune personne déjà
  connectée.
- **SC-007**: Avant le lancement, une restauration des comptes du service depuis la copie hors
  de la machine a réussi au moins une fois.

## Assumptions

- Le service de comptes est en place sur la machine de production : realm `sibylle` créé par
  OpenTofu (`keycloak/terraform`), pages et e-mails de la Gazette (`keycloak/theme`), console
  d'administration joignable seulement par le tunnel SSH, adresse publique
  `https://auth.sibylle.cc` derrière Cloudflare.
- La production n'a, avant la bascule, que des comptes d'essai (clarification du 2026-11-07).
- Les e-mails du service partent par Brevo, avec le même expéditeur que ceux de Sibylle.
- Changer d'adresse e-mail reste hors du périmètre, comme dans la v1. Les noms ne sont pas
  modifiables dans les réglages de Sibylle ; s'ils changent dans le service, Sibylle les recopie
  à la connexion suivante.
- Les autres moyens de connexion du service (codes à usage unique, clés d'accès, comptes Google…)
  et l'authentification à deux facteurs des membres restent hors du périmètre.
- La décision R4 (`specs/001-sibylle-v1/research.md`) est réécrite, et le service en plus
  justifié dans le Complexity Tracking, pendant la planification.
- La bascule se fait avant ou après le lancement du 1ᵉʳ décembre 2026 selon l'avancement ; le
  plan le fixe.
