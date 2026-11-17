import {
  base,
  createRecorder,
  deleteLobbies,
  deleteUsers,
  launchBrowser,
  outputDir,
  settle,
  unexpectedErrors,
} from "./lib/verify.mjs";

const out = await outputDir("guest");
const browser = await launchBrowser();
const { checks, errors, check, watch } = createRecorder();
const username = `verify_guest_${Date.now()}`;
const email = `${username}@example.com`;
const lobbyIds = [];

try {
  const hostContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const host = await hostContext.newPage();
  watch(host, "guest host");
  const joinerContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const joiner = await joinerContext.newPage();
  watch(joiner, "guest joiner");

  await host.goto(base + "/start", { waitUntil: "networkidle" });
  await host.getByLabel("Display name", { exact: true }).fill("Riley");
  await host.getByRole("button", { name: /Open a room/i }).click();
  await host.waitForURL(/\/lobby\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  const lobbyId = new URL(host.url()).pathname.split("/").pop();
  lobbyIds.push(lobbyId);
  await host.getByText("The room is filling up.").waitFor();
  check("guest can open an open room", true);
  check("guest sees the save-this-night prompt", await host.getByText("Save this night").isVisible());

  await joiner.goto(`${base}/join/${lobbyId}`, { waitUntil: "networkidle" });
  await joiner.getByLabel("Your display name", { exact: true }).fill("Alex");
  await joiner.getByRole("button", { name: /Join as guest/i }).click();
  await joiner.waitForURL(new RegExp(`/lobby/${lobbyId}$`), { timeout: 15_000 });
  await host.getByText("0 of 2 ready").first().waitFor({ timeout: 15_000 });
  check("second guest can join with a name only", true);

  await host.getByRole("button", { name: "I'm in", exact: true }).click();
  await joiner.getByRole("button", { name: "I'm in", exact: true }).click();
  await host.getByText("2 of 2 ready").first().waitFor({ timeout: 15_000 });
  check("both guests can ready up", true);
  await settle(host);
  await host.screenshot({ path: `${out}/01-guest-waiting.png`, fullPage: true });

  await host.getByText("Save this night").click();
  await host.waitForURL(/\/auth\?next=/, { timeout: 10_000 });
  await host.getByRole("tab", { name: "Create account" }).click();
  await host.getByLabel("Username", { exact: true }).fill(username);
  await host.getByLabel("Email", { exact: true }).fill(email);
  await host.getByLabel("Password", { exact: true }).fill("testpass123");
  await host.getByLabel("Confirm password").fill("testpass123");
  await host.getByRole("button", { name: "Create account", exact: true }).last().click();
  await host.waitForURL(new RegExp(`/lobby/${lobbyId}$`), { timeout: 15_000 });
  await host.getByText("Save this night").waitFor({ state: "detached" }).catch(() => {});
  check("guest claim keeps the same room", true);
  check("claim removes the guest prompt", (await host.getByText("Save this night").count()) === 0);
  await host.getByRole("button", { name: /Start the night|Start with/i }).waitFor({ timeout: 15_000 });
  check("claim keeps the host", true);
  await host.locator(".player-row.is-you").getByText(username).waitFor({ timeout: 15_000 });
  check("claim keeps the account name in the room", true);

  await settle(joiner);
  await joiner.screenshot({ path: `${out}/02-guest-claimed.png`, fullPage: true });

  const meaningful = unexpectedErrors(errors);
  check("no unexpected console or page errors", meaningful.length === 0, meaningful.join(" | "));
} finally {
  deleteLobbies(lobbyIds);
  deleteUsers([username]);
  await browser.close();
}

console.log(JSON.stringify({ checks, errors, screenshots: out }, null, 2));
if (unexpectedErrors(errors).length) process.exitCode = 1;
