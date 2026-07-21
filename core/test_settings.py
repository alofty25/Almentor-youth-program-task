"""
core/test_settings.py

CI-specific test settings that override the main settings.
Used by GitHub Actions to run tests WITHOUT a real PostgreSQL instance.
Locally, developers should run tests using the default settings.py (which uses Postgres).
"""

from core.settings import *  # noqa: F401, F403 — inherit everything from main settings

# -----------------------------------------------------------------
# Override: use SQLite in-memory for fast, zero-config CI testing.
# This avoids needing a Postgres service container in GitHub Actions.
# -----------------------------------------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
