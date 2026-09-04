/**
 * The Streamlit app still works against the modified engine.
 *
 * masonbennett-budget.streamlit.app auto-deploys from master and shares
 * `calculations.py` with the web app, so any change to the engine can take it
 * down. CLAUDE.md is explicit that a green import proves nothing about it:
 * Streamlit re-runs the script in a long-lived process, so `import
 * calculations` can hand back the copy already in sys.modules. The check has
 * to be a real page load, on every page.
 *
 * Run it before pushing anything that touches calculations.py.
 *
 * IT IS THE FALLBACK NOW, NOT THE RECRUITER LINK — this header used to say the
 * opposite, and it stopped being true on 3 Sep 2026 when
 * budget.masonjbennett.com became the primary. That matters for what this
 * check is FOR: a backup is only a backup if it works, so `BASE` points it at
 * the DEPLOYMENT as well as at localhost. It was hardcoded to localhost:8502
 * and had therefore never once looked at the live app.
 *
 *   node streamlit.mjs                                    # local, port 8502
 *   BASE=https://masonbennett-budget.streamlit.app node streamlit.mjs
 *
 * Streamlit Cloud serves the app inside an iframe at `<host>/~/+/` and leaves
 * the outer document empty, so a probe pointed at the bare host measures
 * nothing and reports it as a dead app. The suffix is added here rather than
 * being something the caller has to know.
 */
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "out");
mkdirSync(OUT, { recursive: true });

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PAGES = ["Dashboard", "Income Setup", "Budget Builder", "Expense Tracker",
               "Net Worth", "Debt Payoff", "Savings Goals", "Investments",
               "FIRE Calculator", "Tax Estimator", "Data Management"];

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
const page = await browser.newPage();
await page.setViewport({ width: 1500, height: 1000 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));

const RAW = process.env.BASE ?? "http://localhost:8502";
// Streamlit Cloud frames the app; localhost serves it directly.
const TARGET = /streamlit\.app/.test(RAW) && !/~\/\+/.test(RAW)
  ? RAW.replace(/\/+$/, "") + "/~/+/"
  : RAW;
console.log(`  target: ${TARGET}`);
await page.goto(TARGET, { waitUntil: "networkidle0", timeout: 120000 });
/* An app that never boots is a FAILED CHECK, not a stack trace. Pointed at a
   URL with no app behind it this threw an unhandled TimeoutError — it did
   exit non-zero, so it failed, but a wall of puppeteer internals is not a
   report and the next reader has to work out whether the app or the check is
   broken. */
const booted = await page
  .waitForFunction(() => document.querySelectorAll('[data-testid="stApp"]').length > 0,
                   { timeout: 90000 })
  .then(() => true)
  .catch(() => false);
if (!booted) {
  check("the app boots at all", false, `no [data-testid="stApp"] at ${TARGET} after 90s`);
  await browser.close();
  console.log(`\nSTREAMLIT: ${pass} passed, ${fails.length} failed`);
  process.exit(1);
}
/* WAIT for the charts, do not sleep and hope.

   This was a flat 5s pause, which is ample against localhost and not against
   a deployment waking from sleep: pointed at the live app for the first time
   it reported "0 plotly charts" on a dashboard that draws four. Measured
   afterwards on the warm app, they appear 2s after `stApp` — so the check was
   impatient, the app was fine, and the failure was about cold start.

   Polling keeps it able to fail: if the charts never arrive the wait times
   out and the assertion below still reads 0. */
await page
  .waitForFunction(() => document.querySelectorAll(".js-plotly-plot").length > 0,
                   { timeout: 60000 })
  .catch(() => {});
await new Promise((r) => setTimeout(r, 2500));

const first = await page.evaluate(() => ({
  widgets: document.querySelectorAll('[data-testid^="st"]').length,
  charts: document.querySelectorAll(".js-plotly-plot").length,
  // Streamlit renders a Python traceback into the page rather than the console.
  exceptions: document.querySelectorAll('[data-testid="stException"]').length,
  errorText: [...document.querySelectorAll('[data-testid="stException"]')]
    .map((e) => e.textContent.slice(0, 200)),
  text: document.body.innerText.slice(0, 400),
  navItems: [...document.querySelectorAll('[data-testid="stSidebar"] button')]
    .map((b) => b.textContent.trim()),
}));

check("the app boots and renders", first.widgets > 50, `${first.widgets} widgets`);
check("no Python exception on the dashboard", first.exceptions === 0,
      first.errorText.join(" | "));
check("charts render", first.charts >= 1, `${first.charts} plotly charts`);
check("no ImportError anywhere in the page text",
      !/ImportError|ModuleNotFoundError|cannot import name/.test(first.text),
      first.text.slice(0, 160));

// Walk every page. An ImportError from a stale sys.modules copy shows up on
// the page that first touches the missing name, not necessarily the first one.
let visited = 0;
for (const label of PAGES) {
  const clicked = await page.evaluate((want) => {
    const btns = [...document.querySelectorAll('[data-testid="stSidebar"] button')];
    const b = btns.find((x) => x.textContent.trim().endsWith(want));
    if (!b) return false;
    b.click();
    return true;
  }, label);
  if (!clicked) { check(`nav to ${label}`, false, "no such nav button"); continue; }
  await new Promise((r) => setTimeout(r, 3500));
  const st = await page.evaluate(() => ({
    exceptions: document.querySelectorAll('[data-testid="stException"]').length,
    detail: [...document.querySelectorAll('[data-testid="stException"]')]
      .map((e) => e.textContent.slice(0, 220)).join(" | "),
    widgets: document.querySelectorAll('[data-testid^="st"]').length,
  }));
  visited++;
  check(`${label}: renders with no exception`,
        st.exceptions === 0 && st.widgets > 20,
        `${st.widgets} widgets · ${st.detail}`);
}

check("every page was reachable", visited === PAGES.length, `${visited}/${PAGES.length}`);
check("no uncaught JS errors", errors.length === 0, errors.slice(0, 2).join(" | "));

await page.screenshot({ path: join(OUT, "streamlit-after.png") });
await browser.close();
console.log(`\nSTREAMLIT: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
