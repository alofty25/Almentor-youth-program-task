#!/bin/sh
# =============================================================================
#  docker-entrypoint.sh
#  Runs inside the api container before the main process starts.
#  Responsibilities:
#    1. Wait for PostgreSQL to be ready (avoids "Connection refused" on startup)
#    2. Apply any pending database migrations automatically
#    3. Optionally seed the database (set SEED_DB=true in .env.docker)
#    4. Hand off to the CMD (Django dev server)
# =============================================================================

set -e

echo "==> Waiting for PostgreSQL to be ready..."
# Poll pg_isready until the database accepts connections (max 60s)
until python -c "
import sys, psycopg2, os, time
for attempt in range(60):
    try:
        psycopg2.connect(
            dbname=os.environ['DB_NAME'],
            user=os.environ['DB_USER'],
            password=os.environ['DB_PASSWORD'],
            host=os.environ['DB_HOST'],
            port=os.environ.get('DB_PORT', '5432'),
        )
        break
    except psycopg2.OperationalError:
        print(f'  Attempt {attempt+1}/60 — Postgres not ready yet, retrying...')
        time.sleep(1)
else:
    print('ERROR: PostgreSQL did not become ready within 60 seconds.')
    sys.exit(1)
"; do
    sleep 1
done
echo "==> PostgreSQL is ready."

echo "==> Applying database migrations..."
python manage.py migrate --noinput
echo "==> Migrations applied."

# Optional: seed database on first boot when SEED_DB=true
if [ "${SEED_DB:-false}" = "true" ]; then
    echo "==> SEED_DB=true detected. Seeding database with production-like data..."
    python manage.py seed --clear
    echo "==> Seeding complete."
fi

echo "==> Starting Django application..."
exec "$@"
