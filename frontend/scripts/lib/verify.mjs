import { chromium } from "playwright-core";
import { execFileSync } from "node:child_process";
import { mkdir } from "node:fs/promises";

export const base = process.env.WATCHLOG_URL ?? "http://localhost:5173";
export const outRoot = process.env.WATCHLOG_OUT ?? "/tmp/watchlog-verify";
export const passwords = {
  alice: "correct horse",
  bob: "correct horse",
  carol: "correct horse",
};

export async function outputDir(name) {
  const dir = `${outRoot}/${name}`;
  await mkdir(dir, { recursive: true });
  return dir;
}

export async function launchBrowser() {
  return chromium.launch({
    executablePath: process.env.CHROME_PATH ?? "/usr/bin/google-chrome",
    headless: true,
  });
}

export function createRecorder() {
  const checks = [];
  const errors = [];

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

  return { checks, errors, check, watch };
}

export function unexpectedErrors(errors, ignore = []) {
  return errors.filter(
    (error) =>
      !error.includes("401 (Unauthorized)") &&
      !error.includes("403 (Forbidden)") &&
      !error.includes("WebSocket is closed before the connection is established") &&
      !ignore.some((entry) => error.includes(entry)),
  );
}

export async function settle(page, wait = 350) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(wait);
}

export async function login(page, username = "alice", password = passwords[username]) {
  await page.goto(base + "/auth", { waitUntil: "networkidle" });
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(base + "/", { timeout: 10_000 });
}

export async function register(page, username, password = "testpass123") {
  await page.goto(base + "/auth", { waitUntil: "networkidle" });
  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Username").fill(username);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password").fill(password);
  await page.getByRole("button", { name: "Create account", exact: true }).last().click();
  await page.waitForURL(base + "/", { timeout: 10_000 });
}

export async function csrfHeaders(context) {
  const cookie = (await context.cookies(base)).find((entry) => entry.name === "wl_csrf");
  if (!cookie) throw new Error("No CSRF cookie in the browser context");
  return { "X-CSRF-Token": cookie.value, Origin: base };
}

export async function apiGroups(context) {
  const response = await context.request.get(`${base}/api/groups`);
  if (!response.ok()) throw new Error(`GET /api/groups: ${response.status()}`);
  return (await response.json()).groups;
}

export async function addFilmFromApi(context, groupId, tmdbId) {
  const response = await context.request.post(`${base}/api/groups/${groupId}/films`, {
    headers: await csrfHeaders(context),
    data: { tmdb_id: tmdbId, media_type: "movie" },
  });
  if (!response.ok()) {
    throw new Error(`POST /api/groups/${groupId}/films: ${response.status()} ${await response.text()}`);
  }
  return response.json();
}

export async function startGroupNight(page) {
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Start a movie night/i }).click();
  await page.getByRole("dialog").getByRole("button", { name: /Start the room/i }).click();
  await page.waitForURL(/\/lobby\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  return new URL(page.url()).pathname.split("/").pop();
}

export async function startOpenNight(page) {
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: /Start a movie night/i }).click();
  const dialog = page.getByRole("dialog");
  await dialog.locator(".choice-open").click();
  await dialog.getByRole("button", { name: /Start the room/i }).click();
  await page.waitForURL(/\/lobby\/[0-9a-f-]{36}$/, { timeout: 15_000 });
  return new URL(page.url()).pathname.split("/").pop();
}

function databaseSql(sql) {
  execFileSync(
    "docker",
    [
      "compose",
      "-f",
      "docker-compose.yml",
      "-f",
      "docker-compose.dev.yml",
      "exec",
      "-T",
      "database",
      "sh",
      "-c",
      `psql -U "$POSTGRES_USER" -d watchlog_v2 -v ON_ERROR_STOP=1 -c "${sql}"`,
    ],
    { cwd: "..", stdio: "pipe" },
  );
}

export function setLobbyPool(lobbyId, movieIds) {
  if (!movieIds.length) throw new Error("setLobbyPool needs at least one movie id");
  databaseSql(
    `UPDATE lobbies SET pool='[${movieIds.join(",")}]'::jsonb WHERE id='${lobbyId}'`,
  );
}

export function deleteLobbies(lobbyIds) {
  const ids = lobbyIds.filter(Boolean);
  if (!ids.length) return;
  databaseSql(
    `DELETE FROM lobbies WHERE id IN (${ids.map((id) => `'${id}'`).join(",")})`,
  );
}

export function deleteUsers(usernames) {
  const names = usernames.filter(Boolean);
  if (!names.length) return;
  databaseSql(
    `DELETE FROM users WHERE username IN (${names.map((name) => `'${name}'`).join(",")})`,
  );
}

export function resetLobbies() {
  databaseSql("DELETE FROM lobbies");
}
