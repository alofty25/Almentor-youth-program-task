# =============================================================================
#  Almentor Task Management API — Developer Makefile
#  Works on: Linux, macOS, WSL, Git Bash on Windows
#  For native Windows PowerShell → use: scripts\dev.ps1
# =============================================================================

.DEFAULT_GOAL := help

# --- Internal variables -------------------------------------------------------
PYTHON  := uv run python
MANAGE  := $(PYTHON) manage.py

# ANSI colour codes (work in Git Bash / Unix terminals)
BOLD   := \033[1m
GREEN  := \033[0;32m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
BLUE   := \033[0;34m
RED    := \033[0;31m
DIM    := \033[2m
RESET  := \033[0m

# Declare all targets as phony (no output files)
.PHONY: help \
        install update \
        dev shell superuser seed \
        migrate migrations check-migrations \
        test test-unit test-integration test-fast \
        docker-up docker-up-seed docker-down docker-clean \
        clean \
        token

# =============================================================================
#  HELP  (default target)
# =============================================================================
help:
	@printf "\n$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n"
	@printf "$(BOLD)  Almentor Task Management API — Make Commands $(RESET)\n"
	@printf "$(BOLD)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(RESET)\n\n"

	@printf "$(CYAN)$(BOLD)⚙  SETUP$(RESET)\n"
	@printf "  $(GREEN)make install$(RESET)           Install all dependencies via UV\n"
	@printf "  $(GREEN)make update$(RESET)            Update dependencies to latest allowed versions\n\n"

	@printf "$(CYAN)$(BOLD)🚀  DEVELOPMENT$(RESET)\n"
	@printf "  $(GREEN)make dev$(RESET)               Start the dev server at http://127.0.0.1:8000\n"
	@printf "  $(GREEN)make shell$(RESET)             Open the Django interactive Python shell\n"
	@printf "  $(GREEN)make superuser$(RESET)         Create a new superuser account\n"
	@printf "  $(GREEN)make seed$(RESET)              Seed database with production-like data\n"
	@printf "  $(GREEN)make token u=<username>$(RESET)  Print a fresh JWT token for quick API testing\n\n"

	@printf "$(CYAN)$(BOLD)🗄  DATABASE$(RESET)\n"
	@printf "  $(GREEN)make migrate$(RESET)           Apply all pending database migrations\n"
	@printf "  $(GREEN)make migrations$(RESET)        Generate new migration files (detects model changes)\n"
	@printf "  $(GREEN)make check-migrations$(RESET)  Warn if any model changes are missing a migration\n\n"

	@printf "$(CYAN)$(BOLD)🧪  TESTING$(RESET)\n"
	@printf "  $(GREEN)make test$(RESET)              Run ALL tests (unit + integration) vs PostgreSQL\n"
	@printf "  $(GREEN)make test-unit$(RESET)         Run unit tests only (core / projects / tasks)\n"
	@printf "  $(GREEN)make test-integration$(RESET)  Run integration tests only (real JWT + DB flows)\n"
	@printf "  $(GREEN)make test-fast$(RESET)         Unit tests with SQLite — fastest, no Postgres needed\n\n"

	@printf "$(CYAN)$(BOLD)🐳  DOCKER$(RESET)\n"
	@printf "  $(GREEN)make docker-up$(RESET)         Build image + start API and Postgres containers\n"
	@printf "  $(GREEN)make docker-up-seed$(RESET)    Same as docker-up, but seeds DB on first boot\n"
	@printf "  $(GREEN)make docker-down$(RESET)       Stop and remove containers (keeps DB data volume)\n"
	@printf "  $(GREEN)make docker-clean$(RESET)      Full teardown: stop containers + delete DB volume\n\n"

	@printf "$(CYAN)$(BOLD)🧹  CLEANUP$(RESET)\n"
	@printf "  $(GREEN)make clean$(RESET)             Remove all __pycache__ dirs and .pyc files\n\n"

	@printf "$(DIM)Tip: Windows PowerShell users → run  .\\scripts\\dev.ps1 help$(RESET)\n\n"

# =============================================================================
#  SETUP
# =============================================================================
install:
	@printf "$(YELLOW)Installing dependencies via UV...$(RESET)\n"
	uv sync
	@printf "$(GREEN)✔ Dependencies installed.$(RESET)\n"

update:
	@printf "$(YELLOW)Updating dependencies...$(RESET)\n"
	uv sync --upgrade
	@printf "$(GREEN)✔ Dependencies updated.$(RESET)\n"

# =============================================================================
#  DEVELOPMENT
# =============================================================================
dev:
	@printf "$(GREEN)Starting dev server → http://127.0.0.1:8000$(RESET)\n"
	$(MANAGE) runserver

shell:
	@printf "$(CYAN)Opening Django shell...$(RESET)\n"
	$(MANAGE) shell

superuser:
	@printf "$(CYAN)Creating superuser...$(RESET)\n"
	$(MANAGE) createsuperuser

seed:
	@printf "$(CYAN)Seeding database with production-like data...$(RESET)\n"
	$(MANAGE) seed --clear

# Usage: make token u=myusername
# Requires the user to already exist. Prints the access token to stdout.
token:
	@if [ -z "$(u)" ]; then \
		printf "$(RED)Error: provide a username → make token u=<username>$(RESET)\n"; \
		exit 1; \
	fi
	@printf "$(CYAN)Fetching JWT token for user '$(u)'...$(RESET)\n"
	@$(PYTHON) -c "\
import os, django, json, urllib.request, urllib.parse; \
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings'); \
django.setup(); \
password = input('Password: '); \
data = urllib.parse.urlencode({'username': '$(u)', 'password': password}).encode(); \
req = urllib.request.Request('http://127.0.0.1:8000/api/token/', data=data); \
try: \
    resp = urllib.request.urlopen(req); \
    token = json.loads(resp.read())['access']; \
    print('\n$(GREEN)Access Token:$(RESET)\n' + token + '\n'); \
except Exception as e: \
    print('$(RED)Failed: ' + str(e) + '$(RESET)'); \
"

# =============================================================================
#  DATABASE
# =============================================================================
migrate:
	@printf "$(YELLOW)Applying database migrations...$(RESET)\n"
	$(MANAGE) migrate
	@printf "$(GREEN)✔ Migrations applied.$(RESET)\n"

migrations:
	@printf "$(YELLOW)Generating migration files...$(RESET)\n"
	$(MANAGE) makemigrations
	@printf "$(GREEN)✔ Done. Review new files before committing.$(RESET)\n"

check-migrations:
	@printf "$(CYAN)Checking for missing migrations...$(RESET)\n"
	$(MANAGE) makemigrations --check --dry-run
	@printf "$(GREEN)✔ No missing migrations.$(RESET)\n"

# =============================================================================
#  TESTING
# =============================================================================
test:
	@printf "\n$(BOLD)$(CYAN)Running ALL tests (unit + integration) against PostgreSQL...$(RESET)\n\n"
	$(MANAGE) test --verbosity=2
	@printf "\n$(GREEN)$(BOLD)✔ All tests passed.$(RESET)\n"

test-unit:
	@printf "\n$(BOLD)$(CYAN)Running unit tests (core / projects / tasks) against PostgreSQL...$(RESET)\n\n"
	$(MANAGE) test core projects tasks --verbosity=2
	@printf "\n$(GREEN)$(BOLD)✔ Unit tests passed.$(RESET)\n"

test-integration:
	@printf "\n$(BOLD)$(CYAN)Running integration tests against PostgreSQL...$(RESET)\n\n"
	$(MANAGE) test integration_tests --verbosity=2
	@printf "\n$(GREEN)$(BOLD)✔ Integration tests passed.$(RESET)\n"

test-fast:
	@printf "\n$(BOLD)$(CYAN)Running unit tests with SQLite (fastest — no Postgres needed)...$(RESET)\n\n"
	$(MANAGE) test core projects tasks \
		--settings=core.test_settings \
		--verbosity=2
	@printf "\n$(GREEN)$(BOLD)✔ Fast tests passed.$(RESET)\n"

# =============================================================================
#  CLEANUP
# =============================================================================
clean:
	@printf "$(YELLOW)Removing __pycache__ and .pyc files...$(RESET)\n"
	@$(PYTHON) -c "\
import shutil, pathlib; \
removed = 0; \
[shutil.rmtree(str(p), ignore_errors=True) or setattr(type('x', (), {'n': 0}), 'n', removed + 1) \
    for p in pathlib.Path('.').rglob('__pycache__') if '.venv' not in str(p)]; \
[p.unlink(missing_ok=True) for p in pathlib.Path('.').rglob('*.pyc') if '.venv' not in str(p)]; \
print('Done.'); \
"
	@printf "$(GREEN)✔ Cache cleared.$(RESET)\n"

# =============================================================================
#  DOCKER
# =============================================================================
docker-up:
	@printf "$(CYAN)Building and starting Docker containers...$(RESET)\n"
	docker compose up --build

docker-up-seed:
	@printf "$(CYAN)Building and starting Docker containers with DB seeding...$(RESET)\n"
	SEED_DB=true docker compose up --build

docker-down:
	@printf "$(YELLOW)Stopping and removing containers (data volume preserved)...$(RESET)\n"
	docker compose down

docker-clean:
	@printf "$(RED)Full teardown — stopping containers AND deleting data volume...$(RESET)\n"
	docker compose down -v
