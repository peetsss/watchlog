import {
  base,
  createRecorder,
  deleteLobbies,
  launchBrowser,
  login,
  outputDir,
  resetLobbies,
  seedWatchProviders,
  setLobbyPool,
  settle,
  startGroupNight,
  unexpectedErrors,
} from "./lib/verify.mjs";

const out = await outputDir("detail");
const browser = await launchBrowser();
const { checks, errors, check, watch } = createRecorder();
const lobbyIds = [];

try {
  resetLobbies();
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "detail");

  await login(page, "alice");
  const lobbyId = await startGroupNight(page);
  lobbyIds.push(lobbyId);
  setLobbyPool(lobbyId, [1]);
  await page.getByText("The room is filling up.").waitFor();
  await page.locator(".room-actions .text-button", { hasText: "I'm in" }).click();
  await page.getByRole("button", { name: /Start with 1 ready/i }).click();
  await page.getByRole("heading", { name: "The reel." }).waitFor({ timeout: 10_000 });
  seedWatchProviders(1);

  const trigger = page.locator(".reel-info");
  await trigger.click();
  const dialog = page.getByRole("dialog");
  await dialog.waitFor();
  await settle(page, 500);

  check("detail shows the current movie", await dialog.getByRole("heading", { name: "Inception" }).isVisible());
  check("detail shows the story", await dialog.getByRole("heading", { name: "The story" }).isVisible());
  check("detail shows credits", await dialog.getByRole("heading", { name: "The credits" }).isVisible());
  check(
    "detail shows where to watch",
    await dialog.getByRole("heading", { name: "Where to watch" }).isVisible(),
  );
  check(
    "detail carries JustWatch attribution",
    await dialog.getByRole("link", { name: /Watch options by JustWatch/i }).isVisible(),
  );
  check("detail shows the room context", await dialog.getByText("You haven't voted on this one yet.").isVisible());
  check("detail URL carries the catalog id", page.url().includes("film=1"), page.url());
  await page.screenshot({ path: `${out}/01-detail-desktop.png`, fullPage: true });

  await page.keyboard.press("1");
  await page.waitForTimeout(350);
  check("room keyboard shortcuts are blocked by the sheet", page.url().includes("film=1"));

  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "detached" });
  check("escape removes the movie parameter", !page.url().includes("film="), page.url());
  const focused = await page.evaluate(() => ({
    tag: document.activeElement?.tagName,
    label: document.activeElement?.getAttribute("aria-label"),
  }));
  check("focus returns to the trigger", focused.tag === "BUTTON" && focused.label === "About Inception", JSON.stringify(focused));

  await page.goto(`${base}/lobby/${lobbyId}?film=1`, { waitUntil: "networkidle" });
  await page.getByRole("dialog").waitFor();
  check("deep link opens the sheet", await page.getByRole("dialog").isVisible());
  await page.reload({ waitUntil: "networkidle" });
  await page.getByRole("dialog").waitFor();
  check("refresh keeps the sheet", await page.getByRole("dialog").isVisible());

  await page.setViewportSize({ width: 390, height: 844 });
  await settle(page, 400);
  const metrics = await page.evaluate(() => {
    const sheet = document.querySelector(".detail-sheet")?.getBoundingClientRect();
    const footer = document.querySelector(".detail-footer")?.getBoundingClientRect();
    const body = document.querySelector(".detail-body");
    return {
      sheetTop: sheet?.top,
      sheetBottom: sheet?.bottom,
      footerBottom: footer?.bottom,
      bodyScrollHeight: body?.scrollHeight,
      bodyClientHeight: body?.clientHeight,
      bodyOverflowY: body ? getComputedStyle(body).overflowY : null,
      scrollWidth: document.documentElement.scrollWidth,
      innerWidth: window.innerWidth,
    };
  });
  check("mobile sheet reaches the bottom", metrics.sheetBottom === 844, JSON.stringify(metrics));
  check("mobile sheet leaves a top strip", (metrics.sheetTop ?? 0) > 40, JSON.stringify(metrics));
  check("mobile footer stays visible", metrics.footerBottom === 844, JSON.stringify(metrics));
  check("mobile sheet body is scrollable", ["auto", "scroll"].includes(metrics.bodyOverflowY), JSON.stringify(metrics));
  check("mobile has no horizontal overflow", metrics.scrollWidth <= metrics.innerWidth, JSON.stringify(metrics));
  await page.screenshot({ path: `${out}/02-detail-mobile.png`, fullPage: true });

  await page.getByRole("dialog").getByRole("button", { name: "Close movie details" }).click();
  await page.getByRole("dialog").waitFor({ state: "detached" });
  await page.setViewportSize({ width: 1440, height: 1000 });

  await page.locator(".reel-choice", { hasText: "I'm in" }).click();
  await page.getByText("Everyone was in.").waitFor({ timeout: 10_000 });
  await page.getByRole("button", { name: /Finish the reel/ }).click();
  await page.getByRole("heading", { name: /1 movie. One stage./ }).waitFor({ timeout: 10_000 });
  await page.getByRole("button", { name: "Select Inception" }).click();
  await page.getByRole("button", { name: /Lock in Inception/ }).click();
  await page.getByText("Everyone has picked. Roll the premiere.").waitFor({ timeout: 10_000 });
  await page.getByRole("button", { name: /Roll the pick/ }).click();
  await page.locator(".premiere-winner").waitFor({ timeout: 10_000 });

  await page.getByRole("button", { name: "About the movie" }).click();
  const winnerDialog = page.getByRole("dialog");
  await winnerDialog.waitFor();
  await settle(page, 400);
  check("winner detail is marked as tonight's pick", await winnerDialog.getByText("Tonight's pick", { exact: true }).isVisible());
  check("winner detail notes the room's verdict", await winnerDialog.getByText("The room has spoken", { exact: true }).isVisible());
  await page.screenshot({ path: `${out}/03-detail-winner.png`, fullPage: true });
  await winnerDialog.getByRole("button", { name: "Close movie details" }).click();

  const meaningful = unexpectedErrors(errors);
  check("no unexpected console or page errors", meaningful.length === 0, meaningful.join(" | "));
} finally {
  deleteLobbies(lobbyIds);
  await browser.close();
}

console.log(JSON.stringify({ checks, errors, screenshots: out }, null, 2));
if (unexpectedErrors(errors).length) process.exitCode = 1;
