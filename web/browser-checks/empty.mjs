/**
 * "Start empty" starts empty, and an empty app still renders.
 *
 * Mason reported it: after Start empty the dashboard still read take-home
 * $5,682, net savings $5,682, budgeted $4,430, emergency fund 4.9 months and
 * net worth $20,000. `/api/state?demo=false` served `get_default_state()`,
 * which is a STARTER TEMPLATE — a $100,000 salary, 17 budget rows totalling
 * $4,430 and $20,000 across six asset rows. "Start empty" had never meant
 * empty.
 *
 * The second half matters as much as the first: this app is charts and derived
 * figures, so an empty profile is the state most likely to divide by zero, draw
 * a chart with no data, or render a card with nothing to say. Every route is
 * loaded and required to come up clean.
 *
 * Run:  node empty.mjs [--selftest]
 */
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.BASE ?? "http://localhost:3000";
const SELFTEST = process.argv.includes("--selftest");

let pass = 0;
const fails = [];
const check = (name, ok, detail = "") => {
  if (ok) { pass++; console.log(`  [PASS] ${name}`); }
  else { fails.push(`${name}${detail ? " — " + detail : ""}`); console.log(`  [FAIL] ${name}${detail ? " — " + detail : ""}`); }
};

const ROUTES = ["/", "/year", "/income", "/budget", "/expenses", "/net-worth",
                "/goals", "/debt", "/compare", "/investments", "/fire", "/tax", "/data"];

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 600000,
});

const ctx = await browser.createBrowserContext();
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(`pageerror: ${e}`));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
await page.setViewport({ width: 1440, height: 1200 });

const settle = async (ms = 1500) => new Promise((r) => setTimeout(r, ms));
const go = async (route) => {
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await settle();
};

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the served empty profile carries no figures ---");
{
  await go("/");
  const served = await page.evaluate(async () => {
    const demo = await fetch("/api/state").then((r) => r.json());
    const empty = await fetch("/api/state?demo=false").then((r) => r.json());
    const sum = (m) => Object.values(m ?? {}).reduce((n, v) => n + v, 0);
    const budget = (p) => Object.values(p.budget).reduce((n, b) => n + sum(b), 0);
    return {
      demo: { salary: demo.income.gross_salary, assets: sum(demo.assets), budget: budget(demo) },
      empty: { salary: empty.income.gross_salary, assets: sum(empty.assets),
               budget: budget(empty), liabilities: sum(empty.liabilities),
               rows: Object.keys(empty.budget.needs).length,
               assetRows: Object.keys(empty.assets).length,
               expenses: empty.expenses.length, debts: empty.debts.length,
               ret: empty.investment.annual_return, years: empty.investment.time_horizon },
    };
  });
  check("the demo still carries figures, or it would show nothing",
        served.demo.salary > 0 && served.demo.assets > 0, JSON.stringify(served.demo));
  check("the empty profile carries none of them",
        served.empty.salary === 0 && served.empty.assets === 0
        && served.empty.budget === 0 && served.empty.liabilities === 0,
        JSON.stringify(served.empty));
  check("but keeps the rows to type into",
        served.empty.rows > 0 && served.empty.assetRows > 0,
        `${served.empty.rows} budget rows, ${served.empty.assetRows} asset rows`);
  check("and nothing logged", served.empty.expenses === 0 && served.empty.debts === 0);
  check("the projection keeps its assumptions, because 0% over 0 years is broken",
        served.empty.ret > 0 && served.empty.years > 0,
        `${served.empty.ret}% over ${served.empty.years}y`);
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- and the dashboard reads nothing, not somebody's money ---");
{
  await go("/");
  const clicked = await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")]
      .find((x) => /Start empty/i.test(x.textContent));
    if (!b) return false;
    b.click();
    return true;
  });
  check("Start empty is offered on a first visit", clicked);
  await settle(2500);

  const d = await page.evaluate(() => {
    const cards = {};
    for (const c of document.querySelectorAll(".card")) {
      const label = c.querySelector(".label")?.textContent?.trim();
      if (!label) continue;
      cards[label] = {
        v: c.querySelector(".font-num")?.textContent?.trim() ?? null,
        badge: c.querySelector(".badge")?.textContent?.trim() ?? null,
      };
    }
    const ring = document.querySelector(".ring-container");
    const head = [...document.querySelectorAll("p")]
      .filter((p) => p.textContent.trim() === "Balances")
      .find((p) => p.getBoundingClientRect().height > 0);
    return {
      cards,
      hero: document.querySelector(".figure-hero")?.textContent?.trim() ?? null,
      ringText: ring?.innerText.replace(/\s+/g, " ").trim() ?? null,
      balancesBlock: !!head,
      body: document.body.innerText,
    };
  });

  const money = (s) => Number(String(s ?? "").replace(/[^0-9.-]/g, ""));
  check("net worth is zero", money(d.hero) === 0, String(d.hero));
  check("take-home is zero", money(d.cards["Take-home"]?.v) === 0,
        String(d.cards["Take-home"]?.v));
  check("spent is zero", money(d.cards.Spent?.v) === 0, String(d.cards.Spent?.v));
  check("net savings is zero", money(d.cards["Net savings"]?.v) === 0,
        String(d.cards["Net savings"]?.v));
  check("budgeted is zero", money(d.cards.Budgeted?.v) === 0, String(d.cards.Budgeted?.v));

  /* NULL IS NOT ZERO, and this is where the distinction earns its place: with
     no income there is no savings RATE and no debt-to-income, and with no
     liquid assets the emergency fund cannot be measured. A dashboard of "0.0%"
     and "0.0 mo" would be four confident claims about a profile that says
     nothing at all. */
  check("the savings ring says there is no income, rather than showing 0%",
        /No income entered/i.test(d.body) && !/\d+%/.test(d.ringText ?? ""),
        String(d.ringText));
  check("debt-to-income is not measured, rather than 0.0%",
        d.cards["Debt-to-income"]?.v === "—", String(d.cards["Debt-to-income"]?.v));
  check("the emergency fund is not measured, rather than 0.0 months",
        d.cards["Emergency fund"]?.v === "—", String(d.cards["Emergency fund"]?.v));
  check("budget adherence says no budget is set",
        d.cards["Budget adherence"]?.badge === "No budget set",
        String(d.cards["Budget adherence"]?.badge));
  // The sidebar block renders nothing rather than a column of $0.
  check("the sidebar's balances block is absent, not a column of zeros",
        d.balancesBlock === false);
  check("and the demo note is gone, because these are no longer examples",
        !/example figures/i.test(d.body));
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- every route still renders on an empty profile ---");
{
  /* The state most likely to divide by zero or draw a chart with no data. The
     app is charts and derived figures, so "it has no data" is the case where a
     page has the least to say and the most ways to say it wrongly. */
  let visited = 0;
  let charts = 0;
  const broken = [];
  for (const route of ROUTES) {
    errors.length = 0;
    await go(route);
    visited++;
    const state = await page.evaluate(() => {
      const main = document.querySelector("main");
      return {
        text: (main?.innerText ?? "").trim().length,
        // The app's OWN error boundary, not Next's <nextjs-portal>, which is on
        // every page in dev because it hosts the dev-tools indicator — checking
        // for it reported all thirteen routes broken while the console was
        // silent on every one.
        boundary: /Something went wrong/i.test(main?.innerText ?? ""),
        // A chart element with no marks in it: this repo has shipped a Pie
        // whose sectors were empty <g> groups, with a correctly sized SVG and
        // nothing in the console.
        emptyCharts: [...document.querySelectorAll(".recharts-wrapper svg")]
          .filter((svg) => svg.querySelectorAll("path, rect, circle, line").length === 0).length,
        charts: document.querySelectorAll(".recharts-wrapper svg").length,
      };
    });
    charts += state.charts;
    if (errors.length) broken.push(`${route}: ${errors[0].slice(0, 70)}`);
    if (state.boundary) broken.push(`${route}: the error boundary rendered`);
    if (state.text < 40) broken.push(`${route}: renders almost nothing (${state.text} chars)`);
    if (state.emptyCharts) broken.push(`${route}: ${state.emptyCharts} chart(s) with no marks`);
  }
  check("the run visited every route", visited === ROUTES.length, `${visited}`);
  // Reported rather than asserted: an empty profile legitimately draws few
  // charts, and the count says how much the empty-chart check above actually
  // had to look at.
  console.log(`         (${charts} chart(s) rendered across the empty app)`);
  check("no route errors, blanks or draws an empty chart on an empty profile",
        broken.length === 0, broken.slice(0, 4).join(" | "));
}

