# watchlog prototype

A clickable, mock-data React prototype for the lobby-first watchlog app. It exists to validate the warm film club direction and the full movie-night flow before the Django API is wired.

The Django project in the repository remains the real app. This folder is a standalone Vite app and does not touch the database.

## Run it

```bash
cd prototype
npm install
npm run dev
```

Open http://localhost:5173.

```bash
npm run build      # typecheck + production build
npm run typecheck
npm run verify
npm run verify:edges
npm run verify:detail
npm run verify:guest
```

## Frontend stack

- **React 19 + Vite + TypeScript** for the member and guest shell.
- **Base UI** (`@base-ui/react`) for accessible dialogs and sheets; the visual layer stays custom CSS.
- **Sonner** for toasts, rendered through a headless custom toast so the cream pill stays part of the film-club design.
- **React Router**, **Lucide** icons and **Fontsource** type.
- No component kit. The warm film-club tokens in `src/styles.css` are the design system.

## What is in this slice

- **Member shell** — desktop sidebar, mobile top bar and bottom nav, user identity, active-room shortcut, sign-out, offline banner.
- **Guest shell** — a public Home, guest name gate for host/join, guest tags in the room, and a member-only groups guard. No account is needed to play.
- **Home / hub** — a tonight board with the live room at its centre, then the log: the club's recent nights with their notes and scores.
- **Group watchlist** — `/groups/:id` with poster-led films, up-next/watched status, the club average, every member's score, sort and filter, plus score and mark-watched actions.
- **Groups** — group list, member avatars, film counts, last night, create a group, start a group room, and open each watchlist.
- **Search** — a small mock catalogue, genre filters, a target-group selector, and add-to-watchlist that updates the group's count, watchlist and poster stack.
- **Lobby room** — full-screen waiting room, a one-film-at-a-time reel for voting (drag it after the reveal), then the premiere: shortlist line-up, lock-in, roll the pick and the winning film. Guests can host or join an open room with just a display name.
- **Guest account gate** — a guest is prompted only when they try to keep the crew/save the night or leave the room. Dismissing cancels the action; creating an account claims the guest name and unlocks groups.
- **Film detail sheet** — read the full synopsis, credits, club context and current room status without leaving the live room. Desktop opens a right-side panel; phone opens a bottom sheet you can swipe down from the film hero. It can cast your vote, lock your final pick, or add the winner to the watchlist. The sheet is shareable via `?film=`, and browser back closes it.
- **Open and group lobbies** — open rooms are link-only and never listed; group rooms explain that the whole group is already in the room.
- **Invite preview** — `/join/7f3k2` with host, room status, players, privacy, a guest-name field, and a real join → waiting-room path. Invalid codes have their own state.
- **States** — empty shortlist, room closed, 404, copy feedback, toasts, dialogs, guest auto-start simulation, keyboard voting, reduced-motion support.

## Demo routes

| Route | What it shows |
|---|---|
| `/` | Tonight board and the log |
| `/groups` | Groups list and create group |
| `/groups/friday` | Friday Film Club watchlist and scores |
| `/groups/slow-burn` | The Slow Burn Society watchlist |
| `/groups/letterboxd` | Letterboxd Refugees watchlist |
| `/search?group=friday` | Mock film search with a group preselected |
| `/join/7f3k2` | Valid open-lobby invite |
| `/join/wrong` | Expired invite |
| `/lobby/friday?stage=waiting` | Waiting room |
| `/lobby/friday?stage=playing` | The reel: one film at a time |
| `/lobby/friday?stage=playing&film=past-lives` | The reel with the film detail sheet open |
| `/lobby/friday?stage=final` | The premiere: shortlist line-up |
| `/lobby/friday?stage=final&film=grand-budapest` | The premiere with a film detail sheet open |
| `/lobby/friday?stage=winner` | The premiere: winning film |
| `/lobby/friday?stage=winner&film=past-lives` | Winner with the film detail sheet open |
| `/lobby/nope` | Closed room |

The `stage` query is a review aid only. It seeds the prototype state once and is then removed from the URL. The real room is `/lobby/:uuid` and would fetch its state from the server.

The demo invite code is `7f3k2`.

