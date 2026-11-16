# watchlog API handover

Status: parity contract frozen for the frontend-wiring project. Changes from
here should be additive; a breaking change needs a new path or a versioned
contract.

## Base URLs and artifacts

- Development API: `http://localhost:8001`
- OpenAPI JSON: `http://localhost:8001/api/openapi.json`
- Swagger UI: `http://localhost:8001/api/docs` when docs are enabled
- Committed schema: [openapi.json](openapi.json)
- Lobby protocol details: [lobby-api.md](lobby-api.md)

Start the API with `just api-db`, `just api-migrate`, `just api`. Run the checks
with `just api-check`.

## Authentication and sessions

1. Fetch `GET /api/auth/csrf`. It returns `{"csrfToken": "..."}` and sets:
   - `wl_session` (HttpOnly) for an anonymous session
   - `wl_csrf` (readable) for the double-submit token
2. Send `X-CSRF-Token: <csrfToken>` on every unsafe request (`POST`, `PUT`,
   `PATCH`, `DELETE`). The header must match both the `wl_csrf` cookie and the
   token stored in the server session.
3. `POST /api/auth/register` or `POST /api/auth/login` rotates the session ID and
   the CSRF token. Read the new `wl_csrf` cookie after the response; do not keep
   using the pre-login token.
4. `POST /api/auth/logout` deletes the server-side session, clears both cookies
   and returns `204`.
5. `GET /api/me` returns the member plus stats:

```json
{
  "viewer": {
    "mode": "member",
    "id": 12,
    "username": "alice",
    "initials": "AL",
    "color": "#d09a83"
  },
  "stats": { "titles_watched": 3, "average_score": 8.1 }
}
```

Cookie names differ by environment:

| Environment | Session cookie | CSRF cookie |
|---|---|---|
| dev/test | `wl_session` | `wl_csrf` |
| prod | `__Host-wl_session` | `wl_csrf` |

The session cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` in production.
Sessions are opaque server-side records in Redis; no JWT is used. `Origin` or
`Referer` is also checked on unsafe requests.

`GET /api/lobby/csrf/` remains as an alias of `GET /api/auth/csrf` for older
clients. The alias is intentionally hidden from OpenAPI.

## Endpoints

### Auth and profile

| Method | Path | Notes |
|---|---|---|
| GET | `/api/auth/csrf` | Bootstrap token and session |
| POST | `/api/auth/register` | `{username, password}`, returns `201 {viewer}` |
| POST | `/api/auth/login` | `{username, password}`, returns `{viewer}` |
| POST | `/api/auth/logout` | `204` |
| GET | `/api/me` | `{viewer, stats}` |

### Movies

| Method | Path | Notes |
|---|---|---|
| GET | `/api/movies/search?q=` | Auth required; returns `{movies: [...]}` with `tmdb_id` and local `movie_id` when known |
| GET | `/api/movies/{movie_id}` | Local catalog detail; does not expose embeddings |

### Groups

| Method | Path | Notes |
|---|---|---|
| GET | `/api/groups` | Viewer's groups with members and counts |
| POST | `/api/groups` | `{name, description?}`, returns `201` group detail |
| GET | `/api/groups/{group_id}` | Group detail; members only |
| GET | `/api/groups/{group_id}/watchlist` | `{films: [...]}` with club and viewer scores |
| POST | `/api/groups/{group_id}/films` | `{tmdb_id, media_type}`, idempotent |
| PATCH | `/api/groups/{group_id}/films/{film_id}` | `{status: "up_next"|"watched"}` |
| PUT | `/api/groups/{group_id}/films/{film_id}/score` | `{score: 1..10}` |
| GET | `/api/groups/{group_id}/films/{film_id}/scores` | Per-member scores |
| GET | `/api/groups/{group_id}/stats` | Counts, average and per-member stats |
| GET | `/api/groups/{group_id}/invite` | `{invite_link}`; group UUID stays in the URL |
| POST | `/api/groups/{group_id}/members` | Join by UUID, idempotent |
| DELETE | `/api/groups/{group_id}/members/me` | Leave, `204` |
| POST | `/api/groups/{group_id}/lobbies` | Create a group lobby |

### Lobby

| Method | Path | Notes |
|---|---|---|
| GET | `/api/lobby/csrf/` | CSRF alias |
| GET | `/api/lobby/active/` | `{active: summary | null}` |
| POST | `/api/lobby/` | Optional `{group_uuid}`; `201` state |
| GET | `/api/lobby/{uuid}/preview/` | `{preview}`; group rooms are member-only |
| POST | `/api/lobby/{uuid}/join/` | Join an open room |
| GET | `/api/lobby/{uuid}/` | State; supports `If-None-Match` and returns `304` |
| POST | `/api/lobby/{uuid}/{action}/` | `ready`, `unready`, `start`, `vote`, `pick`, `advance`, `next-round`, `finalize`, `leave`, `end`, `restart` |
| WS | `/ws/lobby/{uuid}/` | See [lobby-api.md](lobby-api.md) |

## Response conventions

- JSON is snake_case, except the existing `csrfToken` field.
- Errors are always:

```json
{"error": {"code": "not_found", "message": "..."}}
```

- Lobby state responses are wrapped in `{"lobby": ...}`, previews in
  `{"preview": ...}`, active summaries in `{"active": ...}`.
- State responses carry `ETag: "v<version>"` and `Cache-Control: private,
  no-cache` with `Vary: Cookie`. Send `If-None-Match` to receive `304`.
- Lobby action responses are `200`, create/restart `201`, leave `204`.
- Scores are validated to 1–10 and stored to one decimal.

### Error codes

| Code | HTTP | Meaning |
|---|---|---|
| `unauthorized` | 401 | No member session |
| `invalid_credentials` | 401 | Bad login |
| `not_a_member` | 403 | Group or private room access denied |
| `not_host` | 403 | Host-only action |
| `csrf_failed` | 403 | Missing or mismatched CSRF/Origin |
| `not_found` | 404 | Missing group, film, movie or lobby |
| `method_not_allowed` | 405 | Wrong HTTP method |
| `not_joinable` | 409 | Room closed, started or group-only |
| `invalid_state` | 409 | Action not valid in the current phase |
| `already_active` | 409 | Group already has an active lobby |
| `username_taken` | 409 | Registration conflict |
| `invalid_choice` | 400 | Bad movie id or vote choice |
| `invalid_pool` | 400 | Invalid explicit lobby pool |
| `invalid_action` | 400 | Unknown action or malformed JSON |
| `invalid_request` | 422 | Body/query validation failed |
| `tmdb_unavailable` | 502 | TMDB request failed |
| `server_error` | 500 | Unexpected failure |

## Participant contract

Lobby state uses stable string participant IDs, not member IDs:

```json
{
  "viewer_id": "9f1d...",
  "host_id": "9f1d...",
  "players": [
    {
      "id": "9f1d...",
      "name": "Maya Chen",
      "initials": "MC",
      "color": "#9bb39a",
      "is_host": true,
      "is_guest": false,
      "is_ready": true
    }
  ],
  "ballot": [
    { "participant_id": "9f1d...", "name": "Maya Chen", "choice": "interested" }
  ]
}
```

`is_guest` is present now even though guest sessions are not enabled yet. Group
films use the group-film `id` for scoring and status changes; the nested
`movie.id` is the catalog ID.

## Realtime

Connect to `ws://<host>/ws/lobby/<uuid>/` with the session cookie. The handshake
also validates `Origin`. The server sends the full personalized state on connect,
then `lobby.state` after each committed change. See
[lobby-api.md](lobby-api.md) for message shapes, close codes and the action
list.

