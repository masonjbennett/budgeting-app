/**
 * Put holdings on /portfolio by DRIVING the page, and share the one
 * implementation between every check that needs them.
 *
 * WHY THIS EXISTS. `/compare` taught this repo that a route sweep walking a
 * page the demo profile leaves empty is indistinguishable from a sweep that
 * passes: both report clean, and the screen the page exists for was never
 * measured. `/portfolio` is the same shape — the served profile ships no
 * `holdings`, so the empty state is all a sweep would ever see, and every
 * figure, chart, table and coverage banner on the page would go unswept.
 *
 * WHY IT DRIVES THE UI RATHER THAN WRITING localStorage. `readLocalProfile`
 * validates the shape it reads and DROPS anything malformed, silently and
 * correctly — so a hand-built profile that is one field short would leave the
 * page empty while this helper reported success, and the check would pass over
 * a page it never populated. Clicking the buttons cannot lie about that.
 *
 * The set is chosen so the page has something to say about each thing it
 * claims to measure: two funds the table knows (one of them ten times dearer
 * than the other for the same index), one held in two accounts, an individual
 * stock, an untabled 401(k) fund so coverage is NOT 100%, employer stock, and
 * cash.
 *
 * THE UNTABLED FUND IS A COLLECTIVE TRUST, and deliberately the sharpest one
 * available. `VTIVX` — Vanguard Target Retirement 2045, the mutual fund — IS
 * in the table now, and a plan holding the TRUST version holds a different
 * vehicle with a different fee. The page must not match them, which is why
 * holdings resolve on ticker and never on name; the fixture holds the trust
 * with no symbol, so it lands uncovered, is NAMED as a collective trust, and
 * exercises the section that says why it can never be otherwise. It replaced
 * "Company Stock Fund", which fired nothing and left that section absent from
 * every run — the /compare lesson, where a fixture hides a whole screen.
 */

export const HOLDINGS = [
  { symbol: "VOO", label: "Vanguard S&P 500", kind: "fund", account: "401(k)", value: 50000 },
  { symbol: "SPY", label: "SPDR S&P 500", kind: "fund", account: "Brokerage", value: 25000 },
  { symbol: "VOO", label: "Vanguard S&P 500", kind: "fund", account: "Roth IRA", value: 12000 },
  { symbol: "NVDA", label: "Nvidia", kind: "stock", account: "Brokerage", value: 18000 },
  { symbol: "", label: "Vanguard Target Retirement 2045 Trust II", kind: "fund", account: "401(k)", value: 20000 },
  { symbol: "ACME", label: "Acme Corp", kind: "employer", account: "Brokerage", value: 9000 },
  { symbol: "", label: "Cash", kind: "cash", account: "Brokerage", value: 6000 },
];

/** A real workplace menu: a collective trust AND an untabled fund that is not
 *  one, so the unreachable money is PART of the uncovered money rather than
 *  all of it.
 *
 *  This is the common case in the wild and the fixture above cannot reach it —
 *  with a single uncovered holding the unreachable share is always 100%, and
 *  the page's other wording would be a branch nothing ever rendered. An
 *  unexercised guard reads as protection and enforces nothing; the Sankey's
 *  deleted minimum-height floor is the precedent.
 *
 *  $40k of $70k uncovered is unreachable, so the page must say 57.1% and must
 *  NOT say "all of it". */
export const PLAN_MENU = [
  { symbol: "VOO", label: "Vanguard S&P 500", kind: "fund", account: "Roth IRA", value: 30000 },
  { symbol: "", label: "Vanguard Target Retirement 2045 Trust II", kind: "fund", account: "401(k)", value: 40000 },
  { symbol: "", label: "Plan Growth Fund R6", kind: "fund", account: "401(k)", value: 30000 },
];

/** A portfolio most of whose money the fee table cannot see — the state the
 *  coverage floor exists for, and the one that must not print a confident
 *  weighted expense ratio as its headline. */
export const MOSTLY_UNCOVERED = [
  { symbol: "VOO", label: "Vanguard S&P 500", kind: "fund", account: "401(k)", value: 5000 },
  { symbol: "", label: "Plan Growth Fund R6", kind: "fund", account: "401(k)", value: 60000 },
  { symbol: "", label: "Plan Bond Fund R6", kind: "fund", account: "401(k)", value: 35000 },
];

/* React does not see a value assigned straight to `input.value` — its own
   descriptor is on the instance, so the change never reaches state and the
   field snaps back on the next render, having reported success. */
const SET = `(el, v) => {
  const proto = Object.getPrototypeOf(el);
  const desc = Object.getOwnPropertyDescriptor(proto, "value");
  desc.set.call(el, v);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}`;

export async function seedHoldings(page, rows = HOLDINGS) {
  /* Start from nothing. Signed-out figures persist to localStorage, so a
     second run in the same browser profile - sweep.mjs walks this route once
     per THEME - opens on the rows the first run left behind, and adding to
     them silently doubles the portfolio. The first version waited for exactly
     rows.length value fields and simply timed out, which at least failed
     loudly; the version that waited for "at least" would have measured a
     fourteen-holding page and called it seven. */
  for (let guard = 0; guard < 200; guard++) {
    /* ONE click per turn of the loop, with a yield between them. Clicking
       every Remove button inside a single page.evaluate does NOT remove every
       row: each handler filters the `holdings` array captured in its own
       closure, React has not re-rendered between the synchronous clicks, so
       all N handlers see the same starting array and the last one to run
       wins - six of seven rows survive. The loop looked correct and left the
       page populated, which is why the seed then timed out waiting for an
       empty table rather than reporting a wrong count. */
    const left = await page.evaluate(() => {
      const b = [...document.querySelectorAll("button")]
        .find((x) => /^Remove holding/i.test(x.getAttribute("aria-label") || ""));
      if (b) b.click();
      return document.querySelectorAll('[aria-label^="Value of holding"]').length;
    });
    if (left === 0) break;
    await new Promise((r) => setTimeout(r, 60));
  }
  await page.waitForFunction(
    () => document.querySelectorAll('[aria-label^="Value of holding"]').length === 0,
    { timeout: 20000 });

  for (let i = 0; i < rows.length; i++) {
    await page.evaluate(() => [...document.querySelectorAll("button")]
      .find((b) => /Add a holding/i.test(b.textContent))?.click());
    await new Promise((r) => setTimeout(r, 120));
  }
  await page.waitForFunction(
    (n) => document.querySelectorAll('[aria-label^="Value of holding"]').length === n,
    { timeout: 20000 }, rows.length);

  await page.evaluate((rows, setSrc) => {
    const set = eval(setSrc);
    rows.forEach((h, i) => {
      const q = (p) => document.querySelector(`[aria-label="${p} ${i + 1}"]`);
      set(q("Symbol for holding"), h.symbol);
      set(q("Name for holding"), h.label);
      set(q("Value of holding"), String(h.value));
      for (const sel of [q("Type of holding"), q("Account for holding")]) {
        if (!sel) continue;
        const want = sel === q("Type of holding") ? h.kind : h.account;
        const opt = [...sel.options].find((o) => o.value === want || o.textContent === want);
        if (opt) {
          sel.value = opt.value;
          sel.dispatchEvent(new Event("change", { bubbles: true }));
        }
      }
    });
  }, rows, SET);

  // The X-ray refetches on every change; wait for the figures, not a timer.
  await page.waitForFunction(
    () => /WHAT THIS IS/i.test(document.body.innerText)
       || /What this is/.test(document.body.innerText),
    { timeout: 30000 });
  await new Promise((r) => setTimeout(r, 400));
}
