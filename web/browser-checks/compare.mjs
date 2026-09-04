/**
 * /compare, driven — the page no check had ever seen.
 *
 * THE REASON IT WAS INVISIBLE IS THE INTERESTING PART. `sweep.mjs` and
 * `mobile.mjs` both walk `/compare`, at ten widths between them, and both were
 * right to report it clean: the demo profile ships NO `scenarios`, so the page
 * renders its empty state and the side-by-side table — the whole reason the
 * screen exists — does not exist to be measured. The importer taught this
 * lesson once already ("a route sweep does not see what is behind a button");
 * here the button does not reveal the table, it CREATES it.
 *
 * What driving it found, all live, none of it visible to a green suite:
 *
 *   1. The table hid a scenario column on every phone. At 375px with two
 *      scenarios, 171px of 504px was off screen; with three, 313px. The hidden
 *      column is a whole scenario, and the hidden rows include Take-home and
 *      Worth — the answer. The clipped edge read "$105," and "$70,": a
 *      truncated number that still reads as a number, for the fourth time in
 *      this codebase.
 *   2. Two columns could carry one name without anybody typing a duplicate —
 *      add two, remove the first, add again — and the winner's colour then
 *      landed on EVERY column carrying the winning name. Measured: a $49,438
 *      column and a $133,988 column both painted best, plus eleven React
 *      duplicate-key errors in the console.
 *   3. A blank name left the remove button announcing "Remove ".
 *
 * Run:  node compare.mjs [--selftest]
 *       BASE=https://budget.masonjbennett.com node compare.mjs
 */
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));

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

/* An isolated context per section. Signed-out figures persist to localStorage
   now (lib/localProfile.ts), so scenarios added by one section would otherwise
   still be there for the next — and every section here begins by counting how
   many scenarios exist. */
async function open({ width = 1440, theme = "light", route = "/compare" } = {}) {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  /* Close the CONTEXT only, which disposes its pages. Closing the page and
     then the context tears the same frames down twice, and with a lifecycle
     watcher still live the second raises "detached Frame" from a CDP event
     handler — uncatchable at the call site, and fatal to `npm run all`. */
  page.close = async () => {
    await new Promise((r) => setTimeout(r, 80));
    await ctx.close().catch(() => {});
  };
  await page.setViewport({ width, height: 1200 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.evaluateOnNewDocument((t) => {
    try { localStorage.setItem("mjb_budget_theme", t); } catch {}
  }, theme);
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 800));
  page.__errors = errors;
  return page;
}

const addScenario = async (page, n = 1) => {
  for (let i = 0; i < n; i++) {
    await page.evaluate(() => [...document.querySelectorAll("button")]
      .find((b) => /Add a scenario/i.test(b.textContent))?.click());
    await new Promise((r) => setTimeout(r, 650));
  }
  // the comparison refetches on every change; wait for the table to settle
  await page.waitForFunction(
    (want) => {
      const t = [...document.querySelectorAll("table")].find((x) => /Take-home/i.test(x.textContent));
      return t && t.querySelectorAll("thead th").length === want + 2;
    },
    { timeout: 15000 }, n,
  ).catch(() => {});
  await new Promise((r) => setTimeout(r, 500));
};

/** Type into a React-controlled input the way React will notice. */
const setValue = (page, handleOrSel, value) => page.evaluate((sel, value) => {
  const el = typeof sel === "string" ? document.querySelector(sel) : sel;
  const proto = el instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement;
  Object.getOwnPropertyDescriptor(proto.prototype, "value").set.call(el, value);
  el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
}, handleOrSel, value);

