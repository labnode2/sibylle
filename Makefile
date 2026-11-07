COMPOSE = docker compose -f deploy/docker-compose.yml --env-file deploy/.env

# Ports de l'interface et du serveur ; `make dev WEB_PORT=5199 API_PORT=8010` quand 5173 ou
# 8000 sont déjà pris.
WEB_PORT ?= 5173
API_PORT ?= 8000
# Adresse où l'interface est servie : localhost, ou l'IP du PC sur le réseau local pour ouvrir
# l'appli depuis un téléphone (`make dev UI_HOST=192.168.71.12`, ou UI_HOST=… dans deploy/.env).
# L'origine attendue par le serveur la suit.
UI_HOST ?= $(or $(shell sed -n 's/^UI_HOST=//p' deploy/.env 2>/dev/null),localhost)
ORIGIN = http://$(UI_HOST):$(WEB_PORT)
# Les tests de bout en bout ont leurs propres ports (API 8001, interface 5180) : ils ne
# croisent jamais un `make dev` ouvert à côté.
E2E_WEB_PORT ?= 5180

.DEFAULT_GOAL := help

.PHONY: help setup env install db stop migrate seed dev api worker web \
	check check-backend check-frontend e2e keycloak keycloak-stop check-keycloak

help: ## Affiche cette aide
	@grep -hE '^[a-z0-9-]+:.*## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "} {printf "  make %-15s %s\n", $$1, $$2}'

# Premier démarrage

setup: env install db migrate seed ## Tout installer et préparer la base (première fois)
	@echo ""
	@echo "Prêt. Lancer l'appli avec : make dev"

# Les réglages de la connexion par Keycloak, venus après la création de deploy/.env, y sont
# ajoutés avec leurs valeurs de développement ; jamais dans un deploy/.env de production.
OIDC_SETTINGS = OIDC_ISSUER KEYCLOAK_INTERNAL_URL OIDC_CLIENT_ID OIDC_CLIENT_SECRET

env: deploy/.env ## Crée deploy/.env pour le développement, ou y ajoute les réglages qui manquent
	@if ! grep -q '^ENVIRONMENT=production' deploy/.env; then \
		for key in $(OIDC_SETTINGS); do \
			grep -q "^$$key=" deploy/.env && continue; \
			[ -z "$$(tail -c1 deploy/.env)" ] || echo >> deploy/.env; \
			grep "^$$key=" deploy/.env.example >> deploy/.env; \
			echo "$$key ajouté à deploy/.env (valeur de développement)."; \
		done; \
	fi

deploy/.env:
	sed -e 's/^POSTGRES_PASSWORD=$$/POSTGRES_PASSWORD=sibylle/' \
		-e 's/<mot de passe>/sibylle/' \
		deploy/.env.example > $@
	@echo "deploy/.env créé (valeurs de développement)."

install: ## Installe les dépendances du serveur et de l'interface
	cd backend && uv sync
	cd frontend && npm install

# Base de données et faux serveur d'e-mails pour le développement
db: env ## Démarre PostgreSQL et Mailpit (Docker)
	$(COMPOSE) --profile dev up -d --wait db mailpit

stop: ## Arrête PostgreSQL et Mailpit (les données sont gardées)
	$(COMPOSE) --profile dev stop

migrate: ## Applique les migrations de la base
	cd backend && uv run alembic upgrade head

seed: ## Crée la rédaction de démonstration (relançable sans doublon)
	cd backend && uv run sibylle seed-demo

# Lancement

dev: db ## Lance serveur, worker et interface ensemble (Ctrl+C pour tout arrêter)
	@echo "Interface : $(ORIGIN)   E-mails : http://localhost:8025"
	$(MAKE) -j3 api worker web

api: ## Lance seulement le serveur (port API_PORT, 8000 par défaut)
	cd backend && PUBLIC_ORIGIN=$(ORIGIN) \
		uv run uvicorn sibylle.main:create_app --factory --reload --port $(API_PORT)

worker: ## Lance seulement le worker (tâches planifiées)
	cd backend && PUBLIC_ORIGIN=$(ORIGIN) uv run sibylle worker

web: ## Lance seulement l'interface (sur UI_HOST)
	cd frontend && SIBYLLE_API_PORT=$(API_PORT) \
		npm run dev -- --host $(UI_HOST) --port $(WEB_PORT) --strictPort

# Vérifications

check: check-backend check-frontend ## Formatage, analyse, types et tests

check-backend:
	cd backend && uv run ruff format --check
	cd backend && uv run ruff check
	cd backend && uv run mypy
	cd backend && uv run pytest

check-frontend:
	cd frontend && npm run format:check
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm run test
	cd frontend && npm run check:api

# Les parcours se connectent par les pages du Keycloak local, avec son client sibylle-e2e.
e2e: ## Parcours de bout en bout (Playwright), avec le Keycloak local (make keycloak)
	@curl --silent --fail --output /dev/null http://localhost:8280/realms/sibylle || \
		{ echo "Le Keycloak local ne répond pas : lance d'abord make keycloak." >&2; exit 1; }
	cd frontend && SIBYLLE_WEB_PORT=$(E2E_WEB_PORT) npm run e2e

# Thème Keycloak (keycloak/README.md) : le Keycloak de la production, en local, avec le thème et
# le realm de keycloak/dev-realm.json ; ses e-mails arrivent dans Mailpit. Une retouche du thème
# se voit au rechargement de la page.

keycloak: db ## Lance un Keycloak local avec le thème (http://localhost:8280)
	keycloak/dev.sh start

keycloak-stop: ## Arrête le Keycloak local
	keycloak/dev.sh stop

check-keycloak: ## Affiche et vérifie chaque page et e-mail du thème (après make keycloak)
	python3 -I keycloak/check-theme.py
