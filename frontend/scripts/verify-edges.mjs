import { randomUUID } from "node:crypto";
import {
  base,
  createRecorder,
  deleteLobbies,
  deleteUsers,
  launchBrowser,
  login,
  outputDir,
  register,
  resetLobbies,
  settle,
  startGroupNight,
  startOpenNight,
  unexpectedErrors,
} from "./lib/verify.mjs";

const out = await outputDir("edges");
const browser = await launchBrowser();
const { checks, errors, check, watch } = createRecorder();
const lobbyIds = [];
const username = `verify_edge_${Date.now()}`;

try {
  resetLobbies();

  const aliceContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const alice = await aliceContext.newPage();
  watch(alice, "alice");
  const bobContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const bob = await bobContext.newPage();
  watch(bob, "bob");

  await login(alice, "alice");
  const openLobby = await startOpenNight(alice);
  lobbyIds.push(openLobby);
  await alice.getByText("Anyone with the link can join").waitFor();
  const invite = (await alice.locator(".invite-url").innerText()).trim();
  check("open invite points at the room uuid", invite.includes(`/join/${openLobby}`), invite);
  await settle(alice);
  await alice.screenshot({ path: `${out}/01-open-waiting.png`, fullPage: true });

  await login(bob, "bob");
  await bob.goto(`${base}/join/${openLobby}`, { waitUntil: "networkidle" });
  await bob.getByRole("heading", { name: /saved you a seat/i }).waitFor();
  check("join preview names the host", await bob.getByText("Hosted by").isVisible());
  await settle(bob);
  await bob.screenshot({ path: `${out}/02-join-preview.png`, fullPage: true });
  await bob.getByRole("button", { name: /^Join the room/ }).click();
  await bob.waitForURL(`${base}/lobby/${openLobby}`, { timeout: 10_000 });
  await bob.getByText("The room is filling up.").waitFor();
  await bob.locator(".players-list").getByText("bob").waitFor();
  check("invite join adds the member", true);

  await alice.locator(".room-exit").click();
  await alice.waitForURL(base + "/", { timeout: 10_000 });

  const groupLobby = await startGroupNight(alice);
  lobbyIds.push(groupLobby);
  await alice.getByText("The room is filling up.").waitFor();

  const privateContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const privatePage = await privateContext.newPage();
  watch(privatePage, "non-member");
  await register(privatePage, username);
  await privatePage.goto(`${base}/lobby/${groupLobby}`, { waitUntil: "networkidle" });
  await privatePage.getByText("This room is private.").waitFor({ timeout: 10_000 });
  check("non-members cannot open a group room", true);
  await alice.locator(".room-exit").click();
  await alice.waitForURL(base + "/", { timeout: 10_000 });

  await alice.goto(`${base}/lobby/${randomUUID()}`, { waitUntil: "networkidle" });
  await alice.getByText("This room has closed.").waitFor({ timeout: 10_000 });
  check("unknown room shows the closed state", true);

  await alice.goto(base + "/nope", { waitUntil: "networkidle" });
  await alice.getByText("This page isn't in the log.").waitFor();
  check("unknown page shows the 404 state", true);

  await alice.goto(base + "/search", { waitUntil: "networkidle" });
  await alice.getByLabel("Search films and series by title").fill("Inception");
  const offline = alice.getByText("Film search is offline.");
  const results = alice.locator(".search-card");
  await Promise.race([
    offline.waitFor({ timeout: 15_000 }),
    results.first().waitFor({ timeout: 15_000 }),
  ]);
  if (await offline.isVisible()) {
    check("search reports an unavailable catalog", true);
    await settle(alice);
    await alice.screenshot({ path: `${out}/03-search-offline.png`, fullPage: true });
  } else {
    check("search returns catalog results", (await results.count()) > 0);
  }

  await alice.setViewportSize({ width: 390, height: 844 });
  await alice.goto(base + "/", { waitUntil: "networkidle" });
  await alice.getByRole("button", { name: /Start a movie night/i }).click();
  const dialog = alice.getByRole("dialog");
  await dialog.waitFor();
  await settle(alice);
  const dialogRect = await dialog.boundingBox();
  check(
    "mobile start dialog is a bottom sheet",
    dialogRect && Math.abs(dialogRect.y + dialogRect.height - 844) < 2,
    JSON.stringify(dialogRect),
  );
  check(
    "mobile home has no horizontal overflow",
    await alice.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  );
  await alice.screenshot({ path: `${out}/04-mobile-dialog.png`, fullPage: true });
  await alice.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });

  const ignored = [
    "WebSocket handshake: Unexpected response code: 403",
    "404 (Not Found)",
    "502 (Bad Gateway)",
  ];
  const meaningful = unexpectedErrors(errors, ignored);
  check("no unexpected console or page errors", meaningful.length === 0, meaningful.join(" | "));
} finally {
  deleteLobbies(lobbyIds);
  deleteUsers([username]);
  await browser.close();
}

console.log(JSON.stringify({ checks, errors, screenshots: out }, null, 2));
if (unexpectedErrors(errors, ["WebSocket handshake: Unexpected response code: 403", "404 (Not Found)", "502 (Bad Gateway)"]).length) {
  process.exitCode = 1;
}
