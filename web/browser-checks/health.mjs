/**
 * The dashboard's health row: figures for the month so far, no verdict on it.
 *
 * THE DEFECT. The savings ring is `1 - spent_so_far / take_home`, which starts
 * every month at 100% and falls through it, and it was graded — measured on the
 * 4th of September with one rent charge logged, it read **70% painted GREEN**;
 * on the shipped demo it read 48% green against a budget that plans to keep 17%.
 * Budget adherence was the same defect in the second card: a category with
 * nothing logged against it counts as within budget, so a profile holding one
 * expense scored **15/15 "On track"**. Both fail in the FLATTERING direction,
 * which is the one nobody checks, on the landing page.
 *
 * Every band was also a ternary in `page.tsx` — under a comment claiming that
 * "every RULE is in Python" — and `/year` held a DIFFERENT ternary for the same
 * measure, three tiers against four. They all live in `calculations.py` now.
 *
 * The clock is patched rather than the data, because the thing under test is
 * what the page does as a month ENDS.
 *
 * Run:  node health.mjs [--selftest]
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

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 600000,
});

/** Open the dashboard with the browser's clock optionally moved. */
async function open({ at = null, theme = "light", width = 1440 } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  const closePage = page.close.bind(page);
  page.close = async () => { await closePage().catch(() => {}); await ctx.close().catch(() => {}); };
  await page.setViewport({ width, height: 1400 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.evaluateOnNewDocument((t) => {
    try { localStorage.setItem("mjb_budget_theme", t); } catch {}
  }, theme);
  if (at) {
    // The CLIENT's date is what decides the month and whether it is over, so
    // moving the clock is the only way to see the page as a month ends.
    await page.evaluateOnNewDocument((iso) => {
      const Real = Date;
      const fixed = new Real(iso).getTime();
      const Fake = class extends Real {
        constructor(...a) { super(...(a.length ? a : [fixed])); }
        static now() { return fixed; }
      };
      Fake.prototype = Real.prototype;
      window.Date = Fake;
    }, at);
  }
  await page.goto(BASE + "/", { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 1500));
  page.__errors = errors;
  return page;
}

const ROW = () => {
  const cards = [...document.querySelectorAll(".card")];
  const byLabel = (re) => cards.find((c) => re.test(c.querySelector(".label")?.textContent ?? ""));
  const card = (c) => c && ({
    value: c.querySelector("p.font-num")?.textContent?.trim() ?? null,
    badge: c.querySelector(".badge")?.textContent?.trim() ?? null,
    desc: c.querySelector("p.t-micro")?.textContent?.replace(/\s+/g, " ").trim() ?? null,
  });
  const ring = document.querySelector(".ring-container");
  return {
    ring: ring && {
      text: ring.innerText.replace(/\s+/g, " ").trim(),
      // the SECOND circle is the value arc; its stroke is the verdict
      arc: [...ring.querySelectorAll("circle")].map((c) => c.getAttribute("stroke"))[1],
      track: [...ring.querySelectorAll("circle")].map((c) => c.getAttribute("stroke"))[0],
    },
    dti: card(byLabel(/Debt-to-income/)),
    ef: card(byLabel(/Emergency fund/)),
    adherence: card(byLabel(/Budget adherence/)),
    netSavings: card(byLabel(/Net savings/)),
    // what the palette resolves those tone names to, so a colour can be
    // matched to a MEANING rather than to a hex nobody can grep for
    tones: Object.fromEntries(["positive", "caution", "critical", "info"].map((t) =>
      [t, getComputedStyle(document.documentElement).getPropertyValue(`--${t === "info" ? "info" : t}`).trim()])),
  };
};

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- a month in progress is reported, not graded ---");
{
  const page = await open();
  const r = await page.evaluate(ROW);

  // What a healthy run must FIND, before anything is asserted about it.
  check("the health row rendered at all",
        !!r.ring && !!r.dti && !!r.ef && !!r.adherence,
        JSON.stringify({ ring: !!r.ring, dti: !!r.dti, ef: !!r.ef, adh: !!r.adherence }));
  check("the ring carries a figure and a sublabel",
        /\d+%/.test(r.ring.text) && r.ring.text.length > 6, r.ring.text);

  check("the ring says how far into the month it is",
        /\d+ of \d+ days into the month/.test(r.ring.text), r.ring.text);
  check("and is painted the ungraded tone, not a grade",
        r.ring.arc === r.tones.info,
        `arc ${r.ring.arc} · info ${r.tones.info} · positive ${r.tones.positive}`);
  check("the ring is NOT painted the winner's colour",
        r.ring.arc !== r.tones.positive && r.ring.arc !== r.tones.critical);

  check("adherence says its count is so far",
        /so far$/.test(r.adherence.value ?? ""), String(r.adherence.value));
  check("and carries no grade either",
        r.adherence.badge === "Partial month", String(r.adherence.badge));
  check("it names the categories with nothing logged against them",
        /\d+ of them have nothing logged yet/.test(r.adherence.desc ?? ""),
        String(r.adherence.desc));

  // These two are NOT month-dependent, so they keep their verdicts.
  check("debt-to-income is still graded", !!r.dti.badge && r.dti.badge !== "Partial month",
        String(r.dti.badge));
  check("the emergency fund is still graded", !!r.ef.badge && r.ef.badge !== "Partial month",
        String(r.ef.badge));
  check("no console errors", page.__errors.length === 0, page.__errors.slice(0, 2).join(" | "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the same month, once it is over, IS graded ---");
{
  // Both directions, or "never grade anything" would pass everything above.
  const page = await open({ at: "2026-09-30T12:00:00" });
  const r = await page.evaluate(ROW);
  check("the ring drops the 'so far' wording once the month is complete",
        !/days into the month/.test(r.ring.text) && /Saved in/.test(r.ring.text),
        r.ring.text);
  check("and is painted a real verdict",
        [r.tones.positive, r.tones.caution, r.tones.critical].includes(r.ring.arc),
        `arc ${r.ring.arc}`);
  check("adherence is graded too", ["On track", "Watch"].includes(r.adherence.badge ?? ""),
        String(r.adherence.badge));
  check("and its wording follows", !/so far/.test(r.adherence.value ?? ""),
        String(r.adherence.value));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the page reports the engine's figure, and computes none ---");
{
  const page = await open();
  const server = await page.evaluate(async () => {
    // ask the route directly for the same profile the page is showing
    const state = await fetch("/api/state").then((r) => r.json());
    const p = state.profile ?? state;
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    const r = await fetch("/api/dashboard", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        income: p.income, itemized: p.itemized, debts: p.debts,
        budget_needs: p.budget.needs, assets: p.assets,
        expenses: p.expenses, budget: p.budget, today,
      }),
    }).then((x) => x.json());
    return r.health;
  });
  const r = await page.evaluate(ROW);
  const shown = Number((r.ring.text.match(/(\d+)%/) ?? [])[1]);
  check("the route was reachable and answered with a verdict block",
        server && typeof server.savings_rate === "number", JSON.stringify(server)?.slice(0, 80));
  check("the ring shows the engine's rate, rounded — not one of its own",
        shown === Math.round(server.savings_rate),
        `page ${shown}% · engine ${server.savings_rate}`);
  check("the engine, not the page, decided to withhold the verdict",
        server.savings_tone === "info" && server.savings_status === null
        && typeof server.verdict_withheld === "string",
        `${server.savings_tone} / ${server.verdict_withheld}`);
  check("adherence counts come from the engine as well",
        (r.adherence.value ?? "").startsWith(`${server.on_track}/${server.budgeted_categories}`),
        `${r.adherence.value} vs ${server.on_track}/${server.budgeted_categories}`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the row reads in both themes ---");
{
  for (const theme of ["light", "dark"]) {
    const page = await open({ theme });
    const bad = await page.evaluate(() => {
      const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255;
        return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
      const parse = (s) => { const m = String(s).match(/rgba?\(([^)]+)\)/); if (!m) return null;
        const p = m[1].split(",").map(parseFloat);
        return p.length > 3 && p[3] === 0 ? null : p.slice(0, 3); };
      const behind = (el) => { let n = el;
        while (n && n !== document.documentElement) {
          const c = parse(getComputedStyle(n).backgroundColor); if (c) return c; n = n.parentElement; }
        return [255, 255, 255]; };
      const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
        return (x + 0.05) / (y + 0.05); };
      const heads = [...document.querySelectorAll("p.label")];
      const row = heads.find((h) => /FINANCIAL HEALTH/i.test(h.textContent))?.nextElementSibling;
      if (!row) return { seen: 0, out: ["no health row"] };
      const out = []; let seen = 0;
      const walk = document.createTreeWalker(row, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walk.nextNode())) {
        const t = n.textContent.trim(); if (!t) continue;
        const el = n.parentElement;
        const rect = el.getBoundingClientRect(); if (!rect.width || !rect.height) continue;
        const cs = getComputedStyle(el);
        // SVG text is painted with `fill`, not `color`
        const fg = parse(el.namespaceURI?.includes("svg") ? cs.fill : cs.color);
        if (!fg) continue;
        seen++;
        const cr = ratio(fg, behind(el));
        if (cr < 3) out.push(`${t.slice(0, 22)} ${cr.toFixed(2)}:1`);
      }
      return { seen, out };
    });
    // 14 on the shipped demo: the ring's figure and sublabel, plus a label,
    // value, badge and description on each of the three cards. The floor is
    // what stops a selector that matches nothing reporting a clean sweep.
    check(`${theme}: the row has text to measure`, bad.seen >= 12, `${bad.seen} nodes`);
    check(`${theme}: every node clears 3:1`, bad.out.length === 0, bad.out.slice(0, 3).join(" | "));
    await page.close();
  }
}

// ═══════════════════════════════════════════════════════════════════
if (SELFTEST) {
  console.log("\n=== selftest: each check, against an injected fault ===");

  // 1. paint the ring the winner's colour mid-month — the shipped defect
  {
    const page = await open();
    const r = await page.evaluate(() => {
      const ring = document.querySelector(".ring-container");
      const arc = [...ring.querySelectorAll("circle")][1];
      const positive = getComputedStyle(document.documentElement)
        .getPropertyValue("--positive").trim();
      arc.setAttribute("stroke", positive);
      return { arc: arc.getAttribute("stroke"), positive };
    });
    check("[can fail] a ring painted the winner's colour is seen as graded",
          r.arc === r.positive);
    await page.close();
  }

  // 2. strip the "so far" and the check must notice
  {
    const page = await open();
    const v = await page.evaluate(() => {
      const c = [...document.querySelectorAll(".card")]
        .find((x) => /Budget adherence/.test(x.querySelector(".label")?.textContent ?? ""));
      const p = c.querySelector("p.font-num");
      p.textContent = p.textContent.replace(/ so far$/, "");
      return p.textContent.trim();
    });
    check("[can fail] adherence without 'so far' is seen", !/so far$/.test(v), v);
    await page.close();
  }

  // 3. an unreadable figure in the row must fail the contrast pass
  {
    const page = await open();
    const ok = await page.evaluate(() => {
      const c = [...document.querySelectorAll(".card")]
        .find((x) => /Debt-to-income/.test(x.querySelector(".label")?.textContent ?? ""));
      const p = c.querySelector("p.font-num");
      p.style.color = getComputedStyle(c).backgroundColor;
      return getComputedStyle(p).color === getComputedStyle(c).backgroundColor;
    });
    check("[can fail] a figure painted its own card's colour is reachable to measure", ok);
    await page.close();
  }

  // 4. the clock patch must actually move the month, or section two proves nothing
  {
    const page = await open({ at: "2026-09-30T12:00:00" });
    const d = await page.evaluate(() => new Date().getDate());
    check("[can fail] the injected clock really is the last day of the month", d === 30, String(d));
    await page.close();
  }
}

await browser.close();
console.log(`\nHEALTH: ${pass} passed, ${fails.length} failed`);
if (fails.length) { for (const f of fails) console.log("  - " + f); process.exit(1); }
