# finance_data — Makefile
# Reproduzierbare Targets: Stack, Migrationen, Ingest, Tests, DQ.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON  ?= poetry run python
DB_DSN  ?= postgresql+psycopg://$${POSTGRES_USER:-finance}:$${POSTGRES_PASSWORD:-finance}@localhost:$${POSTGRES_PORT:-5432}/$${POSTGRES_DB:-finance}
COMPOSE ?= docker compose

.DEFAULT_GOAL := help

.PHONY: help
help: ## Zeige alle Targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --- Stack ------------------------------------------------------------------

.PHONY: init
init: ## Komplett-Setup: deps + Stack + Migrations
	poetry install
	$(COMPOSE) up -d
	@echo "Warte auf Postgres ..."
	@for i in $$(seq 1 30); do \
	  $(COMPOSE) exec -T postgres pg_isready -U $${POSTGRES_USER:-finance} >/dev/null 2>&1 && break; \
	  sleep 1; \
	done
	$(MAKE) migrate
	@echo "Init fertig. UI: Adminer :8080, Prefect :4200"

.PHONY: up
up: ## docker-compose Stack starten
	$(COMPOSE) up -d

.PHONY: down
down: ## docker-compose Stack stoppen
	$(COMPOSE) down

.PHONY: logs
logs: ## docker-compose Logs (tail)
	$(COMPOSE) logs -f --tail=200

.PHONY: ps
ps: ## Container-Status
	$(COMPOSE) ps

.PHONY: shell-db
shell-db: ## psql-Shell in die finance-DB
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-finance} -d $${POSTGRES_DB:-finance}

# --- Schema / Migrations ---------------------------------------------------

.PHONY: migrate
migrate: ## Alembic-Migrationen anwenden
	DATABASE_URL=$(DB_DSN) $(PYTHON) -m alembic upgrade head

.PHONY: revision
revision: ## Neue Alembic-Revision (Usage: make revision m="msg")
	DATABASE_URL=$(DB_DSN) $(PYTHON) -m alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## Eine Migration zurückrollen
	DATABASE_URL=$(DB_DSN) $(PYTHON) -m alembic downgrade -1

# --- Ingest ----------------------------------------------------------------

.PHONY: ingest-all
ingest-all: ## Alle Asset-Klassen ingesten (idempotent)
	@echo "TODO: implement ingest-all"

.PHONY: ingest-%
ingest-%: ## Ingest einer Asset-Klasse (z.B. ingest-equities)
	@echo "TODO: implement ingest-$*"

# --- Quality / Tests -------------------------------------------------------

.PHONY: test
test: ## pytest + pandera schemas
	DATABASE_URL=$(DB_DSN) $(PYTHON) -m pytest

.PHONY: tui
tui: ## OpenTUI-Explorer starten (Bun erforderlich)
	@if ! command -v bun >/dev/null 2>&1; then \
		echo "Bun nicht installiert. Install: curl -fsSL https://bun.sh/install | bash"; \
		exit 1; \
	fi
	cd tui && bun install --silent && bun run start

.PHONY: tui-install
tui-install: ## TUI-Dependencies installieren
	cd tui && bun install

.PHONY: tui-typecheck
tui-typecheck: ## TUI TypeScript typecheck
	cd tui && bun run typecheck

.PHONY: tui-test
tui-test: ## TUI-Tests (Unit + Integration)
	@if ! command -v bun >/dev/null 2>&1; then \
		echo "Bun nicht installiert. Install: curl -fsSL https://bun.sh/install | bash"; \
		exit 1; \
	fi
	cd tui && bun test

.PHONY: test-cov
test-cov: ## pytest mit Coverage
	DATABASE_URL=$(DB_DSN) $(PYTHON) -m pytest --cov=src/finance_data --cov-report=term-missing

.PHONY: dq-full
dq-full: ## Vollständige DB-Validierung
	@echo "TODO: implement dq-full"

.PHONY: dq-report
dq-report: ## HTML-Report der letzten 7 Tage
	@echo "TODO: implement dq-report"

# --- Lint / Format / Typecheck --------------------------------------------

.PHONY: format
format: ## ruff format
	$(PYTHON) -m ruff format .

.PHONY: lint
lint: ## ruff check (inkl. --fix mit FIX=1)
	@if [ "$${FIX:-0}" = "1" ]; then \
	  $(PYTHON) -m ruff check --fix . ; \
	else \
	  $(PYTHON) -m ruff check . ; \
	fi

.PHONY: typecheck
typecheck: ## mypy
	$(PYTHON) -m mypy src/

.PHONY: check
check: lint typecheck test ## Alles: lint + typecheck + test

# --- Util ------------------------------------------------------------------

.PHONY: clean-pyc
clean-pyc: ## __pycache__ + .pyc entfernen
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: clean-venv
clean-venv: ## Poetry-Venv neu erstellen
	poetry env remove --all || true
	poetry install
