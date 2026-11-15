# watchlog — design notes

The working design system for the warm film club direction. This is the reference for the React prototype and for the Django-backed app when the shell moves over.

## Intent

- **Lobby first.** The home screen answers “what are we watching tonight?”, not “search for a film”.
- **A club, not a streaming service.** Warm charcoal, cream, amber, one display serif, poster-led layouts. No gradients for decoration, no carousel walls, no dashboard grid.
- **Quiet shell, energetic room.** The hub and watchlists are calm. The live room uses backdrop imagery, larger type, and motion because it is a shared moment.
- **Show the cause.** Every vote reveals its outcome; every add names the group; every finished night leaves a visible trace.
- **One primary action per surface.** Start the room, ready up, vote, pick, add to watchlist.

## Colour roles

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0f1012` | App background |
| `--bg-deep` | `#0b0c0e` | Reserved for deeper wells |
| `--surface` | `#17181b` | Cards, panels, dialogs |
| `--surface-2` | `#1d1e22` | Hover, secondary buttons |
| `--surface-3` | `#25262a` | Chips, tracks, pressed states |
| `--text` | `#f4efe6` | Primary text |
| `--text-soft` | `#ded7cc` | Body copy on dark imagery |
| `--muted` | `#aaa49c` | Secondary copy |
| `--muted-2` | `#8d8880` | Micro-labels, timestamps |
| `--amber` | `#e7b45a` | Primary action, live, winner, “in” |
| `--amber-strong` | `#f0c06b` | Primary hover |
| `--amber-ink` | `#1a1305` | Text on solid amber |
| `--sage` | `#9bb39a` | Ready, added, positive secondary |
| `--rose` | `#d09a83` | Skipped, warnings, tie note |
| `--border` | `rgba(244,239,230,.11)` | Default hairline |
| `--border-strong` | `rgba(244,239,230,.19)` | Inputs, focused cards |

Rules:

- Amber is the only action accent. Red is not a general accent; rose is used for skipped / warning copy.
- Borders and tone shifts carry hierarchy. Shadows are reserved for floating layers (dialogs, vote panel, posters).
- Do not put light text on amber; use `--amber-ink`.

## Typography

- **Display:** Instrument Serif 400, including italic. Used for the wordmark, page titles, film titles, winner titles, and big numbers. Letter-spacing `-0.02em` to `-0.03em`, line-height `0.9–1.0`.
- **UI:** Inter Variable. Used for navigation, labels, buttons, metadata, body copy.
- **Micro-labels:** 9–11px, uppercase, `0.12–0.18em` tracking, `--muted-2`. Keep them short.
- **Body:** 13–15px; lobby synopsis 14px; hero lede 16.5px.
- **Eyebrow pattern:** a small uppercase label above a display title, optionally with a live pill or section kicker.

Suggested scale:

| Role | Size |
|---|---|
| Hero title | `clamp(40px, 4.9vw, 68px)` |
| Page title | `clamp(48px, 5.6vw, 72px)` |
| Room title | `clamp(48px, 5.6vw, 76px)` |
| Winner title | `clamp(56px, 7vw, 104px)` |
| Section title | 33px |
| Card title | 24–31px |
| Body | 13–15px |
| Micro label | 9–11px |

## Space and shape

- 8px base rhythm. Common gaps: 8, 12, 16, 20, 24, 32, 40, 48, 56, 64.
- Page padding: 48px desktop, 28px tablet, 20px phone.
- Content width: 1240px for the shell, 1180px for rooms, 1120px for the invite page.
- Radii: 8px controls, 10–12px inputs and rows, 14–16px cards and dialogs, 999px pills. Do not round everything.
- Borders: 1px. Dashed borders only for empty states and secondary notes.
- Touch targets: 44px minimum on mobile. Icon-only controls get a 44px box even when the glyph is 16–18px.

## Core components

- **Button:** primary (solid amber), secondary (surface 2 + border), ghost (transparent), quiet, danger. Sizes 38/44/52; 44 on mobile.
- **Card:** surface, 1px border, 14px radius, optional poster stack. Hover is a border shift plus a 2px lift, never a shadow bloom.
- **PosterStack:** three overlapping 2:3 posters, slight rotation, used as a group signature. One poster works; zero shows a dashed film placeholder.
- **Avatar / AvatarStack:** initials on warm pastel fills with dark text. Stack overlaps by 8px with a 2px background ring. Always labelled as a group when used as a cluster.
- **Dialog:** Base UI dialog, blurred overlay, 560px max, display title, description, close, sticky footer. Mobile becomes a bottom sheet with a sticky footer.
- **Toast:** cream pill on dark, dark check mark, bottom centre, `role="status"`. On mobile it sits above the bottom nav.
- **Empty state:** dashed outline, 52px icon well, display heading, one sentence, one action. Use for empty final, closed room, 404, no results.
- **Live pill:** amber dot + uppercase “Live”, only for a room in progress.
- **Rating chip:** amber outline + star; label includes “out of 10” for assistive tech.
- **Score block:** the club average in display serif, the number of scores, a 1–10 spread of member dots, and your own score. The film sheet expands it into one bar per member. Use it on group watchlists; never reduce the group score to a small corner badge.

