# watchlog backend architecture

A working description of how the FastAPI backend is put together, where state
lives, and which invariants the code relies on. It describes the current code,
not an aspirational design.

## 1. Runtime shape

One image runs every backend role. `scripts/api_entrypoint.py` starts Uvicorn
for the API; the Celery command starts workers; a second Celery process runs
beat. Migrations run as a one-shot Compose service before the API and workers
start.

```text
Browser
  ├── HTTPS /api/* ───────┐
  └── WSS   /ws/* ────────┤
                          ▼
                 host reverse proxy          (TLS, configured outside the repo)
                          │
                          ▼
                    FastAPI / Uvicorn       ── PostgreSQL 18 + pgvector
                          │                 ── Redis 8 (sessions, pub/sub, broker DB 1)
                          │
                    Celery worker + beat    ── Resend (email)
                                            ── TMDB / JustWatch (watch data)
```

In production the API publishes only on `127.0.0.1:8000`; the host proxy is the
public entry point. Redis databases are split by convention: DB 0 for sessions,
CSRF and rate limits, DB 1 for the Celery broker.

## 2. Code map

| Path | Responsibility |
| --- | --- |
| `app/main.py` | Composition root: settings, lifespan resources, middleware, routers, SPA serving |
| `app/api/routers/` | Thin HTTP/WebSocket endpoints; request parsing and response schemas |
| `app/api/deps.py` | Authentication, viewer resolution, TMDB client, settings and DB dependencies |
| `app/services/` | Business logic and transactions: accounts, groups, lobbies, invites, email, watch data |
| `app/domain/lobby/` | Pure, immutable lobby state machine (`Game`) with no database or framework imports |
| `app/models/` | SQLAlchemy 2 models and table constraints |
| `app/schemas/` | Pydantic request/response contracts; the source of the OpenAPI document |
| `app/realtime/` | WebSocket endpoint and the Redis-backed lobby pub/sub hub |
| `app/tasks/` | Celery tasks for email, guest cleanup and watch-provider refresh |
| `app/clients/` | Outbound HTTP clients for Resend and TMDB |
| `app/core/` | Config, sessions, CSRF, rate limits, DB engine, errors, logging, security headers |
| `alembic/` | Versioned schema migrations; one head, checked in CI |
| `scripts/` | Operational entrypoints: API startup, ingest, embeddings, admin, backups |

Dependencies point inward: routers depend on services and schemas; services
depend on models, the lobby engine and clients. The lobby engine depends on
nothing but the standard library.

## 3. Request lifecycle

Middleware is registered in `app/main.py`. Starlette runs the last-added
middleware first, so a request passes through:

1. `RequestContextMiddleware` — request ID, structured access logging, timing.
2. `SecurityHeadersMiddleware` — CSP, `X-Frame-Options`, `Referrer-Policy`,
   Permissions-Policy; HSTS in production.
3. `TrustedHostMiddleware` — `WATCHLOG_ALLOWED_HOSTS`; skipped in tests.
4. `SessionMiddleware` — reads the session cookie from Redis, refreshes its TTL,
   and exposes `SessionData` on `request.state`.
5. `CSRFMiddleware` — for unsafe methods, checks the `X-CSRF-Token` header equals
   both the CSRF cookie and the session’s CSRF value, then validates `Origin`
   (falling back to `Referer`).
6. Router → dependencies → service → SQLAlchemy session.

A request-scoped `AsyncSession` comes from `app/core/db.py`
(`expire_on_commit=False`, `autoflush=False`). Services own commits; routers do
not. Lobby mutations additionally receive a session whose `db.info` carries the
pub/sub publisher, so state changes can be broadcast after the transaction.

All errors use one envelope:

```json
{"error": {"code": "invalid_request", "message": "The request body or parameters are invalid."}}
```

`AppError`, lobby-domain errors, validation errors, HTTP errors and unexpected
exceptions are mapped centrally in `app/core/errors.py`; unexpected exceptions
log with the request ID and return a generic 500. Rate-limit responses add
`Retry-After`.

