/**
 * The phone, measured rather than looked at.
 *
 * The checks that already existed prove the layout does not BREAK at 375px:
 * no horizontal overflow on `/`, the drawer opens and closes, focus returns.
 * They proved nothing about whether the thing is usable one-handed, because
 * none of them ever focused an input, measured a tap target, or asked which
 * table columns were actually on screen. Everything below was a real defect on
 * the live site in September 2026 and every one of them was invisible to a
 * green suite AND to a screenshot.
 *
 *   1. TEXT-ENTRY CONTROLS ARE >= 16px ON A TOUCH DEVICE. Mobile Safari zooms
 *      the viewport when you focus a field under 16px and does not zoom back
 *      out on blur — which is the mechanism behind "I had to pinch". 74
 *      controls across 10 routes were 14px, and the two /expenses filters were
 *      11px. HEADLESS CHROME DOES NOT IMPLEMENT THE ZOOM, so this can only
 *      ever be caught as a NUMBER; there is no rendering to look at.
 *   2. And the desktop type is NOT bumped with it. The fix is conditioned on
 *      `pointer: coarse`; a fix that also fired on a mouse would be a silent
 *      redesign of every form in the app.
 *   3. NO SECTION HEADER OVERFLOWS, AND NONE LOSES ITS HAIRLINE. The slug is
 *      [bar] [title] [hairline] [action] and it did not wrap, so /expenses ran
 *      107px past the right edge of a phone. The hairline is `flex-1` with a
 *      basis of 0, so it surrenders its width silently — two headers were
 *      measured at exactly the available width with a rule of ZERO, one
 *      character from overflowing, and nothing anywhere reported it.
 *   4. NO TABLE SCROLLS SIDEWAYS. A table inside `overflow-x-auto` does not
 *      overflow the PAGE, so every horizontal-overflow check in this repo
 *      passes on it, correctly. The question they cannot ask is whether the
 *      column carrying the number is on screen: /expenses hid AMOUNT, /year
 *      hid Spent, Of budget and Variance — every figure it reports.
 *   5. EVERY CONTROL CLEARS 24x24 (WCAG 2.2 AA 2.5.8). The delete buttons in
 *      the /debt and /expenses tables were bare glyphs at 11x21 — the smallest
 *      controls in the app, for a destructive action with no confirmation.
 *
 * 639 and 640 are both checked on purpose. The columns come back at 640px, so
 * that pair is where a table could return before it fits — a gap that would be
 * invisible at any of the widths anyone thinks to test.
 *
 * Run:  node mobile.mjs            (add --selftest to prove it can fail)
 */
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const BASE = process.env.BASE ?? "http://localhost:3000";
const SELFTEST = process.argv.includes("--selftest");
const ROUTES = ["/", "/year", "/income", "/budget", "/expenses", "/net-worth",
                "/goals", "/debt", "/compare", "/investments", "/fire", "/tax", "/data"];

// What a healthy run must FIND, not just what it must not flag. A run that
// looks at nothing reports zero problems: during this work a probe printed
// "0 problems" across all 13 routes while every page was a 500 from a JSX
// parse error, because it counted failures and never counted subjects.
const EXPECT_CONTROLS = 60;   // 74 today
const EXPECT_HEADERS = 30;    // 38 today, at one width
const EXPECT_TAPS = 100;      // 130 today
const EXPECT_TABLES = 4;      // 5 today

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

async function pageAt(width, { touch = width < 700 } = {}) {
  const p = await browser.newPage();
  await p.setViewport({
    width, height: 900, deviceScaleFactor: 1,
    isMobile: touch, hasTouch: touch,
  });
  return p;
}
async function go(p, route) {
  await p.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await p.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 600));
}

/* ── probes ──────────────────────────────────────────────────────────── */

// A checkbox, radio or range never opens a keyboard and never triggers the
// zoom, so they are not text entry and are excluded rather than exempted.
const FIELDS = () => {
  const entry = new Set(["text", "number", "email", "password", "search",
                         "tel", "url", "date", "month", ""]);
  const out = [];
  for (const el of document.querySelectorAll("input, select, textarea")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    const t = (el.getAttribute("type") || "").toLowerCase();
    if (el.tagName === "INPUT" && !entry.has(t)) continue;
    out.push({
      tag: el.tagName.toLowerCase() + (t ? `[${t}]` : ""),
      cls: String(el.className || "").slice(0, 24),
      fs: parseFloat(getComputedStyle(el).fontSize),
    });
  }
  return out;
};

