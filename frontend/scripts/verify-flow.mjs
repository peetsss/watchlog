import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

const base = process.env.WATCHLOG_URL ?? "http://localhost:5173";
const out = process.env.WATCHLOG_OUT ?? "/tmp/watchlog-prototype/flow";
await mkdir(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  headless: true,
});

const errors = [];
const checks = [];

function check(name, condition, detail = "") {
  checks.push({ name, ok: Boolean(condition), detail });
  if (!condition) throw new Error(`FAILED: ${name} ${detail}`);
}

async function ready(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
}

function watch(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${label} console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`${label} pageerror: ${error.message}`));
}

// ---------------------------------------------------------------- desktop flow
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "desktop");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await ready(page);
  await page.screenshot({ path: `${out}/01-hub.png`, fullPage: true });

  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("dialog").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/02-start-dialog.png` });
  check("start dialog has three groups", (await page.locator(".choice-list .choice").count()) === 3);

  await page.getByRole("button", { name: /Start the room/ }).click();
  await page.waitForURL("**/lobby/friday");
  await page.locator(".waiting-room").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/03-waiting.png` });

  await page.getByRole("button", { name: "I'm in", exact: true }).click();
  const startButton = page.getByRole("button", { name: /Start the night/ });
  await startButton.waitFor();
  check("host can start when everyone is ready", await startButton.isEnabled());
  await ready(page);
  await page.screenshot({ path: `${out}/04-waiting-ready.png` });

  await startButton.click();
  await page.locator(".reel-room").waitFor();
  await page.getByRole("heading", { name: "Past Lives", exact: true }).waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/05-playing.png` });

  await page.getByRole("button", { name: /I'm in/ }).click();
  await page.getByText("Waiting for the room").waitFor();
  await page.screenshot({ path: `${out}/06-playing-waiting.png` });
  await page.getByText("Everyone was in.").waitFor({ timeout: 4000 });
  await ready(page);
  await page.screenshot({ path: `${out}/07-playing-shortlisted.png` });
  await page.getByRole("button", { name: /Next film/ }).click();

  await page.getByRole("heading", { name: "Oppenheimer", exact: true }).waitFor();
  await page.getByRole("button", { name: /I'm in/ }).click();
  await page.getByText("Not everyone was in.").waitFor({ timeout: 4000 });
  await ready(page);
  await page.screenshot({ path: `${out}/08-playing-skipped.png` });
  await page.getByRole("button", { name: /Next film/ }).click();

  await page.getByRole("heading", { name: "The Grand Budapest Hotel", exact: true }).waitFor();
  await page.getByRole("button", { name: /I'm in/ }).click();
  await page.getByText("Everyone was in.").waitFor({ timeout: 4000 });
  await page.getByRole("button", { name: /See the shortlist/ }).click();

  await page.locator(".premiere-final").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/09-final.png` });
  check("two finalists", (await page.locator(".premiere-card").count()) === 2);

  await page.getByRole("button", { name: "Select Past Lives" }).click();
  await page.getByRole("button", { name: /Lock in Past Lives/ }).click();
  await page.getByText("Everyone has picked.").waitFor({ timeout: 4000 });
  await ready(page);
  await page.screenshot({ path: `${out}/10-final-picked.png` });
  await page.getByRole("button", { name: /Roll the pick/ }).click();

  await page.getByRole("heading", { name: "Past Lives", exact: true }).waitFor();
  await page.getByText("3 of 5 picked it").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/11-winner.png` });

  await page.getByRole("button", { name: /Add to watchlist/ }).click();
  await page.getByRole("button", { name: /On the watchlist/ }).waitFor();
  await page.getByText("Past Lives added to Friday Film Club.").waitFor();
  await page.screenshot({ path: `${out}/12-winner-added.png` });

  await page.getByRole("button", { name: "Leave the room and go home" }).click();
  await page.getByText("Last night").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/13-hub-last-night.png`, fullPage: true });

  await context.close();
}