## 4. Identity, sessions and authorisation

There are three session kinds in `SessionData`:

| Kind | Identity | Default TTL |
| --- | --- | --- |
| `member` | `user_id` | 14 days |
| `guest` | `guest_id` | 24 hours |
| `anonymous` | none; used to bootstrap CSRF | 1 hour |

Session IDs are random, stored server-side in Redis, and sent in an HttpOnly,
`SameSite=Lax` cookie. Production adds `Secure` and the `__Host-` prefix and
uses the `__Host-wl_session` name; the CSRF cookie stays readable by the SPA.
Login, registration and guest claim rotate the session ID. Password reset and
password change revoke every session for the user.

`Viewer` (`app/services/identity.py`) is exactly one of a member or a guest.
Anonymous callers can read a join preview but cannot join, vote or hold a seat.
`CurrentUser` requires a member session; `LobbyViewer` accepts either identity;
`VerifiedUser` additionally enforces the soft email gate used by group creation
and invite links.

A guest is a row in `guests` with an expiry. Active play extends the expiry.
When a guest registers or logs in, claim runs automatically:

- guest lobby participants are converted to member participants;
- if the member was already in the room, ready flags merge and the guest’s
  votes and pick move to the existing participant, with duplicates dropped;
- if the guest was host, the surviving participant becomes host;
- the guest row is marked claimed and never reused.

This is the invariant behind “claim keeps your votes, picks and host seat”.

## 5. Data model

| Table | Purpose |
| --- | --- |
| `users` | Accounts, email state, region, password hash, active flag |
| `guests` | Temporary identities with expiry and claim marker |
| `groups` | Clubs with name and description; the creator becomes an `admin` member |
| `group_memberships` | Membership and `admin`/`member` role |
| `group_movies` | Watchlist rows with status (`up_next`, `watched`) |
| `reviews` | One member score and optional comment per watchlist film |
| `movies` | Local TMDB catalogue, genres, credits, metadata, optional embeddings |
| `lobbies` | Room type, status, JSONB pool/finalists, host, winner, version |
| `lobby_participants` | Member or guest seat, display name, ready flag, host link |
| `lobby_votes` | One choice per participant per pool film |
| `lobby_picks` | One final-round pick per participant |
| `group_invites` | SHA-256 hashed invite tokens with expiry and revocation |
| `email_tokens` | SHA-256 hashed verification/reset/change tokens |
| `email_outbox` | Transactional email queue with status and retry metadata |
| `movie_watch_regions` | Availability snapshot per movie and region, TTL metadata |
| `movie_watch_providers` | Normalised offers per region/movie/type/provider |

Constraints carry important invariants: one active lobby per group, one seat per
member per lobby, unique invite token hashes, two-letter uppercase region codes,
valid lobby statuses and offer types. `movies.embeddings` exists because the
catalogue schema supports it, but retrieval/RAG is not part of the product.
Alembic is the only schema authority; `alembic check` fails CI on drift.

## 6. Lobby state machine

The domain model is a frozen `Game` dataclass with immutable transitions in
`app/domain/lobby/engine.py`. Services load a `Lobby`, build a `Game`, apply one
transition and persist the result. The UI never computes a vote, reveal or
winner.

```text
ready ──start──▶ playing ──last film / advance──▶ final_round ──finalize──▶ finished
                    │                               │
                    └── advance / next-round ───────┘
```

Rules:

- A room is `group` (members only) or `open` (guests allowed).
- The pool is 25 random non-adult films, excluding the group’s existing
  watchlist for group rooms, or an explicit pool for tests.
- Ready players are the players; unready members are removed on start. The host
  cannot leave.
- Each playing film receives one vote per player: `interested`, `watched` or
  `not_interested`. Votes stay hidden until everyone has voted.
- A unanimously `interested` film is added to the finalists, up to 10.
- `next-round` moves to the next film after a reveal; `advance` skips an
  unrevealed film. Reaching 10 finalists or exhausting the pool enters the final
  round; if no film qualified, the room finishes without a winner.
