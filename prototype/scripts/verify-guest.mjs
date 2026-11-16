import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

const base = process.env.WATCHLOG_URL ?? "http://localhost:5173";
const out = process.env.WATCHLOG_OUT ?? "/tmp/watchlog-prototype/guest";
await mkdir(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  headless: true,
});

const checks = [];
const errors = [];

function check(name, condition, detail = "") {
  checks.push({ name, ok: Boolean(condition), detail });
  if (!condition) throw new Error(`FAILED: ${name} ${detail}`);
}

async function ready(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
}

function watch(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${label} console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`${label} pageerror: ${error.message}`));
}

// Guest can host an open room without an account.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "host");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await ready(page);
  check("member Home has a sign-out action", await page.getByRole("button", { name: "Sign out" }).isVisible());

  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByText("No account needed to join a room").waitFor();
  check("public Home hides the member groups", (await page.locator(".side-group").count()) === 0);
  check(
    "public Home hides the Groups tab",
    (await page.locator(".side-nav-link", { hasText: "Groups" }).count()) === 0,
  );

  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("dialog").waitFor();
  check("guest start asks for a name", await page.getByLabel("Your name").isVisible());
  await page.getByLabel("Your name").fill("Riley");
  await page.getByRole("button", { name: "Start the room" }).click();
  await page.waitForURL("**/lobby/friday");
  await page.locator(".waiting-room").waitFor();

  const tags = (await page.locator(".player-row.is-you .tag").allInnerTexts()).join(" ");
  check("guest host carries a Guest tag", tags.toLowerCase().includes("guest"));
  check("guest host carries a Host tag", tags.toLowerCase().includes("host"));
  await page.screenshot({ path: `${out}/01-guest-host.png`, fullPage: true });

  await page.getByRole("button", { name: "Leave the room and go home" }).click();
  await page.getByRole("dialog").waitFor();
  check(
    "leaving as a guest opens the account gate",
    (await page.getByRole("dialog").getByRole("heading").innerText()) === "Leaving as a guest?",
  );
  await page.screenshot({ path: `${out}/02-leave-gate.png` });

  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  check("dismissing the gate cancels the leave", page.url().includes("/lobby/friday"));

  await page.getByRole("button", { name: "Leave the room and go home" }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByRole("button", { name: "Leave as guest" }).click();
  await page.waitForURL(base + "/");
  check(
    "declining the gate leaves the guest identity intact",
    (await page.locator(".side-user").innerText()).includes("Riley"),
  );
  await context.close();
}

// Guest can join an invite and create an account from the room.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "join");

  await page.goto(base + "/join/7f3k2", { waitUntil: "networkidle" });
  await ready(page);
  check("invite asks a guest for a name", await page.getByLabel("What should we call you?").isVisible());
  await page.getByLabel("What should we call you?").fill("Riley");
  await page.screenshot({ path: `${out}/03-invite-guest.png`, fullPage: true });
  await page.getByRole("button", { name: /Join as guest/ }).click();
  await page.waitForURL("**/lobby/friday");
  await page.locator(".waiting-room").waitFor();

  check(
    "guest appears as themselves in the room",
    (await page.locator(".player-row.is-you").innerText()).includes("Riley"),
  );
  check(
    "guest sees the host label",
    (await page.locator(".player-row .tag-amber").innerText()).toLowerCase().includes("host"),
  );

  await page.getByRole("button", { name: "Leave the room and go home" }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByLabel("Email").fill("riley@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForURL(base + "/");
  await page.waitForTimeout(300);

  check(
    "creating an account keeps the guest name",
    (await page.locator(".side-user strong").innerText()) === "Riley",
  );
  check(
    "creating an account unlocks the Groups tab",
    (await page.locator(".side-nav-link", { hasText: "Groups" }).count()) === 1,
  );
  await page.screenshot({ path: `${out}/04-account-home.png`, fullPage: true });
  await context.close();
}

// Guest saves the night through the winner screen.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "save");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await ready(page);
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("dialog").waitFor();
  await page.getByLabel("Your name").fill("Riley");
  await page.getByRole("button", { name: "Start the room" }).click();
  await page.waitForURL("**/lobby/friday");
  await page.waitForTimeout(400);

  await page.getByRole("button", { name: /I'm in/ }).click();
  await page.getByRole("button", { name: /Start the night/ }).click();
  await page.locator(".reel-room").waitFor();
  await page.waitForTimeout(400);

  for (let round = 0; round < 3; round += 1) {
    await page.locator(".reel-choice.is-in").click();
    await page.getByText(/Everyone was in\.|Not everyone was in\./).waitFor({ timeout: 5000 });
    await page.getByRole("button", { name: /Next film|See the shortlist/ }).click();
    await page.waitForTimeout(300);
  }

  await page.locator(".premiere-final").waitFor();
  await page.locator(".premiere-select").first().click();
  await page.getByRole("button", { name: /Lock in/ }).click();
  await page.getByText("Everyone has picked. Roll the premiere.").waitFor({ timeout: 5000 });
  await page.getByRole("button", { name: /Roll the pick/ }).click();
  await page.locator(".premiere-winner").waitFor();

  await page.getByRole("button", { name: /Keep the crew/ }).click();
  await page.getByRole("dialog").waitFor();
  check(
    "saving as a guest opens the account gate",
    (await page.getByRole("dialog").getByRole("heading").innerText()) === "Keep this night?",
  );

  await page.getByLabel("Email").fill("riley@example.com");
  await page.getByLabel("Password").fill("password123");
  await page.getByRole("button", { name: "Create account" }).click();
  await page.waitForTimeout(600);
  check("creating an account completes the save", await page.getByRole("button", { name: /Crew saved/ }).isVisible());

  await page.getByRole("button", { name: /Back home/ }).click();
  await page.waitForURL(base + "/");
  await page.waitForTimeout(300);
  check(
    "the saved crew appears on the member Home",
    (await page.locator(".side-group").allInnerTexts()).includes("Movie night crew"),
  );
  await context.close();
}

await browser.close();
console.log(JSON.stringify({ checks, errors }, null, 2));
if (errors.length) process.exit(1);
