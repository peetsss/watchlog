import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

const base = process.env.WATCHLOG_URL ?? "http://localhost:5173";
const out = process.env.WATCHLOG_OUT ?? "/tmp/watchlog-prototype/detail";
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

function watch(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${label} console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`${label} pageerror: ${error.message}`));
}

async function settle(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(650);
}

async function openPlayingSheet(page) {
  await page.goto(base + "/lobby/friday?stage=playing", { waitUntil: "networkidle" });
  await settle(page);
  await page.locator(".reel-info").click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await page.waitForTimeout(450);
  return dialog;
}

// ---------------------------------------------------------------- desktop read
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "desktop");
  const dialog = await openPlayingSheet(page);

  check("detail title", await dialog.getByRole("heading", { name: "Past Lives" }).isVisible());
  check("detail voting status", await dialog.getByText("Voting now · Film 1 of 3").isVisible());
  check("detail story", await dialog.getByRole("heading", { name: "The story" }).isVisible());
  check("detail credits", await dialog.getByRole("heading", { name: "The credits" }).isVisible());
  check("detail club", await dialog.getByRole("heading", { name: "In the club" }).isVisible());
  check("detail director", await dialog.getByText("Celine Song").first().isVisible());
  check("detail cast", await dialog.getByText("Greta Lee, Teo Yoo, John Magaro").isVisible());
  check("detail not on watchlist", await dialog.getByText("Not on the watchlist yet").isVisible());
  check("detail URL", page.url().includes("film=past-lives"));
  await page.screenshot({ path: `${out}/01-detail-desktop.png` });

  await page.keyboard.press("1");
  await page.waitForTimeout(350);
  check(
    "room keyboard shortcuts are blocked while the sheet is open",
    await dialog.getByText("Voting now · Film 1 of 3").isVisible(),
  );
  check("sheet still offers a vote", await dialog.getByRole("button", { name: /I'm in/ }).isVisible());

  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.waitForTimeout(120);
  const focusAfterClose = await page.evaluate(() => ({
    tag: document.activeElement?.tagName,
    label: document.activeElement?.getAttribute("aria-label"),
  }));
  check("escape closes and removes film param", !page.url().includes("film="), page.url());
  check(
    "focus returns to the film trigger",
    focusAfterClose.tag === "BUTTON" && focusAfterClose.label === "About Past Lives",
    JSON.stringify(focusAfterClose),
  );

  // Direct link with both stage seed and film.
  await page.goto(base + "/lobby/friday?stage=playing&film=past-lives", { waitUntil: "networkidle" });
  await page.getByRole("dialog").waitFor();
  await settle(page);
  check("deep link opens sheet", await page.getByRole("dialog").isVisible());
  check("deep link removes stage but keeps film", !page.url().includes("stage=") && page.url().includes("film=past-lives"), page.url());
  await page.getByRole("dialog").getByRole("button", { name: "Close film details" }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });

  // Back button closes.
  await page.locator(".reel-info").click();
  await page.getByRole("dialog").waitFor();
  await page.goBack();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  check("browser back closes the sheet", true);

  // Refresh while open keeps the sheet.
  await page.locator(".reel-info").click();
  await page.getByRole("dialog").waitFor();
  await page.reload({ waitUntil: "networkidle" });
  await page.getByRole("dialog").waitFor();
  check("refresh keeps the detail sheet", await page.getByRole("dialog").isVisible());
  await page.getByRole("dialog").getByRole("button", { name: "Close film details" }).click();

  await context.close();
}

// ---------------------------------------------------------------- vote from sheet
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "vote");
  const dialog = await openPlayingSheet(page);
  await dialog.getByRole("button", { name: /I'm in/ }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.getByText("Waiting for the room").waitFor();
  await page.getByText("Everyone was in.").waitFor({ timeout: 4000 });
  check("vote from detail sheet resolves the room", true);
  await page.screenshot({ path: `${out}/02-vote-from-sheet.png` });
  await context.close();
}

// ---------------------------------------------------------------- pick from sheet
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "pick");
  await page.goto(base + "/lobby/friday?stage=final", { waitUntil: "networkidle" });
  await settle(page);
  await page.getByRole("button", { name: "About Past Lives" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await page.waitForTimeout(400);
  check("finalist status", await dialog.getByText("Finalist").isVisible());
  check("finalist hidden picks", await dialog.getByText("Picks stay hidden.").isVisible());
  await page.screenshot({ path: `${out}/03-detail-finalist.png` });
  await dialog.getByRole("button", { name: "Pick this film" }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.getByText("Everyone has picked.").waitFor({ timeout: 4000 });
  check("pick from detail sheet resolves the final", true);
  await context.close();
}

// ---------------------------------------------------------------- add from sheet
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "add");
  await page.goto(base + "/lobby/friday?stage=winner", { waitUntil: "networkidle" });
  await settle(page);
  await page.getByRole("button", { name: "About the film" }).click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await page.waitForTimeout(400);
  check("winner status", await dialog.getByText("Tonight's pick").isVisible());
  check("winner count", await dialog.getByText("3 of 5 picked it").first().isVisible());
  await page.screenshot({ path: `${out}/04-detail-winner.png` });
  await dialog.getByRole("button", { name: /Add to watchlist/ }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.getByRole("button", { name: /On the watchlist/ }).waitFor();
  await page.getByText("Past Lives added to Friday Film Club.").waitFor();
  check("add from detail sheet updates the winner", true);
  await page.screenshot({ path: `${out}/05-winner-added.png` });
  await context.close();
}

// ---------------------------------------------------------------- mobile
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  watch(page, "mobile");
  const dialog = await openPlayingSheet(page);
  const metrics = await page.evaluate(() => {
    const sheet = document.querySelector(".detail-sheet")?.getBoundingClientRect();
    const footer = document.querySelector(".detail-footer")?.getBoundingClientRect();
    const body = document.querySelector(".detail-body");
    return {
      sheetBottom: sheet?.bottom,
      sheetTop: sheet?.top,
      footerBottom: footer?.bottom,
      bodyScrollHeight: body?.scrollHeight,
      bodyClientHeight: body?.clientHeight,
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    };
  });
  check("mobile sheet reaches the bottom", metrics.sheetBottom === 844, JSON.stringify(metrics));
  check("mobile sheet leaves a top strip", metrics.sheetTop > 40, JSON.stringify(metrics));
  check("mobile footer is visible", metrics.footerBottom === 844, JSON.stringify(metrics));
  check("mobile sheet body scrolls", (metrics.bodyScrollHeight ?? 0) > (metrics.bodyClientHeight ?? 0), JSON.stringify(metrics));
  check("mobile has no horizontal overflow", metrics.scrollWidth <= metrics.innerWidth, JSON.stringify(metrics));
  await page.screenshot({ path: `${out}/06-detail-mobile.png` });
  await page.getByRole("dialog").getByRole("button", { name: "Close film details" }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });

  await page.goto(base + "/lobby/friday?stage=final", { waitUntil: "networkidle" });
  await settle(page);
  await page.getByRole("button", { name: "About Past Lives" }).click();
  await page.getByRole("dialog").waitFor();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/07-detail-final-mobile.png` });
  await page.keyboard.press("Escape");
  await page.getByRole("dialog").waitFor({ state: "detached" });

  await page.goto(base + "/lobby/friday?stage=winner", { waitUntil: "networkidle" });
  await settle(page);
  await page.getByRole("button", { name: "About the film" }).click();
  await page.getByRole("dialog").waitFor();
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${out}/08-detail-winner-mobile.png` });
  check("mobile winner detail has add action", await page.getByRole("dialog").getByRole("button", { name: /Add to watchlist/ }).isVisible());
  await context.close();
}

console.log(JSON.stringify({ checks, errors }, null, 2));
await browser.close();
if (errors.length) process.exitCode = 1;
if (checks.some((item) => !item.ok)) process.exitCode = 1;
