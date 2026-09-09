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

import { MOSTLY_UNCOVERED, PLAN_MENU, seedHoldings } from "./fixtures/seed-holdings.mjs";

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
        /Vanguard Target Retirement 2045 Trust II/.test(t)
        && /\$20,000 is in 1 holding/.test(t));

  /* Not every gap is the same gap. A mistyped ticker is worth checking and a
     collective trust never resolves, and until this was measured the page
     told the reader the same thing about both — while blaming a cause
     ("institutional share classes with no public ticker") that turned out not
     to be what a 401(k) menu is mostly made of. */
  check("an uncovered holding that can NEVER be covered says so, and by what",
        /files nothing with the SEC/i.test(t)
        && /collective investment trust/i.test(t),
        "the unreachable block did not render");
  /* The share of the UNMEASURED money (not of the portfolio) is asserted in
     section 2b, where it is a real fraction. Here every uncovered dollar is
     unreachable, so the page says so in words instead — see below. */
  check("and it sends the reader to the document that does carry the fee",
        /annual fee disclosure/i.test(t));
  /* The whole point of the split: the tool must not tell somebody to go
     hunting for a ticker that does not exist. */
  check("it never suggests checking a symbol that cannot exist",
        !/check the symbol/i.test(t));
  check("the page's limits name collective trusts, with the measurement",
        /88% of the fund dollars/i.test(t) && /Form 11-K/i.test(t),
        "the limits list still blames untickered share classes");
  /* The fund table now carries VTIVX — the MUTUAL FUND of the same name and
     year. The trust is a different vehicle with a different fee, so matching
     them on the name would print a confident wrong number. Holdings resolve
     on TICKER, and the coverage percentage is what enforces it: $120,000 of
     $140,000 is measurable, and a page that had quietly matched the trust by
     name would report 100%. */
  /* Case-INSENSITIVE, and that is not a detail: `.label` uppercases the
     banner in CSS and `innerText` reflects text-transform, so this reads
     "MEASURED OVER 85.7% OF THIS PORTFOLIO". Same trap as the look-through's
     "BOTH" badge, and it failed here first on a page that was correct. */
  check("a trust is NOT matched to the same-named fund now in the table",
        /measured over 85\.7% of this portfolio/i.test(t),
        t.match(/measured over [\d.]+% of this portfolio/i)?.[0] || "absent");
  /* With one uncovered holding the unreachable share is the whole of it, and
     restating the same dollar figure three lines under itself read as a
     subset of itself. Found by looking at the rendered card. */
  check("where ALL the unmeasured money is unreachable, it is not restated",
        /all of it is in something that files nothing/i.test(t)
        && !/of what could not be measured/i.test(t),
        t.match(/[^\n]*could not be measured[^\n]*/i)?.[0] || "");

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
  // Provenance is SPLIT, not blanket. Most ratios are now the fund's own
  // filed figure; the seed deliberately includes SPY, which is a unit
  // investment trust and files no fund prospectus of this shape, so the
  // mixed branch is the one under test. Asserting only the all-sourced
  // sentence would pass on a page that never admits a gap.
  check("the page says where the fee figures came from",
        /own filed expense ratio, read from its SEC prospectus filing/.test(t));
  check("and names the funds whose ratio is still hand-written",
        /hand-written figure not yet checked against a filing/.test(t)
        && /SPDR S&P 500/.test(t));
  check("and never claims the whole table was verified",
        !/last verified/.test(t));

  // ── Look-through ──────────────────────────────────────────────
  //
  // The seed holds NVDA outright AND holds VOO, which holds NVDA. That pair
  // is the whole feature: the page can say a number nobody can read off a
  // statement. Asserted on the RENDERED page rather than the API, because
  // the section shipped with no browser assertion at all on its first run --
  // 22 passed before and after it existed.
  check("the page opens the funds up and names what is inside them",
        /counting through the funds/i.test(t) && /NVIDIA/i.test(t));
  check("and says what share of the portfolio it could actually see",
        /Measured across [\d.]+% of the portfolio/i.test(t),
        t.match(/Measured across [^.]*\./i)?.[0]?.slice(0, 90));
  // A floor, never a ceiling -- each fund stores its largest holdings only.
  check("and that every figure in it is the lowest it can be",
        /is not attributed to any company here/i.test(t)
        && /lowest.{0,20}it can be/i.test(t));
  // Case-INSENSITIVE deliberately: the badge is uppercased by CSS, and
  // innerText reflects text-transform, so a rendered "BOTH" failed
  // /\bboth\b/ on a page that was perfectly correct. Same trap as the
  // dashboard's month strip, whose visible capitals are also a transform.
  check("a company held outright AND through a fund is marked both",
        /\bboth\b/i.test(t)
        && /hold it outright .{0,10}and.{0,10} through a fund/i.test(t));
  check("and the look-through names its own source",
        /N-PORT filing with the SEC/i.test(t));

  check("no console errors while driving it", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));
  await page.close();
}

// ── 2b. A real menu: unreachable is PART of the unmeasured money ────
//
// The fixture above has one uncovered holding, so its unreachable share is
// always 100% and the page's other wording would be a branch nothing ever
// rendered. This is the common shape in the wild — a plan holding a
// collective trust AND a fund the table simply does not carry.
{
  const page = await open();
  await seedHoldings(page, PLAN_MENU);
  const t = await textOf(page);

  check("with a trust beside an untabled fund, the share is a real fraction",
        /57\.1% of what could not be measured/.test(t),
        t.match(/[\d.]+% of what could not be measured/)?.[0] || "absent");
  check("and only the trust is named as unreachable, not the untabled fund",
        /Vanguard Target Retirement 2045 Trust II/.test(t)
        && !/Plan Growth Fund R6[^\n]*collective/i.test(t));
  check("while the untabled fund is still reported as uncovered",
        /Plan Growth Fund R6/.test(t));
  check("no console errors on a mixed menu",
        page.__errors.length === 0, page.__errors.slice(0, 2).join(" | "));
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

  // The look-through table present but claiming to have seen everything --
  // the shape that would let the page read as a complete inventory.
  {
    const page = await open();
    await seedHoldings(page);
    await page.evaluate(() => {
      const el = [...document.querySelectorAll("p")]
        .find((n) => /is not attributed to any company here/i.test(n.textContent));
      if (el) el.textContent = "Measured across 100.0% of the portfolio.";
    });
    const t = await textOf(page);
    check("[selftest] a look-through claiming it saw everything is caught",
          !/is not attributed to any company here/i.test(t));
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

  /* An uncovered holding reported as a plain gap when it is a vehicle that
     can never be covered. This is the state the page was in before the
     11-K measurement, so the selftest reproduces a defect that shipped
     rather than one invented for the occasion. */
  {
    const page = await open();
    await seedHoldings(page);
    await page.evaluate(() => {
      const el = [...document.querySelectorAll("div")]
        .find((n) => /files nothing with the SEC/i.test(n.textContent)
                     && n.children.length < 4);
      if (el) el.remove();
    });
    const t = await textOf(page);
    check("[selftest] a page that does not say WHY a gap is permanent is caught",
          !/files nothing with the SEC/i.test(t));
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