To review the guest flow, use **Sign out** in the sidebar (or the icon in the mobile top bar), then start or join an open room. Opening `/join/7f3k2` in a new tab starts directly in the guest invite state.

## How the mock works

- The lobby mirrors the current Django engine: every player votes on each film, a unanimous **I'm in** puts it on the shortlist, then every player picks one finalist.
- Three films are in the prototype pool: _Past Lives_, _Oppenheimer_, and _The Grand Budapest Hotel_. Other players are deterministic: Oppenheimer is the skip (3 of 5 in), the other two are unanimous.
- Your final pick decides the room: _Past Lives_ wins 3–2 if you pick it; _The Grand Budapest Hotel_ wins 3–2 if you pick that. A single finalist or an empty shortlist is handled.
- Lobby state lives in React and sessionStorage. Refreshing the same tab keeps the room; a new tab starts clean. This is deliberate for a mock, not the server contract.
- The winning film can be added to the group watchlist. That updates the in-memory group (film count, watchlist and poster stack).
- Keeping the crew from an open-lobby winner creates a group with the room's players and the winning film on its watchlist.
- Viewer identity lives in sessionStorage as `member`, `guest` or `anonymous`. Opening a direct `/join/` link without a stored viewer starts as an anonymous guest, not as the demo member. Signing out from the sidebar returns to the public Home.
- The account gate is a prototype-only simulation: it stores the chosen name and unlocks the member view, but no real account or email is created.
- Group films carry a status (`Up next` or `Watched`), the member who added them, the date, and one score per member. The group page derives the club average from the scores that exist; the card shows the average, the score spread and your own score, and the film sheet lists every member's score.
- Marking a film watched asks for your score and moves it into the watched list. Adding from Search drops the film at the top of the watchlist as `Up next`.
- The film detail sheet uses the longer descriptions and taglines already present in the Django movie data; writers, cast, and language are filled in for the prototype. It fetches nothing at runtime.
- Opening the sheet adds `?film=<id>` to the room URL, so it can be shared and browser back closes it. When the room advances while the sheet is open, the sheet's status changes to “Not in this room” rather than offering a stale vote.

## Verification

Start the dev server, then in another terminal:

```bash
npm run verify        # full host flow: hub → waiting → 3 films → premiere → winner → home
npm run verify:edges  # open lobby, keep-the-crew, keyboard voting, empty final, 404, mobile targets
npm run verify:detail # detail sheet: read, vote, pick, add, deep link, back, refresh, mobile sheet
```

These use `playwright-core` with the installed Chrome. Screenshots are written to `/tmp/watchlog-prototype` by default; override with `WATCHLOG_OUT`. If Chrome is not at `/usr/bin/google-chrome`, set `CHROME_PATH`.

Verified at 1440×1000 and 390×844, including no horizontal overflow, fixed mobile action bars, dialog Escape, touch targets, and the full click-through flow.

## Not in this slice

- Real API, authentication, WebSockets, or persistence.
- Profile, comments, notifications, and review threads. The watchlist has group scores and a score action, not written reviews.
- Public lobby discovery, chat, moderation, reporting.
- Where-to-watch availability, full filmographies, or a public movie catalogue page. Film details live in the room sheet and the group watchlist sheet.
- The deferred rules: host start-now / remove player / end night, pool safety filters, and a disclosed tie-break. The prototype mirrors the current voting rules but visualises an explicit host **Start the night** once everyone is ready; the current engine auto-starts. That explicit start is a proposed control and needs a rules decision before the API is wired.
- Group lobbies auto-include every group member, matching the current engine.
- The legacy Django pages are not migrated or restyled here.

## Next step

Wire the same screens to Django Ninja endpoints and Channels, keeping Django for auth/admin. The lobby state payload should include players, ready state, current film, progress, shortlist, pick counts, winner, `last_result`, and a monotonically increasing `version` so the client can ignore stale socket messages. Fetch film detail on demand from `GET /api/movies/:id` and combine it with the local room status; do not put the full credits payload in every lobby state message.

## Assets

Poster and backdrop images are from TMDB and are used here only as prototype content. Attribution: this product uses the TMDB API but is not endorsed or certified by TMDB.
