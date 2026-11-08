# Feature Specification: Sibylle v1, le jeu de pronostics des rédactions

**Feature Branch**: `001-sibylle-v1`

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Sibylle v1 : jeu de pronostics par organisation, backend Python et frontend React", à partir du cahier des charges « Cahier des charges Sibylle » (https://claude.ai/artifact/9K25HDvGc4XEhxednqcTQ6), des maquettes « Gazette » (https://claude.ai/artifact/U1j9b9bbyqA7jMC71DLUCf) et des décisions du 1ᵉʳ novembre 2026.

Sibylle est un jeu de pronostics gratuit et sans enjeu réel, pour des organisations de 10 à 50 personnes. Chaque organisation est une rédaction fermée ; on y pronostique des événements, on gagne des lauriers en voyant juste, on peut en miser, et on se classe par saison. Vocabulaire : un **prono** est une question ; un **pari** est la réponse d'un membre à un prono ; la **rédaction en chef** administre l'organisation.

## Clarifications

### Session 2026-11-04

- Q: Quels jeux tournent une semaine que la rédaction en chef n'a pas programmée ? → A: Ceux d'une « semaine ordinaire », réglée par la rédaction en chef : les deux jeux au départ. Le programme semaine par semaine ne sert qu'aux exceptions.
- Q: Une semaine peut-elle n'avoir aucun jeu ? → A: Oui ; l'encadré « Jeux de la semaine » disparaît alors de la une.
- Q: Que deviennent les parties déjà jouées quand un jeu est retiré de la semaine en cours ? → A: La semaine de ce jeu est annulée. La course ne paie rien le lundi. Le dessin de Pixel mystère en cours s'arrête et son mot est donné. Les lauriers déjà gagnés restent. La même règle vaut quand une semaine sans Pixel mystère commence pendant un dessin.
- Q: Jusqu'à combien de semaines la rédaction en chef programme-t-elle ? → A: La semaine en cours et les 3 suivantes.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entrer dans une rédaction (Priority: P1)

