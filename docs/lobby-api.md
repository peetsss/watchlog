# Lobby API and WebSocket protocol

## Authentication

HTTP endpoints use the `wl_session` cookie (or `__Host-wl_session` in
production). Mutating requests must send the CSRF token in `X-CSRF-Token`; get it
from `GET /api/auth/csrf`. The older alias `GET /api/lobby/csrf/` is kept.

Cookies:

- `wl_session` — HttpOnly, SameSite=Lax, Secure in production
- `wl_csrf` — readable double-submit token

`Origin` (or `Referer`) is checked on unsafe requests. Sessions are server-side
records in Redis. WebSocket connections use the same session cookie and validate
`Origin` during the handshake.

## HTTP endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/lobby/csrf/` | Return `{"csrfToken": "..."}` and set the cookies |
| GET | `/api/lobby/active/` | Current member's active lobby summary or `null` |
| POST | `/api/lobby/` | Create a lobby. Optional body: `{"group_uuid": "..."}` |
| GET | `/api/lobby/<uuid>/preview/` | Join preview |
| POST | `/api/lobby/<uuid>/join/` | Join an open lobby |
| GET | `/api/lobby/<uuid>/` | Full personalized lobby state |
| POST | `/api/lobby/<uuid>/ready/` | Mark ready |
| POST | `/api/lobby/<uuid>/unready/` | Remove ready |
| POST | `/api/lobby/<uuid>/start/` | Host starts |
| POST | `/api/lobby/<uuid>/vote/` | Body: `{"movie_id": 1, "choice": "interested"}` |
| POST | `/api/lobby/<uuid>/pick/` | Body: `{"movie_id": 1}` |
| POST | `/api/lobby/<uuid>/advance/` | Host skips the current film before reveal |
| POST | `/api/lobby/<uuid>/next-round/` | Any member advances after a reveal |
| POST | `/api/lobby/<uuid>/finalize/` | Host, or any member after all picks are in |
| POST | `/api/lobby/<uuid>/leave/` | Leave; returns `204` |
| POST | `/api/lobby/<uuid>/end/` | Host ends the night |
| POST | `/api/lobby/<uuid>/restart/` | Host creates a fresh lobby after finishing |

Vote choices are `interested`, `watched` and `not_interested`.

Host start uses the host plus every member currently marked ready. Members who
are not ready are removed from the room, so an absent member cannot block the
night.

State responses are wrapped as `{"lobby": {...}}`; previews as
`{"preview": {...}}`; the active summary as `{"active": {...} | null}`.
`POST /api/lobby/` returns `201`. Actions return `200`, except `restart` (`201`,
with `previous_uuid` and the new state) and `leave` (`204`).

The state response includes `ETag: "v<version>"`. Send `If-None-Match` to receive
`304` while nothing has changed.

Group rooms are member-only. A non-member gets `403 not_a_member` from the
preview and state endpoints and `409 not_joinable` from join.

## Error shape

```json
{"error": {"code": "invalid_state", "message": "..."}}
```

| Code | HTTP |
|---|---|
| `unauthorized` | 401 |
| `not_found` | 404 |
| `not_a_member` | 403 |
| `not_host` | 403 |
| `csrf_failed` | 403 |
| `not_joinable` | 409 |
| `invalid_state` | 409 |
| `already_active` | 409 |
| `invalid_choice` | 400 |
| `invalid_pool` | 400 |
| `invalid_action` | 400 |
| `tmdb_unavailable` | 502 |

## State fields

The personalized state contains:

- lobby metadata: `uuid`, `type`, `status`, `version`, `host_id`, group fields,
  `created_at`, `started_at`, `finished_at`
- viewer fields: `viewer_id`, `viewer_is_host`, `viewer_ready`, `viewer_vote`,
  `viewer_pick`
- players: `players`, `player_count`, `ready_count`
- progress: `pool_size`, `pool_index`, `round_number`, `remaining_count`
- film and reveal: `current_movie`, `submitted_count`, `revealed`, `vote_tally`,
  `ballot`
- final round: `finalists`, `picks_revealed`, `winner`
- `capabilities` booleans for the UI

Participant identity is a stable string ID:

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

`is_guest` is always present; guest sessions are not enabled yet.

Privacy rules:

- `vote_tally` and `ballot` are `null`/empty until `revealed` is true.
- `finalists[].pick_count` is `null` until `picks_revealed` is true.
- `winner` is only set after the lobby is `finished`.

## WebSocket protocol

Connect to `ws://<host>/ws/lobby/<uuid>/` with the session cookie. The handshake
validates `Origin`. On success the server sends:

```json
{"type": "lobby.state", "lobby": {...}}
```

Client actions:

```json
{"action": "vote", "movie_id": 1, "choice": "interested"}
{"action": "pick", "movie_id": 1}
{"action": "advance"}
{"action": "next_round"}
{"action": "ready"}
{"action": "unready"}
{"action": "start"}
{"action": "finalize"}
{"action": "end"}
{"action": "leave"}
{"action": "restart"}
{"action": "state.get"}
```

Server messages:

- `lobby.state` — personalized state after every change or a `state.get`
- `lobby.error` — `{"code": "...", "message": "..."}`; the socket stays open
- `lobby.left` — the socket left the lobby, then closes `4000`
- `lobby.removed` — the member is no longer in the room, then closes `4403`
- `lobby.restarted` — the host created a new lobby; connect to `new_lobby_uuid`

Close codes: `4401` unauthorized, `4403` forbidden, `4404` not found, `4000`
left, `4001` restarted.

Reconnect with exponential backoff and use the state from the first message; the
server sends the full state on connect and never requires a client-side version
cursor. If the socket is unavailable, `GET /api/lobby/<uuid>/` is the fallback.
Deduplicate by `version` if a reconnect overlaps a broadcast.
