/**
 * Every route, both themes.
 *
 * Rebuilt from the description in web/README.md, because the browser checks
 * are deliberately not in the repo — they need a real Chrome and a running dev
 * server, which CI here does not have.
 *
 * What it asserts, and why each one exists:
 *   - no token renders as an unresolved `var(--x)`, which paints NOTHING;
 *   - every rendered text node clears 3:1 against what is actually behind it;
 *   - every chart has <path> elements (Recharts leaves a pie's sectors as
 *     empty groups when an entry animation does not complete);
 *   - every colour a chart paints with is a palette token, not a literal;
 *   - no chart label loses ink to its own `overflow: hidden` surface;
 *   - no console errors.
 *
 * Run:  node sweep.mjs [--theme=dark] [--only=/year]
 */
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
// BASE is overridable so the same checks can be run against a
// deployment: BASE=https://... node sweep.mjs
const BASE = process.env.BASE ?? "http://localhost:3000";
const ROUTES = ["/", "/year", "/income", "/budget", "/expenses", "/net-worth",
                "/goals", "/debt", "/compare", "/investments", "/fire", "/tax",
                "/data"];

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => a.replace(/^--/, "").split("=")),
);
const THEMES = args.theme ? [args.theme] : ["light", "dark"];
const only = args.only ? [args.only] : ROUTES;

let pass = 0;
const fails = [];
function check(name, ok, detail = "") {
  if (ok) { pass++; return; }
  fails.push(`${name}${detail ? " — " + detail : ""}`);
}

/* ── The page-side probe ────────────────────────────────────────────────
   Two things here were wrong in an earlier version of this check and both
   invented defects rather than finding them: it read only backgroundColor and
   walked straight past a linear-gradient, scoring white-on-navy as
   white-on-white; and it credited any ancestor's background without asking
   whether the element actually SITS on that box, which scored a floating
   label against a 4px track it overhangs.                               */
