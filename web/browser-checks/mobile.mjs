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
import { writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name.
const HERE = dirname(fileURLToPath(import.meta.url));
mkdirSync(join(HERE, "fixtures"), { recursive: true });

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
  const pageOver = [];
  let narrowScrolled = 0;

  // The widths a phone or a window actually is. 320 is the iPhone 5 / SE
  // 1st gen; 360 the common Android; 375 the current small iPhone; 390 the
  // 14/15; 414 the Plus. 639/640 straddle the breakpoint where the hidden
  // columns come back, and 768/1024 are the tablet and the rail.
  //
  // EVERY WIDTH GETS THE PAGE-OVERFLOW TEST, and that is the point of the
  // list rather than a nicety: /goals pushed the page sideways by up to 34px
  // between 640 and 690 — its `sm:grid-cols-4` puts a date input, whose
  // min-content Chrome will not take below 149px, in a 127px cell beside a
  // fixed button. It had been shipping since the re-skin, invisible because
  // every check ran at 375, 414, 768 or 1440 and the band is 50px wide.
  for (const width of [320, 360, 375, 390, 414, 639, 640, 768, 1024, 1440]) {
    const p = await pageAt(width);
    for (const route of ROUTES) {
      await go(p, route);
      const pg = await p.evaluate(() => {
        const de = document.documentElement;
        return de.scrollWidth - de.clientWidth;
      });
      if (pg > 1) pageOver.push(`${route}@${width} +${pg}px`);
      for (const t of await p.evaluate(TABLES)) {
        tables++;
        if (t.hidden > 1) {
          // 320px is 2016 hardware and the tables fall back to their own
          // scroller there rather than breaking the page. That is reported,
          // not asserted away, so the day it gets worse is visible.
          if (width <= 320) { narrowScrolled++; continue; }
          const off = t.cols.filter((c) => !c.vis).map((c) => c.name);
          bad.push(`${route}@${width} ${t.hidden}px hidden — ${off.join(", ") || "?"}`);
        }
      }
    }
    await p.close();
  }
  check("the run found the tables at all", tables >= EXPECT_TABLES * 8, `${tables} renders`);
  check("no page scrolls sideways, at any of the ten widths",
        pageOver.length === 0, pageOver.slice(0, 3).join(" | "));
  check("every table fits its scroller from 360px up",
        bad.length === 0, bad.slice(0, 3).join(" | "));
  console.log(`         (at 320px, ${narrowScrolled} table renders fall back to their own scroller)`);
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

/* ── 6. the importer, which is BEHIND A BUTTON ───────────────────────── */
console.log("\n--- the importer at 375px ---");
{
  // Everything above walks routes as they load. The importer is collapsed by
  // default, so none of it ever saw the app's biggest table or its only
  // checkboxes: measured before the fix, 736px of table in a 335px scroller
  // with 401px off screen, and six 13x13 ticks. A check that only visits
  // routes cannot see a panel.
  const p = await pageAt(375);
  await go(p, "/expenses");
  const opened = await p.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => /open importer/i.test(x.textContent));
    if (!b) return false;
    b.click();
    return true;
  });
  check("the importer opens", opened);
  await new Promise((r) => setTimeout(r, 800));

  const input = await p.$('input[type="file"]');
  check("it offers a file input", !!input);
  if (input) {
    const csv = join(HERE, "fixtures", "phone-import.csv");
    writeFileSync(csv, [
      "Date,Description,Amount",
      "09/01/2026,STARBUCKS STORE 442,-5.40",
      "09/01/2026,UBER TRIP 8F2K,-18.75",
      "09/02/2026,NETFLIX.COM,-15.99",
      "09/02/2026,WHOLE FOODS MKT,-84.12",
      "09/03/2026,PAYMENT THANK YOU,250.00",
    ].join("\n"));
    await input.uploadFile(csv);
    await p.waitForFunction(() => document.querySelectorAll(".table-cards tbody tr").length > 0,
                            { timeout: 30000 }).catch(() => {});
    await new Promise((r) => setTimeout(r, 900));
  }

  const imp = await p.evaluate(() => {
    const de = document.documentElement;
    const t = document.querySelector(".table-cards");
    const sc = t ? t.closest(".overflow-x-auto") : null;
    const boxes = [...document.querySelectorAll('input[type="checkbox"]')].map((c) => {
      const r = c.getBoundingClientRect();
      return { w: Math.round(r.width), h: Math.round(r.height) };
    });
    // In card mode the header is gone and each cell shows its own label, so
    // the labels are the witness that the stacked layout is actually on.
    const labels = t
      ? [...new Set([...t.querySelectorAll("tbody td[data-label]")]
          .filter((td) => getComputedStyle(td).display !== "none")
          .map((td) => td.getAttribute("data-label")))]
      : [];
    return {
      rows: t ? t.querySelectorAll("tbody tr").length : 0,
      headVisible: t && t.querySelector("thead")
        ? getComputedStyle(t.querySelector("thead")).display !== "none" : null,
      hidden: sc ? sc.scrollWidth - sc.clientWidth : null,
      pageOverflow: de.scrollWidth - de.clientWidth,
      boxes,
      labels,
    };
  });

  check("the preview built rows", imp.rows > 0, `${imp.rows} rows`);
  check("the row is stacked, not a table — the header is hidden",
        imp.headVisible === false, `thead display is ${imp.headVisible}`);
  check("and every field is labelled in the card",
        ["Import", "Date", "Description", "Amount", "Category", "Status"]
          .every((l) => imp.labels.includes(l)),
        imp.labels.join(", "));
  check("nothing in the importer scrolls sideways",
        imp.hidden !== null && imp.hidden <= 1 && imp.pageOverflow <= 1,
        `scroller ${imp.hidden}px, page ${imp.pageOverflow}px`);
  check("the ticks are the app's only checkboxes, and they clear 24x24",
        imp.boxes.length > 0 && imp.boxes.every((b) => b.w >= 24 && b.h >= 24),
        `${imp.boxes.length} boxes: ${[...new Set(imp.boxes.map((b) => `${b.w}x${b.h}`))].join(", ")}`);
  await p.close();
}