- In the final round each player picks one finalist. Picks stay hidden until all
  picks are in.
- `finalize` awards the winner to the most-picked finalist; ties break
  deterministically by the lower movie id. For group rooms the winner is written
  to the group watchlist.
- `start`, `advance`, `next-round`, `end` and `restart` are host-only.
  `finalize` is host-only until every pick is in, then any player may trigger it.
- `restart` creates a new lobby and emits a restart event; the old room stays
  finished.
- Every mutation increments `version`. REST state responses expose an `ETag` of
  `"v<version>"` and support `If-None-Match`.

Lobby writes take a row lock (`SELECT … FOR UPDATE`) and are serialised per
room. After commit, a `LobbyChanged` or `LobbyRestarted` event is published to
Redis; clients receive the full personalised state, not a patch.

## 7. Realtime

`/ws/lobby/<uuid>/` authenticates from the same session cookie, checks the
`Origin` header against trusted origins, and closes with:

| Code | Meaning |
| --- | --- |
| `4401` | No valid session |
| `4403` | Not a member / untrusted origin |
| `4404` | Lobby not found |
| `4000` | The viewer left |
| `4001` | A restart moved the room |

On connect and after every change the server sends `lobby.state` with the full
personalised state. The hub uses one Redis channel per lobby
(`watchlog:lobby:<uuid>`) so multiple API processes see the same events. The SPA
reconnects with backoff, ignores stale versions and falls back to
`GET /api/lobby/<uuid>/` when the socket is unavailable.

## 8. Email and account flows

Email is transactional, not fire-and-forget:

1. The service hashes the token, stores it in `email_tokens` and writes a row to
   `email_outbox` in the same database transaction.
2. Beat enqueues `watchlog.email.dispatch_outbox` every 5 seconds.
3. A worker claims rows, sends through Resend (or logs in development), and
   records `sent`/`failed` with attempts and backoff (up to 8 attempts, capped at
   one hour).

Tokens are single-use, SHA-256 hashed at rest, and replacing a token invalidates
the previous one for that purpose. TTLs: verification 24 h, password reset 1 h,
email change 24 h. Password reset and password change revoke all sessions.
Changing email writes the new address only after the new address confirms.
Account export is self-serve JSON; deletion is support-assisted for the first
release.

## 9. TMDB and watch availability

The API uses an async TMDB client; Celery tasks use a synchronous client. Watch
availability is a Postgres snapshot, never a live request from a list render:

- `movie_watch_regions` holds the JustWatch deep link, fetch time, last error and
  offer count per movie/region.
- `movie_watch_providers` holds normalised `flatrate`/`free`/`ads`/`rent`/`buy`
  offers with provider id, name, logo path and display priority.
- Cached data is fresh for 24 hours (`WATCHLOG_WATCH_PROVIDER_TTL_SECONDS`).
  Stale rows render immediately with `stale: true` and refresh in the background
  or on the next detail request.
- The film sheet refreshes on demand. Lobby finalists use cached rows only.
- Beat refreshes group-watchlist movies daily and prefetches active finalists
  every two minutes. `just watch-providers` backfills on demand.

TMDB metadata and JustWatch availability require visible attribution; removing
it can revoke API access. Availability is regional (`PL` by default) and can
change.

## 10. Background jobs

| Task | Schedule | Purpose |
| --- | --- | --- |
| `email.dispatch_outbox` | 5 s | Enqueue pending email rows |
| `email.cleanup_tokens` | hourly at :15 | Delete expired tokens |
| `email.cleanup_outbox` | daily 03:30 | Prune old sent/failed rows |
| `guests.cleanup_expired` | 5 min | Delete expired guests, transfer host or delete empty open rooms |
| `guests.cleanup_lobbies` | 15 min | Delete open rooms idle for 24 h |
| `watch.refresh_stale` | daily 04:00 | Refresh stale group-watchlist availability |
| `watch.prefetch_active_finalists` | 2 min | Warm availability for live final rounds |

