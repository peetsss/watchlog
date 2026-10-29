#!/bin/bash
set -e

while ! nc -z "$POSTGRES_HOST" "$POSTGRES_PORT"; do
  sleep 0.1
done

while ! nc -z "${REDIS_HOST:-redis}" "${REDIS_PORT:-6379}"; do
  sleep 0.1
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec daphne -b 0.0.0.0 -p 8000 watchlog.asgi:application
