#!/bin/bash
set -e

echo "Running Alembic migrations..."

DB_URL="${BIBMEDED_DATABASE_URL:-}"
if [ -z "$DB_URL" ]; then
  DB_URL=$(python -c "from app.config import settings; print(settings.database_url)")
fi

case "$DB_URL" in
  sqlite*)
    # SQLite is a single file with no concurrent-writer race across
    # containers to guard against -- run the migration directly.
    alembic upgrade head
    ;;
  *)
    # Postgres: the api and worker containers boot concurrently and both
    # run this entrypoint, so serialize the migration with a session-scoped
    # advisory lock. The loser blocks until the winner releases it, then
    # runs `alembic upgrade head` itself and finds nothing left to do,
    # instead of racing the winner on the same DDL.
    python <<'PY'
import subprocess
import sys

from sqlalchemy import create_engine, text

from app.config import settings

_MIGRATION_LOCK_KEY = 916234871  # arbitrary, fixed for every bibmeded deployment

engine = create_engine(settings.database_url)
with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
    conn.execute(text("SELECT pg_advisory_lock(:key)"), {"key": _MIGRATION_LOCK_KEY})
    try:
        rc = subprocess.call(["alembic", "upgrade", "head"])
    finally:
        conn.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _MIGRATION_LOCK_KEY})
sys.exit(rc)
PY
    ;;
esac

echo "Starting application..."
exec "$@"
