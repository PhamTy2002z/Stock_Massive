#!/bin/sh
set -e

echo "Waiting for database..."
# Wait for database to be ready
while ! nc -z db 5432; do
  sleep 1
done
echo "Database is ready!"

echo "Running database migrations..."
cd /code && alembic upgrade head

echo "Starting application..."
exec "$@"