// ---------------------------------------------------------------- search + group
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "utility");

  await page.goto(base + "/search", { waitUntil: "networkidle" });
  await page.getByRole("searchbox").fill("Past");
  check("search filters to one film", (await page.locator(".search-card").count()) === 1);
  await page.getByRole("button", { name: /Add Past Lives/ }).click();
  await page.getByText("Added Past Lives to Friday Film Club.").waitFor();
  await page.getByRole("button", { name: /Past Lives added to Friday Film Club/ }).waitFor();
  await page.screenshot({ path: `${out}/14-search-added.png` });

  await page.goto(base + "/groups", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Create a group/ }).click();
  await page.getByLabel("Group name").fill("Sunday Matinee");
  await page.getByLabel(/What's the group about/).fill("Slow starts, strong coffee.");
  await page.getByRole("button", { name: "Create group" }).click();
  await page.getByText("Sunday Matinee is ready. Invite your people.").waitFor();
  await page.getByRole("heading", { name: "Sunday Matinee" }).waitFor();
  await page.screenshot({ path: `${out}/15-groups-created.png` });

  await context.close();
}

// ---------------------------------------------------------------- mobile flow
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  watch(page, "mobile");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await ready(page);
  await page.screenshot({ path: `${out}/16-mobile-hub.png`, fullPage: true });

  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("dialog").waitFor();
  await ready(page);
  const dialogRect = await page.locator(".dialog-content").boundingBox();
  check("mobile dialog is a bottom sheet", dialogRect && Math.abs(dialogRect.y + dialogRect.height - 844) < 2, JSON.stringify(dialogRect));
  await page.screenshot({ path: `${out}/17-mobile-dialog.png` });
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });

  await page.goto(base + "/lobby/friday?stage=waiting", { waitUntil: "networkidle" });
  await ready(page);
  const actionRect = await page.locator(".room-actionbar").boundingBox();
  check("mobile waiting action bar is fixed in view", actionRect && Math.abs(actionRect.y + actionRect.height - 844) < 2, JSON.stringify(actionRect));
  await page.screenshot({ path: `${out}/18-mobile-waiting.png` });

  await page.getByRole("button", { name: "I'm in", exact: true }).click();
  await page.getByRole("button", { name: /Start the night/ }).click();
  await page.locator(".reel-room").waitFor();
  await ready(page);
  check(
    "mobile playing has no horizontal overflow",
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  );
  await page.screenshot({ path: `${out}/19-mobile-playing.png` });

  await page.goto(base + "/lobby/friday?stage=final", { waitUntil: "networkidle" });
  await ready(page);
  const finalBar = await page.locator(".premiere-bar").boundingBox();
  check("mobile final action bar is fixed in view", finalBar && Math.abs(finalBar.y + finalBar.height - 844) < 20, JSON.stringify(finalBar));
  await page.screenshot({ path: `${out}/20-mobile-final.png` });

  await page.getByRole("button", { name: "Select Past Lives" }).click();
  await page.getByRole("button", { name: /Lock in Past Lives/ }).click();
  await page.getByText("Everyone has picked.").waitFor({ timeout: 4000 });
  await page.getByRole("button", { name: /Roll the pick/ }).click();
  await page.locator(".premiere-winner").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/21-mobile-winner.png` });

  await context.close();
}

// ---------------------------------------------------------------- join flow
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  watch(page, "join");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Join with a link" }).click();
  await page.getByRole("button", { name: "Use the demo invite" }).click();
  await page.getByRole("button", { name: /Continue/ }).click();
  await page.waitForURL("**/join/7f3k2");
  await page.getByRole("heading", { name: "Maya saved you a seat." }).waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/22-mobile-join.png` });

  await page.getByRole("button", { name: /Join the room/ }).click();
  await page.waitForURL("**/lobby/friday");
  await page.getByText("Open movie night").first().waitFor();
  check("joined room is hosted by Maya", (await page.getByText("Host", { exact: true }).count()) >= 1);
  await page.getByRole("button", { name: "I'm in", exact: true }).click();
  await page.locator(".reel-room").waitFor({ timeout: 6000 });
  await page.screenshot({ path: `${out}/23-mobile-join-started.png` });

  await context.close();
}

console.log(JSON.stringify({ checks, errors }, null, 2));
await browser.close();

if (errors.length) process.exitCode = 1;
if (checks.some((item) => !item.ok)) process.exitCode = 1;