Cami crée son compte avec son e-mail et un mot de passe, puis rejoint « Sophia Office » grâce au lien d'invitation d'Inès (ou au code d'accès, ou à une invitation reçue par e-mail). Elle choisit son pseudo dans cette rédaction, un avatar parmi les modèles, accepte la charte et arrive sur la une comme lecteur·rice. Inès, elle, avait créé l'organisation et en a pris la rédaction en chef.

**Why this priority**: sans compte ni rédaction, rien d'autre n'existe ; c'est le socle de toutes les autres histoires.

**Independent Test**: créer un compte, créer une organisation, générer un lien d'invitation, le faire utiliser par un second compte ; vérifier que le second compte voit la rédaction avec son pseudo et le rôle lecteur·rice, et qu'un troisième compte sans invitation ne voit rien.

**Acceptance Scenarios**:

1. **Given** une personne sans compte, **When** elle s'inscrit avec un e-mail et un mot de passe valides, **Then** son compte est créé et elle peut créer ou rejoindre une organisation.
2. **Given** un compte connecté, **When** il crée une organisation, **Then** il en devient la rédaction en chef et reçoit le solde de départ de l'organisation.
3. **Given** un lien d'invitation avec 7 places restantes et non expiré, **When** une personne connectée l'ouvre, choisit un pseudo libre et un avatar et accepte la charte, **Then** elle devient lecteur·rice et il reste 6 places.
4. **Given** un lien d'invitation expiré ou complet, **When** quelqu'un l'ouvre, **Then** l'appli explique que l'invitation n'est plus valable et n'ajoute personne.
5. **Given** un pseudo déjà pris dans cette rédaction, **When** Cami le choisit, **Then** l'appli le refuse et propose d'en choisir un autre.
6. **Given** Cami membre de deux rédactions, **When** elle passe de l'une à l'autre, **Then** elle y retrouve un pseudo, un avatar, des lauriers et des statistiques propres à chacune.
7. **Given** un mot de passe oublié, **When** Cami demande sa réinitialisation, **Then** elle reçoit un lien par e-mail, valable une seule fois et pendant une durée limitée.

---

### User Story 2 - Jouer un prono (Priority: P1)

Hugo, journaliste, publie « Nice ou Monaco samedi ? » avec trois choix, une clôture samedi 20:00 et un gain de base de 20 lauriers (sous le plafond de 50 fixé par la rédaction). Cami choisit « Nice » et mise 20 lauriers ; son choix est définitif. Tout le monde voit en direct la répartition des votes, qui a choisi quoi et combien chacun a misé, ainsi que la cagnotte qui grossit.

**Why this priority**: c'est le cœur du jeu ; avec l'histoire 3, c'est le produit minimum.

**Independent Test**: avec une rédaction de trois membres, publier un prono de chaque type, parier depuis deux navigateurs et vérifier que l'autre navigateur voit la répartition et la cagnotte changer sans recharger ; vérifier qu'aucun pari n'est accepté après la clôture.

**Acceptance Scenarios**:

1. **Given** un·e journaliste, **When** il ou elle crée un prono de type choix, oui/non, nombre ou date avec une question, une rubrique, une date de clôture et un gain de base sous le plafond, **Then** le prono est publié et ouvert (ou programmé si une date d'ouverture est fixée).
2. **Given** un prono ouvert et un solde de 342 lauriers, **When** Cami choisit une réponse et mise 20, **Then** son pari est enregistré, son solde passe à 322 et la cagnotte augmente de 20.
3. **Given** un pari déjà fait, **When** Cami essaie de changer de réponse ou de mise, **Then** l'appli refuse : le choix est définitif.
4. **Given** une mise supérieure au solde, **When** Cami valide, **Then** le pari est refusé ; une mise de 0 (« sans mise ») est toujours possible.
5. **Given** deux membres qui regardent le même prono, **When** l'un parie, **Then** l'autre voit dans les 2 secondes la nouvelle répartition, le nouveau pari et la nouvelle cagnotte.
6. **Given** la date de clôture passée, **When** quelqu'un essaie de parier, **Then** le pari est refusé et le prono apparaît « clos, en attente du résultat ».
7. **Given** un prono sur lequel personne n'a encore parié, **When** son ou sa journaliste le modifie, **Then** la modification est acceptée ; dès le premier pari, elle ne l'est plus.
8. **Given** un prono de date « sans fin », **When** la date choisie par Cami passe sans que l'événement arrive, **Then** Cami peut parier une nouvelle date, et sa première mise reste dans la cagnotte.

---

### User Story 3 - Désigner le résultat et être payé (Priority: P1)

Après le match, un·e journaliste désigne la bonne réponse. Les gagnants reçoivent le gain de base, le bonus lève-tôt s'ils étaient parmi les premiers, et leur part de la cagnotte au prorata de leur mise. Le résultat paraît dans une « édition spéciale » et chaque participant est prévenu. Si le match est reporté, le prono est relancé avec une nouvelle date et garde ses paris.

**Why this priority**: sans résultat ni gains, le jeu n'a pas de fin ; c'est ce qui donne du sens aux mises.

**Independent Test**: reproduire l'exemple du cahier des charges (quatre membres misent 10, un seul voit juste) et vérifier qu'il reçoit le gain de base plus 40 lauriers, que les trois autres ont perdu 10 et que le total des lauriers distribués depuis la cagnotte vaut exactement la cagnotte.

**Acceptance Scenarios**:

1. **Given** un prono clos, **When** un·e journaliste coche une ou plusieurs bonnes réponses, **Then** le prono est résolu, les gains sont versés et une édition spéciale est publiée.
2. **Given** quatre paris de 10 lauriers dont un seul juste, avec un gain de base de 20, **When** le résultat est désigné, **Then** le gagnant reçoit 20 + 40 lauriers et son score augmente de 50 ; chaque perdant voit son score baisser de 10.
3. **Given** des gagnants qui ont misé 30 et 10 sur une cagnotte de 100, **When** le résultat est désigné, **Then** ils reçoivent 75 et 25 lauriers de cagnotte, en plus du gain de base.
4. **Given** aucun gagnant, ou des gagnants qui n'ont rien misé, **When** le résultat est désigné, **Then** la cagnotte est perdue.
5. **Given** un prono de type nombre ou date, **When** le ou la journaliste saisit la valeur réelle, **Then** gagnent celles et ceux dont la réponse est la plus proche, à égalité s'il le faut.
6. **Given** un bonus lève-tôt de 20 % pour les 5 premiers, **When** le 3ᵉ parieur voit juste sur un prono à 20 lauriers, **Then** il reçoit 4 lauriers de bonus.
7. **Given** un événement reporté, **When** un·e journaliste relance le prono avec une nouvelle date de clôture, **Then** le prono rouvre, les paris existants sont conservés et de nouveaux membres peuvent parier.
8. **Given** un résultat erroné, **When** un membre appuie sur « Signaler une erreur », **Then** la rédaction en chef est prévenue et peut corriger le résultat ; les gains sont alors recalculés.
9. **Given** un prono annulé par la rédaction en chef, **When** l'annulation est confirmée, **Then** toutes les mises sont rendues et aucun gain n'est versé.
10. **Given** un prono clos sans résultat, **When** sa date de résultat attendu passe, **Then** son créateur reçoit des rappels pour le désigner.

---

### User Story 4 - Classements, saisons et trophées (Priority: P2)

Cami consulte le classement de sa rédaction : par lauriers (son score) ou par pronos gagnés, sur le mois, la saison ou depuis toujours. Le 20 décembre au soir, la saison d'automne se termine : chaque membre qui a joué reçoit une boule de cristal gravée, le podium a un cadre doré, et tout le monde repart au solde de départ.

**Why this priority**: le classement donne envie de revenir ; les saisons évitent qu'un écart creusé tôt décourage les autres.

**Independent Test**: avec des paris réglés sur deux mois et une fin de saison simulée, vérifier les six classements, les trophées, les cadres dorés et la remise au solde de départ.

**Acceptance Scenarios**:

1. **Given** des pronos réglés, **When** Cami ouvre le classement, **Then** elle voit les deux classements (lauriers, pronos gagnés) sur les trois périodes, avec tous les membres, elle comprise.
2. **Given** un achat de 400 pièces dans la collection, **When** le classement est recalculé, **Then** ses pièces ont baissé de 400, mais ses lauriers et son score n'ont pas changé.
3. **Given** la fin d'une saison, **When** elle est clôturée, **Then** chaque membre ayant parié au moins une fois dans la saison reçoit un trophée gravé de l'année, de la saison et de son score, les trois premiers ont un cadre doré, puis chaque solde repart au solde de départ.
4. **Given** plusieurs saisons passées, **When** Cami regarde le classement « depuis toujours », **Then** il additionne les lauriers gravés sur ses trophées et son score de la saison en cours.

---

### User Story 5 - La une et la vie de la rédaction (Priority: P2)

La une s'ouvre sur le prono dont la clôture est la plus proche, puis déroule les autres pronos ouverts, les pronos à désigner (pour les journalistes), les derniers résultats, le haut du classement, les jeux de la semaine et le mot de la rédaction en chef. Un·e lecteur·rice peut proposer un prono, publié après validation par un·e journaliste. Chacun peut réagir aux pronos avec des réactions rapides.

**Why this priority**: la une fait vivre la rédaction au quotidien ; les propositions ouvrent la création à tous.

**Independent Test**: avec des pronos dans plusieurs états, vérifier l'ordre de la une pour un·e lecteur·rice et pour un·e journaliste, faire proposer puis valider un prono, et ajouter puis retirer une réaction.

**Acceptance Scenarios**:

1. **Given** plusieurs pronos ouverts, **When** Cami ouvre la une, **Then** le prono à la une est celui dont la clôture est la plus proche, suivi des blocs dans l'ordre prévu.
2. **Given** un·e lecteur·rice, **When** il ou elle propose un prono, **Then** le prono attend une validation et les journalistes en sont informés ; validé, il est publié ; refusé, son auteur·rice en est informé·e.
3. **Given** un prono, **When** Cami ajoute une réaction rapide, **Then** le compteur de cette réaction augmente pour tout le monde ; un second appui la retire.
4. **Given** des rubriques créées par la rédaction, **When** Cami filtre par rubrique, **Then** elle ne voit que les pronos de cette rubrique.

---

### User Story 6 - Régler sa rédaction (Priority: P2)

Inès, rédaction en chef, personnalise la carte de l'organisation (logo en pixel art, fond, titre), règle les lauriers (plafond du gain de base, solde de départ, bonus lève-tôt), nomme les journalistes, gère les invitations et le code d'accès, ajoute ou retire des lauriers à un membre avec un motif et traite les signalements.

**Why this priority**: chaque rédaction doit pouvoir s'organiser seule ; c'est aussi elle qui modère.

**Independent Test**: changer chaque réglage avec le compte de la rédaction en chef et vérifier son effet ; vérifier que les mêmes actions sont refusées à un·e journaliste et à un·e lecteur·rice.

**Acceptance Scenarios**:

1. **Given** la rédaction en chef, **When** elle fixe le plafond du gain de base à 50, **Then** aucun nouveau prono ne peut proposer un gain supérieur à 50.
2. **Given** la rédaction en chef, **When** elle nomme Hugo journaliste, **Then** Hugo peut aussitôt publier, valider, désigner et relancer des pronos.
3. **Given** la rédaction en chef, **When** elle retire 15 lauriers à un membre avec le motif « erreur de saisie », **Then** le solde du membre baisse de 15, son score ne change pas et l'écriture apparaît dans son relevé avec le motif.
4. **Given** un nouveau code d'accès généré, **When** quelqu'un saisit l'ancien code, **Then** il est refusé.
5. **Given** un signalement ouvert, **When** la rédaction en chef le traite (correction ou rejet), **Then** son auteur·rice en est informé·e et le signalement est clos.

---

### User Story 7 - Carte de presse, avatar et collection (Priority: P3)

Cami ouvre sa carte de presse : pseudo, avatar, statistiques (lauriers, pronos joués, taux de réussite) et collection. Elle débloque une couleur avec ses pièces ; dans « Personnaliser ma carte », elle redessine son avatar en 16×16 ou 32×32, change son pseudo, choisit son cadre et met en avant jusqu'à trois objets ou trophées, en voyant à chaque changement sa carte telle que les autres la verront. Les boules de cristal ne s'achètent pas : on les gagne en fin de saison (le trophée gravé) ou avec un code secret. L'onglet « Rédaction » lui montre sa rédaction, puis ses membres avec leur rôle, et la carte de presse de chacun. Chaque lundi, ses lauriers en or lui rapportent autant de pièces, et une fenêtre lui annonce la bonne nouvelle. Son relevé détaille chaque gain, mise, gain de mini-jeu et ajustement.

**Why this priority**: c'est ce qui rend chacun reconnaissable et donne un usage aux lauriers gagnés, mais le jeu fonctionne sans.

**Independent Test**: dessiner et enregistrer un avatar, convertir les lauriers en or d'une semaine, acheter une couleur, débloquer une boule par code secret et les mettre en avant sur sa carte, et vérifier les pièces, les lauriers et le score inchangés, le relevé, l'affichage de l'avatar partout où apparaît le pseudo, et la carte vue par un autre membre.

**Acceptance Scenarios**:

1. **Given** « Personnaliser ma carte » ouverte, **When** Cami dessine en 32×32 avec la palette de base, **Then** sa carte se redessine à chaque trait ; une fois enregistrée, son nouvel avatar apparaît dans toute la rédaction.
2. **Given** une couleur verrouillée à 400 pièces et assez de pièces, **When** Cami la débloque, **Then** la couleur s'ajoute à sa palette et ses pièces baissent de 400 ; ses lauriers ne bougent pas.
3. **Given** une fin de saison, **When** Cami a joué dans la saison, **Then** son trophée apparaît dans sa collection.
4. **Given** un code secret valide, **When** Cami le saisit, **Then** la surprise associée (variante de boule, couleur rare) est débloquée une seule fois.
5. **Given** 90 lauriers verts et 30 lauriers misés sur des pronos pas encore réglés, soit 120 lauriers en or, **When** le lundi commence (00:00, heure de Paris), **Then** Cami reçoit 120 pièces, garde ses 90 lauriers, et à sa prochaine ouverture de l'appli une fenêtre lui annonce les 120 pièces, une seule fois.
6. **Given** une couleur achetée, une boule débloquée par code secret et un trophée de saison, **When** Cami en choisit deux pour sa carte, **Then** ils s'affichent sur sa carte dans l'ordre choisi ; un quatrième choix est refusé.
7. **Given** la rédaction de Cami, **When** Inès ouvre l'onglet « Rédaction », **Then** elle voit la carte de la rédaction puis les membres avec leur rôle ; sur la carte de Cami, elle voit son pseudo, son avatar, ses statistiques et ses objets mis en avant, mais pas son relevé.
8. **Given** la collection, **When** Cami la parcourt, **Then** aucune boule n'est à vendre : seules les boules qu'elle a débloquées y figurent, à côté de ses trophées.

---

### User Story 8 - Être prévenu (Priority: P3)

Cami reçoit une notification push sur son téléphone (appli installée) et un e-mail quand un prono est publié, quand un prono ferme dans 2 heures et qu'elle n'a pas joué, et quand le résultat d'un prono qu'elle a joué tombe. Hugo reçoit des rappels pour désigner ses résultats. Chacun règle chaque type de notification, canal par canal.

**Why this priority**: les notifications ramènent les joueurs au bon moment, mais le jeu reste jouable sans.

**Independent Test**: s'abonner aux notifications push sur un appareil, déclencher chacun des quatre événements et vérifier la réception push et e-mail, puis couper un type et vérifier qu'il n'arrive plus.

**Acceptance Scenarios**:

1. **Given** un prono qui ferme dans 2 heures, **When** Cami n'a pas parié, **Then** elle reçoit une seule notification ; si elle a déjà parié, elle n'en reçoit pas.
2. **Given** Cami a coupé les e-mails pour « nouveau prono », **When** un prono est publié, **Then** elle reçoit seulement la notification push.
3. **Given** un appareil sans appli installée ou sans autorisation, **When** une notification part, **Then** l'e-mail est quand même envoyé si ce canal est actif.

---

### User Story 9 - Course de la boule (Priority: P3)

Sur la une, l'encadré « Jeux de la semaine » propose la course de la boule : un personnage en pixel art saute des obstacles, comme le dinosaure de Chrome. Chacun a 5 essais par semaine ; seul son meilleur score compte. À la fin de la semaine, le classement de la rédaction rapporte 10 lauriers au 1er, 7 au 2e, 5 au 3e et 2 à chaque autre joueur.

**Why this priority**: c'est un bonus de fidélité entre deux pronos ; la sortie peut glisser sans bloquer le reste.

**Independent Test**: jouer 5 parties, vérifier qu'une 6ᵉ est refusée, que seul le meilleur score s'affiche, puis simuler la fin de semaine et vérifier les lauriers versés.

**Acceptance Scenarios**:

1. **Given** 5 essais déjà joués cette semaine, **When** Cami lance une partie, **Then** l'appli refuse et indique la date de remise à zéro.
2. **Given** la fin de la semaine, **When** les gains sont versés, **Then** les trois premiers reçoivent 10, 7 et 5 lauriers, les autres joueurs 2, dans leur solde uniquement (leur score ne bouge pas).
3. **Given** « réduire les animations » activé, **When** Cami ouvre le jeu, **Then** le jeu reste jouable sans effets superflus.

---

### User Story 10 - Pixel mystère (Priority: P4)

Un·e journaliste dépose un dessin en pixel art et le mot à deviner. Chaque jour, quelques pixels se dévoilent au hasard. Le premier qui trouve le mot gagne 10 lauriers, le deuxième 7, le troisième 5, les suivants 3. Le jeu se termine quand toute la rédaction a trouvé ou quand tous les pixels sont dévoilés.

**Why this priority**: c'est le jeu qui peut glisser en décembre si le calendrier se tend, comme prévu dans le cahier des charges.

**Independent Test**: lancer un dessin, faire deviner plusieurs membres dans un ordre donné et vérifier les gains, puis vérifier la fin du jeu dans les deux cas.

**Acceptance Scenarios**:

1. **Given** un Pixel mystère en cours, **When** Cami propose le bon mot (sans tenir compte des majuscules ni des accents), **Then** elle gagne les lauriers de son rang d'arrivée et voit le dessin entier.
2. **Given** 3 essais déjà faits aujourd'hui, **When** Cami propose un mot, **Then** l'appli refuse jusqu'au lendemain.
3. **Given** tous les membres sauf l'auteur·rice ont trouvé, **When** le dernier trouve, **Then** le jeu se termine et le dessin s'affiche pour tous.
4. **Given** tous les pixels dévoilés, **When** la dernière révélation a lieu, **Then** le jeu se termine et le mot est donné.

---

### User Story 11 - Mes données et mes préférences (Priority: P3)

Cami choisit le thème clair, sombre ou automatique, coupe les animations, règle ses notifications, quitte une rédaction, exporte ses données ou supprime son compte en un clic.

**Why this priority**: obligatoire pour la confiance et la conformité, mais simple et indépendant du jeu.

**Independent Test**: exporter les données d'un compte actif, puis le supprimer et vérifier que son e-mail, ses nom et prénom ont disparu et que ses anciens paris apparaissent sous « ancien membre ».

**Acceptance Scenarios**:

1. **Given** un compte, **When** Cami demande l'export, **Then** elle obtient un fichier avec son compte, ses rédactions, ses paris, son relevé de lauriers et sa collection.
2. **Given** un compte, **When** Cami confirme la suppression, **Then** ses données personnelles sont effacées et ses paris passés restent comptés sous « ancien membre ».
3. **Given** Cami seule rédaction en chef d'une organisation qui a d'autres membres, **When** elle veut quitter l'organisation ou supprimer son compte, **Then** l'appli lui demande d'abord de nommer une autre rédaction en chef.

---

### User Story 12 - Programmer les jeux de la semaine (Priority: P3)

Inès, rédaction en chef, ouvre l'onglet « Jeux » des réglages. Une semaine ordinaire, Sophia Office joue à la course de la boule et à Pixel mystère. Pour la semaine de Noël, Inès décoche les deux jeux ; pour la suivante, elle ne garde que la course. Les membres ne voient sur la une et ne jouent que les jeux de la semaine en cours. Un mercredi, Inès retire Pixel mystère : le dessin en cours s'arrête et son mot est donné.

**Why this priority**: les jeux restent un bonus ; les programmer laisse chaque rédaction les doser selon ses semaines, sans toucher au reste.

**Independent Test**: avec la rédaction en chef, retirer la course de la semaine en cours, puis vérifier qu'elle disparaît de la une d'un·e lecteur·rice et qu'une partie est refusée. Programmer une semaine sans jeu, avancer l'horloge et vérifier que l'encadré disparaît. Retirer Pixel mystère pendant un dessin et vérifier que le mot est donné. Vérifier qu'un·e journaliste ne peut ni voir ni changer le programme.

**Acceptance Scenarios**:

1. **Given** une rédaction qui n'a rien programmé, **When** une semaine commence, **Then** ses jeux sont ceux d'une semaine ordinaire : au départ, la course de la boule et Pixel mystère.
2. **Given** la rédaction en chef, **When** elle décoche Pixel mystère dans « Une semaine ordinaire », **Then** les semaines suivantes sans programme propre n'ont plus que la course ; la semaine en cours garde ses jeux.
3. **Given** l'onglet « Jeux », **When** Inès décoche les deux jeux de la semaine du 21 décembre, **Then** cette semaine-là n'a aucun jeu : l'encadré « Jeux de la semaine » disparaît de la une, et les pages des jeux disent qu'ils ne sont pas au programme.
4. **Given** une semaine sans la course, **When** Cami lance une partie, **Then** l'appli refuse : la course n'est pas au programme cette semaine.
5. **Given** des essais déjà joués cette semaine, **When** Inès retire la course de la semaine en cours, **Then** plus aucune partie ne s'ouvre ni ne se termine, et le lundi ne verse rien pour cette semaine. Si Inès remet la course avant la fin de la semaine, les essais joués comptent de nouveau.
6. **Given** un Pixel mystère en cours, **When** Inès retire Pixel mystère de la semaine en cours, ou qu'une semaine sans Pixel mystère commence, **Then** le dessin s'arrête, son mot est donné et les lauriers déjà gagnés restent ; les dessins déposés attendent la prochaine semaine avec Pixel mystère.
7. **Given** la semaine en cours et les trois suivantes, **When** Inès veut programmer une semaine passée ou une cinquième semaine, **Then** l'appli refuse. Une semaine à venir déjà programmée peut redevenir une semaine ordinaire.
8. **Given** un·e journaliste ou un·e lecteur·rice, **When** il ou elle veut voir ou changer le programme, **Then** l'appli refuse.

---

### User Story 13 - Enchaîner les victoires (Priority: P3)

Cami gagne trois pronos d'affilée : une petite flamme en pixel art, animée, s'allume à côté de son pseudo dans le classement, sur la une et dans la liste des membres, avec le chiffre 3. Sur sa carte de presse, la flamme suit aussi son pseudo, et son record s'affiche. Un prono perdu éteint la flamme ; un prono qu'elle n'a pas joué, ou un prono annulé, ne la casse pas.

**Why this priority**: la chaîne donne une raison de revenir parier et de bien parier, mais le jeu se joue sans.

**Independent Test**: régler trois pronos gagnés par un membre, vérifier la flamme et le chiffre 3 dans le classement et sur sa carte de presse ; lui faire perdre un prono et vérifier que la flamme s'éteint et que le record reste à 3 ; vérifier qu'un prono annulé ou qu'il n'a pas joué ne casse pas la chaîne, et qu'une correction de résultat la recalcule.

**Acceptance Scenarios**:

1. **Given** Cami a gagné ses deux derniers pronos réglés, **When** on ouvre le classement, **Then** une flamme animée et le chiffre 2 suivent son pseudo ; avec une seule victoire d'affilée, il n'y a pas de flamme.
2. **Given** une chaîne de 3, **When** Cami perd un prono, **Then** la flamme s'éteint partout, et sa carte de presse garde son record : 3 pronos gagnés d'affilée.
3. **Given** une chaîne de 3, **When** un prono qu'elle a joué est annulé, ou qu'un prono qu'elle n'a pas joué est réglé, **Then** sa chaîne reste à 3.
4. **Given** une chaîne de 3, **When** la rédaction en chef corrige le résultat de l'avant-dernier de ces pronos et que Cami l'a alors perdu, **Then** sa chaîne passe à 1 : un prono corrigé garde sa place dans l'ordre des résultats.
5. **Given** « couper les animations » activé, **When** Cami regarde une flamme, **Then** elle reste immobile.

---

### User Story 14 - Discuter d'un prono (Priority: P3)

Sous « Nice ou Monaco samedi ? », Hugo écrit : « Monaco n'a pas gagné à Nice depuis 2019. » Cami, qui regarde le prono, voit le message arriver sans recharger, et l'aime : le compteur passe à 1 pour tout le monde. Chacun peut supprimer ses propres messages ; la rédaction en chef retire ceux qui sortent de la charte.

**Why this priority**: la discussion fait vivre les pronos entre deux paris, mais le jeu se joue sans.

**Independent Test**: depuis deux navigateurs, écrire un message sous un prono et vérifier que l'autre le voit sans recharger ; l'aimer puis retirer son « J'aime » ; supprimer son propre message ; retirer le message d'un autre avec la rédaction en chef ; vérifier qu'un·e lecteur·rice ne peut pas supprimer le message d'un autre et qu'un membre d'une autre rédaction ne voit rien.

**Acceptance Scenarios**:

1. **Given** un prono publié, **When** Cami écrit un message de 1 à 500 caractères, **Then** il apparaît sous le prono avec son pseudo, son avatar et l'heure, chez chaque membre qui regarde le prono, dans les 2 secondes.
2. **Given** un message, **When** Cami appuie sur « J'aime », **Then** le compteur augmente de 1 pour tout le monde ; un second appui retire son « J'aime ». À côté du compteur, on lit qui a aimé.
3. **Given** un message de Cami, **When** elle le supprime, **Then** il disparaît pour tout le monde, avec ses « J'aime ».
4. **Given** un message d'Hugo hors charte, **When** la rédaction en chef le retire, **Then** il disparaît pour tout le monde ; un·e journaliste ou un·e lecteur·rice ne peut retirer que ses propres messages.
5. **Given** un prono proposé ou refusé, **When** quelqu'un veut en discuter, **Then** l'appli refuse : la discussion s'ouvre avec la publication et reste ouverte après le résultat.
6. **Given** des pronos avec des messages, **When** Cami regarde la une ou la liste des pronos, **Then** chaque prono indique son nombre de messages.
7. **Given** une discussion de plus de 20 messages, **When** Cami ouvre le prono, **Then** elle voit les 20 derniers, du plus ancien au plus récent, et peut afficher les précédents.

---

### User Story 15 - Montrer sa carte de presse hors de la rédaction (Priority: P3)

Cami veut montrer sa carte de presse sur son blog. Sous sa carte, elle active « Profil public » : l'appli lui explique ce que tout le monde verra, puis lui donne un lien et le code d'une iframe, qu'elle colle dans son blog. Ses lecteurs y voient sa carte sans compte Sibylle. Quand elle repasse en privé, le lien et l'iframe n'affichent plus sa carte ; si elle la rend publique de nouveau, ils la montrent encore.

**Why this priority**: elle fait connaître le jeu et donne une vitrine à chacun, mais le jeu se joue sans.

**Independent Test**: activer « Profil public » sur sa carte, ouvrir le lien dans un navigateur sans session puis dans l'iframe d'un autre site ; vérifier ce qui s'affiche et ce qui ne s'affiche pas ; repasser en privé et vérifier que le lien ne montre plus rien, puis public de nouveau à la même adresse.

**Acceptance Scenarios**:

1. **Given** sa carte de presse, **When** Cami l'ouvre, **Then** « Profil public » est désactivé et explique ce qu'une carte publique montre, et à qui.
2. **Given** « Profil public » activé, **When** quelqu'un sans compte ouvre le lien, **Then** il voit la carte de Cami seule sur la page (pseudo, avatar et cadre, rôle, rédaction, arrivée, objets mis en avant, lauriers, pronos joués, réussite, chaîne de victoires), et rien d'autre : ni ses paris, ni ses messages, ni son relevé, ni son nom ou son e-mail.
3. **Given** le code d'intégration collé dans le blog de Cami, **When** un lecteur ouvre le blog, **Then** la carte s'affiche dans l'iframe.
4. **Given** une carte publique, **When** Cami la repasse en privé, **Then** le lien et l'iframe disent seulement que la carte n'est pas publique ; rendue publique de nouveau, elle reprend la même adresse.
5. **Given** une carte publique, **When** Cami quitte la rédaction ou supprime son compte, **Then** le lien n'affiche plus sa carte ; si elle revient dans la rédaction, sa carte reste privée tant qu'elle ne la rend pas publique.

---

### Edge Cases

- Deux membres parient au même instant avec le même solde : chaque pari est traité à part et aucun solde ne devient négatif par une mise.
- Un pari arrive à la seconde de la clôture : l'heure du serveur fait foi.
- Un prono est relancé plusieurs fois : les paris restent, la cagnotte s'accumule, le rang lève-tôt reste celui du premier pari.
- Une correction de résultat reprend des lauriers déjà dépensés : le solde peut devenir négatif ; le membre ne peut plus miser tant qu'il l'est.
- Un prono de nombre ou de date avec égalité de distance : tous les ex aequo gagnent.
- Le partage de la cagnotte ne tombe pas juste : les lauriers restants vont un par un aux plus grosses mises, puis aux paris les plus anciens.
- Un prono résolu dans une saison sur lequel on a misé à la saison précédente : les gains comptent dans la saison de la résolution.
- Un membre quitte la rédaction avec des paris en cours : ses mises restent dans les cagnottes et ses gains éventuels sont versés s'il revient.
- Un lien d'invitation est utilisé en même temps par plusieurs personnes alors qu'il reste une seule place : une seule entre.
- Personne n'a parié avant la clôture : le prono est relancé ou annulé par un·e journaliste, il ne se résout pas.
- La machine redémarre pendant une clôture de saison : la clôture reprend sans verser deux fois les trophées ni les remises au solde.
- Un membre ouvre l'appli hors ligne : il voit la dernière version chargée et un message lui indique que les paris demandent une connexion.
- Une partie de course commencée le dimanche soir finit le lundi, dans une semaine sans course : elle compte pour la semaine où elle a commencé.
- La rédaction en chef change la semaine ordinaire le lundi à 00:10, avant le paiement de la course. La semaine écoulée et la semaine en cours gardent leurs jeux, et la course de la semaine écoulée est payée.
- Deux rédactions en chef changent le programme de la même semaine au même moment : la dernière modification l'emporte.
- Deux pronos sont réglés au même instant : la chaîne de victoires suit l'ordre dans lequel ils ont été réglés pour la première fois.
- Un message vide ou fait d'espaces est refusé ; les espaces qui l'entourent sont retirés.
- Deux membres aiment le même message au même instant : chaque « J'aime » compte une fois ; aimer deux fois ne change rien.
- Un message est supprimé pendant qu'un autre membre l'aime : le « J'aime » est refusé et le message disparaît de son écran.
- Un membre quitte la rédaction : ses messages restent sous son pseudo. Un compte supprimé : ses messages sont effacés, ses « J'aime » restent comptés sous « Ancien membre ».
- Un membre de plusieurs rédactions a une carte dans chacune : chaque carte se rend publique à part, avec son propre lien.
- Un lien de carte inventé ou mal recopié répond comme celui d'une carte privée : rien ne dit si la carte existe.
- Plusieurs actions de suite : trois notifications au plus à la fois, la plus ancienne laisse sa place ; la même deux fois de suite n'en montre qu'une.

## Requirements *(mandatory)*

### Functional Requirements

**Comptes**

- **FR-001**: Le système DOIT permettre de créer un compte avec e-mail, mot de passe, nom et prénom, sans invitation.
- **FR-002**: Le système DOIT vérifier l'adresse e-mail par un lien ; un compte non vérifié peut jouer mais ne reçoit pas d'e-mails de notification.
- **FR-003**: Le système DOIT permettre la connexion par e-mail et mot de passe uniquement, et la réinitialisation du mot de passe par un lien e-mail à usage unique.
- **FR-004**: Le système NE DOIT JAMAIS montrer le nom, le prénom ou l'e-mail d'un compte à un autre membre.

**Organisations et invitations**

- **FR-010**: Tout compte DOIT pouvoir créer une organisation et en devient la rédaction en chef.
- **FR-011**: Le système DOIT permettre de rejoindre une organisation par un lien d'invitation (nombre de places et date d'expiration), par un code d'accès, ou par une invitation nominative envoyée par e-mail. Le lien et l'invitation par e-mail portent le rôle choisi par la rédaction en chef en les créant (lecteur·rice par défaut, journaliste ou rédaction en chef) : la page pour rejoindre et l'e-mail le disent, et chaque personne qui entre par eux prend ce rôle, un ancien membre qui revient compris. Le code d'accès fait entrer comme lecteur·rice.
- **FR-012**: En rejoignant, le membre DOIT choisir un pseudo unique dans l'organisation, un avatar parmi des modèles, et accepter la charte de l'organisation.
- **FR-013**: Un compte DOIT pouvoir appartenir à plusieurs organisations ; pseudo, avatar, lauriers, statistiques et collection sont propres à chacune.
- **FR-014**: Les organisations NE DOIVENT avoir aucune visibilité entre elles (pronos, membres, classements, notifications).
- **FR-015**: La carte d'organisation (logo en pixel art, fond choisi dans une liste, titre) DOIT être modifiable par la rédaction en chef seulement. Chaque rédaction a un logo dès sa création, sans avoir à le choisir : le logo par défaut, déjà sélectionné dans les réglages, tant que la rédaction en chef ne le change pas (« Modifier le logo ») ; retirer un logo ramène celui par défaut.
- **FR-016**: Chaque organisation DOIT pouvoir créer, renommer, ordonner et supprimer ses rubriques.

**Rôles**

- **FR-020**: Le système DOIT appliquer la matrice de droits du cahier des charges pour les trois rôles (lecteur·rice, journaliste, rédaction en chef), côté serveur.
- **FR-021**: Un nouveau membre DOIT arriver lecteur·rice ; seule la rédaction en chef nomme ou retire les journalistes et les autres rédactions en chef.
- **FR-022**: Une organisation qui a des membres DOIT toujours garder au moins une rédaction en chef.

**Pronos**

- **FR-030**: Un prono DOIT avoir une question, une rubrique, un type (choix, oui/non, nombre, date), une date de clôture (sauf prono de date « sans fin »), un gain de base et, en option, un lien, une image, une date d'ouverture programmée et une date de résultat attendu.
- **FR-031**: Le gain de base DOIT être choisi par le créateur, entre 0 et le plafond fixé par l'organisation.
- **FR-032**: Un prono à choix DOIT accepter une liste de choix sans limite de taille (au moins deux).
- **FR-033**: Un·e journaliste DOIT pouvoir publier directement ; un·e lecteur·rice DOIT pouvoir proposer un prono, publié après validation ou refusé par un·e journaliste.
- **FR-034**: Un prono DOIT suivre le cycle : proposé → publié (programmé) → ouvert → clos → résolu, avec relance (clos → ouvert, nouvelle date, paris conservés), refus d'une proposition et annulation.
- **FR-035**: Un prono DOIT être modifiable par son créateur journaliste ou la rédaction en chef tant que personne n'a parié.

**Paris et mises**

- **FR-040**: Chaque membre DOIT pouvoir parier une seule fois par prono, de façon définitive ; le créateur peut parier comme les autres.
- **FR-041**: Une mise DOIT être un nombre entier de lauriers entre 0 et le solde du membre, sans autre plafond ; elle est retirée du solde au moment du pari.
- **FR-042**: La répartition des votes, le choix et la mise de chaque membre, et la cagnotte DOIVENT être visibles par toute la rédaction dès le pari, et mis à jour en direct.
- **FR-043**: Pour un prono de date « sans fin », un membre dont la date est passée sans l'événement DOIT pouvoir parier une nouvelle date (strictement future) ; sa mise précédente reste dans la cagnotte.
- **FR-044**: Aucun pari NE DOIT être accepté hors de l'état « ouvert ».

**Résultat, gains et relance**

- **FR-050**: Tout·e journaliste ou rédaction en chef DOIT pouvoir désigner le résultat d'un prono clos : une ou plusieurs bonnes réponses pour un choix, la bonne réponse pour un oui/non, la valeur réelle pour un nombre ou une date.
- **FR-051**: Pour un nombre ou une date, les gagnants DOIVENT être les paris les plus proches de la valeur réelle, ex aequo compris.
- **FR-052**: Chaque gagnant DOIT recevoir le gain de base du prono ; les gagnants parmi les N premiers parieurs DOIVENT recevoir en plus le bonus lève-tôt (pourcentage du gain de base, arrondi à l'entier inférieur), N et le pourcentage étant réglés par l'organisation.
- **FR-053**: La cagnotte (toutes les mises du prono) DOIT être partagée entre les gagnants au prorata de leur mise, arrondie à l'entier inférieur, le reste allant un par un aux plus grosses mises puis aux paris les plus anciens ; s'il n'y a aucun gagnant, ou si les gagnants n'ont rien misé, la cagnotte est perdue.
- **FR-054**: Le résultat DOIT être publié dans une « édition spéciale » et notifié aux participants.
- **FR-055**: Un·e journaliste DOIT pouvoir relancer un prono clos (événement reporté ou annulé, ou aucun pari avant la clôture) avec une nouvelle date ; les paris sont conservés.
- **FR-056**: Chaque membre DOIT pouvoir « Signaler une erreur » sur un résultat ; la rédaction en chef DOIT pouvoir corriger le résultat (les gains sont alors recalculés par écritures inverses) ou annuler le prono (les mises sont rendues).
- **FR-057**: Le créateur d'un prono clos (ou le ou la journaliste qui l'a validé) DOIT recevoir des rappels pour désigner le résultat, à partir de la date de résultat attendu.

**Lauriers**

- **FR-060**: Chaque membre DOIT avoir un solde (ce qu'il peut miser ou dépenser) et un score de saison (gains des pronos moins mises perdues), propres à chaque organisation.
- **FR-061**: Seuls les pronos DOIVENT faire bouger le score ; les achats, les gains de mini-jeux et les ajustements de la rédaction en chef ne touchent que le solde.
- **FR-062**: Chaque mouvement de lauriers DOIT apparaître dans le relevé du membre avec son motif.
- **FR-063**: La rédaction en chef DOIT pouvoir ajouter ou retirer des lauriers à un membre, avec un motif obligatoire.
- **FR-064**: L'organisation DOIT régler son solde de départ, son plafond de gain de base et son bonus lève-tôt (pourcentage et nombre de premiers joueurs).

**Classements et saisons**

- **FR-070**: Le système DOIT proposer deux classements (lauriers, pronos gagnés) sur trois périodes (mois, saison, depuis toujours), avec tous les membres actifs.
- **FR-071**: Les saisons DOIVENT être : printemps du 21 mars au 20 juin, été du 21 juin au 22 septembre, automne du 23 septembre au 20 décembre, hiver du 21 décembre au 20 mars (heure de Paris).
- **FR-072**: À la fin d'une saison, chaque membre ayant parié au moins une fois dans la saison DOIT recevoir un trophée gravé (année, saison, score) ; les trois premiers ont un cadre doré ; puis chaque solde repart au solde de départ et chaque score à zéro.
- **FR-073**: Le classement des lauriers « depuis toujours » DOIT additionner les scores gravés sur les trophées et le score de la saison en cours.
- **FR-074**: La chaîne de victoires d'un membre DOIT compter ses pronos gagnés d'affilée, du plus récent vers le plus ancien, dans l'ordre où les pronos ont été réglés pour la première fois. Un prono perdu la remet à zéro ; un prono annulé ou qu'il n'a pas joué ne la change pas ; une correction de résultat la recalcule. Elle ne repart pas à zéro en fin de saison. Le record est la plus longue chaîne du membre dans la rédaction.
- **FR-075**: À partir de 2 victoires d'affilée, une flamme en pixel art animée et le nombre de victoires DOIVENT suivre le pseudo du membre dans le classement, dans le haut du classement de la une, dans la liste des membres et sur la carte de presse, qui DOIT aussi montrer le record dès qu'il atteint 2. La flamme reste immobile quand les animations sont coupées.

**La une**

- **FR-080**: La une DOIT afficher, dans l'ordre : le prono ouvert dont la clôture est la plus proche, les autres pronos ouverts, les pronos à désigner (pour les journalistes), les derniers résultats, le haut du classement, les jeux de la semaine, le mot de la rédaction en chef.
- **FR-081**: Chaque membre DOIT pouvoir réagir à un prono avec un jeu fixe de réactions rapides, et en discuter (FR-140 à FR-143).

**Profil et collection**

- **FR-090**: Le profil DOIT prendre la forme d'une carte de presse : pseudo, avatar, date d'arrivée, statistiques (lauriers, pronos joués, taux de réussite) et collection.
- **FR-091**: L'éditeur d'avatar DOIT permettre de dessiner en 16×16 ou 32×32 avec une palette fixe : les tons de peau et cinq couleurs (encre, papier, rouge, indigo, or) sont offerts ; les autres couleurs, les cadres et les animations se débloquent contre des pièces. Une couleur déjà présente dans l'avatar enregistré reste utilisable. Le logo de la rédaction et les dessins de Pixel mystère gardent toute la palette de base. Les avatars proposés par défaut n'utilisent que les couleurs offertes. Il DOIT offrir crayon, gomme, remplissage et pipette (aussi au clic droit), un miroir qui dessine les deux moitiés à la fois, la grille à afficher ou masquer, défaire, refaire et tout effacer. Un trait DOIT rester continu même quand le doigt ou la souris va vite, et tout DOIT se faire aussi au clavier.
- **FR-092**: La collection DOIT contenir les trophées de saison (la boule gravée) et les boules débloquées par code secret ; les boules ne s'achètent pas.
- **FR-093**: Des codes secrets DOIVENT pouvoir débloquer une seule fois une surprise (variante de boule, couleur rare).
- **FR-094**: Chaque lundi à 00:00 (heure de Paris), chaque membre actif arrivé avant ce moment DOIT recevoir autant de pièces que ses lauriers en or (solde plus mises des paris pas encore réglés ; rien s'ils sont à zéro ou négatifs). Ses lauriers ne changent pas. La conversion a lieu une seule fois par semaine et par membre, même si le `worker` redémarre.
- **FR-095**: Les pièces DOIVENT être le seul moyen de payer dans la collection ; elles ne comptent dans aucun classement et ne repartent pas à zéro en fin de saison. Chaque semaine (du lundi 00:00 au dimanche 23:59, heure de Paris), un objet à vendre de la collection, tiré au hasard pour chaque rédaction, DOIT être en promotion d'un pourcentage lui aussi tiré au hasard (20, 30, 40 ou 50 %), pendant toute la semaine : la collection montre l'ancien prix barré et le nouveau, et l'achat se paie au prix réduit. Si la semaine change entre l'affichage et l'achat, l'achat est refusé et la collection montre le nouveau prix.
- **FR-096**: L'appli DOIT montrer séparément les lauriers verts (le solde, ce qu'on peut miser), les lauriers en or (solde plus mises en jeu) et les pièces. On mise et on gagne des lauriers verts : les mises, les gains, la carte de presse et les classements les montrent en vert. Chaque compteur DOIT expliquer ce qu'il représente au survol, au focus ou au toucher. À la première ouverture après une conversion, une fenêtre DOIT annoncer les pièces reçues, une seule fois.
- **FR-097**: Le menu principal DOIT avoir un onglet « Rédaction » : la carte de la rédaction (logo, nom, membres, rédaction en chef ; pour la rédaction en chef, les invitations, le code d'accès et les réglages), puis la liste des membres avec leur rôle (rédaction en chef, journalistes, puis lecteur·rices), chacun ouvrant sa carte de presse ; le relevé reste visible de son seul titulaire. Une petite carte de la rédaction (logo, nom, membres), à droite de la navigation sur ordinateur et sur la une sur téléphone, DOIT ouvrir sur place un menu déroulant : les rédactions du compte, celle en cours marquée, pour en changer, puis en dernier « Rejoindre ou créer une rédaction ». Partout, la rédaction se montre par son logo, jamais par une initiale.
- **FR-098**: Chaque membre DOIT pouvoir personnaliser sa carte sur un seul écran : pseudo, avatar dessiné, cadre parmi ceux qu'il possède, et jusqu'à trois objets de sa collection ou trophées de saison mis en avant, montrés dans l'ordre choisi. L'écran DOIT montrer la carte telle que les autres membres la verront, mise à jour à chaque changement, avec dessous « Annuler » (qui remet ce qui était enregistré) et « Enregistrer » (qui garde tout d'un geste), actifs seulement après une modification ; l'écran reste ouvert après l'enregistrement. Un objet qui ne lui appartient plus disparaît de la carte.
- **FR-099**: La page d'accueil « Bienvenue sur Sibylle » DOIT lister, sous « Créer une rédaction », les rédactions du compte pour y revenir. Hors d'une rédaction, une roue crantée en haut à droite DOIT ouvrir « Mes réglages ». Sur sa propre carte de presse, après « Ma collection », chaque membre DOIT trouver « Réglages » puis « Déconnexion », en rouge, qui demande confirmation avant de déconnecter (comme le bouton des réglages). Les réglages DOIVENT ramener là d'où l'on vient : le profil de la rédaction, ou la page d'accueil.

**Notifications**

- **FR-100**: Le système DOIT envoyer des notifications push (appli installée) et des e-mails pour : un nouveau prono, un prono qui ferme dans 2 h sans pari de ma part, le résultat d'un prono que j'ai joué, un rappel de désignation (journalistes).
- **FR-101**: Chaque membre DOIT pouvoir activer ou couper chaque type, canal par canal ; il n'y a aucun récapitulatif périodique.
- **FR-102**: Quand l'appli installée s'ouvre sur une rédaction, elle DOIT proposer d'activer les notifications push dans une fenêtre, une seule fois par appareil ; l'autorisation du navigateur n'est demandée qu'après un clic sur « Activer les notifications ».

**Mini-jeux**

- **FR-110**: La course de la boule DOIT offrir 5 essais par membre et par semaine (du lundi 00:00 au dimanche 23:59, heure de Paris), ne retenir que le meilleur score et verser 10, 7, 5 lauriers aux trois premiers et 2 aux autres joueurs à la fin de la semaine.
- **FR-111**: Pixel mystère DOIT permettre à un·e journaliste ou à la rédaction en chef de déposer un dessin et son mot ; chaque jour, des pixels se dévoilent au hasard, de sorte que le dessin soit entier en 7 jours au plus.
- **FR-112**: Pixel mystère DOIT verser 10, 7, 5 lauriers aux trois premiers qui trouvent, puis 3 aux suivants ; 3 essais par jour et par membre ; l'auteur·rice ne joue pas ; le jeu se termine quand tous les autres membres ont trouvé ou quand tous les pixels sont dévoilés.
- **FR-113**: La rédaction en chef DOIT pouvoir choisir les jeux de la semaine en cours et des 3 suivantes (du lundi 00:00 au dimanche 23:59, heure de Paris), parmi la course de la boule et Pixel mystère. Une semaine peut n'avoir aucun jeu. Seule la rédaction en chef voit et change ce programme.
- **FR-114**: Une semaine sans programme propre DOIT prendre les jeux d'une semaine ordinaire, que règle la rédaction en chef (les deux jeux à la création de la rédaction). Un changement de ce réglage vaut à partir de la semaine suivante : la semaine en cours et les semaines passées gardent leurs jeux. Une semaine à venir programmée DOIT pouvoir redevenir une semaine ordinaire.
- **FR-115**: Les membres NE DOIVENT voir et jouer que les jeux de la semaine en cours. L'encadré « Jeux de la semaine » ne montre qu'eux et disparaît s'il n'y en a aucun ; la page d'un jeu hors programme le dit, et le serveur refuse ses parties et ses propositions.
- **FR-116**: Retirer la course de la semaine en cours DOIT annuler sa semaine : plus aucune partie ne s'ouvre ni ne se termine, et le lundi ne verse rien pour elle. Le lundi ne paie une semaine que si la course est encore à son programme quand elle se termine.
- **FR-117**: Retirer Pixel mystère de la semaine en cours, ou commencer une semaine sans lui, DOIT arrêter le dessin en cours : son mot est donné et les lauriers déjà gagnés restent. Les dessins déposés entre-temps attendent la prochaine semaine où Pixel mystère est au programme.

**Modération et données**

- **FR-120**: Chaque organisation DOIT avoir une charte courte, acceptée en la rejoignant, qui interdit par défaut la santé et la vie privée des collègues et la politique.
- **FR-121**: La rédaction en chef DOIT disposer d'une liste des signalements à traiter.
- **FR-122**: Chaque membre DOIT pouvoir exporter ses données et supprimer son compte ; la suppression efface les données personnelles et rend anonymes les traces de jeu.
- **FR-123**: Chaque membre DOIT pouvoir quitter une organisation ; s'il revient avec le même compte, il retrouve son profil et son historique.

**Discussion**

- **FR-140**: Chaque prono publié DOIT avoir sa discussion, ouverte dans tous ses états sauf proposé et refusé : tout membre actif peut y écrire des messages de 1 à 500 caractères, montrés du plus ancien au plus récent avec le pseudo, l'avatar et l'heure de leur auteur·rice, mis à jour en direct (comme les paris, SC-002). L'écran montre les 20 derniers messages et peut afficher les précédents.
- **FR-141**: Chaque membre DOIT pouvoir aimer un message une fois et retirer son « J'aime ». Le nombre de « J'aime » et les pseudos de qui a aimé sont visibles par toute la rédaction.
- **FR-142**: L'auteur·rice d'un message DOIT pouvoir le supprimer, et la rédaction en chef DOIT pouvoir retirer tout message ; un message supprimé disparaît pour tous, avec ses « J'aime ». Un message ne se modifie pas.
- **FR-143**: La une et la liste des pronos DOIVENT indiquer le nombre de messages de chaque prono. L'export d'un compte DOIT contenir ses messages ; la suppression du compte les efface.

**Carte de presse publique**

- **FR-144**: Chaque membre DOIT pouvoir rendre publique sa carte de presse, rédaction par rédaction, depuis sa carte : un interrupteur « Profil public », désactivé par défaut, avec l'explication de ce que voit le public. Une carte publique DOIT montrer à son membre son lien et le code d'une iframe, chacun avec un bouton pour le copier.
- **FR-145**: Une carte publique DOIT se lire sans compte, à son lien, seule sur la page, y compris dans l'iframe d'un autre site : pseudo, avatar et cadre, rôle, nom de la rédaction, numéro et date d'arrivée, objets mis en avant, lauriers, pronos joués, réussite, chaîne et record de victoires. Jamais les paris, les messages, le relevé, ni le nom, le prénom ou l'e-mail. Les moteurs de recherche sont priés de ne pas l'indexer.
- **FR-146**: Le lien d'une carte DOIT rester le même quand elle repasse en privé puis redevient publique. Tant que la carte est privée, que son membre a quitté la rédaction (sa carte redevient alors privée) ou que son compte est supprimé, le lien répond comme un lien qui n'a jamais existé.

**Préférences et plateforme**

- **FR-130**: Chaque membre DOIT pouvoir choisir le thème clair, sombre ou automatique et couper les animations.
- **FR-131**: L'appli DOIT être installable (mobile et ordinateur) et avoir une mise en page dédiée sur ordinateur.
- **FR-132**: Tous les textes de l'interface et des e-mails DOIVENT passer par un catalogue de traduction ; seul le français est livré en v1.
- **FR-133**: Le parrainage NE FAIT PAS partie de la v1.
- **FR-134**: Après chaque action (enregistrer, parier, publier, inviter, acheter, copier un lien…), l'appli DOIT dire ce qui est fait, ou ce qui a échoué, dans une petite notification en haut à droite de l'écran (en haut sur téléphone), avec une barre qui se vide avant qu'elle disparaisse : 4 secondes, 6,5 pour une erreur. Une croix la ferme ; un clic ailleurs sur elle passe à la page. La page elle-même ne change pas pour le dire : seules les erreurs propres à un champ restent sous ce champ, et les états durables (hors ligne, partie terminée, lien d'invitation à copier) restent dans la page.

### Key Entities *(include if feature involves data)*

- **Compte** : une personne ; e-mail, mot de passe, nom et prénom (privés), préférences.
- **Organisation (rédaction)** : carte (logo, fond, titre), réglages de lauriers, charte, code d'accès, mot de la rédaction en chef.
- **Membre** : le lien entre un compte et une organisation ; rôle, pseudo, avatar, cadre, solde, score de saison, pièces, collection, objets mis en avant, et l'adresse de sa carte publique, s'il l'a rendue publique.
- **Invitation** : lien à places limitées et date d'expiration, ou invitation nominative par e-mail, avec le rôle donné à l'arrivée.
- **Rubrique** : catégorie de pronos propre à une organisation.
- **Prono** : question, type, choix, dates, gain de base, état, résultat, historique des relances.
- **Pari** : la réponse d'un membre à un prono, avec sa mise et son rang d'arrivée.
- **Écriture de lauriers** : un mouvement du registre (mise, gain, part de cagnotte, mini-jeu, ajustement, remise au solde), avec son motif.
- **Écriture de pièces** : la conversion du lundi ou un achat dans la collection.
- **Promotion de la semaine** : l'objet et le pourcentage de réduction d'une rédaction pour une semaine.
- **Saison et trophée** : une période fixe du calendrier ; le trophée grave le score d'un membre à la fin de la saison.
- **Objet de collection** : couleur ou cadre acheté avec des pièces, ou surprise débloquée par code secret (boule, couleur rare).
- **Réaction, signalement, notification** : interactions autour d'un prono.
- **Message et « J'aime »** : la discussion d'un prono, message par message, et qui a aimé chacun.
- **Partie de course et Pixel mystère** : essais, scores, dessins, mots et propositions.
- **Programme des jeux** : les jeux de chaque semaine programmée, et ceux d'une semaine ordinaire, datés de la semaine à partir de laquelle ils valent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Une personne invitée crée son compte, rejoint la rédaction et fait son premier pari en moins de 2 minutes.
- **SC-002**: Un pari est visible chez les autres membres qui regardent le prono en moins de 2 secondes.
- **SC-003**: Dans 100 % des cas testés, les lauriers versés depuis une cagnotte sont égaux à la cagnotte (ou à zéro quand elle est perdue), et aucun solde ne devient négatif par une mise.
- **SC-004**: Avec une rédaction de 50 membres et 20 pronos ouverts, chaque écran s'affiche en moins de 1,5 seconde sur un téléphone en 4G.
- **SC-005**: Un audit réseau de l'appli ne montre aucune requête vers un domaine tiers depuis le navigateur.
- **SC-006**: L'appli s'installe sur Android, iOS (16.4 ou plus) et ordinateur, et y reçoit les notifications push.
- **SC-007**: Les écrans principaux passent un audit automatique d'accessibilité sans erreur bloquante (WCAG 2.2 AA).
- **SC-008**: La v1 est en ligne le 1ᵉʳ décembre 2026, avec les histoires P1 et P2 au minimum.

## Assumptions

- Propositions du cahier des charges retenues : réinitialisation du mot de passe par lien e-mail ; une annulation rend les mises ; les notifications push passent par l'appli installée ; l'ordre de la une ci-dessus.
- Le trophée grave le score de la saison (et non le solde), pour que le classement « depuis toujours » reste cohérent avec le classement des lauriers.
- Les rappels de désignation partent à la date de résultat attendu, puis à J+1, J+3, J+7, puis chaque semaine ; sans date de résultat attendu, ils partent le lendemain de la clôture.
- Une correction de résultat peut rendre un solde négatif ; le membre ne peut plus miser tant qu'il l'est.
- Pixel mystère : une fois un jeu terminé, le dessin suivant préparé par la rédaction démarre le lendemain matin.
- Le catalogue de la collection (couleurs et cadres à acheter, boules à débloquer) et les prix en pièces sont définis par la plateforme et identiques pour toutes les rédactions ; les codes secrets aussi.
- Le jeu fixe de réactions rapides est défini par la plateforme (cinq emoji en pixel art, fixes et animés, research.md J17).
- Sans limite stricte de membres par organisation ; l'appli est conçue pour 10 à 50 membres et doit rester fluide jusqu'à 100.
- L'appli est hébergée sur une machine à domicile, exposée par frp depuis un VPS qui porte le nom de domaine ; les coupures de courant ou de connexion à domicile sont acceptées pour un jeu sans enjeu.
- Les e-mails partent par Brevo ; l'heure de référence est celle de Paris.
