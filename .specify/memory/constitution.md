<!--
Sync Impact Report
- Version: (template) → 1.0.0 (première ratification)
- Principes ajoutés : I. Vie privée d'abord · II. Rédactions étanches · III. Les lauriers sont un registre ·
  IV. Les règles du jeu sont testées d'abord · V. Simple à héberger · VI. Français d'abord, accessible, fidèle à la Gazette
- Sections ajoutées : Contraintes techniques · Flux de travail
- Modèles vérifiés : plan-template.md ✅ (la section « Constitution Check » lit ce fichier) ·
  spec-template.md ✅ · tasks-template.md ✅ (aucune modification nécessaire)
- TODO : aucun
-->

# Constitution de Sibylle

## Core Principles

### I. Vie privée d'abord (NON NÉGOCIABLE)

- Toutes les données restent sur la machine du projet, en Europe. Aucun outil de mesure d'audience,
  de suivi ou de publicité, et aucune ressource chargée depuis un tiers par le navigateur
  (polices, scripts et images sont servis par Sibylle elle-même).
- Les seuls services tiers admis sont l'envoi d'e-mails (Brevo, en Europe) et les services de
  notification push des navigateurs, dont le contenu est chiffré de bout en bout.
- Le nom et le prénom d'un compte ne sont jamais visibles d'un autre membre ; dans une rédaction,
  on n'est connu que par son pseudo.
- Chacun peut exporter ses données et supprimer son compte en un clic ; la suppression efface
  les données personnelles et rend anonymes les traces de jeu qui doivent rester (cagnottes,
  classements passés).

*Pourquoi :* Sibylle se joue entre collègues ; la confiance passe avant toute fonctionnalité.

### II. Rédactions étanches

- Chaque donnée de jeu appartient à une organisation. Toute lecture et toute écriture sont
  filtrées par l'organisation et par le rôle (lecteur·rice, journaliste, rédaction en chef),
  côté serveur, jamais seulement dans l'interface.
- Aucun classement, prono ou notification ne traverse deux organisations.
- Chaque route d'API a un test qui prouve qu'un membre d'une autre organisation, ou d'un rôle
  insuffisant, est refusé.

### III. Les lauriers sont un registre

- Chaque mouvement de lauriers est une écriture ajoutée à un registre, avec son motif ; on ne
  modifie ni ne supprime jamais une écriture. Une correction ajoute des écritures inverses.
- Le solde et le score se déduisent du registre ; les compteurs mis en cache sont mis à jour
  dans la même transaction que l'écriture.
- Les lauriers sont des entiers ; les arrondis suivent une règle écrite et testée, et une
  cagnotte distribuée ne crée ni ne perd jamais un laurier.

### IV. Les règles du jeu sont testées d'abord

- Les règles du jeu (cycle de vie d'un prono, gains, cagnotte, bonus lève-tôt, saisons,
  classements, mini-jeux) vivent dans un module de domaine sans dépendance au web ni à la base,
  et chaque règle a ses tests écrits avant le code.
- Les contrats d'API ont des tests ; les parcours clés (rejoindre, parier, désigner, être payé)
  ont un test de bout en bout.
- Une modification qui casse un test de règle n'est pas fusionnée.

### V. Simple à héberger

- Sibylle tourne sur une seule machine, avec Docker Compose : un serveur web, l'API, un
  processus de tâches et PostgreSQL. Ajouter un service (file de messages, cache, etc.) doit
  être justifié dans la section « Complexity Tracking » du plan.
- Un seul dépôt, un seul déploiement ; pas de microservices.
- Sauvegarde automatique de la base, restauration documentée et testée.

### VI. Français d'abord, accessible, fidèle à la Gazette

- Le français est la langue de lancement, avec l'écriture inclusive des maquettes
  (lecteur·rice) ; chaque texte passe par un catalogue de traduction dès le premier jour, pour
  que l'anglais n'exige aucune réécriture.
- Les heures et les saisons sont calculées dans le fuseau Europe/Paris.
- L'interface vise le niveau AA des WCAG 2.2, respecte « réduire les animations » et fonctionne
  au clavier.
- Le style suit la direction « Gazette » des maquettes (couleurs, polices, filets, angles droits,
  pixel art net) ; s'en écarter demande une décision explicite.

## Contraintes techniques

- Interface : React avec TypeScript, en appli web installable (PWA), sur mobile et ordinateur.
- Serveur : Python avec FastAPI ; temps réel par WebSocket.
- Base de données : PostgreSQL ; schéma versionné par migrations.
- Hébergement : une machine à domicile, exposée par frp depuis un VPS qui porte le nom de
  domaine ; HTTPS obligatoire, chiffré jusqu'à la machine.
- E-mails : Brevo (SMTP) ; notifications push : Web Push (VAPID).
- Lancement visé : 1ᵉʳ décembre 2026.

## Flux de travail

- Chaque fonctionnalité suit Spec Kit : spécification, plan, tâches, puis implémentation, sur
  sa propre branche `NNN-nom`.
- Avant chaque fusion : formatage, analyse statique, vérification des types et tous les tests
  passent, côté serveur et côté interface.
- Les migrations de base sont relues avant d'être appliquées en production, et toujours
  précédées d'une sauvegarde.
- Aucun secret dans le dépôt : configuration par variables d'environnement, avec un fichier
  d'exemple sans valeur réelle.

## Governance

- Cette constitution prime sur les autres pratiques du projet. Chaque plan vérifie ses
  principes dans la section « Constitution Check », avant et après la conception.
- Un écart doit être justifié dans « Complexity Tracking », avec l'option plus simple écartée.
- Les amendements passent par `/speckit-constitution` et suivent la gestion sémantique des
  versions : MAJEURE pour retirer ou redéfinir un principe, MINEURE pour en ajouter un,
  CORRECTIVE pour une clarification.

**Version**: 1.0.0 | **Ratified**: 2026-11-01 | **Last Amended**: 2026-11-01