const PROBE = () => {
  const px = (c) => {
    const m = String(c).match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(",").map((n) => parseFloat(n));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = ({ r, g, b }) => {
    const f = (v) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const ratio = (a, b) => {
    const [x, y] = [lum(a), lum(b)].sort((m, n) => n - m);
    return (x + 0.05) / (y + 0.05);
  };
  const over = (fg, bg) =>
    fg.a >= 1 ? fg : {
      r: fg.r * fg.a + bg.r * (1 - fg.a),
      g: fg.g * fg.a + bg.g * (1 - fg.a),
      b: fg.b * fg.a + bg.b * (1 - fg.a),
      a: 1,
    };
  const contains = (outer, inner) =>
    inner.left >= outer.left - 1 && inner.right <= outer.right + 1 &&
    inner.top >= outer.top - 1 && inner.bottom <= outer.bottom + 1;

  const bgOf = (el) => {
    const box = el.getBoundingClientRect();
    let n = el;
    while (n && n !== document.documentElement) {
      const cs = getComputedStyle(n);
      const img = cs.backgroundImage;
      if (img && img !== "none") {
        // A gradient. Average its stops — good enough to stop this reporting
        // white-on-navy as white-on-white, which is what it did before.
        const stops = (img.match(/rgba?\([^)]+\)/g) || []).map(px).filter(Boolean);
        if (stops.length) {
          return {
            r: stops.reduce((s, c) => s + c.r, 0) / stops.length,
            g: stops.reduce((s, c) => s + c.g, 0) / stops.length,
            b: stops.reduce((s, c) => s + c.b, 0) / stops.length,
            a: 1,
          };
        }
      }
      const bg = px(cs.backgroundColor);
      if (bg && bg.a > 0.05 && contains(n.getBoundingClientRect(), box)) return bg;
      n = n.parentElement;
    }
    return px(getComputedStyle(document.body).backgroundColor) ||
           { r: 255, g: 255, b: 255, a: 1 };
  };

  const visible = (el) => {
    const cs = getComputedStyle(el);
    if (cs.visibility === "hidden" || cs.display === "none") return false;
    if (parseFloat(cs.opacity) < 0.15) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };

  /* ── Custom properties that are REFERENCED but never defined ──
     The first version of this read computed styles looking for a literal
     "var(" and could never fire: an undefined custom property does not survive
     into computed style, it resolves to `unset` and the element INHERITS a
     colour instead. So `color: var(--s9)` renders as whatever the parent is —
     plausible, wrong, and invisible. The self-test caught this by requiring
     the check to fail on an injected fault, and it did not.

     What can fire is reading the stylesheets: collect every var(--x) actually
     referenced and ask the root whether it has a value for it. Tailwind's
     internal --tw-* properties are set per element rather than on :root, and a
     reference carrying its own fallback cannot paint nothing, so both are
     excluded.                                                             */
  const referenced = new Set();
  for (const sheet of document.styleSheets) {
    let rules;
    try { rules = sheet.cssRules; } catch { continue; }   // cross-origin
    const walk = (list) => {
      for (const rule of list) {
        if (rule.cssRules) walk(rule.cssRules);
        const text = rule.style ? rule.style.cssText : "";
        for (const m of text.matchAll(/var\(\s*(--[\w-]+)\s*([,)])/g)) {
          if (m[2] === ")" && !m[1].startsWith("--tw-")) referenced.add(m[1]);
        }
      }
    };
    walk(rules);
  }
  const rootStyle = getComputedStyle(document.documentElement);
  const unresolved = [...referenced].filter(
    (name) => rootStyle.getPropertyValue(name).trim() === "",
  );

  // ── Contrast on every rendered text node ──
  const low = [];
  let textNodes = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    const text = t.textContent.trim();
    if (!text) continue;
    const el = t.parentElement;
    if (!el || !visible(el)) continue;
    if (el.closest("[hidden]")) continue;
    const cs = getComputedStyle(el);
    // SVG TEXT IS PAINTED WITH `fill`, NOT `color`, and this check read
    // `color` for every node including the ones inside charts. On a Recharts
    // tick the two differ: the tspan INHERITS the body ink through `color`
    // while `fill` carries the grey it is actually drawn in. So every chart
    // label was measured as body-ink-on-card — a comfortable pass in either
    // theme, whatever the label was really painted. Measured: a label given
    // its own card's colour, which is invisible, scores 1.00 by fill and
    // 14.8 by the old method. 165 real labels per theme clear 3:1, so nothing
    // was hiding behind it — but nothing could have been seen if it were.
    const inSvg = el.ownerSVGElement != null;
    const raw = inSvg ? cs.fill : cs.color;
    const parsed = px(raw);
    // `fill: none`, or a url(#gradient), is not a colour anyone can judge.
    if (inSvg && !parsed) continue;
    textNodes++;
    const bg = bgOf(el);
    const fg = over(parsed || { r: 0, g: 0, b: 0, a: 1 }, bg);
    const r = ratio(fg, bg);
    if (r < 3) {
      low.push({ text: text.slice(0, 42), ratio: +r.toFixed(2),
                 color: raw, tag: el.tagName });
    }
  }

  // ── Charts: paths present, and painted only in palette colours ──
  const root = getComputedStyle(document.documentElement);
  const palette = new Set();
  for (const name of ["--paper", "--raise", "--card", "--hair", "--hair-soft",
                      "--ink", "--body-c", "--muted", "--faint", "--accent",
                      "--positive", "--critical", "--caution", "--info",
                      "--s1", "--s2", "--s3", "--s4", "--s5", "--s6", "--s7", "--s8"]) {
    const v = root.getPropertyValue(name).trim();
    if (v) palette.add(v.toLowerCase());
  }
  // Resolve each token to the rgb() form the browser reports on an element.
  const probe = document.createElement("div");
  document.body.appendChild(probe);
  const rgbPalette = new Set();
  for (const v of palette) {
    probe.style.color = v;
    rgbPalette.add(getComputedStyle(probe).color);
  }
  probe.remove();

  const svgs = [...document.querySelectorAll("svg")].filter(
    (s) => s.closest(".recharts-wrapper") || s.dataset.chart,
  );
  const emptyCharts = [];
  const offPalette = [];
  for (const svg of svgs) {
    const paths = svg.querySelectorAll("path, rect, circle, line");
    if (paths.length === 0) emptyCharts.push(svg.parentElement?.className || "?");
    for (const p of svg.querySelectorAll("path, rect, circle")) {
      for (const attr of ["fill", "stroke"]) {
        const raw = p.getAttribute(attr);
        if (!raw || raw === "none" || raw === "transparent" ||
            raw.startsWith("url(") || raw === "currentColor") continue;
        probe.style.color = raw;
        document.body.appendChild(probe);
        const resolved = getComputedStyle(probe).color;
        probe.remove();
        if (!rgbPalette.has(resolved)) offPalette.push(`${attr}=${raw}`);
      }
    }
  }

  /* ── A chart label that loses ink to its own surface ──
     Recharts draws a `position: "top"` reference label ABOVE the plot area,
     and the surface is `overflow: hidden`. A chart whose top margin is
     smaller than the label therefore slices it and says nothing: the fan
     chart's "Retirement" was cut by 7px of its 13, so the glyph tops were
     gone and it read as nonsense.

     VERTICAL overhang only. A horizontal pixel or two is the glyph's
     trailing side bearing, which carries no ink — measured at 6x device
     scale on the axis dates, which looked clipped and were not. */
  const clippedLabels = [];
  for (const svg of document.querySelectorAll("svg")) {
    if (getComputedStyle(svg).overflow !== "hidden") continue;
    const R = svg.getBoundingClientRect();
    if (R.width === 0) continue;
    for (const t of svg.querySelectorAll("text")) {
      const q = t.getBoundingClientRect();
      if (q.width === 0 || q.height === 0) continue;
      const lost = Math.max(Math.round(R.top - q.top), Math.round(q.bottom - R.bottom));
      if (lost > 2) {
        clippedLabels.push(`"${(t.textContent || "").trim().slice(0, 20)}" cut ${lost}px`);
      }
    }
  }

  return {
    unresolved, low, textNodes,
    svgCount: svgs.length, emptyCharts,
    offPalette: [...new Set(offPalette)],
    clippedLabels,
  };
};

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--font-render-hinting=none"],
  protocolTimeout: 600000,
});