/** Everything the table says about itself, in one round trip. */
const TABLE = () => {
  const tbl = [...document.querySelectorAll("table")].find((t) => /Take-home/i.test(t.textContent));
  if (!tbl) return null;
  const sc = tbl.closest(".overflow-x-auto");
  const bodyRows = [...tbl.querySelectorAll("tbody tr")];
  const worth = bodyRows.find((tr) => /Worth, in national-average/i.test(tr.textContent));
  return {
    stacked: tbl.classList.contains("table-stacked"),
    hidden: sc.scrollWidth - sc.clientWidth,
    cols: tbl.querySelectorAll("thead th").length,
    heads: [...tbl.querySelectorAll("thead th")].map((t) => t.innerText.trim()),
    rows: bodyRows.length,
    // every cell carrying a figure must say which column it belongs to, or the
    // stacked rendering is a list of numbers with no owners
    valueCells: bodyRows.reduce((n, tr) => n + tr.querySelectorAll("td").length - 1, 0),
    labelled: bodyRows.reduce(
      (n, tr) => n + [...tr.querySelectorAll("td")].slice(1)
        .filter((td) => td.getAttribute("data-label")).length, 0),
    // the winner's paint, by column
    winners: worth
      ? [...worth.querySelectorAll("td")].slice(1)
        .map((td) => /text-positive/.test(td.querySelector("span")?.className ?? ""))
      : null,
    worthValues: worth
      ? [...worth.querySelectorAll("td")].slice(1).map((td) => td.innerText.trim())
      : null,
    verdict: [...(tbl.closest("section")?.querySelectorAll("p") ?? [])]
      .map((p) => p.innerText.replace(/\s+/g, " ").trim())
      .find((t) => /leaves you the most/.test(t)) ?? null,
  };
};

const keyErrors = (page) => page.__errors.filter((e) => /same key/i.test(e));