/* ── 7. the mobile-only renderings, in BOTH themes ───────────────────── */
console.log("\n--- what only exists on a phone, in dark as well as light ---");
{
  // `sweep.mjs` checks contrast in both themes and only at desktop width, so
  // nothing that renders ONLY below 640px has ever been contrast-checked: the
  // importer's cards, and the cash-flow list that replaces the Sankey. Both
  // are new surfaces with their own colours.
  const CONTRAST = () => {
    const px = (c) => {
      const m = String(c).match(/rgba?\(([^)]+)\)/);
      if (!m) return null;
      const q = m[1].split(",").map(Number);
      return { r: q[0], g: q[1], b: q[2], a: q.length > 3 ? q[3] : 1 };
    };
    const lum = ({ r, g, b }) => {
      const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
      return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
    };
    const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
    const bgOf = (el) => {
      // Containment, not mere ancestry: an element that overhangs the box it
      // descends from is not sitting on that colour. And the fallback is the
      // BODY's background rather than white, which in dark mode is the
      // difference between a real ratio and a fabricated one.
      const r = el.getBoundingClientRect();
      for (let e = el; e; e = e.parentElement) {
        const c = px(getComputedStyle(e).backgroundColor);
        const q = e.getBoundingClientRect();
        const inside = r.left >= q.left - 1 && r.right <= q.right + 1
                    && r.top >= q.top - 1 && r.bottom <= q.bottom + 1;
        if (c && c.a > 0 && (e === el || inside)) return c;
      }
      return px(getComputedStyle(document.body).backgroundColor)
          || { r: 255, g: 255, b: 255, a: 1 };
    };
    const bad = [];
    let checked = 0;
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let n;
    while ((n = walk.nextNode())) {
      if (!n.textContent.trim()) continue;
      const el = n.parentElement;
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.opacity === "0") continue;
      // SVG text is painted with `fill`, not `color` — a Recharts tick
      // INHERITS the body ink through `color` while `fill` carries the grey
      // it is drawn in, so reading `color` measures a chart label that does
      // not exist. `fill: none` and url(#gradient) are not judgeable.
      const inSvg = el.ownerSVGElement != null;
      const fg = px(inSvg ? cs.fill : cs.color);
      if (!fg) continue;
      checked++;
      const c = ratio(fg, bgOf(el));
      if (c < 3) bad.push(`${n.textContent.trim().slice(0, 22)} @${c.toFixed(2)}`);
    }
    // A bar drawn with an unresolved custom property paints nothing, which is
    // worse than a wrong colour because there is no literal to grep for.
    const bars = [...document.querySelectorAll('[aria-hidden="true"] > div')]
      .filter((d) => d.style.background)
      .map((d) => getComputedStyle(d).backgroundColor);
    return { checked, bad, bars, unresolvedBars: bars.filter((b) => !/^rgba?\(/.test(b)).length };
  };

  for (const theme of ["light", "dark"]) {
    const p = await browser.newPage();
    await p.setViewport({ width: 375, height: 900, deviceScaleFactor: 1, isMobile: true, hasTouch: true });
    await p.evaluateOnNewDocument((t) => {
      try { localStorage.setItem("mjb_budget_theme", t); } catch { /* private mode */ }
    }, theme);
    await go(p, "/");
    await new Promise((r) => setTimeout(r, 1200));

    const flow = await p.evaluate(() => {
      const sankey = [...document.querySelectorAll("div")]
        .find((d) => typeof d.className === "string" && d.className.includes("min-w-"));
      const list = [...document.querySelectorAll("div")].find((d) => d.className === "mt-1");
      return {
        sankeyHidden: sankey ? getComputedStyle(sankey.parentElement).display === "none" : null,
        listShown: list ? getComputedStyle(list.parentElement).display !== "none" : false,
        groups: list ? list.children.length : 0,
        rows: list ? list.querySelectorAll('[aria-hidden="true"]').length : 0,
        hoverSentence: /names itself on hover/.test(document.body.innerText),
      };
    });
    if (theme === "light") {
      check("the phone gets the list, not the Sankey", flow.sankeyHidden === true && flow.listShown,
            `sankey hidden ${flow.sankeyHidden}, list ${flow.listShown}`);
      check("and it is the whole graph, group by group", flow.groups >= 5 && flow.rows >= 25,
            `${flow.groups} groups, ${flow.rows} rows`);
      // The diagram's affordance does not exist on a touch device, so the
      // sentence describing it must not either.
      check("the caption does not tell a phone to hover", flow.hoverSentence === false);
    }

    const c = await p.evaluate(CONTRAST);
    check(`${theme}: every flow bar resolved to a real colour`,
          c.bars.length > 0 && c.unresolvedBars === 0,
          `${c.bars.length} bars, ${c.unresolvedBars} unresolved`);

    // EVERY route, not just the dashboard. `sweep.mjs` does both themes at
    // desktop width; the layouts below 640px are genuinely different — wrapped
    // slugs, hidden columns, the importer's cards, the cash-flow list — and
    // the only `text-faint` TEXT in the app turned out to live in the mobile
    // header, at a width no contrast check had ever run at. It measured
    // 2.57:1.
    let measured = c.checked;
    const low = c.bad.map((b) => `/ ${b}`);
    for (const route of ROUTES.slice(1)) {
      await go(p, route);
      const rc = await p.evaluate(CONTRAST);
      measured += rc.checked;
      for (const b of rc.bad) low.push(`${route} ${b}`);
    }
    check(`${theme}: the phone's text was actually measured`, measured > 600, `${measured} nodes`);
    check(`${theme}: every text node clears 3:1 on every route at 375px`,
          low.length === 0, low.slice(0, 4).join(" | "));
    await p.close();
  }
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

  // 4b. and the page-overflow half of the same check, which is what /goals
  // needed and what the width list exists for.
  const pushed = await p.evaluate(() => {
    const d = document.createElement("div");
    d.style.cssText = "width:120vw;height:4px";
    document.body.appendChild(d);
    const de = document.documentElement;
    const over = de.scrollWidth - de.clientWidth;
    d.remove();
    return over;
  });
  check("[can fail] a page that scrolls sideways is seen", pushed > 1, `${pushed}px`);

  // 5. shrink a remove control back to a bare glyph.
  const tiny = await p.evaluate(() => {
    const b = document.querySelector(".btn-remove-quiet");
    if (!b) return null;
    b.className = "";
    const r = b.getBoundingClientRect();
    return { w: Math.round(r.width), h: Math.round(r.height) };
  });
  // 6. put the importer back to a plain table and watch it stop fitting.
  await go(p, "/expenses");
  await p.evaluate(() => {
    [...document.querySelectorAll("button")].find((x) => /open importer/i.test(x.textContent))?.click();
  });
  await new Promise((r) => setTimeout(r, 700));
  const fi = await p.$('input[type="file"]');
  if (fi) {
    await fi.uploadFile(join(HERE, "fixtures", "phone-import.csv"));
    await p.waitForFunction(() => document.querySelectorAll("table tbody tr").length > 0,
                            { timeout: 30000 }).catch(() => {});
    await new Promise((r) => setTimeout(r, 900));
  }
  const untabled = await p.evaluate(() => {
    const t = document.querySelector(".table-cards");
    if (!t) return null;
    t.classList.remove("table-cards");
    const sc = t.closest(".overflow-x-auto");
    return sc.scrollWidth - sc.clientWidth;
  });
  check("[can fail] the importer as a plain table is seen to overflow",
        untabled !== null && untabled > 1, `${untabled}px hidden`);

  // 7. show the Sankey on the phone again and require the swap check to fire.
  await go(p, "/");
  await new Promise((r) => setTimeout(r, 1200));
  const swapped = await p.evaluate(() => {
    const sankey = [...document.querySelectorAll("div")]
      .find((d) => typeof d.className === "string" && d.className.includes("min-w-"));
    const list = [...document.querySelectorAll("div")].find((d) => d.className === "mt-1");
    if (!sankey || !list) return null;
    sankey.parentElement.classList.remove("hidden");
    list.parentElement.classList.remove("sm:hidden");
    list.parentElement.style.display = "none";
    return {
      sankeyHidden: getComputedStyle(sankey.parentElement).display === "none",
      listShown: getComputedStyle(list.parentElement).display !== "none",
    };
  });
  check("[can fail] the phone showing the Sankey instead of the list is seen",
        swapped !== null && !(swapped.sankeyHidden === true && swapped.listShown),
        JSON.stringify(swapped));

  check("[can fail] an undersized tap target is seen",
        tiny !== null && (tiny.w < 24 || tiny.h < 24),
        tiny ? `${tiny.w}x${tiny.h}` : "no remove control found");
  await p.close();
}

await browser.close();
console.log(`\nMOBILE: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