Client guidance:

- Use exponential backoff and reconnect on `4401` after refreshing the session.
- Reconnect with the REST state endpoint if the socket is unavailable.
- Treat the latest `lobby.state` as complete; there are no deltas.
- Deduplicate by `version` if reconnect overlap occurs.
- A `lobby.removed` means the member is no longer in the room.
- A `lobby.restarted` carries `new_lobby_uuid`; connect to the new room.

## Intentional differences from the Django app

These are the only behavioral/contract differences to account for while wiring
the frontend:

1. Participant IDs are UUID strings, and players include `id`, `name`,
   `initials`, `color`, `is_guest`; the old integer `user_id`/`username` fields
   are gone.
2. Session and CSRF cookie names and the CSRF header are new (`wl_session`,
   `wl_csrf`, `X-CSRF-Token`).
3. `/api/me` replaces the HTML profile page and includes `stats`.
4. Movie search uses `tmdb_id` plus a local `movie_id`; the old `id` field was
   the TMDB id.
5. Adding a film returns a `GroupFilm` payload, not a message string; scoring and
   status use the group-film id.
6. Group detail and watchlist are separate endpoints.
7. The watched rule is fixed: every current member must score (or a member
   explicitly marks watched). The old "two scores" rule is gone.
8. Film writes require group membership; the old add-movie endpoint did not
   check it.
9. Scores are range-validated to 1–10.
10. `/health` is `/health` (no trailing slash); `/ready` is new.
11. API errors use the JSON envelope and documented status codes; old HTML
    redirects and pages are gone.
12. Group invite links keep the group UUID but no longer use a trailing slash.
13. Group lobby creation is also available at
    `POST /api/groups/{group_id}/lobbies`.

## Development data

```bash
uv run python scripts/seed_dev_data.py
```

Creates `alice`, `bob`, `carol` with password `correct horse` and the
`Friday Film Club` group with films and scores.

The catalog scripts target `watchlog_v2`:

```bash
uv run python scripts/copy_movies.py --truncate
uv run python scripts/ingest_tmdb.py --dry-run
uv run python scripts/embed_movies.py --verify
```

API tests use a separate `watchlog_test` database and never touch the dev
database.

## Contract freeze

The path set and response fields are asserted in
`tests/unit/test_contract.py`. The OpenAPI snapshot is regenerated with:

```bash
just api-openapi
```

Additive fields and new paths are fine. Removing or renaming a field, changing
an error code, or changing a lobby state transition is a breaking change and
needs a versioned path or an explicit migration of the frontend.
