# watchlog production runbook

Status: operational notes for the single-VPS Docker Compose deployment. TLS is
terminated by a reverse proxy on the host; everything else runs in Compose.

## Required environment

Compose reads `.env`:

```text
WATCHLOG_ENV=prod
WATCHLOG_SECRET_KEY=<long random value>
WATCHLOG_PUBLIC_URL=https://watchlog.example
WATCHLOG_ALLOWED_HOSTS=watchlog.example
WATCHLOG_TRUSTED_ORIGINS=https://watchlog.example
WATCHLOG_TRUSTED_PROXY_IPS=172.18.0.0/16
WATCHLOG_MAX_REQUEST_BODY_BYTES=1048576
POSTGRES_PASSWORD=<long random value>
TMDB_ACCESS_TOKEN=<v4 read access token>
# TMDB_API_KEY=<v3 fallback>
WATCHLOG_MAIL_BACKEND=resend
WATCHLOG_MAIL_FROM="watchlog <hello@watchlog.example>"
WATCHLOG_RESEND_API_KEY=<resend key>
WATCHLOG_SENTRY_DSN=<optional sentry dsn>
```

`WATCHLOG_SECRET_KEY` is reserved for future signing use; rotating it does not
revoke sessions today. Keep it set for rollback compatibility.

The deploy workflow writes the current release tag to `.env` as
`WATCHLOG_IMAGE` so later admin and backup commands use the same image. Manual
runs must export it, for example
`WATCHLOG_IMAGE=ghcr.io/<owner>/watchlog:v<version>`.