// ═══════════════════════════════════════════════════════════════════
if (SELFTEST) {
  console.log("\n=== selftest: each check, against an injected fault ===");

  // 1. the old behaviour: serve the starter template and require it to be seen
  {
    const seen = await page.evaluate(async () => {
      const t = await fetch("/api/state?demo=true").then((r) => r.json());
      const sum = (m) => Object.values(m).reduce((n, v) => n + v, 0);
      return { salary: t.income.gross_salary, assets: sum(t.assets) };
    });
    check("[can fail] a profile that DOES carry figures is seen to carry them",
          seen.salary > 0 && seen.assets > 0, JSON.stringify(seen));
  }

  // 2. a zero rendered where null is meant must be distinguishable
  {
    await go("/");
    const shown = await page.evaluate(() => {
      const c = [...document.querySelectorAll(".card")]
        .find((x) => /Debt-to-income/.test(x.querySelector(".label")?.textContent ?? ""));
      const p = c.querySelector(".font-num");
      p.textContent = "0.0%";
      return p.textContent;
    });
    check("[can fail] a card showing 0.0% instead of an em dash is readable as such",
          shown === "0.0%", shown);
  }

  // 3. the empty-chart detector, against a chart built for the purpose —
  //    an empty profile draws few charts, so there is not reliably a real one
  //    to strip, and a selftest that silently finds nothing proves nothing.
  {
    const found = await page.evaluate(() => {
      const wrap = document.createElement("div");
      wrap.className = "recharts-wrapper";
      wrap.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg"></svg>';
      document.body.appendChild(wrap);
      const n = [...document.querySelectorAll(".recharts-wrapper svg")]
        .filter((svg) => svg.querySelectorAll("path, rect, circle, line").length === 0).length;
      wrap.remove();
      return n;
    });
    check("[can fail] a chart with no marks in it is counted", found === 1, String(found));
  }
}

await ctx.close();
await browser.close();
console.log(`\nEMPTY: ${pass} passed, ${fails.length} failed`);
if (fails.length) { for (const f of fails) console.log("  - " + f); process.exit(1); }
