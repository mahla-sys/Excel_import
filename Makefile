.PHONY: help up down build logs migrate makemigrations bootstrap-admin seed test test-backend lint-backend shell-backend dev-backend dev-frontend fmt clean

COMPOSE := docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Start the whole stack (db, backend, frontend)
	$(COMPOSE) up -d --build

down: ## Stop the stack
	$(COMPOSE) down

build: ## Build all images
	$(COMPOSE) build

logs: ## Tail logs
	$(COMPOSE) logs -f

migrate: ## Run Django migrations
	$(COMPOSE) run --rm backend python manage.py migrate

makemigrations: ## Create new Django migrations
	$(COMPOSE) run --rm backend python manage.py makemigrations

bootstrap-admin: ## Create / reset the first system_admin from env vars
	$(COMPOSE) run --rm backend python manage.py bootstrap_admin

seed: ## Seed 7 demo schools and operator accounts
	$(COMPOSE) run --rm backend python manage.py seed_demo

test-backend: ## Run backend tests
	$(COMPOSE) run --rm backend pytest

shell-backend: ## Django shell
	$(COMPOSE) run --rm backend python manage.py shell

fmt: ## Format backend code with black + isort
	$(COMPOSE) run --rm backend sh -c "black . && isort ."

# --- Local (non-docker) development helpers ---

dev-backend: ## Run Django locally (expects venv + running Postgres)
	cd backend && python manage.py runserver 0.0.0.0:8000

dev-frontend: ## Run Vite dev server
	cd frontend && npm run dev

clean: ## Remove build artifacts
	rm -rf backend/staticfiles backend/private_files
	rm -rf frontend/dist