## Screen recipes

### Hub

- One continuous tonight board: date, display question, one-line lede and two actions on the left; a live room panel on the right.
- Panel states: active room → last night → idle club snapshot. The active panel carries the room's stage, players, progress and a single rejoin action. The idle panel shows the club name, member faces, the up-next film beside its poster stack, the last night and its club score, then the start and watchlist actions.
- Board foot: next night and a quiet link to the crews.
- Under it: the log. The latest night is a feature — poster, group/date, title, film metadata, one-sentence note, member score chips and the club score with its spread track. Two older nights sit beside it as a compact archive; every entry opens the night.
- The log score is the same club average and score count as the watchlist. It is not a separate night rating.
- On tablet the feature takes the full width and the archive becomes two columns; on phone everything stacks and the feature tightens to poster + copy, with the revisit CTA reduced to its arrow.

### Group watchlist

- Header: breadcrumb, group title, description, members, then Invite, Add a film and Start a night.
- Stats: films, up next, watched, and the club average with the number of scores behind it.
- Toolbar: All / Up next / Watched, search, and a sort for recently added, highest score or title.
- Cards: poster with status, title and meta, then a score block — the large club average, the number of scores, a score spread of member dots and your own score — then who added it.
- Clicking a card opens the film sheet: club average, every member's score, story and credits; actions are Mark watched or Add/Update your score.
- Scores are per member, one each. Marking a film watched asks for your score and moves it into the watched list.
- Empty watchlist and no-results states, long titles and a many-film list are part of the screen.

### Waiting room

- Full-screen room. Top chrome: wordmark, room name, stage, leave.
- Left: live eyebrow, display “The room is filling up.”, lede, invite link or private note, one-line rules.
- Right: players panel with host, you, ready states, and a sentence naming who is still deciding.
- Bottom: ready dots + primary action. Host starts when everyone is ready; guests see “Maya is starting…” and auto-start is simulated. The current Django engine auto-starts on all-ready; the explicit host action is a proposed control.
- Desktop centres the pair between the chrome and the action bar. Phone fixes the action bar to the bottom and scrolls the roster above it.

### Voting room — the reel

