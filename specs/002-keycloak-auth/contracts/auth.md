# Contrat : comptes et session par Keycloak

Ce qui remplace la section « Comptes et session » de `specs/001-sibylle-v1/contracts/rest-api.md`.
Les conventions de ce contrat-là restent : préfixe `/api`, cookie `sibylle_session`, en-tête
`X-Sibylle: 1` et `Origin` exigés sur toute requête qui modifie, sauf la déconnexion
back-channel ci-dessous.

## Routes

| Méthode | Route | Accès | Contrat |
|---|---|---|---|
| GET | `/auth/login` | Public, navigation | `?action=login\|signup\|password&suite=<chemin>` → `303` vers l'autorisation de Keycloak (`code`, PKCE `S256`, `scope=openid`, `prompt=create` pour `signup`, `kc_action=UPDATE_PASSWORD` pour `password`), cookie `sibylle_signin` posé ; `303 /connexion-indisponible` si le realm ne répond pas dans les 2 s. `suite` invalide (pas un chemin de Sibylle, ou `//…`) : `/`. `?action=forgot` → `303` vers `…/login-actions/reset-credentials?client_id=<OIDC_CLIENT_ID>`, sans tentative ni cookie |
| GET | `/auth/callback` | Public, navigation | `?code&state` (ou `?error&state`) → `303 <suite>` avec le cookie `sibylle_session`, `sibylle_signin` effacé ; `303 /connexion?erreur=<code>` sans session si le cookie manque, si le `state` diffère, si la tentative a expiré ou servi, si l'échange ou le jeton échouent, ou si l'adresse appartient à un autre compte ; `303 /connexion-indisponible` si Keycloak ne répond pas |
| POST | `/auth/logout` | Compte | → `204`, cookie effacé ; ferme aussi la session Keycloak (au mieux, voir research.md K7) |
| POST | `/auth/backchannel-logout` | Keycloak | formulaire `logout_token=<JWT>` → `200` ; `400` si le jeton n'est pas valable. Pas d'`X-Sibylle` ni d'`Origin` : le jeton signé fait foi |
| POST | `/auth/verify-email/resend` | Compte | → `204` (inchangé ; Keycloak envoie l'e-mail) ; `429 rate_limited` au-delà de 3 par heure |
| GET | `/me` | Compte | → `Me` (inchangé) ; pour un compte non confirmé, relit Keycloak au plus une fois par minute ; si Keycloak ne répond pas, renvoie l'état connu, sans erreur |
| PATCH | `/me` | Compte | `{theme?, reduce_motion?, locale?}` → `Me` ; `first_name` et `last_name` ne s'y changent plus |
| DELETE | `/me` | Compte | `{confirm: true}` → `204` ; supprime aussi le compte Keycloak ; `503 identity_unavailable` si Keycloak ne répond pas, rien n'est supprimé ; `409 last_editor` inchangé |

**Retirées** : `POST /auth/signup`, `POST /auth/login`, `POST /auth/verify-email`,
`POST /auth/password-reset`, `POST /auth/password-reset/confirm`, `POST /me/password`.

## Codes d'erreur nouveaux

| Code | Où | Sens |
|---|---|---|
| `identity_unavailable` | `DELETE /me` (503) | Keycloak ne répond pas ; réessayer plus tard |
| `erreur=expired` | retour vers `/connexion` | tentative expirée, déjà servie ou d'un autre navigateur |
| `erreur=denied` | retour vers `/connexion` | la personne a annulé sur la page de Keycloak |
| `erreur=email_taken` | retour vers `/connexion` | l'adresse appartient à un autre compte Sibylle |
| `erreur=failed` | retour vers `/connexion` | échange du code ou jeton refusé |

## Jeton d'identité attendu au retour

Signé par une clé du realm (`RS256`), `iss` = `OIDC_ISSUER`, `aud` contient `OIDC_CLIENT_ID`,
`exp` à venir, `nonce` = celui de la tentative. Champs lus : `sub`, `sid`, `email`,
`email_verified`, `given_name`, `family_name`.

## Jeton de déconnexion back-channel

Signé par une clé du realm, `iss` = `OIDC_ISSUER`, `aud` contient `OIDC_CLIENT_ID`,
`events` contient `http://schemas.openid.net/event/backchannel-logout`, `sid` ou `sub`
présent, pas de `nonce`, `iat` de moins de 5 minutes. Effet : les sessions Sibylle de ce `sid`
(ou de tout le compte si seul `sub` est donné) sont supprimées, et leurs WebSocket fermées
(code 4401, contracts/realtime.md de la v1). Keycloak l'envoie quand des sessions se ferment
(nouveau mot de passe, « Sign out » de l'administrateur, déconnexion de Sibylle elle-même), mais
pas quand un compte est désactivé ou supprimé (research.md K15).

## Relecture horaire du compte

Quand une session se prolonge (au plus une fois par heure, R4), toute requête authentifiée, la
connexion de la WebSocket comprise, relit le compte dans Keycloak : compte absent ou désactivé,
les sessions Sibylle du compte sont supprimées et la requête répond comme sans session (`401
not_authenticated`, ou fermeture 4401) ; Keycloak injoignable, la requête continue.

## Configuration du serveur

| Variable | Exemple | Rôle |
|---|---|---|
| `OIDC_ISSUER` | `https://auth.sibylle.cc/realms/sibylle` | adresse publique du realm : redirections du navigateur, vérification des jetons |
| `KEYCLOAK_INTERNAL_URL` | `http://keycloak:8080` | adresse des appels du serveur (échange du code, clés, API d'admin) ; par défaut, celle d'`OIDC_ISSUER` |
| `OIDC_CLIENT_ID` | `sibylle` | le client du realm |
| `OIDC_CLIENT_SECRET` | (secret) | `keycloak/terraform/tofu.sh output -raw client_secret` en production |

## Pages de l'interface

| Route | Devient |
|---|---|
| `/connexion` | navigation vers `/api/auth/login?suite=…` ; avec `?erreur=…`, une page qui explique et propose de recommencer |
| `/inscription` | navigation vers `/api/auth/login?action=signup&suite=…` |
| `/mot-de-passe/oubli` | navigation vers `/api/auth/login?action=forgot`, la page « Mot de passe oublié » de Keycloak |
| `/mot-de-passe/nouveau`, `/verifier-email` | page « ce lien ne marche plus » avec le bon bouton (FR-018) |
| `/connexion-indisponible` | **nouvelle** : Keycloak ne répond pas, réessayer |
| `/compte` | gagne « Changer mon mot de passe » → `/api/auth/login?action=password&suite=/compte` |
