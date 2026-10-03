#!/bin/bash
set -e

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

python manage.py migrate --noinput
python manage.py collectstatic --noinput

# Serve the ASGI application (HTTP + websockets) via Daphne.
exec daphne watchlog.asgi:application --bind 0.0.0.0 --port 8000
