/**
 * The Streamlit app still works against the modified engine.
 *
 * masonbennett-budget.streamlit.app is the live recruiter-safe link, it
 * auto-deploys from master, and it shares `calculations.py` with the web app.
 * So any change to the engine can take it down, and CLAUDE.md is explicit that
 * a green import proves nothing about it: Streamlit re-runs the script in a
 * long-lived process, so `import calculations` can hand back the copy already
 * in sys.modules. The check has to be a real page load, on every page.
 *
 * Run it before pushing anything that touches calculations.py.
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

await page.goto("http://localhost:8502", { waitUntil: "networkidle0", timeout: 120000 });
await page.waitForFunction(
  () => document.querySelectorAll('[data-testid="stApp"]').length > 0,
  { timeout: 90000 },
);
await new Promise((r) => setTimeout(r, 5000));

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
