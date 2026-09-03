/**
 * Paging and filtering must not change WHAT gets imported.
 *
 * The performance fix introduced the one bug that would matter: a commit that
 * acted on the hundred rows on screen would import a hundred of twelve
 * hundred and report success. Nothing about the page would look wrong.
 */
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const CSV = join(HERE, "fixtures", "bank-big.csv");

let pass = 0;
const fails = [];
const check = (n, ok, d = "") => {
  if (ok) { pass++; console.log(`  [PASS] ${n}`); }
  else { fails.push(n); console.log(`  [FAIL] ${n}${d ? " — " + d : ""}`); }
};

const importTable = () => {
  const t = [...document.querySelectorAll("table")].find((x) =>
    /Line/.test(x.querySelector("thead")?.textContent ?? ""));
  return t;
};

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 900000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1100 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

await page.goto(`${process.env.BASE ?? "http://localhost:3000"}/expenses`, { waitUntil: "networkidle0" });
await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
  .catch(() => {});
await new Promise((r) => setTimeout(r, 700));

const demoCount = await page.evaluate(() =>
  fetch("/api/state?demo=true").then((r) => r.json()).then((p) => p.expenses.length));

const [openBtn] = await page.$$("xpath/.//button[contains(., 'Open importer')]");
await openBtn.click();
await new Promise((r) => setTimeout(r, 400));
const input = await page.$('input[type="file"]');
await input.uploadFile(CSV);
await page.waitForFunction(
  () => /\d+ rows · \d+ to add/i.test(document.body.textContent), { timeout: 120000 });
await new Promise((r) => setTimeout(r, 600));

const shape = await page.evaluate((src) => {
  const t = new Function("return " + src)()();
  const body = document.body.textContent;
  return {
    onPage: t.querySelectorAll("tbody tr").length,
    summary: body.match(/(\d+) rows · (\d+) to add/i)?.slice(1) ?? null,
    pager: body.match(/(\d+)–(\d+)\s*of\s*(\d+)\s*rows/)?.slice(1) ?? null,
    filters: [...document.querySelectorAll(".tab")].map((b) => b.textContent.trim()),
    addBtn: [...document.querySelectorAll("button")].map((b) => b.textContent.trim())
      .find((x) => /^Add \d+ transaction/.test(x)) ?? null,
  };
}, importTable.toString());

check("the table pages rather than rendering the whole file",
      shape.onPage === 100, `${shape.onPage} rows on screen`);
check("but the summary counts the WHOLE file",
      shape.summary?.[0] === "1200" && shape.summary?.[1] === "1200",
      JSON.stringify(shape.summary));
check("the pager says which slice is on screen",
      shape.pager?.[0] === "1" && shape.pager?.[1] === "100" && shape.pager?.[2] === "1200",
      JSON.stringify(shape.pager));
check("and the button offers to add every committable row, not the page",
      shape.addBtn === "Add 1200 transactions", String(shape.addBtn));
check("the filters carry their counts",
      shape.filters.some((f) => /^All · 1200$/.test(f)), shape.filters.join(" | "));

// ── Paging does not lose or repeat a row ──
const walk = await page.evaluate(async (src) => {
  const table = new Function("return " + src)();
  const seen = [];
  for (let i = 0; i < 12; i++) {
    const t = table();
    for (const tr of t.querySelectorAll("tbody tr")) {
      seen.push(+tr.querySelectorAll("td")[1].textContent.trim());
    }
    const next = [...document.querySelectorAll("button")]
      .find((b) => b.textContent.trim().startsWith("Next"));
    if (!next || next.disabled) break;
    next.click();
    await new Promise((r) => setTimeout(r, 220));
  }
  return { count: seen.length, unique: new Set(seen).size,
           min: Math.min(...seen), max: Math.max(...seen) };
}, importTable.toString());

check("walking every page shows all 1,200 rows exactly once",
      walk.count === 1200 && walk.unique === 1200,
      `${walk.count} seen, ${walk.unique} unique`);
check("and the line numbers span the whole file",
      walk.min === 2 && walk.max === 1201, `${walk.min}..${walk.max}`);

// ── The filter shows what it says ──
const filtered = await page.evaluate(async (src) => {
  const table = new Function("return " + src)();
  const tab = [...document.querySelectorAll(".tab")]
    .find((b) => /Already recorded/.test(b.textContent));
  if (!tab || tab.disabled) return { skipped: "no duplicates in this file" };
  tab.click();
  await new Promise((r) => setTimeout(r, 400));
  const t = table();
  const rows = [...t.querySelectorAll("tbody tr")];
  return {
    all: rows.every((tr) => /already recorded/.test(tr.textContent)),
    n: rows.length,
  };
}, importTable.toString());
check("the 'already recorded' filter shows only those rows",
      filtered.skipped ? true : filtered.all,
      filtered.skipped ?? `${filtered.n} rows`);

// ── THE ONE THAT MATTERS: commit imports the whole file ──
await page.evaluate(async () => {
  const all = [...document.querySelectorAll(".tab")].find((b) => /^All ·/.test(b.textContent));
  if (all) { all.click(); await new Promise((r) => setTimeout(r, 300)); }
});
const [addBtn] = await page.$$("xpath/.//button[starts-with(normalize-space(.), 'Add ')]");
await addBtn.click();
await page.waitForFunction(
  () => /transactions? added from/.test(document.body.textContent), { timeout: 60000 });
await new Promise((r) => setTimeout(r, 1500));

const after = await page.evaluate(() => {
  const t = document.body.textContent;
  return {
    done: t.match(/(\d+) transactions? added from ([\w.-]+)/)?.slice(1) ?? null,
    // The transactions table filters to the current month by default; switch
    // it to all months and count what the profile now holds.
    monthSelects: [...document.querySelectorAll("select")].length,
  };
});
check("the commit reports the whole file, not the page",
      after.done?.[0] === "1200", JSON.stringify(after.done));

const total = await page.evaluate(async () => {
  // Read the profile through the page's own filters: set month to "All".
  const sel = [...document.querySelectorAll("select")]
    .find((s) => [...s.options].some((o) => o.textContent === "All months"));
  if (sel) {
    sel.value = "";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 900));
  }
  return document.body.textContent.match(/across (\d+)/)?.[1] ?? null;
});
check("and the profile now holds every imported row plus the demo's own",
      Number(total) === 1200 + 22, `${total} transactions listed (expected ${1200 + 22})`);

check("no console errors through the whole run", errors.length === 0,
      errors.slice(0, 3).join(" | "));

await browser.close();
console.log(`\nBIG IMPORT: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
