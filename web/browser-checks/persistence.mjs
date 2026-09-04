/**
 * Signed-out work survives a refresh — and the guards hold.
 *
 * Not just the happy path: a corrupt payload, a payload from something else,
 * and a browser that throws on every storage access all have to leave the app
 * working, because the alternative to losing one profile is blanking the app
 * for everyone holding a bad one.
 */
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.BASE ?? "http://localhost:3000";
const KEY = "mjb_budget_profile_v1";

let pass = 0;
const fails = [];
const check = (n, ok, d = "") => {
  if (ok) { pass++; console.log(`  [PASS] ${n}`); }
  else { fails.push(n); console.log(`  [FAIL] ${n}${d ? " — " + d : ""}`); }
};

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 600000,
});

async function fresh() {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 1400, height: 1000, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.log(`     [pageerror] ${String(e).slice(0, 120)}`));
  return { ctx, page };
}
async function go(page, route) {
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 1300));
}
const ready = (page) => page.evaluate(() =>
  document.body.innerText.length > 400 && !/could not load/i.test(document.body.innerText));

/* ── 1. the feature ───────────────────────────────────────────────────── */
console.log("--- a category survives a refresh ---");
{
  const { ctx, page } = await fresh();
  await go(page, "/budget");
  await page.click('input[placeholder="Add a category…"]');
  await page.type('input[placeholder="Add a category…"]', "ZZKeepMe", { delay: 10 });
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim() === "Add");
    if (b && !b.disabled) b.click();
  });
  await new Promise((r) => setTimeout(r, 1200));
  check("it is added", await page.evaluate(() => document.body.innerText.includes("ZZKeepMe")));

  const stored = await page.evaluate((k) => {
    const raw = localStorage.getItem(k);
    return raw ? { len: raw.length, hasCat: raw.includes("ZZKeepMe") } : null;
  }, KEY);
  check("it was written to localStorage", stored !== null && stored.hasCat,
        JSON.stringify(stored));

  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 1500));
  check("it is STILL there after a reload",
        await page.evaluate(() => document.body.innerText.includes("ZZKeepMe")));

  await go(page, "/expenses");
  check("and other pages see it", await page.evaluate(() =>
    [...document.querySelectorAll("select option")].map((o) => o.textContent.trim())
      .includes("ZZKeepMe")));

  // Reset must overwrite the stored copy, or the reset does not survive either.
  await go(page, "/data");
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => /load demo profile/i.test(x.textContent));
    if (b) b.click();
  });
  await new Promise((r) => setTimeout(r, 800));
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => /load demo profile|confirm|yes/i.test(x.textContent));
    if (b) b.click();
  });
  await new Promise((r) => setTimeout(r, 2500));
  await page.reload({ waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 2000));
  await go(page, "/budget");
  check("a reset to demo also clears it from storage",
        !(await page.evaluate(() => document.body.innerText.includes("ZZKeepMe"))));
  await ctx.close();
}

/* ── 2. a corrupt payload must not blank the app ──────────────────────── */
console.log("\n--- the guards ---");
for (const [name, value] of [
  ["unparseable JSON", "{not json at all"],
  ["valid JSON, wrong shape", JSON.stringify({ hello: "world" })],
  ["an error object", JSON.stringify({ error: "boom" })],
  ["an empty object", JSON.stringify({})],
  ["a truncated profile", JSON.stringify({ income: { gross_salary: 1 } })],
]) {
  const { ctx, page } = await fresh();
  await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
  await page.evaluate(({ k, v }) => localStorage.setItem(k, v), { k: KEY, v: value });
  await go(page, "/budget");
  const ok = await ready(page);
  const cleared = await page.evaluate((k) => localStorage.getItem(k), KEY);
  check(`${name}: the app still renders`, ok);
  check(`${name}: and the bad copy was dropped`,
        cleared === null || cleared !== value, String(cleared).slice(0, 40));
  await ctx.close();
}

/* ── 3. storage that throws on every access ───────────────────────────── */
{
  const { ctx, page } = await fresh();
  await page.evaluateOnNewDocument(() => {
    const boom = () => { throw new Error("SecurityError: storage disabled"); };
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      get() { return { getItem: boom, setItem: boom, removeItem: boom }; },
    });
  });
  await go(page, "/budget");
  check("storage that throws does not take the app down", await ready(page));
  const canEdit = await page.evaluate(() => {
    const el = document.querySelector('input[placeholder="Add a category…"]');
    return !!el;
  });
  check("and the page is still usable", canEdit);
  await ctx.close();
}

await browser.close();
console.log(`\nPERSISTENCE: ${pass} passed, ${fails.length} failed`);
for (const f of fails) console.log(`  [BROKEN] ${f}`);
process.exit(fails.length ? 1 : 0);
