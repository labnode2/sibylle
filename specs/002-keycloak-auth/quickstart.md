# Quickstart: Connexion par Keycloak

Comment vérifier que la fonctionnalité marche, en local puis en production. Les routes et les
réglages sont dans `contracts/auth.md`, les tables dans `data-model.md`.

## En local

Prérequis : `make setup` déjà fait une fois (base, dépendances, `deploy/.env`).

```bash
make db          # PostgreSQL et Mailpit
make keycloak    # Keycloak 26.8.2 avec le thème et le realm de dev-realm.json, sur :8280
make migrate     # dont 0023_keycloak
make seed        # la rédaction de démonstration, rattachée aux comptes de dev-realm.json
make dev         # serveur, worker et interface
```

`deploy/.env` de développement : `OIDC_ISSUER=http://localhost:8280/realms/sibylle`,
`OIDC_CLIENT_ID=sibylle`, `OIDC_CLIENT_SECRET` = le secret de développement de
`keycloak/dev-realm.json` (`make env` les écrit). Les e-mails de Keycloak arrivent dans Mailpit
(http://localhost:8025) ; sa console d'admin est sur http://localhost:8280/admin/ (`admin` /
`admin`).

| Parcours | Faire | Attendu |
|---|---|---|
| US1, inscription par invitation | Ouvrir un lien d'invitation sans session, « Créer un compte » | Page « Créer un compte · Sibylle » sur :8280 ; retour connecté sur l'invitation ; rejoindre la rédaction |
| US1, connexion | Se déconnecter, ouvrir `/compte` | Page de connexion de Keycloak, puis retour sur `/compte` |
| US1, retour sûr | Ouvrir `/api/auth/login?suite=//exemple.org` | Retour sur `/`, jamais ailleurs |
| US2, confirmation | Créer un compte | Il joue tout de suite ; l'e-mail de confirmation est dans Mailpit ; après le clic, `GET /api/me` dit `email_verified: true` dans la minute |
| US2, renvoi | « Renvoyer l'e-mail » quatre fois | Trois e-mails, puis `429` |
| US3, nouveau mot de passe | Dans un second navigateur connecté, puis depuis `/compte`, « Changer mon mot de passe » avec « déconnecter mes autres appareils » | Retour sur `/compte`, connecté ; le second navigateur est déconnecté et sa WebSocket fermée (4401) |
| US4, déconnexion | « Se déconnecter », puis revenir | Le mot de passe est redemandé |
| US5, suppression | Supprimer son compte | L'utilisateur disparaît de la console de Keycloak ; une nouvelle inscription avec la même adresse donne un compte neuf |
| FR-017, service absent | `make keycloak-stop`, puis se connecter | Page « connexion indisponible » ; une personne déjà connectée continue de jouer |

Les vérifications automatiques :

```bash
make check          # dont les contrats de backend/tests/contract/test_auth.py, contre un faux Keycloak
make e2e            # avec make keycloak lancé : les parcours passent par les pages du thème
make check-keycloak # les pages et les e-mails du thème
```

## En production (User Story 6)

L'ordre est celui de research.md K13 ; `deploy/README.md` en donne les commandes. À la fin :

| Vérification | Attendu |
|---|---|
| Comptes d'essai | Aucun dans la base de Sibylle ni dans le realm `sibylle` (SC-002) |
| `https://sibylle.cc` → « Créer un compte » | Page « Créer un compte · Sibylle » sur `auth.sibylle.cc`, retour connecté |
| Se déconnecter, se reconnecter | Le mot de passe est redemandé, puis retour connecté |
| Changer son mot de passe en déconnectant les autres appareils | L'autre appareil est déconnecté dans la minute (SC-003) |
| Depuis Internet, `https://auth.sibylle.cc/admin/` | Toujours bloqué (520 de Cloudflare) |
| `keycloak/terraform/tofu.sh plan` sur la VM | Aucun changement : connexion par e-mail et mot de passe seulement, liens de 1 h et 24 h, 10 échecs en 15 minutes (FR-002, FR-009, FR-016) |
| Lendemain de la bascule | `backups/` contient la sauvegarde de `keycloak-db`, et sa copie chiffrée est sur le VPS |
| Restauration sur une machine d'essai | Les comptes du realm s'y connectent (SC-007) |