const WIDTHS = [320, 360, 375, 390, 414, 639, 640, 768, 1024, 1440];

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the page starts empty, and adding a scenario builds the table ---");
{
  const page = await open();
  const before = await page.evaluate(TABLE);
  const emptyNote = await page.evaluate(() => /No scenarios yet/.test(document.body.innerText));

  check("a first visit shows the empty state, not a table", before === null && emptyNote);
  await addScenario(page, 1);
  const one = await page.evaluate(TABLE);
  check("adding a scenario builds the comparison", !!one && one.cols === 3,
        `${one?.cols} columns`);
  check("and it carries every measure the page promises", one.rows === 10,
        `${one?.rows} rows`);
  check("no console errors building it", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));
  // A new scenario is a COPY of the baseline, so this is the page's own first
  // state: only the baseline column may call itself the baseline.
  const diff = await page.evaluate(() => {
    const tbl = [...document.querySelectorAll("table")].find((t) => /Take-home/i.test(t.textContent));
    const tr = [...tbl.querySelectorAll("tbody tr")].find((x) => /^Difference/.test(x.innerText));
    return [...tr.querySelectorAll("td")].slice(1).map((td) => td.innerText.trim());
  });
  check("only the baseline column is labelled 'baseline'",
        diff[0] === "baseline" && diff.slice(1).every((d) => d !== "baseline"),
        diff.join(" / "));
  check("a scenario identical to it reports no difference instead",
        diff[1] === "no change", diff.join(" / "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- no scenario column is ever off screen, at any width ---");
{
  /* THE DEFECT THIS FILE EXISTS FOR. A table inside `overflow-x-auto` does not
     overflow the PAGE, so every horizontal-overflow check in this repo passes
     on it — correctly, and none of them can ask whether the column carrying
     the number is on screen. One column per scenario means the width this
     table needs is DATA, so no fixed breakpoint answers it: measured, 3
     columns fit from 323px, 4 from 424px, 5 from 525px and 6 from 738px. */
  let seen = 0;
  const over = [];
  const pageOver = [];
  const unlabelled = [];
  for (const n of [1, 2, 3, 4]) {
    const page = await open({ width: 1440 });
    await addScenario(page, n);
    for (const width of WIDTHS) {
      await page.setViewport({ width, height: 1200 });
      await new Promise((r) => setTimeout(r, 260));
      const t = await page.evaluate(TABLE);
      const pg = await page.evaluate(() =>
        document.documentElement.scrollWidth - document.documentElement.clientWidth);
      seen++;
      // The PAGE, not just the table. mobile.mjs measures this on /compare and
      // has only ever seen the empty state — and the scenario cards carry three
      // <select>s whose min-content width is their longest option, which is the
      // shape that pushed /goals sideways in a band nothing sampled.
      if (pg > 1) pageOver.push(`${n}sc@${width} +${pg}px`);
      if (t.hidden > 1) over.push(`${n}sc@${width} ${t.hidden}px hidden`);
      // a stacked table has to name the column every figure came from
      if (t.stacked && t.labelled !== t.valueCells) {
        unlabelled.push(`${n}sc@${width} ${t.valueCells - t.labelled} unlabelled`);
      }
    }
    await page.close();
  }
  check("the run measured the table at every width and count", seen === 40, `${seen} renders`);
  check("no column is hidden, at any width, for any number of scenarios",
        over.length === 0, over.slice(0, 4).join(" | "));
  check("and the page itself never scrolls sideways with scenarios on it",
        pageOver.length === 0, pageOver.slice(0, 4).join(" | "));
  check("and where it stacks, every figure names the column it came from",
        unlabelled.length === 0, unlabelled.slice(0, 3).join(" | "));
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- it stacks because it MEASURED, not because it is a phone ---");
{
  /* Both directions, or "always stack" would pass the check above. The grid is
     what the page is for — two figures side by side — so it is kept wherever
     it honestly fits, including a single scenario on a 375px phone. */
  const page = await open({ width: 375 });
  await addScenario(page, 1);
  const one375 = await page.evaluate(TABLE);
  check("one scenario fits a phone, so the grid is kept", !one375.stacked && one375.hidden <= 1,
        `stacked=${one375.stacked} hidden=${one375.hidden}`);

  await addScenario(page, 1);
  const two375 = await page.evaluate(TABLE);
  check("a second scenario does not, so it stacks", two375.stacked,
        `hidden=${two375.hidden}`);

  await page.setViewport({ width: 1440, height: 1200 });
  await new Promise((r) => setTimeout(r, 400));
  const two1440 = await page.evaluate(TABLE);
  check("and the grid comes back on a wide window", !two1440.stacked && two1440.hidden <= 1);

  // four scenarios need 738px, which is ABOVE the app's 640px table breakpoint
  // — the band a fixed breakpoint would have left broken.
  await page.setViewport({ width: 700, height: 1200 });
  await addScenario(page, 2);
  await new Promise((r) => setTimeout(r, 500));
  const four700 = await page.evaluate(TABLE);
  check("four scenarios at 700px stack, above the phone breakpoint",
        four700.cols === 6 && four700.stacked && four700.hidden <= 1,
        `cols=${four700.cols} stacked=${four700.stacked} hidden=${four700.hidden}`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the stacked layout is the importer's, and cannot drift from it ---");
{
  /* `.table-stacked` and `.table-cards` are two CSS blocks with the same
     declarations under different gates — a media query cannot add a class and
     a class cannot carry a media query. This is what stops them drifting. */
  const page = await open({ width: 375 });
  await addScenario(page, 2);
  const mine = await page.evaluate(() => {
    const tbl = [...document.querySelectorAll("table")].find((t) => /Take-home/i.test(t.textContent));
    const td = [...tbl.querySelectorAll("tbody td")].find((c) => c.getAttribute("data-label"));
    const cs = getComputedStyle(td), tr = getComputedStyle(td.closest("tr"));
    return {
      thead: getComputedStyle(tbl.querySelector("thead")).display,
      table: getComputedStyle(tbl).display,
      row: tr.display, rowPad: tr.paddingLeft,
      cell: cs.display, just: cs.justifyContent, align: cs.alignItems,
      before: getComputedStyle(td, "::before").content,
    };
  });
  await page.close();

  /* The importer's table exists only once a FILE has been read — opening the
     panel is not enough, which cost this check a run. */
  const imp = await open({ width: 375, route: "/expenses" });
  await imp.evaluate(() => [...document.querySelectorAll("button")]
    .find((b) => /Open importer/i.test(b.textContent))?.click());
  await new Promise((r) => setTimeout(r, 700));
  const fileInput = await imp.$('input[type="file"]');
  // bank.csv, not phone-import.csv: that one is gitignored and written by
  // mobile.mjs, which runs after this check.
  if (fileInput) await fileInput.uploadFile(join(HERE, "fixtures", "bank.csv"));
  await imp.waitForFunction(() => document.querySelectorAll(".table-cards tbody tr").length > 0,
                            { timeout: 30000 }).catch(() => {});
  await new Promise((r) => setTimeout(r, 700));
  const theirs = await imp.evaluate(() => {
    const tbl = document.querySelector(".table-cards");
    if (!tbl) return null;
    const td = [...tbl.querySelectorAll("tbody td")].find((c) => c.getAttribute("data-label"));
    const cs = getComputedStyle(td);
    return {
      thead: getComputedStyle(tbl.querySelector("thead")).display,
      table: getComputedStyle(tbl).display,
      row: getComputedStyle(td.closest("tr")).display,
      cell: cs.display, just: cs.justifyContent, align: cs.alignItems,
    };
  });
  await imp.close();

  check("the stacked table is a block, its head is gone, its rows are blocks",
        mine.table === "block" && mine.thead === "none" && mine.row === "block",
        JSON.stringify(mine));
  check("its cells are flex with the label left and the figure right",
        mine.cell === "flex" && mine.just === "space-between" && mine.align === "baseline");
  check("and the label is drawn from the cell's own data-label",
        /AS YOU ARE NOW|SCENARIO/i.test(mine.before), mine.before);
  check("the importer's card layout still agrees with it, property for property",
        theirs !== null
        && theirs.table === mine.table && theirs.thead === mine.thead
        && theirs.row === mine.row && theirs.cell === mine.cell
        && theirs.just === mine.just && theirs.align === mine.align,
        JSON.stringify(theirs));
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- a generated name never collides with one already in the set ---");
{
  /* `Scenario ${scenarios.length + 1}` produced two "Scenario 2" from add,
     add, remove-first, add — no duplicate typed, eleven React key errors, and
     the winner's colour on both columns. */
  const page = await open();
  await addScenario(page, 2);
  await page.evaluate(() => document.querySelector(".btn-remove")?.click());
  await new Promise((r) => setTimeout(r, 900));
  await addScenario(page, 1);
  const t = await page.evaluate(TABLE);
  const names = t.heads.slice(1);
  check("add, add, remove the first, add again leaves three distinct columns",
        names.length === 3 && new Set(names).size === 3, names.join(" / "));
  check("and React reports no duplicate keys", keyErrors(page).length === 0,
        `${keyErrors(page).length} key errors`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- exactly one column is painted the winner ---");
{
  /* A name is a label, not an identity: the reader may type the same one
     twice. The engine returns `best_index` for this, and the paint follows it. */
  const page = await open();
  await addScenario(page, 2);
  await page.evaluate(() => {
    const set = (el, v) => {
      const p = el instanceof HTMLSelectElement ? HTMLSelectElement : HTMLInputElement;
      Object.getOwnPropertyDescriptor(p.prototype, "value").set.call(el, v);
      el.dispatchEvent(new Event(el instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
    };
    const cards = [...document.querySelectorAll(".card")]
      .filter((c) => c.querySelector('input[aria-label="Scenario name"]'));
    cards.forEach((c, i) => {
      set(c.querySelector('input[aria-label="Scenario name"]'), "Same name");
      set(c.querySelector('input[type="number"]'), i === 0 ? "60000" : "200000");
    });
  });
  await new Promise((r) => setTimeout(r, 1800));
  const t = await page.evaluate(TABLE);
  const n = t.winners.filter(Boolean).length;
  const money = t.worthValues.map((v) => Number(v.replace(/[^0-9.]/g, "")));
  const painted = t.worthValues[t.winners.indexOf(true)];
  check("two columns share a name and only ONE is marked best", n === 1,
        `${n} of ${t.winners.length} painted — ${t.worthValues.join(" / ")}`);
  check("and it is the column with the highest figure",
        Math.max(...money) === Number(String(painted).replace(/[^0-9.]/g, "")),
        `painted ${painted} of ${t.worthValues.join(" / ")}`);
  check("no duplicate-key errors even with a name typed twice",
        keyErrors(page).length === 0, `${keyErrors(page).length}`);
  check("the verdict sentence still names a winner", /leaves you the most/.test(t.verdict ?? ""),
        String(t.verdict).slice(0, 60));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- a blank name still leaves a usable page ---");
{
  const page = await open();
  await addScenario(page, 1);
  await setValue(page, 'input[aria-label="Scenario name"]', "");
  await new Promise((r) => setTimeout(r, 1500));
  const label = await page.evaluate(() =>
    document.querySelector(".btn-remove")?.getAttribute("aria-label"));
  const t = await page.evaluate(TABLE);
  check("the remove button still announces what it removes",
        !!label && label.trim() !== "Remove" && label.length > "Remove ".length, String(label));
  check("and the column still has a heading", (t.heads[2] ?? "").length > 0, t.heads.join("/"));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- contrast on the table, in both themes, stacked and not ---");
{
  /* `sweep.mjs` does both themes at ONE width and had never seen this table at
     all; the stacked rendering is a surface that exists only below the fit
     width. A new surface is a new set of colours nobody has measured. */
  const CONTRAST = () => {
    const lum = (c) => { const [r, g, b] = c.map((v) => { v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
    const parse = (s) => { const m = String(s).match(/rgba?\(([^)]+)\)/); if (!m) return null;
      const p = m[1].split(",").map(parseFloat);
      return p.length > 3 && p[3] === 0 ? null : p.slice(0, 3); };
    const behind = (el) => { let n = el;
      while (n && n !== document.documentElement) {
        const c = parse(getComputedStyle(n).backgroundColor); if (c) return c; n = n.parentElement; }
      return parse(getComputedStyle(document.body).backgroundColor) ?? [255, 255, 255]; };
    const ratio = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
      return (x + 0.05) / (y + 0.05); };
    const sect = [...document.querySelectorAll("section")]
      .find((s) => /Side by side/i.test(s.textContent));
    if (!sect) return { seen: 0, bad: [] };
    const bad = []; let seen = 0;
    const walk = document.createTreeWalker(sect, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walk.nextNode())) {
      const t = node.textContent.trim(); if (!t) continue;
      const el = node.parentElement;
      const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
      const cs = getComputedStyle(el);
      // SVG text is painted with `fill`, not `color` — reading `color` on it
      // returns the inherited body ink and scores a label nobody can see as fine
      const fg = parse(el.namespaceURI?.includes("svg") ? cs.fill : cs.color);
      if (!fg) continue;
      seen++;
      const cr = ratio(fg, behind(el));
      if (cr < 3) bad.push(`${t.slice(0, 24)} ${cr.toFixed(2)}:1`);
    }
    // the ::before labels the stacked rendering invents are text too
    const pseudo = [];
    for (const td of sect.querySelectorAll("td[data-label]")) {
      const cs = getComputedStyle(td, "::before");
      if (cs.content === "none" || !cs.content) continue;
      const fg = parse(cs.color); if (!fg) continue;
      seen++;
      const cr = ratio(fg, behind(td));
      if (cr < 3) pseudo.push(`label ${td.getAttribute("data-label")} ${cr.toFixed(2)}:1`);
    }
    return { seen, bad: [...bad, ...pseudo] };
  };

  let total = 0;
  const bad = [];
  for (const theme of ["light", "dark"]) {
    for (const width of [375, 1440]) {
      const page = await open({ theme, width });
      await addScenario(page, 2);
      const r = await page.evaluate(CONTRAST);
      total += r.seen;
      for (const b of r.bad) bad.push(`${theme}@${width} ${b}`);
      await page.close();
    }
  }
  check("the contrast sweep found text to measure", total > 150, `${total} nodes`);
  check("every rendered text node clears 3:1, both themes, stacked and grid",
        bad.length === 0, bad.slice(0, 4).join(" | "));
}

// ═══════════════════════════════════════════════════════════════════
if (SELFTEST) {
  console.log("\n=== selftest: each check, against an injected fault ===");

  // 1. drop the stacking class and the hidden column must come back
  {
    const page = await open({ width: 375 });
    await addScenario(page, 2);
    const hidden = await page.evaluate(() => {
      const t = [...document.querySelectorAll("table")].find((x) => /Take-home/i.test(x.textContent));
      t.classList.remove("table-stacked");
      const sc = t.closest(".overflow-x-auto");
      return sc.scrollWidth - sc.clientWidth;
    });
    check("[can fail] without stacking, a column really is off screen", hidden > 1,
          `${hidden}px hidden`);
    await page.close();
  }

  // 2. stack a table that fits, and the "grid is kept" assertion must fire
  {
    const page = await open({ width: 375 });
    await addScenario(page, 1);
    const before = await page.evaluate(TABLE);
    const after = await page.evaluate(() => {
      const t = [...document.querySelectorAll("table")].find((x) => /Take-home/i.test(x.textContent));
      t.classList.add("table-stacked");
      return t.classList.contains("table-stacked");
    });
    check("[can fail] a table forced to stack is seen to have stacked",
          !before.stacked && after === true);
    await page.close();
  }

  // 3. paint a second winner and the count must catch it
  {
    const page = await open({ width: 1440 });
    await addScenario(page, 2);
    const n = await page.evaluate(() => {
      const tbl = [...document.querySelectorAll("table")].find((x) => /Take-home/i.test(x.textContent));
      const worth = [...tbl.querySelectorAll("tbody tr")]
        .find((tr) => /Worth, in national-average/i.test(tr.textContent));
      const tds = [...worth.querySelectorAll("td")].slice(1);
      for (const td of tds) {
        const s = td.querySelector("span");
        if (s) s.className = "font-medium text-positive";
      }
      return tds.filter((td) => /text-positive/.test(td.querySelector("span")?.className ?? "")).length;
    });
    check("[can fail] more than one winner is counted as more than one", n > 1, `${n} painted`);
    await page.close();
  }

  // 4. strip the data-labels and the stacked figures lose their owners
  {
    const page = await open({ width: 375 });
    await addScenario(page, 2);
    await page.evaluate(() => {
      const tbl = [...document.querySelectorAll("table")].find((x) => /Take-home/i.test(x.textContent));
      tbl.querySelectorAll("td[data-label]").forEach((td) => td.removeAttribute("data-label"));
    });
    const m = await page.evaluate(TABLE);
    check("[can fail] a stacked figure with no data-label is seen as unlabelled",
          m.stacked && m.labelled < m.valueCells, `${m.labelled}/${m.valueCells} labelled`);
    await page.close();
  }

  // 5. an invisible figure must fail the contrast pass
  {
    const page = await open({ width: 375 });
    await addScenario(page, 2);
    const worst = await page.evaluate(() => {
      const sect = [...document.querySelectorAll("section")]
        .find((s) => /Side by side/i.test(s.textContent));
      const td = sect.querySelector("td[data-label]");
      const bg = getComputedStyle(td.closest("table").closest(".card")).backgroundColor;
      td.style.color = bg;
      return getComputedStyle(td).color === bg;
    });
    check("[can fail] a figure painted its own card's colour is reachable to measure", worst);
    await page.close();
  }
}

await browser.close();
console.log(`\nCOMPARE: ${pass} passed, ${fails.length} failed`);
if (fails.length) { for (const f of fails) console.log("  - " + f); process.exit(1); }
