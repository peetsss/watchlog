# watchlog frontend

The React UI for watchlog. It is wired to the FastAPI API and is the app UI;
Django is no longer used.

## Run it

From the repository root, start the API, Postgres and Redis:

```bash
just dev
```

Then run the frontend:

```bash
cd frontend
npm install
npm run dev
```

The API is expected on http://localhost:8001. Vite proxies `/api`, `/health`
and `/ws` to it.

Seed members (from the repository root, after migrations):

```bash
uv run python scripts/seed_dev_data.py
```

The seed creates `alice`, `bob`, `carol`, all with `correct horse`.

## API types

Types are generated from the frozen contract:

```bash
npm run api:types
```

This regenerates `src/lib/api-types.ts` from `../docs/openapi.json`.
`src/lib/api.ts` wraps `openapi-fetch` with cookies, CSRF and the API error
envelope; `src/lib/query.ts` holds the React Query client.

## Routes

| Path | What it is |
|---|---|
| `/auth` | Sign in / create account |
| `/` | Member home, live room, watchlist and watched log |
| `/groups` | Groups and group creation |
| `/groups/:id` | Watchlist, scores, invite and start-night |
| `/search` | Add films to a group watchlist |
| `/lobby/:uuid` | Waiting room, voting, final round and winner |
| `/join/:uuid` | Open-lobby invite preview and join |
| `/join/group/:uuid` | Group invite preview and join |

Members only. Guest hosting, guest join, account claim and keep-the-crew are
deferred until the guest backend exists.

## Verification

Start the API and Vite first. The scripts use the installed Chrome through
`playwright-core`; set `CHROME_PATH` if it is not `/usr/bin/google-chrome`.

```bash
npm run verify        # two-user group night: ready, vote, final, winner, restart
npm run verify:auth   # redirect, login, register, logout, return URL, mobile
npm run verify:edges  # open invite/join, private room, 404, search, mobile dialog
npm run verify:detail # film sheet: deep link, focus, mobile layout, winner state
npm run verify:all    # all of the above
```

The flow/detail scripts shorten a test lobby's pool through the dev Postgres
container so the full night can be played quickly; they delete the lobbies they
create. `verify:flow` also clears existing lobbies before it starts, so do not
run it while someone is using a dev room. Screenshots go to
`/tmp/watchlog-verify` by default; override with `WATCHLOG_OUT`.

Film search needs `TMDB_API_KEY`. Without it the Search page shows its offline
state; the verification scripts accept either the offline state or live results.
