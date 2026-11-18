# Test suite adversarial review

Date: 2026-11-18

Scope: all backend pytest modules, the five Playwright verification flows, and
the shared verification helpers. Method: line-coverage run
(`pytest --cov=app`, 88% before the fixes below), a full read of the test
modules and frontend scripts, and a pass specifically looking for assertions
that cannot fail, production-default blind spots, and security assumptions.

## Fixed in this pass

| # | Severity | Finding | Fix |
| --- | --- | --- | --- |
| 1 | High | The guest-claim test checked only the name and host role. The product promise also includes keeping votes and picks, which could regress silently. | Added `test_guest_claim_preserves_votes_and_picks`: plays three rounds, picks a finalist as a guest, registers, then asserts finalists, `viewer_pick`, host role and finalization survive. |
| 2 | High | Production defaults were not exercised: tests run with `legacy_group_join_enabled=True`, while production is `False`. The disabled branch had no test. | Added `test_legacy_group_join_is_disabled` asserting `403 legacy_join_disabled`. |
| 3 | Medium | Group invite expiry was untested; only revocation was. An expiry regression would leave links valid forever. | Added `test_group_invite_expires_after_seven_days` using `time-machine`. |
| 4 | Medium | `client_ip()` trusted the **leftmost** `X-Forwarded-For` entry. A client can pre-seed that entry when a proxy appends rather than replaces, defeating per-IP rate limits. | `client_ip()` now uses the rightmost (nearest-proxy) hop. Added tests for forwarded and socket-address fallback. |
| 5 | Medium | Playwright helpers mutate the dev database via `docker compose exec` without checking the target. Pointing `WATCHLOG_URL` at staging could delete real lobbies/users. | `databaseSql()` now refuses non-local hosts unless `WATCHLOG_ALLOW_REMOTE_VERIFY=1`. |

## Accepted risks / follow-ups

| # | Severity | Finding | Disposition |
| --- | --- | --- | --- |
| 6 | Medium | `unexpectedErrors()` ignores every console `401` and `403`. A broken authorization flow could hide among expected unauthenticated probes. | Accepted for now. The flows assert the visible auth outcomes; narrowing the ignore list needs per-route allowlists. Revisit if auth errors grow. |
| 7 | Low | Several Playwright checks pass the literal `true` after a `waitFor()`. They are not false positives — `waitFor()` throws on timeout — but the recorded label does not carry the observed value. | Accepted. Replace with derived booleans only if the reporting becomes user-facing. |
| 8 | Low | `markUserVerified()` and the cleanup helpers interpolate SQL strings. | Accepted. Usernames are generated, and the new local-host guard limits blast radius. Parameterized SQL is preferable if these scripts grow. |
| 9 | Low | Any group member can revoke the group’s active invite link; only admins can delete a group. | Product decision, not a test defect. Confirm intent before launch; otherwise restrict revocation to `role == "admin"`. |
| 10 | Low | No coverage gate. Redis pub/sub (`hub.py`), guest expiry internals and the random lobby pool are the least-covered modules (46–62%). | Not gated on purpose while the suite is young. Add a threshold once the launch surface is stable. |
| 11 | Low | The frontend has no unit tests; it relies on five end-to-end flows. Pure helpers and state reducers are only covered indirectly. | Acceptable for the current surface. Add Vitest if client-side logic grows. |
| 12 | Info | `test_unverified_accounts_cannot_create_groups` temporarily mutates `app.state.settings`. | Works because tests are single-threaded, but prefer a dedicated settings fixture when more production-default tests are added. |
| 13 | Info | Starlette warns that `httpx` with `starlette.testclient` is deprecated in favour of `httpx2`. | Track the Starlette/httpx migration; not launch-blocking. |

## Baseline

- Backend: 263 tests covering auth, CSRF/session rotation, guest host/join/claim,
  invite tokens, rate limits, lobby state machine, WebSockets, TMDB parsing,
  watch-provider snapshots, email outbox/tokens, Celery tasks and settings
  validation.
- Frontend: five Playwright flows (night flow, auth, guest claim, edge states,
  film detail) with console/page-error assertions.
- Command: `just check` and `cd frontend && npm run verify:all`.
