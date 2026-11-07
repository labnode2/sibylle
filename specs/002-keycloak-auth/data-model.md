# Data Model: Connexion par Keycloak

Ce qui change par rapport à `specs/001-sibylle-v1/data-model.md` (section « Comptes »). Une
seule migration de base (`0022_keycloak`) ; le reste du modèle ne bouge pas.

## Dans Sibylle

### accounts (compte)

| Colonne | Changement | Règles |
|---|---|---|
| keycloak_id | **ajoutée**, uuid | unique ; le `sub` du compte Keycloak ; posée à la création par le retour de connexion ; `NULL` après suppression |
| password_hash | **retirée** | Sibylle ne voit plus de mot de passe |
| email | inchangée (citext, unique) | recopiée de Keycloak à chaque connexion ; `NULL` après suppression |
| first_name, last_name | inchangées | recopiés de Keycloak à chaque connexion ; jamais exposés à un autre compte |
| email_verified_at | inchangée | posée la première fois que Keycloak dit l'adresse confirmée (jeton d'identité ou relecture) ; remise à `NULL` s'il dit le contraire |
| identity_checked_at | **ajoutée**, timestamptz | dernière relecture du compte Keycloak pour un compte non confirmé (au plus une par minute) |

Règles : un `keycloak_id` ne désigne qu'un compte vivant ; un compte vivant (sans `deleted_at`)
créé après la migration en a toujours un. La migration ne pose pas de contrainte `NOT NULL` :
les comptes des bases de développement antérieures n'en ont pas, et la production repart de
zéro.

### sessions

| Colonne | Changement | Règles |
|---|---|---|
| keycloak_sid | **ajoutée**, text, indexée | le `sid` du jeton d'identité : la session Keycloak ouverte au même moment ; `NULL` pour les sessions que les tests ouvrent directement |

Une session est supprimée à la déconnexion (avec sa session Keycloak), à la réception d'une
déconnexion back-channel pour son `sid` (ou pour tout le compte), à la suppression du compte,
quand un nouveau mot de passe ferme les autres appareils (par la déconnexion back-channel), et
quand sa prolongation horaire trouve le compte Keycloak supprimé ou désactivé (research.md K15).
Le reste ne change pas : 30 jours glissants, jeton du cookie haché.

### email_tokens

**Retirée**, avec ses liens : Keycloak envoie lui-même les liens de confirmation et de nouveau
mot de passe.

### sign_in_attempts (aller-retour de connexion) — **nouvelle**

| Colonne | Type | Règles |
|---|---|---|
| id | uuid | PK |
| token_hash | text | unique ; SHA-256 du cookie `sibylle_signin` |
| state | text | aléatoire, comparé au `state` du retour |
| nonce | text | aléatoire, comparé à celui du jeton d'identité |
| code_verifier | text | vérificateur PKCE, jamais envoyé au navigateur |
| action | text | `login`, `signup` ou `password` |
| next_path | text | la page de Sibylle où revenir, validée comme `nextPath` |
| created_at, expires_at | timestamptz | 10 minutes |

À usage unique : le retour la supprime, réussi ou non. Le processus de tâches supprime chaque
jour celles qui ont expiré.

## Dans Keycloak (realm `sibylle`)

Rien n'est stocké par Sibylle ici ; pour mémoire :

- **Utilisateur** : `id` (le `keycloak_id` de Sibylle), `username` = e-mail, `email`,
  `emailVerified`, `firstName`, `lastName`, identifiant de mot de passe. Créé par l'inscription
  sur les pages du thème ; supprimé par Sibylle avec le compte (API d'admin).
- **Session** : `id` (le `sid` des jetons), fermée par Sibylle à la déconnexion, ou par
  Keycloak (nouveau mot de passe avec déconnexion des autres appareils, compte désactivé), qui
  prévient alors Sibylle par la déconnexion back-channel.

## Transitions d'un compte

```text
(aucun) --1re connexion, sub inconnu--> vivant, non confirmé --clic sur le lien--> vivant, confirmé
vivant --suppression (Keycloak d'abord, puis anonymisation)--> supprimé (keycloak_id, email, noms à NULL)
```

Si Keycloak ne répond pas à la suppression, le compte reste vivant et rien n'est effacé
(FR-013).
