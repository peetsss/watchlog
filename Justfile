DC := "docker compose -f docker-compose.dev.yml"

default:
    @just --list

# start the dev stack (API, Postgres, Redis, Celery); run `just frontend` separately
dev:
    {{DC}} up -d --build
    @echo "API: http://localhost:8001  ·  SPA: run 'just frontend'"

# start only the development database and Redis
db:
    {{DC}} up -d database redis

# (re)start the API service
api:
    {{DC}} up -d --build api

# follow API logs
api-logs:
    {{DC}} logs -f api

# follow worker logs
worker-logs:
    {{DC}} logs -f worker

# follow beat logs
beat-logs:
    {{DC}} logs -f beat

# follow every container's logs
logs:
    {{DC}} logs -f

# stop the dev stack
stop:
    {{DC}} down

# stop the dev stack and delete its volumes
stop-v:
    {{DC}} down -v

# create the application database in the dev Postgres container
api-db:
    {{DC}} up -d database
    {{DC}} exec -T database sh -c 'createdb -U "$POSTGRES_USER" -T template0 watchlog_v2 2>/dev/null || true'

# install the repo git hooks
hooks:
    git config core.hooksPath .githooks
    @echo "installed .githooks (backend checks + frontend build on commit)"

# apply Alembic migrations on the host
migrate:
    uv run alembic upgrade head

# create an Alembic revision
revision message:
    uv run alembic revision --autogenerate -m "{{message}}"

# seed the demo users and Friday Film Club
seed:
    uv run python scripts/seed_dev_data.py

# import TMDB data
ingest *args:
    uv run python scripts/ingest_tmdb.py {{args}}

# build movie embeddings
embed *args:
    uv run python scripts/embed_movies.py {{args}}

# backfill TMDB/JustWatch watch availability
watch-providers *args:
    uv run python scripts/backfill_watch_providers.py {{args}}

# copy the bundled movie dataset into the app database
copy-movies *args:
    uv run python scripts/copy_movies.py {{args}}

# write docs/openapi.json from the running app
openapi:
    uv run python scripts/export_openapi.py

# dump the database to ./backups (set WATCHLOG_BACKUP_REMOTE for rclone upload)
backup:
    bash scripts/backup_db.sh

# operational commands (user, group, email)
admin *args:
    uv run python scripts/admin.py {{args}}

# run the API tests
test *args:
    uv run pytest {{args}}

# lint, format-check, migration-drift check and tests
check:
    uv run ruff check app tests alembic scripts
    uv run ruff format --check app tests alembic scripts
    uv run alembic check
    uv run pytest

# start the Vite dev server
frontend:
    cd frontend && npm run dev

# build the SPA
frontend-build:
    cd frontend && npm run build

# typecheck and build the SPA
frontend-check:
    cd frontend && npm run typecheck && npm run build

# run the API-backed Playwright flows
frontend-verify:
    cd frontend && npm run verify:all

# build the production image locally and start it on :8000
prod:
    docker build -t watchlog:prod .
    WATCHLOG_IMAGE=watchlog:prod docker compose up -d --remove-orphans

# pull the deployed image and restart the production stack
prod-pull:
    docker compose pull
    docker compose up -d --remove-orphans
