#!/bin/sh
# Don't use set -e to allow graceful handling of migration failures

# Extract database host from DATABASE_URL
# Supports both local docker (db:5432) and remote managed Postgres
if [ -n "$DATABASE_URL" ]; then
    # Parse host from DATABASE_URL (format: postgresql://user:pass@host:port/dbname)
    DB_HOST=$(echo "$DATABASE_URL" | sed -n 's|.*@\([^:/]*\).*|\1|p')
    DB_PORT=$(echo "$DATABASE_URL" | sed -n 's|.*:\([0-9]*\)/.*|\1|p')
    DB_PORT=${DB_PORT:-5432}

    # Only wait for local database (db hostname)
    if [ "$DB_HOST" = "db" ] || [ "$DB_HOST" = "localhost" ]; then
        echo "Waiting for database at $DB_HOST:$DB_PORT..."
        while ! nc -z "$DB_HOST" "$DB_PORT"; do
            sleep 1
        done
        echo "Database is ready!"

        # Local DB: migrations must succeed
        echo "Running database migrations..."
        cd /code && alembic upgrade head
        if [ $? -ne 0 ]; then
            echo "ERROR: Migrations failed for local database"
            exit 1
        fi
    else
        echo "Using remote database: $DB_HOST (skipping wait)"

        # Remote DB: try migrations but don't fail startup
        echo "Running database migrations (non-blocking for remote DB)..."
        cd /code && alembic upgrade head 2>&1 || echo "Warning: Migration returned non-zero exit code (continuing...)"
    fi
else
    echo "WARNING: DATABASE_URL not set, skipping migrations"
fi

echo "Starting application..."
exec "$@"