for (const theme of THEMES) {
  for (const route of only) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 1000 });
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.evaluateOnNewDocument((t) => {
      try { localStorage.setItem("mjb_budget_theme", t); } catch {}
    }, theme);
    let reached = true;
    try {
      await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
    } catch {
      try {
        await page.goto(BASE + route, { waitUntil: "domcontentloaded", timeout: 60000 });
      } catch {
        reached = false;
      }
    }
    if (!reached) {
      check(`${theme} ${route}: the page loads at all`, false, "navigation timed out twice");
      await page.close();
      continue;
    }
    await page.evaluate((t) => document.documentElement.setAttribute("data-theme", t), theme);
    // Every page renders a skeleton until its data lands.
    await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
      .catch(() => {});
    await new Promise((r) => setTimeout(r, 700));

    const res = await page.evaluate(PROBE);
    const tag = `${theme} ${route}`;
    check(`${tag}: every var(--x) referenced in CSS has a value`,
          res.unresolved.length === 0, res.unresolved.slice(0, 4).join(" | "));
    check(`${tag}: every text node clears 3:1 (${res.textNodes} nodes)`,
          res.low.length === 0,
          res.low.slice(0, 3).map((l) => `"${l.text}" ${l.ratio}:1 ${l.color}`).join(" | "));
    check(`${tag}: no chart is empty (${res.svgCount} charts)`,
          res.emptyCharts.length === 0, res.emptyCharts.join(" | "));
    check(`${tag}: no chart label is clipped by its own surface`,
          res.clippedLabels.length === 0, res.clippedLabels.slice(0, 3).join(" | "));
    check(`${tag}: charts paint only palette colours`,
          res.offPalette.length === 0, res.offPalette.slice(0, 4).join(" | "));
    check(`${tag}: no console errors`, errors.length === 0,
          errors.slice(0, 2).join(" | "));
    await page.close();
  }
}

await browser.close();
console.log(`\nSWEEP: ${pass} passed, ${fails.length} failed`);
for (const f of fails) console.log("  [FAIL] " + f);
process.exit(fails.length ? 1 : 0);
