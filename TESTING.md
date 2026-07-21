# TESTING.md — Test Suite Documentation

## Overview

This document describes the complete test suite for the **Almentor Youth Program Task Management API** — a Django REST Framework project with JWT authentication, soft-delete, and data isolation.

The suite is split into two layers:

| Layer | Purpose | Database | Mocking |
|-------|---------|---------|---------|
| **Unit Tests** | Isolated functions, classes, methods | Real PostgreSQL locally / SQLite in CI | External deps mocked (e.g., `logger`) |
| **Integration Tests** | Multi-step API flows with real JWT | Real PostgreSQL (local & CI) | No mocking |

---

## How to Run Tests

### Run All Tests Locally (PostgreSQL)

Ensure your `.env` file is configured and PostgreSQL is running:

```bash
# All tests (unit + integration):
uv run python manage.py test --verbosity=2

# Unit tests only:
uv run python manage.py test core projects tasks --verbosity=2

# Integration tests only:
uv run python manage.py test integration_tests --verbosity=2
```

### Run CI-Style (SQLite, unit tests only)

```bash
uv run python manage.py test \
  --settings=core.test_settings \
  --verbosity=2 \
  core projects tasks
```

### Run a Specific Test File or Class

```bash
# A specific test file:
uv run python manage.py test integration_tests.test_project_lifecycle

# A specific test class:
uv run python manage.py test integration_tests.test_filters_and_search.TaskSearchAndPaginationTest

# A specific test method:
uv run python manage.py test integration_tests.test_filters_and_search.TaskSearchAndPaginationTest.test_default_page_returns_10_results
```

---

## Test Coverage Summary

### Unit Tests (117 tests)

| App | Test File | Tests | Focus |
|-----|-----------|-------|-------|
| `core` | `test_models.py` | 9 | `BaseModel`, `ActiveManager` |
| `projects` | `test_models.py` | 7 | Cascade soft-delete, `UniqueConstraint` |
| `projects` | `test_serializers.py` | 9 | `validate_name`, field exposure, read-only |
| `projects` | `test_views.py` | 18 | Auth, data isolation, full CRUD |
| `tasks` | `test_models.py` | 7 | `validate_due_date` boundaries, defaults |
| `tasks` | `test_serializers.py` | 8 | `DONE→TODO` warning, read-only `project_id` |
| `tasks` | `test_views.py` | 22 | Auth, data isolation, CRUD, soft-delete |
| `tasks` | `test_filters.py` | 17 | All filter/search/sort params, combined |

### Integration Tests (63 tests)

| File | Tests | Critical Flow |
|------|-------|---------------|
| `test_project_lifecycle.py` | 9 | **Flow 1**: Create project → Add tasks → Mark done → Delete (cascade) |
| `test_filters_and_search.py` | 27 | **Flow 2**: Filter by status/priority/date + **Flow 3**: Search + Pagination |
| `test_authentication_flow.py` | 13 | JWT obtain → use → refresh → all error cases |
| `test_data_isolation.py` | 14 | Full cross-user isolation (projects + tasks, all endpoints) |
| `test_task_status_transitions.py` | 10 | All transitions, DONE→TODO warning, invalid values |

**Total: 180 tests**

---

## Critical Flows Covered

### Flow 1 — Full Project Lifecycle
```
POST /api/projects/
  → POST /api/projects/:id/tasks/   (×2 tasks)
    → PUT /api/tasks/:id/  (mark done)
      → DELETE /api/projects/:id/
        → verify tasks cascade soft-deleted (not hard-deleted)
        → verify 404 on deleted task GET
```

### Flow 2 — Filter by Status and Priority
```
Create 6 tasks with distinct status × priority combinations
  → GET /api/tasks/?status=todo
  → GET /api/tasks/?priority=high
  → GET /api/tasks/?status=in_progress&priority=medium
  → GET /api/tasks/?due_date_from=...&due_date_to=...
  → GET /api/tasks/?ordering=-due_date
```

### Flow 3 — Search and Pagination
```
Create 15 tasks (8 with keyword, 7 without)
  → GET /api/tasks/?q=authentication  (returns 8, first page = 10)
  → GET /api/tasks/?q=authentication&limit=5  (paginated search)
  → GET /api/tasks/?page=2  (remaining 5 results)
  → verify next/previous links, no duplicate IDs across pages
```

