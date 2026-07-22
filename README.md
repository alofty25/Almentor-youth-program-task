<!-- Badges -->
![Build Status](https://img.shields.io/github/actions/workflow/status/alofty25/Almentor-youth-program-task/test.yml?branch=main&style=flat-square&label=CI)
![Python](https://img.shields.io/badge/Python-3.10-3776AB?style=flat-square&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-5.2-092E20?style=flat-square&logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF-3.17-ff1709?style=flat-square&logo=django&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)
![Tests](https://img.shields.io/badge/Tests-186_passing-brightgreen?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)

# 📋 Almentor Task Management API

A **production-grade RESTful API** for managing projects and tasks, built with Django REST Framework and PostgreSQL. The API features JWT authentication, per-user data isolation, soft-delete with cascade, full-text search, multi-parameter filtering, and pagination — all backed by a comprehensive **186-test** suite (unit + integration) and fully containerized with Docker.

---

## 🏗 Tech Stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.10 |
| **Framework** | Django 5.2 + Django REST Framework 3.17 |
| **Authentication** | JWT via `djangorestframework-simplejwt` |
| **Database** | PostgreSQL 16 |
| **Package Manager** | [UV](https://docs.astral.sh/uv/) (fast Python package manager) |
| **Containerization** | Docker + Docker Compose |
| **CI/CD** | GitHub Actions (unit tests on SQLite + integration tests on PostgreSQL) |
| **Test Data** | Faker (realistic seeding) |

---

## 🏛 Database Architecture

### Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    PROJECT ||--o{ TASK : contains

    USER {
        int id PK
        string username UK
        string password
        string email
        string first_name
        string last_name
    }

    PROJECT {
        int id PK
        int owner_id FK
        string name
        text description
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }

    TASK {
        int id PK
        int project_id FK
        string title
        text description
        enum status
        enum priority
        date due_date
        datetime created_at
        datetime updated_at
        datetime deleted_at
    }
```

### Design Decisions

| Decision | Rationale |
|---|---|
| **Soft-delete (`deleted_at`)** | Records are never hard-deleted. Setting `deleted_at` allows audit trails, undo capability, and prevents orphan data. The `ActiveManager` automatically hides soft-deleted records from all default queries. |
| **Cascade soft-delete** | Deleting a project soft-deletes all its tasks. This maintains referential integrity while preserving data recoverability. |
| **Per-user unique project names** | A `UniqueConstraint` on `(owner, name)` allows different users to have identically-named projects while preventing duplicates for the same user. |
| **Data isolation via 404** | Accessing another user's resource returns `404 Not Found` (not `403 Forbidden`), preventing resource ID enumeration attacks. |
| **`BaseModel` abstract class** | All models inherit `created_at`, `updated_at`, `deleted_at`, and soft-delete logic from a single source of truth. |

### Soft-Delete Flow

```mermaid
flowchart LR
    A["DELETE /api/projects/1/"] --> B["Project.delete()"]
    B --> C["Set project.deleted_at = now()"]
    B --> D["For each task in project"]
    D --> E["Set task.deleted_at = now()"]
    C --> F["ActiveManager hides from queries"]
    E --> F
    F --> G["GET returns 404"]
    F --> H["all_objects still returns record"]
```

---

## 🚀 Getting Started

### Prerequisites

| Tool | Version | Required For |
|---|---|---|
| [Docker](https://docs.docker.com/get-docker/) + Docker Compose | Latest | Docker setup (recommended) |
| [Python](https://www.python.org/) | 3.10+ | Local setup |
| [UV](https://docs.astral.sh/uv/) | Latest | Local dependency management |
| [PostgreSQL](https://www.postgresql.org/) | 16+ | Local setup (without Docker) |

---

### 🐳 Option 1: Run with Docker (Recommended)

The fastest way to get up and running. **No Python, UV, or PostgreSQL installation required** — everything runs inside containers.

#### 1. Clone the repository

```bash
git clone https://github.com/alofty25/Almentor-youth-program-task.git
cd Almentor-youth-program-task
```

#### 2. Create your environment file

```bash
cp .env.docker.example .env.docker
```

#### 3. Start everything

```bash
# Start API + PostgreSQL (migrations run automatically)
docker compose up --build

# OR — start with a pre-seeded database (6 users, 25 projects, 120 tasks)
docker compose up --build -e SEED_DB=true
```

#### 4. Access the API

```
API:       http://localhost:8000/api/
Postgres:  localhost:5432 (accessible via DBeaver, pgAdmin, etc.)
```

#### Docker Lifecycle Commands

```bash
docker compose up --build       # Build and start (API on :8000, DB on :5432)
docker compose down             # Stop containers (DB data preserved in volume)
docker compose down -v          # Full teardown — stop + delete DB data volume
docker compose logs -f api      # Stream API container logs
```

```mermaid
flowchart TB
    subgraph Docker["docker compose up --build"]
        DB["🐘 PostgreSQL 16<br/>postgres:16-alpine<br/>Port 5432"]
        Entry["🔧 docker-entrypoint.sh"]
        API["🐍 Django API<br/>python:3.10-slim<br/>Port 8000"]

        DB -->|"healthcheck: pg_isready"| Entry
        Entry -->|"1. Wait for DB"| DB
        Entry -->|"2. Run migrations"| API
        Entry -->|"3. Seed DB (optional)"| API
        Entry -->|"4. Start runserver"| API
    end

    Client["👤 Client / Browser"] -->|"HTTP :8000"| API
    DBeaver["🔍 DBeaver / pgAdmin"] -->|"TCP :5432"| DB
```

---

### 💻 Option 2: Run Locally (Without Docker)

#### 1. Clone and install dependencies

```bash
git clone https://github.com/alofty25/Almentor-youth-program-task.git
cd Almentor-youth-program-task
uv sync
```

#### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your local PostgreSQL credentials:

```env
DB_NAME=task_management_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

#### 3. Create the database

```bash
# In psql or your preferred PostgreSQL client:
CREATE DATABASE task_management_db;
```

#### 4. Apply migrations and start the server

```bash
uv run python manage.py migrate
uv run python manage.py runserver
```

#### 5. (Optional) Seed the database with realistic data

```bash
uv run python manage.py seed --clear
```

This creates **6 users**, **25 projects**, and **120 tasks** with realistic names, varied statuses/priorities, past/future due dates, and ~10% soft-deleted records.

**Demo credentials** (all use password `Password123!`):

| Username | Role |
|---|---|
| `demo_admin` | Admin |
| `sarah_pm` | User |
| `alex_dev` | User |
| `maya_ux` | User |
| `david_qa` | User |
| `sam_devops` | User |

---

### Environment Variables Reference

| Variable | Description | Default |
|---|---|---|
| `SECRET_KEY` | Django secret key (generate a unique one for production) | Insecure dev default |
| `DEBUG` | Enable Django debug mode | `True` |
| `ALLOWED_HOSTS` | Comma-separated list of valid hostnames | `localhost,127.0.0.1` |
| `DB_NAME` | PostgreSQL database name | `task_management_db` |
| `DB_USER` | PostgreSQL user | `postgres` |
| `DB_PASSWORD` | PostgreSQL password | — |
| `DB_HOST` | Database host (`db` for Docker, `localhost` for local) | `localhost` |
| `DB_PORT` | Database port | `5432` |
| `SEED_DB` | Auto-seed database on Docker boot (`true` / `false`) | `false` |

---

## 🔐 Authentication

All API endpoints (except token obtain/refresh) require a valid JWT Bearer token.

### Obtain a Token

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "sarah_pm", "password": "Password123!"}'
```

**Response** `200 OK`:

```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Use the Token

```bash
curl http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Refresh an Expired Token

```bash
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJhbGciOiJIUzI1NiIs..."}'
```

**Response** `200 OK`:

```json
{
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

| Setting | Value |
|---|---|
| Access token lifetime | 60 minutes |
| Refresh token lifetime | 24 hours |

---

## 📡 API Reference

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/token/` | Obtain JWT access + refresh tokens |
| `POST` | `/api/token/refresh/` | Refresh an expired access token |

### Projects

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/projects/` | List authenticated user's projects |
| `POST` | `/api/projects/` | Create a new project |
| `GET` | `/api/projects/:id/` | Retrieve a project |
| `PUT` | `/api/projects/:id/` | Update a project |
| `PATCH` | `/api/projects/:id/` | Partially update a project |
| `DELETE` | `/api/projects/:id/` | Soft-delete a project (cascades to tasks) |

### Tasks

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/tasks/` | List all tasks across all user's projects |
| `GET` | `/api/tasks/:id/` | Retrieve a specific task |
| `PUT` | `/api/tasks/:id/` | Update a task |
| `DELETE` | `/api/tasks/:id/` | Soft-delete a task |
| `GET` | `/api/projects/:id/tasks/` | List tasks for a specific project |
| `POST` | `/api/projects/:id/tasks/` | Create a task in a specific project |

---

### 📂 Project Endpoints — Detailed

#### Create a Project

```bash
curl -X POST http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Cloud Infrastructure Migration",
    "description": "Migrate all services from on-prem to AWS EKS."
  }'
```

**Response** `201 Created`:

```json
{
  "id": 1,
  "name": "Cloud Infrastructure Migration",
  "description": "Migrate all services from on-prem to AWS EKS.",
  "created_at": "2026-07-22T01:30:00Z",
  "updated_at": "2026-07-22T01:30:00Z"
}
```

#### List Projects

```bash
curl http://localhost:8000/api/projects/ \
  -H "Authorization: Bearer <token>"
```

**Response** `200 OK`:

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 2,
      "name": "AI Customer Support Chatbot",
      "description": "Build an NLP-powered chatbot for tier-1 support.",
      "created_at": "2026-07-22T02:00:00Z",
      "updated_at": "2026-07-22T02:00:00Z"
    },
    {
      "id": 1,
      "name": "Cloud Infrastructure Migration",
      "description": "Migrate all services from on-prem to AWS EKS.",
      "created_at": "2026-07-22T01:30:00Z",
      "updated_at": "2026-07-22T01:30:00Z"
    }
  ]
}
```

#### Delete a Project (Soft-Delete + Cascade)

```bash
curl -X DELETE http://localhost:8000/api/projects/1/ \
  -H "Authorization: Bearer <token>"
```

**Response** `204 No Content` — the project and all its tasks are soft-deleted.

---

### ✅ Task Endpoints — Detailed

#### Create a Task

```bash
curl -X POST http://localhost:8000/api/projects/2/tasks/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Configure Redis Cache Layer",
    "description": "Implement Redis caching for hot API endpoints.",
    "status": "todo",
    "priority": "high",
    "due_date": "2026-08-15"
  }'
```

**Response** `201 Created`:

```json
{
  "id": 1,
  "project_id": 2,
  "project_name": "AI Customer Support Chatbot",
  "title": "Configure Redis Cache Layer",
  "description": "Implement Redis caching for hot API endpoints.",
  "status": "todo",
  "priority": "high",
  "due_date": "2026-08-15",
  "created_at": "2026-07-22T03:00:00Z",
  "updated_at": "2026-07-22T03:00:00Z"
}
```

#### Update a Task (Status Transition)

```bash
curl -X PUT http://localhost:8000/api/tasks/1/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Configure Redis Cache Layer",
    "status": "done",
    "priority": "high"
  }'
```

**Response** `200 OK`:

```json
{
  "id": 1,
  "project_id": 2,
  "project_name": "AI Customer Support Chatbot",
  "title": "Configure Redis Cache Layer",
  "description": "Implement Redis caching for hot API endpoints.",
  "status": "done",
  "priority": "high",
  "due_date": "2026-08-15",
  "created_at": "2026-07-22T03:00:00Z",
  "updated_at": "2026-07-22T03:15:00Z"
}
```

> **Business Rule:** Transitioning a task from `done` back to `todo` is allowed but triggers a server-side `logger.warning` for audit visibility — this unusual pattern may indicate a regression.

---

### 🔍 Filtering, Search & Pagination

The global task list (`GET /api/tasks/`) and project-scoped task list (`GET /api/projects/:id/tasks/`) both support the following query parameters:

| Parameter | Type | Description | Example |
|---|---|---|---|
| `status` | string | Filter by exact status | `?status=todo` |
| `priority` | string | Filter by exact priority | `?priority=high` |
| `due_date_from` | date | Tasks due on or after this date | `?due_date_from=2026-08-01` |
| `due_date_to` | date | Tasks due on or before this date | `?due_date_to=2026-08-31` |
| `q` | string | Case-insensitive search in title and description | `?q=redis` |
| `ordering` | string | Sort results | `?ordering=-due_date` |
| `page` | int | Page number (default: 1) | `?page=2` |
| `limit` | int | Results per page (default: 10) | `?limit=5` |

**Allowed `ordering` values:** `due_date`, `-due_date`, `priority`, `-priority`, `created_at`, `-created_at`

#### Example: Combined Filters

```bash
curl "http://localhost:8000/api/tasks/?status=todo&priority=high&ordering=-due_date&limit=5" \
  -H "Authorization: Bearer <token>"
```

**Response** `200 OK`:

```json
{
  "count": 12,
  "next": "http://localhost:8000/api/tasks/?limit=5&ordering=-due_date&page=2&priority=high&status=todo",
  "previous": null,
  "results": [
    {
      "id": 45,
      "project_id": 3,
      "project_name": "Payment Gateway Integration",
      "title": "Audit OWASP Top 10 Vulnerabilities",
      "description": "Run automated security scanner and fix XSS risks.",
      "status": "todo",
      "priority": "high",
      "due_date": "2026-09-30",
      "created_at": "2026-07-20T10:00:00Z",
      "updated_at": "2026-07-20T10:00:00Z"
    }
  ]
}
```

#### Enum Values Reference

| Field | Allowed Values |
|---|---|
| `status` | `todo`, `in_progress`, `done` |
| `priority` | `low`, `medium`, `high` |

---

## 🧪 Testing

The project has **186 tests** across two layers:

```mermaid
flowchart TB
    subgraph Unit["Unit Tests — 117 tests"]
        UM["core/tests/test_models.py<br/>BaseModel, ActiveManager"]
        PM["projects/tests/test_models.py<br/>Cascade, UniqueConstraint"]
        PS["projects/tests/test_serializers.py<br/>validate_name, field exposure"]
        PV["projects/tests/test_views.py<br/>Auth, isolation, CRUD"]
        TM["tasks/tests/test_models.py<br/>validate_due_date, defaults"]
        TS["tasks/tests/test_serializers.py<br/>DONE-to-TODO, read-only fields"]
        TV["tasks/tests/test_views.py<br/>Auth, isolation, CRUD"]
        TF["tasks/tests/test_filters.py<br/>Filters, search, ordering"]
    end

    subgraph Integration["Integration Tests — 69 tests"]
        F1["test_project_lifecycle.py<br/>Create → Task → Done → Delete"]
        F2["test_filters_and_search.py<br/>Status/Priority + Pagination"]
        F3["test_authentication_flow.py<br/>JWT obtain, use, refresh"]
        F4["test_data_isolation.py<br/>Cross-user safety"]
        F5["test_task_status_transitions.py<br/>All status paths"]
    end

    Unit -->|"must pass"| Integration
```

### Running Tests

```bash
# All tests (unit + integration) against PostgreSQL
uv run python manage.py test --verbosity=2

# Unit tests only
uv run python manage.py test core projects tasks --verbosity=2

# Integration tests only
uv run python manage.py test integration_tests --verbosity=2

# Fastest: unit tests on SQLite (no PostgreSQL needed)
uv run python manage.py test core projects tasks --settings=core.test_settings --verbosity=2
```

### Using the Convenience Scripts

```bash
# PowerShell (Windows)
.\scripts\dev.ps1 test              # All tests
.\scripts\dev.ps1 test-unit         # Unit only
.\scripts\dev.ps1 test-integration  # Integration only
.\scripts\dev.ps1 test-fast         # SQLite (fastest)

# Makefile (Linux / macOS / Git Bash)
make test                           # All tests
make test-unit                      # Unit only
make test-integration               # Integration only
make test-fast                      # SQLite (fastest)
```

### CI/CD Pipeline

The GitHub Actions workflow runs automatically on every push and pull request:

```mermaid
flowchart LR
    Push["git push / PR"] --> J1["Unit Tests<br/>Python 3.10<br/>SQLite"]
    J1 -->|"pass"| J2["Integration Tests<br/>Python 3.10<br/>PostgreSQL 16"]
    J2 -->|"pass"| OK["✅ All Clear"]
    J1 -->|"fail"| Fail["❌ Blocked"]
```

---

## 📁 Project Structure

```
Almentor-youth-program-task/
├── .github/workflows/test.yml      # CI: unit tests (SQLite) + integration tests (Postgres)
├── core/
│   ├── models.py                   # BaseModel, ActiveManager (soft-delete engine)
│   ├── settings.py                 # Django + DRF + JWT configuration
│   ├── test_settings.py            # SQLite override for fast CI unit tests
│   ├── urls.py                     # Root URL config + JWT token routes
│   ├── management/commands/seed.py # Database seeding command (Faker)
│   └── tests/test_models.py       # BaseModel & ActiveManager unit tests
├── projects/
│   ├── models.py                   # Project model + cascade soft-delete
│   ├── serializers.py              # ProjectSerializer + unique name validation
│   ├── views.py                    # ProjectViewSet (ModelViewSet)
│   ├── urls.py                     # DRF router-based URLs
│   └── tests/                      # Unit tests (models, serializers, views)
├── tasks/
│   ├── models.py                   # Task model + status/priority enums + due_date validator
│   ├── serializers.py              # TaskSerializer + DONE→TODO warning
│   ├── views.py                    # Task views + apply_task_filters + pagination
│   ├── urls.py                     # Task URL patterns
│   └── tests/                      # Unit tests (models, serializers, views, filters)
├── integration_tests/
│   ├── base.py                     # Shared test base with real JWT auth helpers
│   ├── test_project_lifecycle.py   # Flow 1: Full project lifecycle
│   ├── test_filters_and_search.py  # Flow 2 & 3: Filters + search + pagination
│   ├── test_authentication_flow.py # JWT auth flow end-to-end
│   ├── test_data_isolation.py      # Cross-user data safety
│   └── test_task_status_transitions.py  # Status machine validation
├── scripts/dev.ps1                 # PowerShell convenience commands (Windows)
├── Makefile                        # Make convenience commands (Linux/macOS/WSL)
├── Dockerfile                      # Multi-stage build (UV + python:3.10-slim)
├── docker-compose.yml              # API + PostgreSQL 16 services
├── docker-entrypoint.sh            # DB wait → migrate → seed → start
├── .env.example                    # Template for local development
├── .env.docker.example             # Template for Docker development
├── TESTING.md                      # Detailed test documentation
├── pyproject.toml                  # Python project config + dependencies
└── uv.lock                        # Locked dependency versions
```

---

## ⚡ Developer Convenience Commands

Both the `Makefile` and `scripts/dev.ps1` provide identical shortcuts:

| Command | What It Does |
|---|---|
| `install` | Install all dependencies via UV |
| `dev` | Start Django dev server on `:8000` |
| `shell` | Open Django interactive Python shell |
| `superuser` | Create a superuser account |
| `seed` | Seed database with realistic production-like data |
| `token <user>` | Fetch a JWT token for quick API testing |
| `migrate` | Apply pending database migrations |
| `migrations` | Generate new migration files |
| `check-migrations` | Detect missing migrations |
| `test` | Run all 186 tests against PostgreSQL |
| `test-unit` | Run 117 unit tests |
| `test-integration` | Run 69 integration tests |
| `test-fast` | Unit tests on SQLite (fastest feedback loop) |
| `docker-up` | Build + start API and Postgres containers |
| `docker-up-seed` | Same + auto-seed database on first boot |
| `docker-down` | Stop containers (preserve DB volume) |
| `docker-clean` | Full teardown: containers + DB volume |
| `clean` | Remove all `__pycache__` and `.pyc` files |

```bash
# PowerShell
.\scripts\dev.ps1 <command>

# Makefile
make <command>
```
