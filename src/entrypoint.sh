#!/bin/bash
set -e

while ! nc -z $POSTGRES_HOST $POSTGRES_PORT; do
  sleep 0.1
done

python manage.py migrate

exec "$@"
