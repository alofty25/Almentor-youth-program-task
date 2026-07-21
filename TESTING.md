# TESTING.md — Test Suite Documentation

## Overview

This document describes the unit test suite for the **Almentor Youth Program Task Management API** — a Django REST Framework project with JWT authentication, soft-delete, and data isolation.

> **Philosophy**: These are strictly *unit tests*. They test isolated functions, classes, and methods. External dependencies (JWT, logging) are mocked. No integration or E2E tests at this stage.

---

## How to Run Tests

### Locally (against the real PostgreSQL database)

Ensure your `.env` file is properly configured and PostgreSQL is running, then:

```bash
# Using uv (recommended):
uv run python manage.py test --verbosity=2

# Without uv:
python manage.py test --verbosity=2
```

This runs all tests against the **real PostgreSQL database** configured in your `.env` file. Django creates a temporary test database (`test_<DB_NAME>`), runs all tests, and drops it at the end.

### In CI / Without PostgreSQL (SQLite)

The `core/test_settings.py` file overrides the database to use in-memory SQLite:

```bash
uv run python manage.py test --settings=core.test_settings --verbosity=2
```

### Run a specific app's tests

```bash
# All tests for the 'tasks' app:
uv run python manage.py test tasks --verbosity=2

# A specific test file:
uv run python manage.py test tasks.tests.test_filters --verbosity=2

# A specific test class:
uv run python manage.py test tasks.tests.test_filters.ApplyTaskFiltersSearchTestCase

# A specific test method:
uv run python manage.py test tasks.tests.test_filters.ApplyTaskFiltersSearchTestCase.test_search_matches_title_case_insensitive
```

---

## Test Coverage Summary

| App | Test File | Test Cases | What's Covered |
|-----|-----------|-----------|----------------|
| `core` | `test_models.py` | 9 | `ActiveManager` filtering, `BaseModel.delete()`, `restore()`, `hard_delete()` |
| `projects` | `test_models.py` | 7 | `__str__`, cascade soft-delete to tasks, `UniqueConstraint` at DB level |
| `projects` | `test_serializers.py` | 9 | `validate_name` business rule, field exposure, read-only enforcement |
| `projects` | `test_views.py` | 18 | Auth, data isolation, list/create/retrieve/update/delete via API |
| `tasks` | `test_models.py` | 7 | `validate_due_date` boundaries, `__str__`, default field values |
| `tasks` | `test_serializers.py` | 8 | Field exposure, read-only `project_id`, `DONE→TODO` warning log |
| `tasks` | `test_views.py` | 22 | Auth, data isolation, all CRUD endpoints, soft-delete, past due date |
| `tasks` | `test_filters.py` | 17 | All filter/search/sort params, invalid inputs, combined filters |
| **Total** | **8 files** | **~97 tests** | |

---

## Edge Cases Handled

### `core` — BaseModel / ActiveManager

| Edge Case | Test |
|-----------|------|
| Soft-deleted records are hidden from `objects` | `test_soft_deleted_record_hidden_from_default_manager` |
| Soft-deleted records remain in `all_objects` | `test_soft_deleted_record_still_in_all_objects` |
| `deleted_at` timestamp matches time of deletion | `test_soft_delete_timestamp_is_close_to_now` |
| `restore()` re-exposes the record | `test_restore_makes_record_visible_in_default_manager` |
| `hard_delete()` works even on already-soft-deleted records | `test_hard_delete_on_soft_deleted_record_also_removes_row` |

### `projects` — Model

| Edge Case | Test |
|-----------|------|
| Cascade soft-delete doesn't hard-delete tasks | `test_soft_deleting_project_keeps_tasks_in_all_objects` |
| Cascade only affects the deleted project's tasks | `test_soft_delete_does_not_affect_tasks_of_other_projects` |
| Two users can share the same project name | `test_different_users_can_share_project_names` |

### `projects` — Serializer

| Edge Case | Test |
|-----------|------|
| `validate_name` excludes self during UPDATE (prevent false rejection) | `test_update_existing_project_with_same_name_passes_validation` |
| `owner` and `deleted_at` never exposed in API output | `test_serialized_output_does_not_expose_*` |
| Read-only fields (`id`, `created_at`) cannot be overwritten via payload | `test_id_and_timestamps_are_read_only` |

### `projects` — Views

| Edge Case | Test |
|-----------|------|
| Accessing another user's project returns 404, not 403 | `test_retrieve_other_users_project_returns_404` |
| Soft-deleted projects hidden from list view | `test_list_does_not_return_soft_deleted_projects` |
| DELETE is a soft-delete (row still exists in DB) | `test_delete_soft_deletes_project` |

### `tasks` — Model / Validator

| Edge Case | Test |
|-----------|------|
| Yesterday fails (strictly past) | `test_yesterday_fails_validation` |
| Today passes (boundary: inclusive) | `test_today_passes_validation` |
| `due_date` field is nullable (optional) | `test_due_date_is_optional` |

### `tasks` — Serializer

| Edge Case | Test |
|-----------|------|
| `DONE → TODO` transition triggers `logger.warning` | `test_done_to_todo_transition_triggers_logger_warning` |
| `DONE → TODO` is still *allowed* (warning only, not blocked) | `test_done_to_todo_transition_still_saves_new_status` |
| Updating title without changing status does NOT trigger warning | `test_update_without_status_change_does_not_log_warning` |
| `project_id` in payload is ignored (read-only) | `test_project_id_is_read_only` |

### `tasks` — Views

| Edge Case | Test |
|-----------|------|
| Creating a task with a past `due_date` returns 400 | `test_create_task_with_past_due_date_returns_400` |
| Creating a task with an invalid `status` value returns 400 | `test_create_task_with_invalid_status_returns_400` |
| After soft-delete, a GET on the same task returns 404 | `test_deleted_task_returns_404_on_subsequent_get` |
| User1 cannot create tasks in User2's project | `test_create_task_in_other_users_project_returns_404` |

### `tasks` — Filters (`apply_task_filters`)

| Edge Case | Test |
|-----------|------|
| Invalid/unknown `status` value returns empty queryset | `test_filter_by_invalid_status_returns_empty_queryset` |
| SQL-injection-like `ordering` key is silently ignored | `test_invalid_ordering_key_is_silently_ignored` |
| Date range boundaries are inclusive (exact match included) | `test_due_date_range_inclusive_boundaries` |
| Search is case-insensitive | `test_search_matches_title_case_insensitive` |
| Search is partial (not exact match) | `test_search_partial_match_works` |
| Combined filters use AND logic | `test_combined_status_and_search_filter` |

---

## Test Architecture Decisions

### Why SQLite in CI?
Running against SQLite in GitHub Actions means no Postgres service container is needed — simpler YAML, faster runs, works on any GitHub-hosted runner. Locally, tests run against the real PostgreSQL database for full fidelity.

### Why `force_authenticate()` instead of JWT tokens?
`force_authenticate()` bypasses the JWT middleware entirely, keeping view-layer tests focused on *business logic* rather than authentication plumbing. JWT token generation is already tested by `djangorestframework-simplejwt`'s own test suite.

### Why mock `logger` in serializer tests?
Mocking `tasks.serializers.logger` lets us assert that `logger.warning()` is called (or not) with specific arguments, without polluting test output or relying on log handlers. It also ensures tests are deterministic.

### Why a dedicated `test_filters.py`?
`apply_task_filters()` is a pure queryset-transformation function with significant branching logic. Isolating it in its own file (with mock request objects) makes each filter concern independently testable without going through the HTTP layer.