---

## Edge Cases Handled

### Unit Tests

| Edge Case | Test Location |
|-----------|--------------|
| Soft-deleted records hidden from default manager | `core/tests/test_models.py` |
| `restore()` re-exposes soft-deleted records | `core/tests/test_models.py` |
| Cascade soft-delete doesn't hard-delete tasks | `projects/tests/test_models.py` |
| `validate_name` excludes self during UPDATE | `projects/tests/test_serializers.py` |
| `owner` and `deleted_at` never exposed in API | `projects/tests/test_serializers.py` |
| Accessing another user's resource returns 404 (not 403) | `projects/tests/test_views.py` |
| `validate_due_date`: today is valid (boundary inclusive) | `tasks/tests/test_models.py` |
| `DONE → TODO` triggers `logger.warning` | `tasks/tests/test_serializers.py` |
| `DONE → TODO` is still allowed (not blocked) | `tasks/tests/test_serializers.py` |
| SQL-injection-like ordering key silently ignored | `tasks/tests/test_filters.py` |
| Invalid status filter returns empty queryset | `tasks/tests/test_filters.py` |
| Combined filters use AND logic | `tasks/tests/test_filters.py` |

### Integration Tests

| Edge Case | Test Location |
|-----------|--------------|
| Wrong password returns 401 | `test_authentication_flow.py` |
| Wrong auth scheme (`Token` vs `Bearer`) returns 401 | `test_authentication_flow.py` |
| Malformed JWT returns 401 | `test_authentication_flow.py` |
| Tampered refresh token returns 401 | `test_authentication_flow.py` |
| User A updating User B's project leaves B's data unchanged | `test_data_isolation.py` |
| User A cannot create tasks in User B's project | `test_data_isolation.py` |
| Same project name allowed for different users | `test_data_isolation.py` |
| Cascade soft-delete persists tasks in `all_objects` | `test_project_lifecycle.py` |
| Filter results reflect status changes immediately (no caching) | `test_task_status_transitions.py` |
| Status preserved after a rejected invalid update | `test_task_status_transitions.py` |
| Out-of-range page returns 404 | `test_filters_and_search.py` |
| Pagination: no duplicate IDs across pages | `test_filters_and_search.py` |
| Search: uppercase = lowercase (case-insensitive) | `test_filters_and_search.py` |
| Search + status filter combined via real API | `test_filters_and_search.py` |

---

## CI/CD Workflow (GitHub Actions)

### Two Jobs

```
push / pull_request
       │
       ▼
┌──────────────────────────┐
│  unit-tests              │  Python 3.10 · SQLite (fast, zero-config)
│  Runs core/projects/tasks│
└────────────┬─────────────┘
             │ needs: unit-tests
             ▼
┌──────────────────────────┐
│  integration-tests       │  Python 3.10 · PostgreSQL 16 service container
│  Runs integration_tests/ │
└──────────────────────────┘
```

**Why single Python version?**
The project's `.python-version` file pins **Python 3.10**. Running the matrix on 3.10/3.11/3.12 added unnecessary CI minutes with no real benefit — the library ecosystem is stable across versions for this project's dependencies.

**Why PostgreSQL in CI for integration tests?**
Integration tests must run against the real database engine to catch PostgreSQL-specific constraint enforcement, query behaviour, and transaction semantics that SQLite doesn't replicate.

---

## Test Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| `force_authenticate()` in unit tests | Keeps view tests focused on business logic, not auth plumbing |
| Real JWT in integration tests | Tests the complete authentication chain as users experience it |
| `IntegrationTestBase.auth_client()` helper | Encapsulates the token-obtain flow; tests stay readable |
| `patch("tasks.serializers.logger")` | Verifies the warning is triggered without polluting test output |
| `all_objects` manager assertions | Confirms soft-delete (not hard-delete) at the DB level |
| Dedicated `test_filters.py` (unit) + `test_filters_and_search.py` (integration) | `apply_task_filters()` is complex; tested in isolation (unit) AND through the full HTTP stack (integration) |
