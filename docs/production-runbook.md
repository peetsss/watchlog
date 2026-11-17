# watchlog production runbook

Status: operational notes for the single-VPS Docker Compose deployment.

## Required environment

```text
WATCHLOG_ENV=prod
WATCHLOG_SECRET_KEY=<long random value>
WATCHLOG_PUBLIC_URL=https://watchlog.example
WATCHLOG_SITE_ADDRESS=watchlog.example
WATCHLOG_ALLOWED_HOSTS=watchlog.example
WATCHLOG_TRUSTED_ORIGINS=https://watchlog.example
POSTGRES_PASSWORD=<long random value>
TMDB_API_KEY=<tmdb key>
WATCHLOG_MAIL_BACKEND=resend
WATCHLOG_MAIL_FROM="watchlog <hello@watchlog.example>"
WATCHLOG_RESEND_API_KEY=<resend key>
WATCHLOG_SENTRY_DSN=<optional sentry dsn>
```

Do not store these values in Git.

## Deploy

1. Create a database backup and confirm it succeeded.
2. Pull the release commit.
3. `docker compose up -d --build`.
4. Confirm `migrate` exited 0.
5. Confirm the API is healthy at `/ready`.
6. Confirm `worker` and `beat` are running.
7. Smoke test:

```text
GET /health -> ok
GET /ready -> database/redis ok
open / -> app
register with a real inbox -> verification email
open an invite -> guest room -> claim
```

## Rollback

1. Stop the API and worker.
2. Deploy the previous image/commit.
3. Run the matching Alembic revision only after checking whether the release
   added a migration.
4. Restore the database backup if a schema rollback is required.
5. Start the API and worker and run the smoke tests.

Do not run `docker compose down -v` during rollback. It deletes named data
volumes.

## Backup and restore

Backup:

```bash
set -a
source .env
set +a
WATCHLOG_BACKUP_DIR=/srv/watchlog/backups just backup
```

Restore into a fresh database:

```bash
pg_restore --clean --if-exists --no-owner \
  --dbname=watchlog_v2 \
  /srv/watchlog/backups/watchlog_v2-<timestamp>.dump
```

Test the restore on a staging database before relying on it.

## Admin commands

```bash
just admin user disable alice
just admin user enable alice
just admin user revoke-sessions alice
just admin group delete <group-uuid>
just admin group revoke-invites <group-uuid>
just admin email requeue --recipient alice@example.com
just admin email requeue --id 123
```

## Email

- Verify the sending domain in Resend.
- Configure SPF, DKIM and DMARC before launch.
- Transactional mail is written to `email_outbox` in the same transaction as
  the token; the Celery email dispatcher sends it.
- Failed rows are visible in the outbox and can be requeued with the admin CLI.
- Account security emails (password reset/change) should never be disabled.

## TMDB and JustWatch

- TMDB film metadata and images require `TMDB_API_KEY`.
- Watch availability comes from TMDB's `/watch/providers`, powered by JustWatch.
- Provider snapshots live in `movie_watch_regions` and
  `movie_watch_providers`.
- A daily task refreshes group-watchlist providers; active finalists are
  prefetched by the worker.
- Backfill manually after a catalogue import:

```bash
just watch-providers --scope watchlists --limit 500
just watch-providers --scope popular --limit 500
```

Do not call JustWatch directly. Keep the TMDB and JustWatch attribution visible
in the app; removing it can revoke API access.

## Account deletion

For the first release, account deletion is support-assisted. Ask the user to
export their data from Account settings, then use a reviewed SQL transaction to
remove memberships, reviews and the user row. Do not delete a group owned solely
by the account without transferring or deleting the group first.

## Incident checks

- API unavailable: check Caddy, API logs, `/ready`, database and Redis health.
- WebSocket issues: confirm Caddy is proxying `/ws` and Redis is healthy.
- Email missing: check `email_outbox.status`, worker logs and Resend dashboard.
- Watch data missing: check the provider snapshot row, TMDB key and Celery
  worker logs.
- Suspicious account: disable the user, revoke sessions and review group
  invites.
