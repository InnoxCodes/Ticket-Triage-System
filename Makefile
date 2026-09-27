.PHONY: help install dataset train seed api web test lint build up down

BACKEND := backend
FRONTEND := frontend

help: ## List the available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-9s\033[0m %s\n", $$1, $$2}'

install: ## Create the backend venv and install both apps' dependencies
	cd $(BACKEND) && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd $(FRONTEND) && npm ci

dataset: ## Regenerate the synthetic training corpus (seed 42, reproducible)
	cd $(BACKEND) && .venv/bin/python -m ml.generate_dataset --n 1400 --seed 42

train: ## Retrain both classifiers and rewrite metrics.json
	cd $(BACKEND) && .venv/bin/python -m ml.train

seed: ## Reset the local database to 90 demo tickets
	cd $(BACKEND) && .venv/bin/python -m scripts.seed --n 90 --reset

api: ## Run the API with auto-reload on :8000
	cd $(BACKEND) && .venv/bin/uvicorn app.main:app --reload --port 8000

web: ## Run the Vite dev server on :5173 (proxies /api and /ws to :8000)
	cd $(FRONTEND) && npm run dev

test: ## Run the backend test suite
	cd $(BACKEND) && .venv/bin/python -m pytest

lint: ## Lint the backend and type-check the frontend
	cd $(BACKEND) && .venv/bin/ruff check app ml scripts tests
	cd $(FRONTEND) && npx tsc -b

build: ## Production build of the frontend
	cd $(FRONTEND) && npm run build

up: ## Build and run the whole stack in Docker (app on :8080, API docs on :8000/docs)
	docker compose up --build

down: ## Stop the Docker stack
	docker compose down
