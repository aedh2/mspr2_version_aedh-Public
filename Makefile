# HealthAI Coach — commandes d'exploitation (blocs 3/4 : produire & maintenir).
# Utilise ">" comme préfixe de recette (au lieu de TAB) pour la portabilité d'édition.
.RECIPEPREFIX := >
COMPOSE ?= docker compose

.PHONY: help up down reset ps logs test backup restore monitoring-up monitoring-down

MONITORING = -f docker-compose.yml -f docker-compose.monitoring.yml

help:
> @echo "Cibles disponibles :"
> @echo "  make up                 Démarre toute la stack (build)"
> @echo "  make down               Arrête la stack"
> @echo "  make reset              Réinitialise (supprime les volumes) puis redémarre"
> @echo "  make ps                 État des services"
> @echo "  make logs               Logs agrégés (suivi)"
> @echo "  make test               Tests backend (pytest)"
> @echo "  make backup             Sauvegarde MariaDB + MongoDB -> backups/"
> @echo "  make restore DIR=...    Restaure une sauvegarde (ex: DIR=backups/20260702_120000)"
> @echo "  make monitoring-up      Démarre la stack + Prometheus + Grafana"
> @echo "  make monitoring-down    Arrête la stack + monitoring"

up:
> $(COMPOSE) up -d --build

down:
> $(COMPOSE) down

reset:
> $(COMPOSE) down -v
> $(COMPOSE) up -d --build

ps:
> $(COMPOSE) ps

logs:
> $(COMPOSE) logs -f --tail=100

test:
> cd backend && python -m pytest -q

backup:
> bash scripts/backup.sh

restore:
> bash scripts/restore.sh $(DIR)

monitoring-up:
> $(COMPOSE) $(MONITORING) up -d --build

monitoring-down:
> $(COMPOSE) $(MONITORING) down
