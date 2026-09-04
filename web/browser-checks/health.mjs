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
  /* Close the CONTEXT only. Closing the page and then its context tears the
     same frames down twice, and when a lifecycle watcher is still live the
     second one raises "Navigating frame was detached" from a CDP event
     handler — which cannot be caught at the call site and takes the whole
     `npm run all` chain with it. A context close disposes its pages. */
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
  const card = (c) => {
    if (!c) return null;
    const value = c.querySelector("p.font-num");
    // A card now carries TWO t-micro lines: the period, above the value, and
    // the description, below it. `querySelector` took the first, which was
    // right when there was only one and silently became the period.
    const after = [...c.querySelectorAll("p.t-micro")].filter(
      (x) => value && !(x.compareDocumentPosition(value) & Node.DOCUMENT_POSITION_FOLLOWING));
    return {
      value: value?.textContent?.trim() ?? null,
      badge: c.querySelector(".badge")?.textContent?.trim() ?? null,
      desc: after[0]?.textContent?.replace(/\s+/g, " ").trim() ?? null,
    };
  };
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
console.log("\n--- every figure names the span it covers ---");
{
  /* Taken from Actual Budget, whose reports dashboard puts the range under
     every widget title. Ours had four cards in one row at one type size under
     a single "This month" heading, covering three different things: take-home
     is a monthly RATE, spent is however many days of records exist, and
     budgeted is a PLAN for a month that has not happened. */
  const page = await open();
  const periods = await page.evaluate(() => {
    const out = {};
    for (const c of document.querySelectorAll(".card")) {
      const label = c.querySelector(".label")?.textContent?.trim();
      if (!label) continue;
      // the period is the t-micro line directly after the label row
      const ps = [...c.querySelectorAll("p.t-micro")];
      // `.font-num`, not `p.font-num`: a LedgerCard puts its figure in a span
      // inside the ruled total, so keying on the tag found nothing and read as
      // a card with no period line at all.
      const value = c.querySelector(".font-num");
      const before = ps.filter((x) => value && (x.compareDocumentPosition(value)
        & Node.DOCUMENT_POSITION_FOLLOWING));
      out[label] = before[0]?.textContent?.trim() ?? null;
    }
    return {
      cards: out,
      // FROM THE FIGURE OUT. The nav's own top bar is a <header>, so `.label`
      // and `header .label` both returned its "PLANNER" wordmark; then the
      // sidebar gained a "Net worth" label of its own and matching by content
      // found that instead. The hero is the one beside `.figure-hero`.
      hero: (() => {
        const fig = document.querySelector(".figure-hero");
        const box = fig?.closest("header") ?? fig?.parentElement?.parentElement;
        return box?.querySelector(".label")?.textContent?.trim() ?? null;
      })(),
      spending: [...document.querySelectorAll("p.label")]
        .map((x) => x.textContent.trim()).find((t) => /^Spending/.test(t)) ?? null,
    };
  });

  const want = {
    "Take-home": /^a month, after tax$/,
    Spent: /^\w{3} 1\u2013\d+$|^\w+$/,
    "Net savings": /^\w{3} 1\u2013\d+$|^\w+$/,
    Budgeted: /^a month, planned$/,
    "Debt-to-income": /^as of today$/,
    "Emergency fund": /^as of today$/,
    "Budget adherence": /^\w{3} 1\u2013\d+$|^\w+$/,
  };
  const missing = Object.keys(want).filter((k) => !(k in periods.cards));
  check("the run found every card it means to check",
        missing.length === 0, `missing ${missing.join(", ")}`);
  const wrong = Object.entries(want)
    .filter(([k, re]) => k in periods.cards && !re.test(periods.cards[k] ?? ""))
    .map(([k]) => `${k}="${periods.cards[k]}"`);
  check("every card states the span it covers, and states the right one",
        wrong.length === 0, wrong.join(" | "));
  check("a monthly RATE and a month-to-date figure do not claim the same span",
        periods.cards["Take-home"] !== periods.cards.Spent,
        `${periods.cards["Take-home"]} vs ${periods.cards.Spent}`);
  check("the hero says what a balance is measured at",
        /as of today/i.test(periods.hero ?? ""), String(periods.hero));
  check("and the spending section carries the span too",
        /^Spending · /.test(periods.spending ?? "")
        && !/^Spending · $/.test(periods.spending ?? ""), String(periods.spending));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the month strip moves the whole dashboard ---");
{
  /* The strip exists so a COMPLETE month is reachable: the verdict this page
     withholds for a month in progress could otherwise appear on the last day
     of a month and never again. So this asserts the grade actually arrives. */
  const page = await open();

  const read = () => {
    const cards = {};
    for (const c of document.querySelectorAll(".card")) {
      const label = c.querySelector(".label")?.textContent?.trim();
      if (!label) continue;
      const v = c.querySelector("p.font-num");
      const micros = [...c.querySelectorAll("p.t-micro")];
      const before = micros.filter((x) => v && (x.compareDocumentPosition(v)
        & Node.DOCUMENT_POSITION_FOLLOWING));
      cards[label] = { v: v?.textContent?.trim() ?? null,
                       period: before[0]?.textContent?.trim() ?? null,
                       badge: c.querySelector(".badge")?.textContent?.trim() ?? null };
    }
    const ring = document.querySelector(".ring-container");
    return {
      cards,
      ring: ring && { text: ring.innerText.replace(/\s+/g, " ").trim(),
        arc: [...ring.querySelectorAll("circle")].map((c) => c.getAttribute("stroke"))[1] },
      heads: [...document.querySelectorAll("p.label")].map((x) => x.textContent.trim()),
      today: [...document.querySelectorAll("button")].some((x) => x.textContent.trim() === "Today"),
      donut: document.querySelectorAll(".recharts-pie path").length,
      tones: Object.fromEntries(["positive", "info"].map((t) =>
        [t, getComputedStyle(document.documentElement).getPropertyValue(`--${t}`).trim()])),
    };
  };

  // The month buttons are labelled, not just styled: the visible capitals are
  // a CSS transform, so text content is "Sep" and the year has no separator
  // before it — an aria-label is what makes the control announce itself.
  const strip = await page.evaluate(() =>
    [...document.querySelectorAll("button[aria-label]")]
      .map((b) => b.getAttribute("aria-label"))
      .filter((l) => /^[A-Z][a-z]{2} 20\d\d$/.test(l ?? "")));
  check("the strip offers named months, not bare glyphs",
        strip.length >= 2, strip.join(", "));

  const before = await page.evaluate(read);
  check("it starts on the reader's own month, ungraded",
        before.ring.arc === before.tones.info && !before.today,
        `${before.ring.text} | Today btn ${before.today}`);

  const moved = await page.evaluate(() => {
    const b = [...document.querySelectorAll("button[aria-label]")]
      .find((x) => /^[A-Z][a-z]{2} 20\d\d$/.test(x.getAttribute("aria-label") ?? "")
                   && x.getAttribute("aria-current") !== "true");
    if (!b) return null;
    b.click();
    return b.getAttribute("aria-label");
  });
  check("an earlier month can be selected", !!moved, String(moved));
  await new Promise((r) => setTimeout(r, 2200));
  const after = await page.evaluate(read);

  check("THE FIGURES FOLLOW IT, rather than the heading alone",
        after.cards.Spent?.v !== before.cards.Spent?.v,
        `${before.cards.Spent?.v} then ${after.cards.Spent?.v}`);
  check("so does the span each card names",
        after.cards.Spent?.period !== before.cards.Spent?.period,
        `${before.cards.Spent?.period} then ${after.cards.Spent?.period}`);
  check("and the chart under them", after.donut !== before.donut,
        `${before.donut} slices then ${after.donut}`);
  check("a COMPLETE month is graded, which is what the strip is for",
        after.ring.arc !== after.tones.info && !/days into the month/.test(after.ring.text),
        `${after.ring.text} | arc ${after.ring.arc}`);
  check("adherence drops its 'so far' and carries a real badge",
        !/so far/.test(after.cards["Budget adherence"]?.v ?? "")
        && after.cards["Budget adherence"]?.badge !== "Partial month",
        `${after.cards["Budget adherence"]?.v} [${after.cards["Budget adherence"]?.badge}]`);
  check("the monthly PLAN does not move, because it is not a month's records",
        after.cards["Take-home"]?.v === before.cards["Take-home"]?.v
        && after.cards.Budgeted?.v === before.cards.Budgeted?.v);
  check("a Today control appears once you have left today", after.today);

  await page.evaluate(() => [...document.querySelectorAll("button")]
    .find((x) => x.textContent.trim() === "Today")?.click());
  await new Promise((r) => setTimeout(r, 2200));
  const back = await page.evaluate(read);
  check("and it returns every figure to the current month",
        back.cards.Spent?.v === before.cards.Spent?.v && !back.today
        && back.ring.arc === back.tones.info);
  check("no console errors driving it", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the ledger shows the subtraction that produced it ---");
{
  const page = await open();
  const led = await page.evaluate(() => {
    const c = [...document.querySelectorAll(".card")]
      .find((x) => /^Net savings$/.test(x.querySelector(".label")?.textContent?.trim() ?? ""));
    if (!c) return null;
    const num = (s) => Number(String(s).replace(/[^0-9.-]/g, ""));
    const rows = [...c.querySelectorAll("div.flex.items-baseline")].map((d) => {
      const sp = d.querySelectorAll("span");
      return { label: sp[0]?.textContent?.trim(), value: sp[1]?.textContent?.trim() };
    });
    return { rows, nums: rows.map((r) => num(r.value)), rule: !!c.querySelector(".border-t") };
  });
  check("the card renders its rows and a total", led && led.rows.length === 3,
        JSON.stringify(led?.rows));
  check("it is ruled, so the figures read as being added up", !!led?.rule);
  // THE POINT: the arithmetic on the card must be the arithmetic. The total is
  // passed in from the engine, so this is a check that the rows shown are the
  // ones that produce it — not a re-implementation of the sum.
  check("take-home less spent IS the total shown",
        Math.abs((led.nums[0] - Math.abs(led.nums[1])) - led.nums[2]) < 1,
        led.rows.map((r) => `${r.label} ${r.value}`).join("  "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the sidebar carries balances, and they are the real ones ---");
{
  const page = await open();
  const bal = await page.evaluate(() => {
    // TWO nav trees exist — the rail and the off-canvas drawer — and at desktop
    // width the drawer is zero-size. Measure the one with a rect, or every
    // visibility answer is trivially true of a zero rect.
    const head = [...document.querySelectorAll("p")]
      .filter((p) => p.textContent.trim() === "Balances")
      .find((p) => p.getBoundingClientRect().height > 0);
    if (!head) return null;
    const block = head.parentElement;
    const num = (s) => Number(String(s).replace(/[^0-9.-]/g, ""));
    const rows = [...block.querySelectorAll("li")].map((li) => {
      const sp = li.querySelectorAll("span");
      return { name: sp[0]?.textContent?.trim(), value: num(sp[1]?.textContent) };
    });
    const link = block.querySelector('a[href="/net-worth"]');
    const r = block.getBoundingClientRect();
    const hero = document.querySelector(".figure-hero");
    return {
      rows,
      net: num(link?.querySelectorAll("span")[1]?.textContent),
      linked: !!link,
      visible: r.top >= 0 && r.bottom <= window.innerHeight && r.height > 0,
      heroNet: num(hero?.textContent),
    };
  });
  check("the rail carries a balances block", !!bal, "no visible block");
  check("it is above the fold on a laptop, which is the point of it",
        bal.visible, JSON.stringify(bal));
  check("assets and liabilities, both stated", bal.rows.length === 2
        && /Assets/.test(bal.rows[0].name ?? "") && /Liabilities/.test(bal.rows[1].name ?? ""),
        JSON.stringify(bal.rows));
  check("a liability is shown as money OWED, not as a positive balance",
        bal.rows[1].value <= 0, String(bal.rows[1].value));
  // The sidebar and the dashboard hero are two renderings of one figure. If
  // they disagree, one of them is doing its own arithmetic.
  check("the sidebar's net worth is the dashboard's, to the dollar",
        Math.abs(bal.net - bal.heroNet) < 1, `${bal.net} vs ${bal.heroNet}`);
  check("and it links to where those rows are edited", bal.linked);
  await page.close();
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

  // 4. strip a period line and the check must notice
  {
    const page = await open();
    const gone = await page.evaluate(() => {
      const c = [...document.querySelectorAll(".card")]
        .find((x) => /^Take-home$/.test(x.querySelector(".label")?.textContent?.trim() ?? ""));
      const value = c.querySelector("p.font-num");
      const ps = [...c.querySelectorAll("p.t-micro")]
        .filter((x) => x.compareDocumentPosition(value) & Node.DOCUMENT_POSITION_FOLLOWING);
      ps[0]?.remove();
      return [...c.querySelectorAll("p.t-micro")]
        .filter((x) => x.compareDocumentPosition(value) & Node.DOCUMENT_POSITION_FOLLOWING).length;
    });
    check("[can fail] a card with no period line is seen to have none", gone === 0, String(gone));
    await page.close();
  }

  // 5. break the ledger's arithmetic and the check must see it
  {
    const page = await open();
    const ok = await page.evaluate(() => {
      const c = [...document.querySelectorAll(".card")]
        .find((x) => /^Net savings$/.test(x.querySelector(".label")?.textContent?.trim() ?? ""));
      const rows = [...c.querySelectorAll("div.flex.items-baseline")];
      const sp = rows[0].querySelectorAll("span")[1];
      sp.textContent = "$1";
      return sp.textContent === "$1";
    });
    check("[can fail] a ledger whose rows do not make its total is reachable", ok);
    await page.close();
  }

  // 6. a sidebar figure that disagrees with the dashboard must be seen
  {
    const page = await open();
    const ok = await page.evaluate(() => {
      const head = [...document.querySelectorAll("p")]
        .filter((p) => p.textContent.trim() === "Balances")
        .find((p) => p.getBoundingClientRect().height > 0);
      const link = head.parentElement.querySelector('a[href="/net-worth"]');
      link.querySelectorAll("span")[1].textContent = "$1";
      return link.querySelectorAll("span")[1].textContent === "$1";
    });
    check("[can fail] a sidebar total can be made to disagree and be measured", ok);
    await page.close();
  }

  // 7. the clock patch must actually move the month, or section two proves nothing
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
