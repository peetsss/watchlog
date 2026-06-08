export USER_ID := `id -u`
export GROUP_ID := `id -g`

DC := "docker compose -f docker-compose.yml -f docker-compose.dev.yml"

# show all available commands
default:
    @just --list

# start development stack (hot-reload, runserver)
dev:
    {{DC}} up -d --build

# stop all containers
stop:
    {{DC}} down

# stop all containers and clear volumes
stop-v:
    {{DC}} down -v

# tail all containers logs
logs:
    {{DC}} logs -f

# bash in django container
bash:
    {{DC}} run --rm django /bin/bash

# create superuser
superuser:
    {{DC}} run --rm django python manage.py createsuperuser

# start production stack (gunicorn)
prod:
    docker compose -f docker-compose.yml up -d --build