- Full-screen backdrop of the current film; one film card centred, the previous and next cards peeking at the edges.
- The current card: poster with an info button, title, meta, and an About link. The deck slides as the room moves to the next film.
- Panel below: “Your call”, three choices (I'm in / Seen it / Not for me) with 1/2/3 key hints; votes reveal together.
- After a vote: waiting stamp on the poster; after the reveal: an outcome stamp, the room's ballot and Next film. The last film leads to the premiere.
- After the reveal, the deck itself is draggable: pull it left to advance, flick it with velocity, or drag right to peek and resist. The Next button remains the accessible path.
- Phone keeps the card at 250px and the panel in thumb reach; the page scrolls if the deck and panel need it.

### Final — the premiere

- Header: “Two films. One stage.” with one sentence of rules; finalist posters on a stage, each selectable.
- Selecting a poster lifts it and adds an amber edge and check. The bottom bar changes from “Pick a film to begin” to “Lock it in when you're ready”.
- After locking: “Waiting for the room…” until picks are in, then “Roll the pick”.
- Empty shortlist: “No film made the cut.” with Start over and Back home.
- Phone shows both posters side by side and fixes the status + action bar to the bottom.

### Winner — the premiere

- Backdrop of the winning film, darkened; a large poster and the winning title, with the tally and the room's picks.
- Display title, meta, synopsis, About the film, “Add to watchlist” or “Keep the crew” for open rooms, Back home.
- Show the tally and disclose a tie if one occurred.
- A little theatre is allowed here: a slow rise on the title and poster. No confetti.
- Phone puts the poster above the copy and stacks the actions full width.

### Guest access

- An invite link or a direct room link opens in guest mode: pick a display name, no password or email. Guests can join an open room or host one; group rooms stay member-only.
- Guests get a quiet `Guest` tag in the room chrome and the player list. They ready, vote and pick like anyone else.
- There is no account wall before or during the night. The account gate appears only when a guest tries to **save** (Keep the crew / Add to watchlist) or **leave** the room.
- Dismissing the gate cancels the action: pressing Escape or the close button on a leave prompt keeps the guest in the room. “Leave as guest” is the explicit exit.
- Creating an account claims the guest name, unlocks Groups, and lets the save action finish. “Already have an account? Sign in” is the secondary path.
- The public Home hides member groups and the Groups tab. It keeps the club preview and log as social proof, with “No account needed to join a room” and a single account CTA.
- Group routes and the log's “Open the group” action are member-only; the night dialog offers account creation instead.

### Invite

- Link-only, not a public listing.
- Warm split card: left explains who, what, status, privacy, players, join; right is the film still and a short line.
- Logged-out is not simulated; the prototype assumes the signed-in shell.

### Film detail sheet

- Opens over the room, never replaces it: right-side panel on desktop, bottom sheet at 92dvh on phone. The room stays visible behind a dimmed overlay.
- Entry points: the current reel poster (with an info badge), the “About the film” link under the card, an “About” link on each finalist, and “About the film” on the winner. The group watchlist uses the same right-panel/bottom-sheet pattern for its film sheet, with the score breakdown in place of room status.
- Content order: backdrop, poster, title/meta/tagline → room status → story → credits → club context → action.
- Actions are contextual and close the sheet so the room's reveal is seen: vote in the playing round, pick in the final, add to the watchlist on a group winner.
- Do not reveal other players' votes or picks before the room does. After the reveal, show the ballot or pick counts.
- Use `?film=<id>` for the open state so browser back closes it and the view is shareable. In production, `/lobby/:uuid/film/:movieId` is the cleaner route.
- On phone, the footer stays fixed while the body scrolls. Swipe down from the film hero to dismiss; there is no fake drag handle.
- If the room advances while the sheet is open, show “Not in this room” and remove the stale action rather than letting someone vote on the wrong film.
- Data: the visual uses the full description/tagline from the Django `Movie` rows plus writers, cast, and language. Keep the real-time lobby state lean; fetch the film detail separately when the API is added.

## Motion

- One idea per transition: fade the room in, lift the title/poster on the winner, pulse the live dot.
- Duration 180–320ms for UI; 600–700ms for the winner reveal.
- Easing: `cubic-bezier(.2,.8,.2,1)` for entrances, ease for hover.
- Gesture surfaces are direct: the reel follows the finger 1:1 and projects release velocity; the film sheet follows a downward drag before it dismisses or springs back.
- Dialogs and sheets animate out along the same path they entered, not just in.
- Always respect `prefers-reduced-motion`: remove movement and keep short opacity cross-fades. Add `prefers-reduced-transparency` and `prefers-contrast: more` states for the translucent chrome.

## Accessibility

- Visible `:focus-visible` amber outline everywhere.
- Semantic landmarks: `main`, `nav`, labelled sections; one `h1` per screen.
- Base UI dialog handles focus trap, Escape, and focus return.
- Live regions for vote wait/reveal, ready status, and toasts.
- Vote choices have full text labels and 1/2/3 keyboard shortcuts. Keyboard shortcuts do not hijack inputs (none on the room screen).
- 44px mobile targets; check the search input's hit area, not just its container.
- Colour is not the only signal: ready uses a check, picks use a badge, skipped uses “Skipped tonight”.
- Contrast: cream on charcoal, amber on charcoal, dark on amber. Do not use muted-2 for essential instructions.

## Tone of voice

- Human, specific, short. “The room is filling up.” “Are you in?” “Seen it.” “Not everyone was in.” “The room has spoken.”
- Avoid database words (“lobby membership”, “pool index”) and fake enthusiasm.
- Explain the rule once, in plain language: “A unanimous yes puts it on the shortlist — then everyone picks one.”

## When extending

- Reuse tokens and components; do not introduce a second accent or a new radius scale.
- New screens should answer one question and expose one primary action.
- Every list needs empty, loading, error, long-text, and many-item states.
- Every creation/join/winner action should leave a trace in the group or hub.
- Keep the legacy Django pages visually consistent until they are migrated; do not let two design languages coexist indefinitely.

## Prototype conventions

- The selected watchlist, reel, premiere and hub directions are the product prototype now; there is no separate variant harness.
- Shared product data is in `src/data.ts`. Lobby behaviour is in `src/state/Lobby.tsx`. Group, film status and score state is in `src/state/Groups.tsx`. Viewer identity (member, guest, anonymous) is in `src/state/Viewer.tsx`; the save/leave account gate is in `src/state/GuestGate.tsx`.
- Deep links with `?stage=` seed a room for review; they are not a product feature.
- `src/styles.css` is the single source of truth for tokens and layout in the prototype. When the production shell is built, split tokens into the shared layer and keep component styles close to components.
