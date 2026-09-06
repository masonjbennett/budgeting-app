/**
 * /portfolio — the X-ray, driven.
 *
 * `sweep.mjs` now seeds this route and measures colour, contrast, charts and
 * overflow on it. What is HERE is the set of claims the page makes that a
 * sweep cannot judge, and every one of them is a claim about honesty rather
 * than about layout:
 *
 *   1. The coverage banner is ABOVE the first figure. Every number on this
 *      page is measured over some share of the money, and a weighted expense
 *      ratio taken across a third of a portfolio is indistinguishable from one
 *      taken across all of it. "Above" is the whole design; a footnote is not.
 *   2. Below the coverage floor the fee card LEADS with the caveat instead of
 *      the number. A page that always prints the figure first has not
 *      implemented the floor, and asserting only the healthy case would pass
 *      on one that never withholds anything.
 *   3. Employer stock names the row the reader marked. The first version put
 *      a checkbox under the table and marked the LARGEST position — driving it
 *      labelled Vanguard S&P 500 as the employer, which is the app asserting
 *      something nobody told it.
 *   4. "Effective holdings" is a count and must not wear a currency symbol.
 *      It shipped as "$3.5" because `fmt` is a money formatter.
 *   5. The page never claims to see inside a fund.
 *
 * Run:  node portfolio.mjs [--selftest]
 *       BASE=https://budget.masonjbennett.com node portfolio.mjs
 */
import puppeteer from "puppeteer-core";

import { MOSTLY_UNCOVERED, seedHoldings } from "./fixtures/seed-holdings.mjs";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.BASE ?? "http://localhost:3000";
const SELFTEST = process.argv.includes("--selftest");

let pass = 0;
const fails = [];
const check = (name, ok, detail = "") => {
  if (ok) { pass++; console.log(`  [PASS] ${name}`); }
  else { fails.push(`${name}${detail ? " — " + detail : ""}`); console.log(`  [FAIL] ${name}${detail ? " — " + detail : ""}`); }
};

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 600000,
});

/* An isolated context per section: signed-out figures persist to
   localStorage, so holdings seeded by one section would still be there for
   the next, and every section here begins by adding rows to an empty page. */