const HEADERS = () => {
  const de = document.documentElement;
  const out = [];
  for (const head of document.querySelectorAll("section.mb-10 > div.mb-4")) {
    const rule = head.querySelector(":scope > .rule");
    const h2 = head.querySelector("h2");
    const r = head.getBoundingClientRect();
    out.push({
      title: (h2 ? h2.textContent : "?").trim().slice(0, 34),
      overflows: r.right > de.clientWidth + 1,
      ruleW: rule ? Math.round(rule.getBoundingClientRect().width) : null,
    });
  }
  return { pageOverflow: de.scrollWidth - de.clientWidth, out };
};

// Only cells that are actually displayed. A `display:none` <th> has a zero
// rect, which an earlier version of this reported as "off screen at -20" —
// the check inventing the very defect it exists to find.
const TABLES = () => {
  const out = [];
  for (const t of document.querySelectorAll("table")) {
    const sc = t.closest(".overflow-x-auto") || t.parentElement;
    const scRect = sc.getBoundingClientRect();
    const cols = [...t.querySelectorAll("thead th")]
      .filter((th) => getComputedStyle(th).display !== "none")
      .map((th) => {
        const r = th.getBoundingClientRect();
        return {
          name: (th.textContent || "").trim().slice(0, 14) || "(actions)",
          vis: r.left >= scRect.left - 1 && r.right <= scRect.right + 1,
        };
      });
    if (!cols.length) continue;
    out.push({ hidden: sc.scrollWidth - sc.clientWidth, cols });
  }
  return out;
};

const TAPS = () => {
  const out = [];
  // Inline text links are exempt from 2.5.8 and are excluded by the selector
  // rather than filtered afterwards, so the exemption is stated in one place.
  const sel = 'button, [role="button"], input[type="checkbox"], input[type="radio"], summary';
  for (const el of document.querySelectorAll(sel)) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") continue;
    out.push({
      w: Math.round(r.width), h: Math.round(r.height),
      text: (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 22),
      label: el.getAttribute("aria-label") || "",
    });
  }
  return out;
};

/* ── 1 + 2. the focus-zoom threshold ─────────────────────────────────── */
console.log("\n--- text entry is 16px on touch, and untouched on a mouse ---");
{
  for (const [what, width, touch, wantMin] of [
    ["touch", 375, true, 16],
    ["mouse", 1440, false, null],
  ]) {
    const p = await pageAt(width, { touch });
    let total = 0;
    const under = [];
    const sizes = new Set();
    for (const route of ROUTES) {
      await go(p, route);
      for (const f of await p.evaluate(FIELDS)) {
        total++;
        sizes.add(f.fs);
        if (f.fs < 16) under.push(`${route} ${f.tag} ${f.fs}px`);
      }
    }
    check(`${what}: the run found the controls at all`, total >= EXPECT_CONTROLS,
          `${total} found, expected ~74`);
    if (wantMin) {
      check(`${what}: every text-entry control is >= 16px, so Safari cannot zoom`,
            under.length === 0, `${under.length} under: ${under.slice(0, 3).join(", ")}`);
    } else {
      // The point is that the coarse-pointer rule did NOT fire here. If every
      // control were 16px on a mouse too, the media query is not doing what it
      // claims and the desktop type scale has silently moved.
      check(`${what}: desktop type is NOT bumped — the rule is pointer-conditional`,
            under.length > 0, `all ${total} controls are >= 16px on a mouse`);
      console.log(`         (desktop sizes: ${[...sizes].sort((a, b) => a - b).join(", ")}px)`);
    }
    await p.close();
  }
}

/* ── 3. the section slug ─────────────────────────────────────────────── */
console.log("\n--- section headers wrap, and keep their hairline ---");
{
  let headers = 0;
  const bad = [];
  for (const width of [375, 414, 768, 1440]) {
    const p = await pageAt(width);
    for (const route of ROUTES) {
      await go(p, route);
      const { pageOverflow, out } = await p.evaluate(HEADERS);
      if (pageOverflow > 1) bad.push(`${route}@${width} page overflows ${pageOverflow}px`);
      for (const h of out) {
        headers++;
        if (h.overflows) bad.push(`${route}@${width} "${h.title}" past the edge`);
        // A slug with no rule is not an overflow, so nothing else reports it.
        if (h.ruleW !== null && h.ruleW < 6) bad.push(`${route}@${width} "${h.title}" rule ${h.ruleW}px`);
      }
    }
    await p.close();
  }
  check("the run found the headers at all", headers >= EXPECT_HEADERS * 4,
        `${headers} renders`);
  check("no header overflows and none loses its hairline, at 375/414/768/1440",
        bad.length === 0, bad.slice(0, 3).join(" | "));
}