The host reverse proxy keeps its own configuration on the VPS, outside this
repository; see [Host reverse proxy](#host-reverse-proxy).

Do not store these values in Git. On the VPS:

```bash
install -m 600 .env
```

## Host reverse proxy

A reverse proxy on the VPS terminates TLS and forwards to the API. It is
configured on the server, not in this repo, so its config is not versioned with
the app. Our VPS uses Caddy; any proxy works if it:

- serves the domain in `WATCHLOG_PUBLIC_URL` on 80/443 with a valid certificate;
- forwards to `127.0.0.1:8000`;
- supports WebSocket upgrades on `/ws`; cap frames to 64 KiB and set a
  connection/message limit at the proxy as the outer guard;
- caps request bodies at 1 MiB; the app returns `413` and the proxy limit is the
  first line of defence;
- sets `X-Forwarded-For` and `X-Forwarded-Proto` (rate limits key on the client
  IP);
- leaves port 8000 closed at the firewall, so the proxy is the only entry
  point.

Set `WATCHLOG_TRUSTED_PROXY_IPS` to the proxy address as seen by the API:
comma-separated exact IPs or CIDRs. With an empty value the API ignores
`X-Forwarded-For` entirely and rate limits key on the proxy IP. Find the Docker
gateway with `docker network inspect watchlog_watchlog`; a value such as
`172.18.0.0/16` is accepted.

Do not use `0.0.0.0/0`; that would let untrusted peers forge the client IP.

After proxy changes, reload it and confirm the site and `/ws` still work. On our
VPS that is `sudo systemctl reload caddy`, with logs in
`journalctl -u caddy -f`.

## Logging

Uvicorn access logs are disabled in the API entrypoint and the dev stack. The
app request log includes the method, redacted path and client IP; tokens in
invite paths and query strings are replaced with `[REDACTED]`.

If the host proxy keeps access logs, redact or disable the invite and token
paths there too. Do not forward token-bearing URLs to a third-party log service.

## CI/CD

Development happens on `dev`; `main` is production. Release and promotion are
explicit manual actions:

1. run the `Release` workflow with the version you want
2. merge the release PR on `dev`
3. the tag build pushes the image and creates the GitHub release
4. run the `Promote release` workflow with the same version
5. merge the promotion PR into `main` to deploy

Nothing is released or promoted by a normal `dev` push.

The first production release is tagged manually as `v0.1.0`; after that, use the
manual Release workflow with an explicit version.

The VPS only pulls images. It never builds.

| Workflow | Trigger | Does |
| --- | --- | --- |
| `ci.yml` | PRs and pushes to `dev`/`main` | checks; Docker build check on PRs; deploy on `main` |
| `release.yml` | manual dispatch with a version | release-please release PR |
| `release-image.yml` | tag `v*` | image build/push; GitHub release |
| `promote.yml` | manual dispatch with a version | promotion PR to `main` |
| `pr-title.yml` | PRs to `dev`/`main` | conventional PR title check |

### GitHub settings

- Make `dev` the default branch.
- Protect `dev` and `main`: require pull requests, the `backend`, `frontend`,
  `image-check` and `PR title` checks, and disable force pushes.
- Allow only squash merges on `main`. The deploy job requires the commit body
  to contain `chore(release): vX.Y.Z`, which is the promotion PR title. Squash
  keeps the subject clean; a merge commit also passes but is noisier.
- Add a repository secret `AUTOMATION_TOKEN`: a fine-grained PAT with
  `contents: write`, `issues: write` and `pull-requests: write`. It is required:
  release-please and the promotion workflow refuse to run without it, so
  bot-created PRs always trigger checks.

Create a `production` environment (Settings → Environments) and add these
environment secrets:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS hostname or IP |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | private ed25519 key for the deploy user |
| `VPS_KNOWN_HOSTS` | output of `ssh-keyscan -H <VPS_HOST>` |
| `VPS_PORT` | optional, defaults to `22` |
| `VPS_APP_DIR` | optional, defaults to `/srv/watchlog` |

Add required reviewers to the environment if production deploys should wait for
approval.

Generate the pair on a trusted machine:

```bash
ssh-keygen -t ed25519 -f watchlog-deploy -C watchlog-deploy
ssh-keyscan -H <VPS_HOST>
```

Put the public key in the deploy user's `~/.ssh/authorized_keys`, the private key
in `VPS_SSH_KEY`, and the keyscan output in `VPS_KNOWN_HOSTS`.

### VPS bootstrap

1. Create a `deploy` user and add it to the `docker` group. Docker group access
   is effectively root; protect the key and the VPS login accordingly.
2. Clone the repository to `/srv/watchlog` with a deploy key or token. The
   workflow runs `git fetch origin main` and resets the working tree to it.
3. Create `.env` from `.env.template`, fill production secrets and domain
   values, and keep it out of Git.
4. Log in to GHCR as the deploy user with a token that can read packages:
   `docker login ghcr.io -u <github-user>`. Make the package public instead if
   you prefer anonymous pulls.
5. Configure the host reverse proxy and firewall as described above.
6. Deploy the first image manually after the first release:

```bash
cd /srv/watchlog
export WATCHLOG_IMAGE=ghcr.io/<owner>/watchlog:v0.1.0
docker compose pull
docker compose up -d --remove-orphans
curl -fsS http://127.0.0.1:8000/ready
```

### First production release

Release and promotion are manual. After the staging smoke tests:

1. Tag the release commit on `dev` and push the tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

2. `release-image.yml` builds and pushes `v0.1.0` and creates the GitHub release.
3. Run the **Promote release** workflow with version `0.1.0` (or open a PR from
   the `v0.1.0` tag to `main` manually). It creates
   `chore(release): v0.1.0`.
4. Merge the promotion PR into `main`. The deploy job verifies the image and
   ships it.

The manual tag is only for the first release.

### Subsequent releases

1. Run the **Release** workflow with the version, for example `0.1.1`.
2. Review and merge the release-please PR on `dev`.
3. The tag build pushes the image and creates the GitHub release.
4. Run the **Promote release** workflow with `0.1.1`.
5. Merge the promotion PR to deploy.

The version input is authoritative; release-please does not choose a bump. No
release or promotion happens on a normal push.

### How a deploy runs

A release promotion to `main` runs the checks and then the deploy job:

1. reads the version from `pyproject.toml`;
2. requires the commit body to contain `chore(release): v<version>`;
3. verifies `ghcr.io/<owner>/watchlog:v<version>` exists;
4. SSHes to the VPS and runs:

```bash
git fetch origin main
git reset --hard FETCH_HEAD
export WATCHLOG_IMAGE=ghcr.io/<owner>/watchlog:v<version>
docker compose pull
docker compose up -d --remove-orphans
curl -fsS http://127.0.0.1:8000/ready
```

`docker compose up` runs the one-shot `migrate` service and then starts the API,
worker and beat. If `/ready` fails, the job fails; inspect `migrate` and API logs
before rolling back.

### Rollback

Deploy the previous version tag without rebuilding:

```bash
cd /srv/watchlog
export WATCHLOG_IMAGE=ghcr.io/<owner>/watchlog:v<previous>
docker compose pull
docker compose up -d --remove-orphans
```

If the release changed the schema incompatibly, restore the database backup
instead of only changing the image.

## Deploy

1. Create a database backup and confirm it succeeded.
2. Merge the release promotion PR into `main`; the workflow verifies and
   deploys the version tag. For a manual deploy, export the version tag and run:

```bash
export WATCHLOG_IMAGE=ghcr.io/<owner>/watchlog:v0.1.0
docker compose pull
docker compose up -d --remove-orphans
```

3. Confirm `migrate` exited 0.
4. Confirm the API is healthy at `/ready`.
5. Confirm `worker` and `beat` are running.
6. Confirm the host reverse proxy is active and reload it after config changes.
7. Smoke test:

```text
GET /health -> ok
GET /ready -> database/redis ok
open / -> app
register with a real inbox -> verification email
open an invite -> guest room -> claim
```

## Rollback

1. Set `WATCHLOG_IMAGE` to the previous `v` tag.
2. `docker compose pull && docker compose up -d --remove-orphans`.
3. Check whether the release added a migration. Do not auto-downgrade a schema
   the old image cannot read.
4. Restore the database backup if a schema rollback is required.
5. Run the smoke tests.

Do not run `docker compose down -v` during rollback. It deletes named data
volumes.

Redis stores sessions and rate-limit counters. Set a `maxmemory` appropriate
for the host, use `noeviction`, and alert when used memory exceeds roughly 70%.
Do not use an eviction policy that silently discards rate-limit keys.

## Backup and restore

Backup:

```bash
set -a
source .env
set +a
WATCHLOG_BACKUP_VIA_DOCKER=1 \
WATCHLOG_BACKUP_DIR=/srv/watchlog/backups \
just backup
```

Restore into the running database container:

```bash
set -a
source .env
set +a
docker compose exec -T database pg_restore \
  -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  --clean --if-exists --no-owner \
  < /srv/watchlog/backups/watchlog_v2-<timestamp>.dump
```

Test the restore on a staging database before relying on it. Database dumps
contain emails, password hashes and email outbox payloads; encrypt them at rest
if the host or backup target is shared. The backup script writes a `0600` dump
inside a `0700` directory.

## Admin commands

On the VPS, run the CLI inside the API container:

```bash
set -a
source .env
set +a
docker compose exec api python scripts/admin.py user disable alice
docker compose exec api python scripts/admin.py user enable alice
docker compose exec api python scripts/admin.py user revoke-sessions alice
docker compose exec api python scripts/admin.py group delete <group-uuid>
docker compose exec api python scripts/admin.py group revoke-invites <group-uuid>
docker compose exec api python scripts/admin.py email requeue --recipient alice@example.com
docker compose exec api python scripts/admin.py email requeue --id 123
```

## Email

- Verify the sending domain in Resend.
- Configure SPF, DKIM and DMARC before launch.
- Transactional mail is written to `email_outbox` in the same transaction as
  the token; the Celery email dispatcher sends it.
- Failed rows are visible in the outbox and can be requeued with the admin CLI.
- Account security emails (password reset/change) should never be disabled.
- The console mailer is development/test only. Production refuses to start with
  `WATCHLOG_MAIL_BACKEND=console`.

## TMDB and JustWatch

- TMDB film metadata and images require a TMDB credential. Prefer a v4 read
  access token (`TMDB_ACCESS_TOKEN`); the v3 `TMDB_API_KEY` remains supported as
  a fallback. If both are set, the access token is used.
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

- API unavailable: check the host reverse proxy, API logs, `/ready`, database
  and Redis health.
- WebSocket issues: confirm the host reverse proxy is upgrading `/ws` and
  Redis is healthy.
- Port 8000 reachable from the internet: stop the stack and fix the loopback
  publish rule; direct API access bypasses TLS and spoofs client IPs.
- Email missing: check `email_outbox.status`, worker logs and Resend dashboard.
- Watch data missing: check the provider snapshot row, TMDB key and Celery
  worker logs.
- Suspicious account: disable the user, revoke sessions and review group
  invites.