Workers initialise their own settings, logging, Sentry and sync SQLAlchemy
engine per process. Results are ignored; state lives in Postgres.

## 11. Configuration and security

`Settings` is a Pydantic settings object with the `WATCHLOG_` prefix and
standard `POSTGRES_*` aliases. Production validation refuses the development
secret, requires a public URL and, when Resend is enabled, both `MAIL_FROM` and
an API key. Notable switches:

| Setting | Default | Effect |
| --- | --- | --- |
| `WATCHLOG_RATE_LIMIT_ENABLED` | `true` | Redis fixed-window limits per route |
| `WATCHLOG_REQUIRE_VERIFIED_EMAIL` | `true` | Soft gate on group creation/invites |
| `WATCHLOG_LEGACY_GROUP_JOIN_ENABLED` | `false` | Keeps the old UUID join endpoint off |
| `WATCHLOG_DOCS_ENABLED` | `true` | Serves `/api/docs` and `/api/openapi.json` |

Security controls: Argon2 password hashing, constant-time CSRF comparison,
session rotation on privilege changes, hashed invite and email tokens, rate
limits keyed on hashed identities, CSP/Permissions-Policy/HSTS headers, trusted
hosts, and an error envelope that never leaks exception text. Invite links are
valid for seven days; creating one revokes the group’s previous live link.

## 12. Testing strategy

- `pytest` creates `watchlog_test`, applies Alembic migrations once per session
  and truncates tables between tests. API tests use a real Postgres and Redis
  engine; only the TMDB client and external mailer are replaced.
- `MemorySessionStore` and `MemoryLobbyHub` replace Redis for API tests; the
  memory rate limiter replaces the Redis script.
- The lobby engine has its own pure unit tests and needs no fixtures.
- Celery tasks are tested by calling `.apply()` with a worker runtime pointed at
  the test database.
- Playwright flows in `frontend/` exercise the SPA against a running dev stack;
  they are intentionally separate from `just check`. The DB helpers refuse a
  non-local `WATCHLOG_URL` unless `WATCHLOG_ALLOW_REMOTE_VERIFY=1`.

## 13. Data operations

The app reads films from the local `movies` table, not live from TMDB. Search
and film detail stay fast, a TMDB outage does not empty the catalogue, and the
lobby pool is a plain ordered query. The cost is an explicit import step after a
fresh deploy.

```bash
just ingest --dry-run                 # parse the TMDB CSV without writing
just ingest --min-votes 50 --limit 50000
just watch-providers --scope popular --limit 500
just seed                             # development only
```

- `ingest_tmdb.py` reads the bundled-format TMDB CSV. The 582 MB file is not in
  the Docker build context, so upload it and mount it when importing on a server.
- `copy_movies.py` copies the catalogue from a legacy database; it is kept for
  migrations, not for normal deploys.
- `embed_movies.py` fills `movies.embeddings`. Retrieval is not part of this
  release, so importing without embeddings is supported.
- `backfill_watch_providers.py` warms availability snapshots; the daily task
  keeps them fresh afterwards.
- `seed_dev_data.py` creates demo users and a club. Never run it in production.

Backups, restore and provider backfill procedures live in
`docs/production-runbook.md`.

## 14. Scaling and failure behaviour

The API is stateless: sessions, CSRF state and rate-limit counters live in Redis;
lobbies and account data live in Postgres. Extra Uvicorn workers
(`WEB_CONCURRENCY`) or extra API containers are safe behind the proxy. WebSocket
clients do not need sticky sessions because every process subscribes to the
Redis lobby channel.

- **Lobby contention** is per room. Writes take a row lock, so fights are limited
  to players acting on the same room at the same time, which is the scale the
  product targets.
- **Redis loss** invalidates sessions and the rate-limit counters; clients
  re-authenticate. Postgres remains the source of truth. The hub reconnects its
  subscriptions on demand.
- **Celery loss** delays email and provider refresh. Email waits in
  `email_outbox`; stale watch rows still render with `stale: true`.
