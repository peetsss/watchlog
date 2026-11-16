import { chromium } from "playwright-core";
import { mkdir } from "node:fs/promises";

const base = process.env.WATCHLOG_URL ?? "http://localhost:5173";
const out = process.env.WATCHLOG_OUT ?? "/tmp/watchlog-prototype/edges";
await mkdir(out, { recursive: true });

const browser = await chromium.launch({
  executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
  headless: true,
});
const errors = [];
function watch(page, label) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`${label}: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`${label}: ${error.message}`));
}
async function ready(page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(600);
}

// Open lobby + invite link + start.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "open-lobby");
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("button", { name: /Open lobby/ }).click();
  await page.getByRole("button", { name: /Start the room/ }).click();
  await page.waitForURL("**/lobby/friday");
  await page.getByText("Anyone with the link can join").waitFor();
  const invite = await page.locator(".invite-url").textContent();
  console.log("open invite:", invite);
  if (!invite?.includes("/join/7f3k2")) throw new Error("open lobby invite missing");
  await ready(page);
  await page.screenshot({ path: `${out}/open-waiting.png` });
  await page.getByRole("button", { name: "I'm in", exact: true }).click();
  const start = page.getByRole("button", { name: /Start the night/ });
  await start.waitFor();
  if (!(await start.isEnabled())) throw new Error("open lobby host cannot start after readying");
  await start.click();
  await page.locator(".reel-room").waitFor();
  console.log("open lobby starts: ok");
  await context.close();
}

// Open lobby on mobile.
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  watch(page, "open-lobby-mobile");
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("button", { name: /Open lobby/ }).click();
  await page.getByRole("button", { name: /Start the room/ }).click();
  await page.waitForURL("**/lobby/friday");
  await ready(page);
  await page.screenshot({ path: `${out}/open-waiting-mobile.png` });
  await context.close();
}

// Keyboard voting + empty shortlist.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "keyboard");
  await page.goto(base + "/lobby/friday?stage=playing", { waitUntil: "networkidle" });
  await page.locator(".reel-room").waitFor();
  for (let round = 0; round < 3; round += 1) {
    await page.keyboard.press("3");
    await page.getByText("Not everyone was in.").waitFor({ timeout: 4000 });
    if (round < 2) {
      await page.getByRole("button", { name: /Next film/ }).click();
    } else {
      await page.getByRole("button", { name: /See the shortlist/ }).click();
    }
  }
  await page.getByText("No film made the cut.").waitFor();
  await ready(page);
  await page.screenshot({ path: `${out}/empty-final.png` });
  console.log("keyboard votes + empty final: ok");
  await context.close();
}

// Open lobby → keep the crew.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "keep-crew");
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Start a movie night" }).click();
  await page.getByRole("button", { name: /Open lobby/ }).click();
  await page.getByRole("button", { name: /Start the room/ }).click();
  await page.getByRole("button", { name: "I'm in", exact: true }).click();
  await page.getByRole("button", { name: /Start the night/ }).click();
  await page.locator(".reel-room").waitFor();

  for (let round = 0; round < 3; round += 1) {
    await page.keyboard.press("1");
    await page.getByText("Everyone was in.").waitFor({ timeout: 4000 });
    if (round < 2) {
      await page.getByRole("button", { name: /Next film/ }).click();
    } else {
      await page.getByRole("button", { name: /See the shortlist/ }).click();
    }
  }

  await page.getByRole("button", { name: "Select Past Lives" }).click();
  await page.getByRole("button", { name: /Lock in Past Lives/ }).click();
  await page.getByText("Everyone has picked.").waitFor({ timeout: 4000 });
  await page.getByRole("button", { name: /Roll the pick/ }).click();
  await page.getByRole("button", { name: /Keep the crew/ }).click();
  await page.getByText("The crew is saved").waitFor();
  await page.getByRole("link", { name: /See your groups/ }).click();
  await page.waitForURL("**/groups");
  const crewRow = page.locator(".group-row").filter({ hasText: "Movie night crew" });
  await crewRow.waitFor();
  if (!(await crewRow.getByText("5 members").count())) throw new Error("kept crew is missing members");
  if (!(await crewRow.getByText("1 film").count())) throw new Error("kept crew is missing the winner");
  await ready(page);
  await page.screenshot({ path: `${out}/keep-crew-groups.png` });
  console.log("open lobby → keep the crew: ok");
  await context.close();
}

// Adding from search updates the group.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "search-group-update");
  await page.goto(base + "/search", { waitUntil: "networkidle" });
  await page.getByRole("searchbox").fill("Past");
  await page.getByRole("button", { name: /Add Past Lives/ }).click();
  await page.getByRole("link", { name: "Groups", exact: true }).click();
  await page.waitForURL("**/groups");
  const fridayRow = page.locator(".group-row").filter({ hasText: "Friday Film Club" });
  await fridayRow.waitFor();
  if (!(await fridayRow.getByText("7 films").count())) throw new Error("search add did not update the group count");
  console.log("search add updates group: ok");
  await context.close();
}

// Unknown lobby + 404.
{
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "not-found");
  await page.goto(base + "/lobby/nope", { waitUntil: "networkidle" });
  await page.getByText("This room has closed.").waitFor();
  await page.goto(base + "/nope", { waitUntil: "networkidle" });
  await page.getByText("This page isn't in the log.").waitFor();
  console.log("unknown room + 404: ok");
  await context.close();
}

// Mobile touch targets on key controls.
{
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  watch(page, "touch");
  await page.goto(base + "/search", { waitUntil: "networkidle" });
  await page.getByRole("searchbox").fill("Past");
  const small = await page.evaluate(() => {
    const selectors = "button, a.btn, .filter-chip, .add-button, input, select";
    return [...document.querySelectorAll(selectors)]
      .map((el) => {
        const rect = el.getBoundingClientRect();
        return {
          tag: el.tagName,
          cls: el.className,
          label: el.getAttribute("aria-label") || el.textContent?.trim().slice(0, 30),
          w: Math.round(rect.width),
          h: Math.round(rect.height),
        };
      })
      .filter((item) => item.w > 0 && item.h > 0 && (item.h < 44 || item.w < 20));
  });
  console.log("small mobile targets:", JSON.stringify(small, null, 2));
  if (small.length) throw new Error("small mobile touch targets found");
  await context.close();
}

console.log("errors", JSON.stringify(errors, null, 2));
await browser.close();
if (errors.length) process.exitCode = 1;
