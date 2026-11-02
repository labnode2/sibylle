# Sibylle

Jeu de pronostics pour les rédactions : on pronostique, on mise des lauriers et on se classe par saison.

- Spécification, plan et tâches : `specs/001-sibylle-v1/`
- Lancer et valider l'appli : `specs/001-sibylle-v1/quickstart.md`
- Serveur (Python, FastAPI) : `backend/` ; interface (React) : `frontend/` ; hébergement : `deploy/`

## Démarrer en local

Prérequis : Docker avec Compose, Python 3.14 avec uv, Node.js 24 ou plus avec npm.

```bash
make setup   # première fois : deploy/.env, dépendances, base, migrations, données de démo
make dev     # serveur, worker et interface ensemble ; Ctrl+C pour tout arrêter
```

Puis ouvrir http://localhost:5173 et se connecter avec un compte de démonstration, par exemple
`ines@demo.sibylle.test` (rédaction en chef), mot de passe `lauriers-de-demo` (liste complète dans
`backend/seed/README.md`). Les e-mails envoyés en local arrivent dans Mailpit : http://localhost:8025.

Si le port 5173 est déjà pris : `make dev WEB_PORT=5199`. Les tests de bout en bout ont leurs
propres ports (API 8001, interface 5180) et peuvent tourner pendant `make dev`.

Les fois suivantes, `make dev` suffit ; après avoir récupéré de nouvelles migrations, lancer
`make migrate`. `make stop` arrête la base et Mailpit sans perdre les données. `make` seul liste
toutes les commandes.

## Vérifier

```bash
make check   # formatage, analyse, types, tests du serveur et de l'interface
make e2e     # parcours de bout en bout dans le navigateur (Playwright)
```

## Mise en production

Pas encore prête : les images Docker, Caddy, le tunnel frpc et les sauvegardes sont prévus dans
`specs/001-sibylle-v1/tasks.md` (T140 à T145). `make setup` et `make dev` servent au développement
seulement.