- **TMDB or Resend outage** degrades search, watch data or email, but not
  sign-in, groups or a running lobby.
- **Proxy misconfiguration** is the main deployment risk: without WebSocket
  upgrades the app falls back to REST; without `X-Forwarded-For` all users share
  the proxy’s rate-limit identity.

## 15. Decisions and trade-offs

| Decision | Why | Cost |
| --- | --- | --- |
| Server-side sessions in Redis | Instant revocation, rotation and per-device control without JWT blocklists | Redis is required for login; a flush signs everyone out |
| Guests as first-class identities | A room can start with only a display name; no throwaway accounts | Two identity paths, claim logic and expiry cleanup |
| Pure immutable lobby engine | The rules are deterministic and testable without a database | Explicit mapping between `Game` and ORM rows |
| Lobby snapshot plus normalised votes/picks | Fast state reload, simple versioning and an audit trail | Pool/finalists are JSONB, so membership is enforced in code |
| Full state over WebSocket | Reconnect-safe and avoids client-side patch bugs | More bytes per update than deltas |
| Redis pub/sub hub | Multiple API processes can serve the same room | No durable event log; clients refetch full state on reconnect |
| Transactional email outbox + Celery | Mail cannot be lost when a transaction commits | Delivery is eventual; worker and beat must be healthy |
| Opaque hashed tokens for email and invites | Revocable, single-use, no JWT secret sprawl | A database lookup per use and periodic cleanup |
| Soft email verification | People can play immediately; only group actions are gated | Unverified accounts remain usable and can host open rooms |
| Fixed-window Redis rate limits | One atomic Lua script, cheap and easy to reason about | Bursts at window boundaries; not a token bucket |
| One image for API, worker, beat and migrate | One build, one set of dependencies, one deploy artefact | Worker images carry web dependencies and vice versa |
| Async SQLAlchemy in the API, sync in Celery | Each runtime gets the natural driver model | Two engines, session factories and TMDB clients |
| Watch availability snapshots in Postgres | Fast lists and finalists, resilient to TMDB latency | Staleness and refresh jobs; availability can lag TMDB |
| Region on the user, `PL` by default | Simple product model and one cached region per user | No per-request region switch or travel mode |
| Alembic migration as a deploy step | Startup is predictable; no racing migrations between replicas | A deploy must run migrations before the new code |
| FastAPI serves the built SPA | Same origin for cookies, CSRF and WebSockets | Frontend build is coupled to the backend image |
| Real Postgres and Redis in tests | Catches constraint, transaction and serialization bugs | Slower suite; services must be running |
| Legacy UUID join kept behind a flag | Existing tests and old links remain diagnosable | A disabled attack surface that must stay disabled |
| Rightmost `X-Forwarded-For` hop | A client cannot pre-seed the address the proxy saw | Assumes one trusted proxy and a loopback-only API |

## 16. Known limitations

- Notifications, scheduling, RAG and an admin UI are out of scope for this
  release.
- Account deletion is support-assisted; self-serve export is available.
- Any group member can revoke the group’s invite link. Admin-only revocation is
  an open product decision.
- The frontend has end-to-end flows but no unit-test layer; pure client helpers
  are covered indirectly.
- TMDB metadata is `en-US`, the catalogue is English, and the default watch
  region is `PL`.
- Rate limiting is fixed-window; there is no token bucket or global concurrency
  limit.
- The deployment is a single VPS with one Postgres and one Redis. There is no
  high-availability setup.
- WebSocket delivery is best-effort; the REST state endpoint is the recovery
  path, not an event replay log.

## 17. Extending the backend

For a new endpoint: add or extend a Pydantic schema, put the transaction in a
service, add a thin router, regenerate `docs/openapi.json` with `just openapi`,
then regenerate the frontend types. For a schema change: edit the model, run
`just revision "<message>"`, review the migration, apply it, and run
`alembic check`. For a new background job: add the task module to
`TASK_MODULES`, register a schedule in `app/celery_app.py`, and test it with
`.apply()`.
