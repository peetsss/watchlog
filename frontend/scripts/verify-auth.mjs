import {
  base,
  createRecorder,
  deleteUsers,
  launchBrowser,
  markUserVerified,
  outputDir,
  settle,
  unexpectedErrors,
} from "./lib/verify.mjs";

const out = await outputDir("auth");
const browser = await launchBrowser();
const { checks, errors, check, watch } = createRecorder();
const username = `verify_auth_${Date.now()}`;

try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  watch(page, "auth");

  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.waitForURL(base + "/auth", { timeout: 10_000 });
  check("anonymous home redirects to auth", new URL(page.url()).pathname === "/auth");
  check("auth page has the members entrance", await page.getByText(/members' entrance/i).isVisible());
  await settle(page);
  await page.screenshot({ path: `${out}/01-auth-desktop.png`, fullPage: true });

  await page.getByLabel(/^Username( or email)?$/).fill("alice");
  await page.getByLabel("Password", { exact: true }).fill("wrong password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByText("That login and password don't match.").waitFor({ timeout: 10_000 });
  check("bad credentials show an error", true);

  await page.getByLabel(/^Username( or email)?$/).fill("alice@example.com");
  await page.getByRole("tab", { name: "Create account" }).click();
  check("email identifier moves to the email field", (await page.getByLabel("Email", { exact: true }).inputValue()) === "alice@example.com");
  check("username field is left empty", (await page.getByLabel("Username", { exact: true }).inputValue()) === "");
  await page.getByRole("tab", { name: "Sign in" }).click();
  check("email returns to the sign-in identifier", (await page.getByLabel(/^Username( or email)?$/).inputValue()) === "alice@example.com");

  await page.getByRole("tab", { name: "Create account" }).click();
  await page.getByLabel("Username", { exact: true }).fill(username);
  await page.getByLabel("Email", { exact: true }).fill(`${username}@example.com`);
  await page.getByLabel("Password", { exact: true }).fill("testpass123");
  await page.getByLabel("Confirm password").fill("testpass123");
  await page.getByRole("button", { name: "Create account", exact: true }).last().click();
  await page.waitForURL(base + "/", { timeout: 10_000 });
  markUserVerified(username);
  await page.locator(".side-user strong").getByText(username, { exact: true }).waitFor({ timeout: 10_000 });
  check("registration signs the member in", true);
  check("member UI has no guest copy", (await page.getByText(/guest/i).count()) === 0);

  await page.reload({ waitUntil: "networkidle" });
  await page.locator(".side-user strong").getByText(username, { exact: true }).waitFor({ timeout: 10_000 });
  check("session survives a reload", true);
  const cookies = await context.cookies(base);
  check("session cookie is present", cookies.some((cookie) => cookie.name === "wl_session"));
  check("csrf cookie is present", cookies.some((cookie) => cookie.name === "wl_csrf"));

  await page.locator(".side-signout").click();
  await page.waitForURL(base + "/auth", { timeout: 10_000 });
  await page.getByRole("heading", { name: /Your seat is waiting/i }).waitFor({ timeout: 10_000 });
  const afterLogout = await context.cookies(base);
  check("sign out clears the session", !afterLogout.some((cookie) => cookie.name === "wl_session"));

  await page.goto(base + "/groups", { waitUntil: "networkidle" });
  await page.waitForURL(/\/auth\?next=/, { timeout: 10_000 });
  check("deep link keeps the return path", new URL(page.url()).searchParams.get("next") === "/groups");
  await page.getByLabel(/^Username( or email)?$/).fill(username);
  await page.getByLabel("Password", { exact: true }).fill("testpass123");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(base + "/groups", { timeout: 10_000 });
  check("sign in restores the return path", true);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.locator(".mobile-icon-button").click();
  await page.waitForURL(base + "/auth", { timeout: 10_000 });
  await page.getByRole("heading", { name: /Your seat is waiting/i }).waitFor({ timeout: 10_000 });
  await settle(page);
  await page.screenshot({ path: `${out}/02-auth-mobile.png`, fullPage: true });
  check("mobile sign out works", true);

  const meaningful = unexpectedErrors(errors);
  check("no unexpected console or page errors", meaningful.length === 0, meaningful.join(" | "));
} finally {
  deleteUsers([username]);
  await browser.close();
}

console.log(JSON.stringify({ checks, errors, screenshots: out }, null, 2));
if (unexpectedErrors(errors).length) process.exitCode = 1;
