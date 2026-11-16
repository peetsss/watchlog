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

# create the FastAPI database in the dev database container
api-db:
    {{DC}} up -d database
    {{DC}} exec -T database sh -c 'createdb -U "$POSTGRES_USER" -T template0 watchlog_v2 2>/dev/null || true'

# apply FastAPI migrations on the host
api-migrate:
    uv run alembic upgrade head

# create a FastAPI migration from the current models
api-revision message:
    uv run alembic revision --autogenerate -m "{{message}}"

# start the FastAPI service (dev compose profile)
api:
    {{DC}} --profile api up -d --build api

# tail FastAPI logs
api-logs:
    {{DC}} logs -f api

# run ruff, alembic drift check and pytest for the FastAPI app
api-check:
    uv run ruff check app tests alembic scripts
    uv run ruff format --check app tests alembic scripts
    uv run alembic check
    uv run pytest

# run FastAPI tests
api-test *args:
    uv run pytest {{args}}

# write the FastAPI OpenAPI schema to docs/openapi.json
api-openapi:
    uv run python scripts/export_openapi.py

# tail all containers logs
logs:
    {{DC}} logs -f

# bash in django container
bash:
    {{DC}} run --rm django /bin/bash

# apply migrations
migrate:
    {{DC}} run --rm django python manage.py makemigrations
    {{DC}} run --rm django python manage.py migrate

# run tests
test *args:
    {{DC}} run --rm -e REDIS_URL= django python manage.py test {{args}}

# run lint, formatting, migration and test checks
check:
    {{DC}} run --rm --no-deps -w /project --entrypoint ruff django check --cache-dir /tmp/ruff-cache src
    {{DC}} run --rm --no-deps -w /project --entrypoint ruff django format --check --cache-dir /tmp/ruff-cache src
    {{DC}} run --rm --no-deps --entrypoint python django manage.py makemigrations --check --dry-run
    {{DC}} run --rm -e REDIS_URL= django python manage.py test

# create superuser
superuser:
    {{DC}} run --rm django python manage.py createsuperuser

# start production stack (daphne ASGI)
prod:
    docker compose -f docker-compose.yml up -d --build