/* ── 4. tables ───────────────────────────────────────────────────────── */
console.log("\n--- no table scrolls sideways, so no figure is off screen ---");
{
  let tables = 0;
  const bad = [];
  // 639 and 640 straddle the breakpoint where the hidden columns come back.
  for (const width of [375, 414, 639, 640, 1440]) {
    const p = await pageAt(width);
    for (const route of ROUTES) {
      await go(p, route);
      for (const t of await p.evaluate(TABLES)) {
        tables++;
        if (t.hidden > 1) {
          const off = t.cols.filter((c) => !c.vis).map((c) => c.name);
          bad.push(`${route}@${width} ${t.hidden}px hidden — ${off.join(", ") || "?"}`);
        }
      }
    }
    await p.close();
  }
  check("the run found the tables at all", tables >= EXPECT_TABLES * 5, `${tables} renders`);
  check("every table fits its scroller at 375/414/639/640/1440",
        bad.length === 0, bad.slice(0, 3).join(" | "));
}

/* ── 5. tap targets ──────────────────────────────────────────────────── */
console.log("\n--- every control clears 24x24 on a phone ---");
{
  const p = await pageAt(375);
  let total = 0, removes = 0;
  const small = [];
  for (const route of ROUTES) {
    await go(p, route);
    for (const t of await p.evaluate(TAPS)) {
      total++;
      if (t.text === "✕" || /remove|delete/i.test(t.label)) removes++;
      if (t.w < 24 || t.h < 24) small.push(`${route} ${t.w}x${t.h} "${t.text || t.label}"`);
    }
  }
  check("the run found the controls at all", total >= EXPECT_TAPS, `${total} found`);
  // Named separately because these were the ones that were 11x21, and they
  // delete something without asking.
  check("the remove controls are present and sized", removes >= 20, `${removes} found`);
  check("nothing is under 24x24", small.length === 0,
        `${small.length}: ${small.slice(0, 3).join(", ")}`);
  await p.close();
}

/* ── the selftest ────────────────────────────────────────────────────── */
if (SELFTEST) {
  console.log("\n--- proving each check can fail ---");
  const p = await pageAt(375);
  await go(p, "/expenses");

  // 1. put the controls back under 16px.
  const zoomy = await p.evaluate(() => {
    for (const el of document.querySelectorAll("input, select, textarea")) el.style.fontSize = "14px";
    return [...document.querySelectorAll("select")].filter((s) => parseFloat(getComputedStyle(s).fontSize) < 16).length;
  });
  check("[can fail] a control under 16px is seen", zoomy > 0, `${zoomy} under 16px`);

  // 3. put the slug back the way it shipped: no wrap, no minimum on the rule.
  const broke = await p.evaluate(() => {
    for (const h of document.querySelectorAll("section.mb-10 > div.mb-4")) {
      h.classList.remove("flex-wrap");
      const r = h.querySelector(":scope > .rule");
      if (r) r.classList.remove("min-w-6");
      const last = h.lastElementChild;
      if (last && last.classList.contains("ml-auto")) {
        while (last.firstChild) h.appendChild(last.firstChild);
        last.remove();
      }
    }
    const de = document.documentElement;
    const bare = [...document.querySelectorAll("section.mb-10 > div.mb-4")]
      .filter((h) => { const r = h.querySelector(":scope > .rule"); return r && r.getBoundingClientRect().width < 6; }).length;
    return { overflow: de.scrollWidth - de.clientWidth, bare };
  });
  check("[can fail] the pre-fix slug is seen, as overflow or as a bare hairline",
        broke.overflow > 1 || broke.bare > 0,
        `overflow ${broke.overflow}px, ${broke.bare} bare`);

  // 4. put the hidden columns back and watch the table stop fitting.
  const wide = await p.evaluate(() => {
    for (const c of document.querySelectorAll("th, td")) c.classList.remove("hidden");
    const t = document.querySelector("table");
    const sc = t.closest(".overflow-x-auto");
    return sc.scrollWidth - sc.clientWidth;
  });
  check("[can fail] a table wider than its scroller is seen", wide > 1, `${wide}px hidden`);

  // 5. shrink a remove control back to a bare glyph.
  const tiny = await p.evaluate(() => {
    const b = document.querySelector(".btn-remove-quiet");
    if (!b) return null;
    b.className = "";
    const r = b.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  });
  check("[can fail] an undersized tap target is seen",
        tiny !== null && (tiny.w < 24 || tiny.h < 24),
        tiny ? `${tiny.w}x${tiny.h}` : "no remove control found");
  await p.close();
}

await browser.close();
console.log(`\nMOBILE: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
