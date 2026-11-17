import {
  apiGroups,
  base,
  createRecorder,
  deleteLobbies,
  launchBrowser,
  login,
  outputDir,
  resetLobbies,
  setLobbyPool,
  settle,
  startGroupNight,
  unexpectedErrors,
} from "./lib/verify.mjs";

const out = await outputDir("flow");
const browser = await launchBrowser();
const { checks, errors, check, watch } = createRecorder();
const lobbyIds = [];

try {
  resetLobbies();

  const aliceContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const alice = await aliceContext.newPage();
  watch(alice, "alice");
  const bobContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const bob = await bobContext.newPage();
  watch(bob, "bob");

  await login(alice, "alice");
  await alice.getByText("Friday Film Club").first().waitFor();
  const seedFilm = alice.getByText(/The Dark Knight|Interstellar/).first();
  await seedFilm.waitFor({ timeout: 10_000 });
  check("home shows the seed club", await seedFilm.isVisible());
  await settle(alice);
  await alice.screenshot({ path: `${out}/01-home.png`, fullPage: true });

  await alice.getByRole("button", { name: /Start a movie night/i }).click();
  const dialog = alice.getByRole("dialog");
  await dialog.waitFor();
  check("start dialog lists the seed group", (await dialog.locator(".choice-list .choice").count()) === 1);
  await dialog.getByRole("button", { name: /Start the room/i }).click();
  await alice.waitForURL(/\/lobby\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  const lobbyId = new URL(alice.url()).pathname.split("/").pop();
  lobbyIds.push(lobbyId);
  setLobbyPool(lobbyId, [1, 2]);
  await alice.getByText("The room is filling up.").waitFor();

  await login(bob, "bob");
  await bob.goto(`${base}/lobby/${lobbyId}`, { waitUntil: "networkidle" });
  await bob.getByText("The room is filling up.").waitFor();
  await settle(alice);
  await alice.screenshot({ path: `${out}/02-waiting.png`, fullPage: true });

  await alice.locator(".room-actions .text-button", { hasText: "I'm in" }).click();
  await bob.getByRole("button", { name: "I'm in", exact: true }).click();
  await alice.locator(".players-head").getByText("2 of 3 ready").waitFor({ timeout: 10_000 });
  await bob.locator(".players-head").getByText("2 of 3 ready").waitFor({ timeout: 10_000 });
  await alice.screenshot({ path: `${out}/03-waiting-ready.png`, fullPage: true });

  await alice.getByRole("button", { name: /Start with 2 ready/i }).click();
  await alice.getByRole("heading", { name: "The reel." }).waitFor({ timeout: 10_000 });
  await bob.getByRole("heading", { name: "The reel." }).waitFor({ timeout: 10_000 });
  check("start keeps only ready players", (await bob.locator(".reel-head").innerText()).toLowerCase().includes("2 in the room"));

  await alice.locator(".reel-choice", { hasText: "I'm in" }).click();
  await bob.locator(".reel-choice", { hasText: "I'm in" }).click();
  await alice.getByText("Everyone was in.").waitFor({ timeout: 10_000 });
  await bob.getByText("Everyone was in.").waitFor({ timeout: 10_000 });
  await settle(alice);
  await alice.screenshot({ path: `${out}/04-playing-reveal.png`, fullPage: true });

  await alice.getByRole("button", { name: /Next film/ }).click();
  await bob.locator(".room-stage").getByText("Film 2 of 2", { exact: true }).waitFor({ timeout: 10_000 });
  await alice.locator(".reel-choice", { hasText: "I'm in" }).click();
  await bob.locator(".reel-choice", { hasText: "I'm in" }).click();
  await alice.getByText("Everyone was in.").waitFor({ timeout: 10_000 });
  await bob.getByRole("button", { name: /Finish the reel/ }).click();

  await alice.getByRole("heading", { name: /2 films. One stage./ }).waitFor({ timeout: 10_000 });
  await bob.getByRole("heading", { name: /2 films. One stage./ }).waitFor({ timeout: 10_000 });
  await settle(alice);
  await alice.screenshot({ path: `${out}/05-final.png`, fullPage: true });

  await alice.getByRole("button", { name: "Select Inception" }).click();
  await alice.getByRole("button", { name: /Lock in Inception/ }).click();
  await bob.getByRole("button", { name: "Select Inception" }).click();
  await bob.getByRole("button", { name: /Lock in Inception/ }).click();
  await alice.getByText("Everyone has picked. Roll the premiere.").waitFor({ timeout: 10_000 });
  await alice.screenshot({ path: `${out}/06-final-picks.png`, fullPage: true });

  await alice.getByRole("button", { name: /Roll the pick/ }).click();
  await alice.locator(".premiere-winner").getByRole("heading", { name: "Inception" }).waitFor({ timeout: 10_000 });
  await bob.locator(".premiere-winner").getByRole("heading", { name: "Inception" }).waitFor({ timeout: 10_000 });
  check("winner shows two picks", (await alice.locator(".premiere-picked").innerText()).includes("2 of 2"));
  check("group winner is on the watchlist", await alice.getByText("On the watchlist").isVisible());
  await settle(alice);
  await alice.screenshot({ path: `${out}/07-winner.png`, fullPage: true });

  const oldPath = new URL(alice.url()).pathname;
  await alice.getByRole("button", { name: /Start another night/ }).click();
  await alice.waitForURL(
    (url) => url.pathname !== oldPath && /\/lobby\/[0-9a-f-]{36}$/.test(url.pathname),
    { timeout: 10_000 },
  );
  await bob.waitForURL(
    (url) => url.pathname !== oldPath && /\/lobby\/[0-9a-f-]{36}$/.test(url.pathname),
    { timeout: 10_000 },
  );
  lobbyIds.push(new URL(alice.url()).pathname.split("/").pop());
  await alice.getByText("The room is filling up.").waitFor();
  check("restart opens a fresh room for both players", true);

  await alice.locator(".room-exit").click();
  await alice.waitForURL(base + "/", { timeout: 10_000 });
  await alice.getByRole("heading", { name: "The log." }).waitFor({ timeout: 10_000 });
  check("ending the room returns home", await alice.getByText("Friday Film Club").first().isVisible());
  await settle(alice);
  await alice.screenshot({ path: `${out}/08-home-after-night.png`, fullPage: true });

  const groups = await apiGroups(aliceContext);
  check("seed club still exists", groups.some((group) => group.name === "Friday Film Club"));

  const meaningful = unexpectedErrors(errors);
  check("no unexpected console or page errors", meaningful.length === 0, meaningful.join(" | "));
} finally {
  deleteLobbies(lobbyIds);
  await browser.close();
}

console.log(JSON.stringify({ checks, errors, screenshots: out }, null, 2));
if (unexpectedErrors(errors).length) process.exitCode = 1;
