export USER_ID := `id -u`
export GROUP_ID := `id -g`

DC := "docker compose -f docker-compose.yml -f docker-compose.dev.yml"

default:
    @just --list

build:
    {{DC}} build

up:
    {{DC}} up

up-d:
    {{DC}} up -d

down:
    {{DC}} down

logs:
    {{DC}} logs -f

bash:
    {{DC}} run --rm django /bin/bash

migrate:
    {{DC}} run --rm django python manage.py makemigrations
    {{DC}} run --rm django python manage.py migrate

superuser:
    {{DC}} run --rm django python manage.py createsuperuser

prod-up:
    docker compose -f docker-compose.yml up -d --build
