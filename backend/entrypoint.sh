#!/bin/sh
set -e

echo "[entrypoint] Waiting for database..."
python manage.py wait_for_db

echo "[entrypoint] Running migrations..."
python manage.py migrate --noinput

echo "[entrypoint] Collecting static files..."
python manage.py collectstatic --noinput

# NOTE: no admin account and no demo data are created automatically.
# Create the first system_admin with:
#   docker compose run --rm backend python manage.py createsuperuser
# Create a school + its operator with:
#   docker compose run --rm backend python manage.py create_school_operator

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