async function open({ width = 1440, theme = "light" } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  // Close the CONTEXT only — closing the page and then the context tears the
  // same frames down twice, which raises "detached Frame" from a CDP handler.
  page.close = async () => {
    await new Promise((r) => setTimeout(r, 80));
    await ctx.close().catch(() => {});
  };
  await page.setViewport({ width, height: 1400 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.evaluateOnNewDocument((t) => {
    try { localStorage.setItem("mjb_budget_theme", t); } catch {}
  }, theme);
  await page.goto(BASE + "/portfolio", { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 600));
  page.__errors = errors;
  return page;
}

const textOf = (page) => page.evaluate(() => document.body.innerText);

/** The top of the DEEPEST element whose text matches, or null.
 *
 *  Deepest, not first. Taking the first in document order returns an ancestor
 *  that merely CONTAINS the words -- the page wrapper qualifies for every
 *  regex -- so the banner and the figures both reported a top of 0 and the
 *  ordering assertion compared nothing with nothing. */
const topOf = (page, re) => page.evaluate((src) => {
  const rx = new RegExp(src, "i");
  const hits = [...document.querySelectorAll("p, h1, h2, div")]
    .filter((n) => rx.test(n.textContent) && n.getBoundingClientRect().height > 0);
  const el = hits.find((n) => !hits.some((o) => o !== n && n.contains(o)));
  return el ? el.getBoundingClientRect().top + window.scrollY : null;
}, re.source);

console.log("=".repeat(70));
console.log(`/portfolio — the X-ray, driven   (${BASE})`);
console.log("=".repeat(70));

// ── 1. The empty state says what to do and measures nothing ─────────
{
  const page = await open();
  const t = await textOf(page);
  check("the empty page invites holdings rather than reporting zeros",
        /Add what someone holds/i.test(t)
        && !/effective holdings/i.test(t) && !/weighted average expense/i.test(t));
  check("and it explains why dollars rather than shares",
        /a share count would need a live price/i.test(t));
  await page.close();
}

// ── 2. Populated: the banner leads, the figures follow ──────────────
{
  const page = await open();
  await seedHoldings(page);
  const t = await textOf(page);

  check("the page reports a total and a position count",
        /\$140,000\b/.test(t) && /across 7/i.test(t), t.match(/across \d+/i)?.[0]);

  const banner = await topOf(page, /Measured over .* of this portfolio/);
  const firstFigure = await topOf(page, /What this is/);
  check("the coverage banner sits ABOVE the first figure on the page",
        banner !== null && firstFigure !== null && banner < firstFigure,
        `banner ${banner} vs figures ${firstFigure}`);
  check("and it names the holdings it could not measure, in dollars",
        /Company Stock Fund/.test(t) && /\$20,000 is in 1 holding/.test(t));

  check("effective holdings is a count, not an amount",
        /EFFECTIVE HOLDINGS\s*\n\s*\d+\.\d/i.test(t) && !/EFFECTIVE HOLDINGS\s*\n\s*\$/i.test(t),
        t.match(/EFFECTIVE HOLDINGS\s*\n\s*\S+/i)?.[0]);

  // The reader marked ONE row. The page must name that row.
  check("employer stock names the holding the reader marked",
        /EMPLOYER STOCK/i.test(t) && /is Acme Corp/.test(t)
        && !/is Vanguard S&P 500\./.test(t),
        t.match(/of the portfolio \(\$[\d,]+\) is [^.]+\./)?.[0]);

  check("the same fund in two accounts is reported as one bet",
        /VOO is held twice/i.test(t)
        && /401\(k\) and Roth IRA|Roth IRA and 401\(k\)/.test(t));

  check("a holding the table does not carry reads as unmeasured, never free",
        /not in table/i.test(t));

  // The page's central limit, and it must be stated rather than implied.
  check("the page says its concentration figure is a floor",
        /lowest the real figures can be/i.test(t)
        && /cannot see inside a fund/i.test(t));
  check("and it says nothing here is a recommendation",
        /None of it is a recommendation to buy, sell or hold/i.test(t));
  check("the fee table's date is on the page",
        /compiled \d{4}-\d{2}-\d{2}/.test(t));
  // The ratios have not been checked against the issuers, and the page has to
  // SAY so. A date beside a fee reads as provenance; without this the reader
  // is told when the table was made and left to assume it was verified —
  // which is the more damaging half of the claim, on the one figure here
  // somebody might act on.
  check("and it does not claim they were verified",
        /not yet checked against the issuers/.test(t)
        && !/last verified/.test(t));

  check("no console errors while driving it", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));
  await page.close();
}

// ── 3. The coverage floor: the caveat takes the headline ────────────
{
  const page = await open();
  await seedHoldings(page, MOSTLY_UNCOVERED);
  const t = await textOf(page);

  check("below the floor the fee card leads with the caveat, not the ratio",
        /Too little of this portfolio to lead with/i.test(t));
  check("and the figure is still given, against the money it describes",
        /describes \$5,000, not \$100,000/.test(t),
        t.match(/describes [^.]+\./)?.[0]);
  // Concentration needs no lookup, so low coverage must not suppress it.
  check("concentration is still reported, because it needs no lookup",
        /EFFECTIVE HOLDINGS/i.test(t) && /LARGEST POSITION/i.test(t));
  await page.close();
}

// ── 4. Proof these can fail ─────────────────────────────────────────
if (SELFTEST) {
  console.log("\n--- selftest: each check must fire against an injected fault ---");

  // The banner moved below the figures — the defect the design exists to
  // prevent, and one that looks completely normal in a screenshot.
  {
    const page = await open();
    await seedHoldings(page);
    await page.evaluate(() => {
      const b = [...document.querySelectorAll("div")]
        .find((n) => /Measured over .* of this portfolio/i.test(n.textContent)
                     && n.className.includes("card"));
      document.querySelector("main, body").appendChild(b);
    });
    const banner = await topOf(page, /Measured over .* of this portfolio/);
    const figures = await topOf(page, /What this is/);
    check("[selftest] a banner moved below the figures is caught",
          !(banner < figures), `banner ${banner} vs figures ${figures}`);
    await page.close();
  }

  // The count formatted as money — exactly how it shipped.
  {
    const page = await open();
    await seedHoldings(page);
    await page.evaluate(() => {
      const el = [...document.querySelectorAll("p, span, div")]
        .find((n) => /^\d+\.\d$/.test(n.textContent.trim()));
      if (el) el.textContent = "$" + el.textContent.trim();
    });
    const t = await textOf(page);
    check("[selftest] a currency symbol on the count is caught",
          /EFFECTIVE HOLDINGS\s*\n\s*\$/i.test(t));
    await page.close();
  }

  // A fee ratio printed as the headline over a portfolio nobody could measure.
  {
    const page = await open();
    await seedHoldings(page, MOSTLY_UNCOVERED);
    await page.evaluate(() => {
      const el = [...document.querySelectorAll("p")]
        .find((n) => /Too little of this portfolio/i.test(n.textContent));
      if (el) el.textContent = "0.03%";
    });
    const t = await textOf(page);
    check("[selftest] a fee figure leading a low-coverage page is caught",
          !/Too little of this portfolio to lead with/i.test(t));
    await page.close();
  }
}

await browser.close();

console.log("\n" + "=".repeat(70));
console.log(`RESULTS: ${pass} passed, ${fails.length} failed`);
if (fails.length) {
  for (const f of fails) console.log("  - " + f);
  console.log("=".repeat(70));
  process.exit(1);
}
console.log("=".repeat(70));
