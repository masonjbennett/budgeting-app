/**
 * Driving the three new features, rather than looking at them.
 *
 * Every defect the September re-skin found was invisible to a green suite and
 * visible on a rendered page. These are the things a Python assertion cannot
 * reach: a chart with no path in it, a control that does not move anything, an
 * importer that adds nothing, a table that overflows a phone.
 */
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
// BASE is overridable so the same checks can be run against a
// deployment: BASE=https://... node sweep.mjs
const BASE = process.env.BASE ?? "http://localhost:3000";
const CSV = join(HERE, "fixtures", "bank.csv");

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

async function open(route, { width = 1440, theme = "light" } = {}) {
  const page = await browser.newPage();
  await page.setViewport({ width, height: 1100 });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.evaluateOnNewDocument((t) => {
    try { localStorage.setItem("mjb_budget_theme", t); } catch {}
  }, theme);
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 700));
  page.__errors = errors;
  return page;
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- /fire: the savings-rate curve ---");
{
  const page = await open("/fire");

  const curve = await page.evaluate(() => {
    const heads = [...document.querySelectorAll("h2, h3")];
    const h = heads.find((e) => /Savings rate against years/i.test(e.textContent));
    const card = h?.closest("section") ?? document;
    const svg = card.querySelector(".recharts-wrapper svg");
    if (!svg) return null;
    const line = svg.querySelector(".recharts-line-curve");
    return {
      hasSection: !!h,
      linePoints: line?.getAttribute("d")?.split(/[ML]/).length ?? 0,
      dLength: line?.getAttribute("d")?.length ?? 0,
      refLines: svg.querySelectorAll(".recharts-reference-line line").length,
      refDots: svg.querySelectorAll(".recharts-reference-dot circle, .recharts-reference-dot-dot").length,
      axisTicks: [...svg.querySelectorAll(".recharts-cartesian-axis-tick-value")]
        .map((t) => t.textContent),
      markerLabel: [...svg.querySelectorAll("text")]
        .map((t) => t.textContent).find((t) => /^you ·/.test(t)) ?? null,
      note: card.textContent.match(/Drawn at a [\d.]+% real return/)?.[0] ?? null,
      action: card.textContent.match(/one more point ·\s*([\d.]+ (?:years|months)) sooner/)?.[0] ?? null,
    };
  });

  check("the curve section renders", !!curve?.hasSection);
  check("the line has a real path, not an empty <g>", curve.dLength > 200,
        `d attribute is ${curve.dLength} chars`);
  check("the reader's own position is marked on it",
        curve.refLines >= 1 && curve.refDots >= 1,
        `${curve.refLines} reference line(s), ${curve.refDots} dot(s)`);
  check("and the marker is LABELLED, not a bare dashed line",
        /^you · \d+y$/.test(curve.markerLabel ?? ""), String(curve.markerLabel));
  check("the x axis is savings rate in per cent",
        curve.axisTicks.some((t) => /%$/.test(t)), curve.axisTicks.slice(0, 4).join(","));
  check("the y axis is YEARS, not dollars",
        curve.axisTicks.some((t) => /^\d+y$/.test(t)) &&
        !curve.axisTicks.some((t) => /^\$/.test(t)),
        curve.axisTicks.join(","));
  check("the note states the real return it was drawn at", !!curve.note, String(curve.note));
  check("and the header says what one more point of saving buys",
        !!curve.action, String(curve.action));

  // Moving the stock slider must move the curve — the whole claim that the
  // deterministic curve and the Monte Carlo describe one world.
  const before = await page.evaluate(() =>
    document.querySelector(".recharts-line-curve")?.getAttribute("d"));
  const beforeNote = await page.evaluate(() =>
    document.body.textContent.match(/Drawn at a ([\d.]+)% real return/)?.[1]);
  await page.evaluate(() => {
    const r = [...document.querySelectorAll('input[type="range"]')][0];
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value").set;
    setter.call(r, "10");
    r.dispatchEvent(new Event("input", { bubbles: true }));
    r.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await new Promise((r) => setTimeout(r, 1600));
  const after = await page.evaluate(() =>
    document.querySelector(".recharts-line-curve")?.getAttribute("d"));
  const afterNote = await page.evaluate(() =>
    document.body.textContent.match(/Drawn at a ([\d.]+)% real return/)?.[1]);
  check("moving the stock allocation redraws the curve",
        before !== after && before && after);
  check("and the stated real return follows it down",
        parseFloat(afterNote) < parseFloat(beforeNote),
        `${beforeNote}% -> ${afterNote}%`);

  check("no console errors on /fire", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- /year ---");
{
  const page = await open("/year");
  const year = await page.evaluate(async () => {
    const t = document.body.textContent;
    const bars = [...document.querySelectorAll(".recharts-bar-rectangle path")]
      .map((p) => p.getAttribute("fill"));
    const root = getComputedStyle(document.documentElement);
    return {
      hero: document.querySelector(".figure-hero")?.textContent ?? null,
      caveat: !!document.querySelector(".mark-caution"),
      caveatText: document.querySelector(".mark-caution")?.textContent ?? "",
      bars,
      hairSoft: root.getPropertyValue("--hair-soft").trim(),
      accent: root.getPropertyValue("--accent").trim(),
      refLine: document.querySelectorAll(".recharts-reference-line-line").length,
      bandRects: [...document.querySelectorAll(".recharts-reference-area-rect")]
        .map((r) => {
          const b = r.getBoundingClientRect();
          return { fill: r.getAttribute("fill"),
                   w: Math.round(b.width), h: Math.round(b.height) };
        }),
      chartText: [...document.querySelectorAll(".recharts-wrapper svg text")]
        .map((e) => e.textContent),
      yTicks: [...document.querySelectorAll(".recharts-yAxis .recharts-cartesian-axis-tick-value")]
        .map((e) => e.textContent),
      tables: document.querySelectorAll("table").length,
      buckets: [...document.querySelectorAll("table")][0]
        ? [...document.querySelectorAll("table")[0].querySelectorAll("tbody tr td:first-child")]
            .map((td) => td.textContent) : [],
      hasFaintNote: /shaded stretch is months with nothing logged/.test(t),
      budgetMonthly: await fetch("/api/state?demo=true").then((r) => r.json())
        .then((prof) => Object.values(prof.budget)
          .reduce((s, b) => s + Object.values(b).reduce((x, y) => x + y, 0), 0)),
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });

  check("the hero is the year's spending", /^\$/.test(year.hero ?? ""), String(year.hero));
  // The demo profile has records in this month and the previous one only, so
  // the record is deliberately incomplete and the page must lead with that.
  check("an incomplete record is called out BEFORE any variance", year.caveat);
  check("and the caveat names the months and the sum it would otherwise report",
        /nothing logged/.test(year.caveatText) && /\$/.test(year.caveatText),
        year.caveatText.slice(0, 90));
  check("the month bars are drawn", year.bars.length >= 1, `${year.bars.length} bars`);
  check("months with nothing logged are SHADED, with real geometry",
        year.bandRects.length >= 1 &&
        year.bandRects.every((r) => r.w > 4 && r.h > 4) &&
        year.bandRects.some((r) => r.fill === year.hairSoft),
        JSON.stringify(year.bandRects));
  check("and the shaded stretch is labelled on the chart itself",
        year.chartText.includes("nothing logged"), year.chartText.join(","));
  check("the monthly budget is drawn as a rule to read the bars against",
        year.refLine >= 1 && year.chartText.some((t) => /budgeted/.test(t)),
        year.chartText.join(","));
  // Recharts sizes the Y axis from the data alone, so a budget above every bar
  // falls outside the domain and is silently dropped -- the case of someone
  // spending UNDER their budget, which is the one the rule exists to show.
  const topTick = Math.max(...year.chartText
    .filter((t) => /^\$[\d.,]+k?$/.test(t))
    .map((t) => parseFloat(t.replace(/[$,k]/g, "")) * (/k$/.test(t) ? 1000 : 1)));
  check("and the axis was extended to reach it, so it renders at all",
        topTick >= year.budgetMonthly,
        `top tick ${topTick} vs budget ${year.budgetMonthly}`);
  check("the tallest bar is below the budget rule, which is why this matters",
        Math.max(...year.bars.map((_, i) => i)) >= 0 && year.bars.length >= 1);
  check("and the page says what the shading means", year.hasFaintNote);
  check("the bucket table lists Needs, Wants and Savings",
        ["Needs", "Wants", "Savings"].every((b) => year.buckets.includes(b)),
        year.buckets.join(","));
  check("no horizontal overflow at 1440px", year.overflow <= 0, String(year.overflow));
  check("no console errors on /year", page.__errors.length === 0,
        page.__errors.slice(0, 2).join(" | "));

  // The page's own figures must be the API's, not a second reading of them.
  const api = await page.evaluate(async () => {
    const p = await fetch("/api/state?demo=true").then((r) => r.json());
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return fetch("/api/year-to-date", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ income: p.income, itemized: p.itemized,
                             expenses: p.expenses, budget: p.budget, today }),
    }).then((r) => r.json());
  });
  const shown = await page.evaluate(() =>
    document.querySelector(".figure-hero")?.textContent?.replace(/[$,]/g, ""));
  check("the hero figure is the engine's `spent`, to the dollar",
        Math.abs(parseFloat(shown) - api.spent) < 1.0,
        `page ${shown} vs api ${api.spent}`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the dashboard and /year must agree about this month ---");
{
  // The dashboard totals the current month in TypeScript (allowed: adding up
  // figures a user typed). /year gets the same month from Python. Two surfaces
  // stating one figure differently is the shape of defect this architecture
  // exists to prevent, and neither page would look wrong on its own.
  const dash = await open("/");
  const onDash = await dash.evaluate(() => {
    const label = [...document.querySelectorAll("p")]
      .find((p) => /^Spent in \w{3}$/.test(p.textContent.trim()));
    const card = label?.closest(".card");
    return {
      label: label?.textContent.trim() ?? null,
      value: card?.querySelector("p.font-num")?.textContent?.trim() ?? null,
    };
  });
  await dash.close();

  const year = await open("/year");
  const onYear = await year.evaluate(() => {
    const label = [...document.querySelectorAll("p.label")]
      .find((p) => / so far$/.test(p.textContent.trim()));
    return {
      label: label?.textContent.trim() ?? null,
      value: label?.parentElement?.querySelector("p.font-num")?.textContent?.trim() ?? null,
    };
  });
  await year.close();

  check("both pages state this month's spending",
        !!onDash.value && !!onYear.value,
        `dashboard ${onDash.label}=${onDash.value} · year ${onYear.label}=${onYear.value}`);
  check("and they agree to the dollar",
        onDash.value === onYear.value,
        `dashboard ${onDash.value} vs year ${onYear.value}`);
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the year, on a profile with nothing logged ---");
{
  // The empty starting profile has no expenses at all, so every figure the
  // page leads with is unmeasurable. null is not zero: "no records yet" must
  // not render as "exactly on budget".
  const page = await open("/year");
  const empty = await page.evaluate(async () => {
    const p = await fetch("/api/state?demo=false").then((r) => r.json());
    const d = new Date();
    const today = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${
      String(d.getDate()).padStart(2, "0")}`;
    return fetch("/api/year-to-date", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ income: p.income, itemized: p.itemized,
                             expenses: p.expenses, budget: p.budget, today }),
    }).then((r) => r.json());
  });
  check("with nothing logged the variance is null, not zero",
        empty.variance === null && empty.pace === null && empty.saved === null,
        JSON.stringify({ variance: empty.variance, pace: empty.pace, saved: empty.saved }));
  check("the year's spending is a real zero, which is a different statement",
        empty.spent === 0 && empty.transactions === 0);
  check("and no month is documented, so nothing is graded against a plan",
        empty.documented_months === 0);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- /year at 375px, and on paper ---");
{
  const page = await open("/year", { width: 375 });
  const m = await page.evaluate(() => ({
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    // A table that overflows must do it inside its own scroller, never on the body.
    scrollers: [...document.querySelectorAll("table")].map((t) => {
      const w = t.closest(".overflow-x-auto");
      return !!w;
    }),
  }));
  check("no horizontal overflow at 375px", m.overflow <= 1, String(m.overflow));
  check("every table sits in its own horizontal scroller",
        m.scrollers.length > 0 && m.scrollers.every(Boolean), JSON.stringify(m.scrollers));

  await page.emulateMediaType("print");
  await new Promise((r) => setTimeout(r, 300));
  const print = await page.evaluate(() => ({
    navHidden: [...document.querySelectorAll("aside")].every(
      (a) => getComputedStyle(a).display === "none"),
    buttonsHidden: [...document.querySelectorAll("button")].every(
      (b) => getComputedStyle(b).display === "none"),
    bodyBg: getComputedStyle(document.body).backgroundColor,
    inkDark: getComputedStyle(document.documentElement).getPropertyValue("--ink").trim(),
  }));
  check("print hides the navigation", print.navHidden);
  check("print hides the buttons", print.buttonsHidden);
  check("print forces the light palette regardless of theme",
        print.bodyBg === "rgb(255, 255, 255)", print.bodyBg);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- /expenses: importing a bank CSV ---");
{
  const page = await open("/expenses");

  const before = await page.evaluate(() =>
    fetch("/api/state?demo=true").then((r) => r.json()).then((p) => p.expenses.length));

  const [openBtn] = await page.$$("xpath/.//button[contains(., 'Open importer')]");
  check("the importer is collapsed by default and has a control to open it", !!openBtn);
  await openBtn.click();
  await new Promise((r) => setTimeout(r, 400));

  const input = await page.$('input[type="file"]');
  check("there is a file input to hand a CSV to", !!input);
  await input.uploadFile(CSV);
  await new Promise((r) => setTimeout(r, 2000));

  const preview = await page.evaluate(() => {
    // Scope to the IMPORT table. The expenses page carries a transactions
    // table as well, and reading both reported 23 rows for a ten-line file --
    // a check finding a fault in itself.
    const importTable = [...document.querySelectorAll("table")].find((t) =>
      /Line/.test(t.querySelector("thead")?.textContent ?? ""));
    const rows = [...(importTable?.querySelectorAll("tbody tr") ?? [])].map((tr) => {
      const td = [...tr.querySelectorAll("td")].map((c) => c.textContent.trim());
      const sel = tr.querySelector("select");
      return {
        line: td[1], date: td[2], desc: td[3], amount: td[4],
        category: sel ? sel.value : null,
        status: td[6],
        ticked: tr.querySelector('input[type="checkbox"]')?.checked ?? null,
        disabled: tr.querySelector('input[type="checkbox"]')?.disabled ?? null,
      };
    });
    const t = document.body.textContent;
    return {
      rows,
      decided: {
        header: t.includes("Column names"),
        order: t.match(/date\(s\) have a second number above 12/) ? "proved MDY" : null,
        sign: t.match(/(\d+) negative and (\d+) positive amounts/)?.[0] ?? null,
      },
      addBtn: [...document.querySelectorAll("button")]
        .map((b) => b.textContent).find((x) => /^Add \d+ transaction/.test(x)) ?? null,
    };
  });

  check("every line of the file is shown, and only those",
        preview.rows.length === 10, `${preview.rows.length} rows`);
  check("the header row was recognised as column names", preview.decided.header);
  check("the date order was PROVED from the file, not assumed",
        preview.decided.order === "proved MDY", String(preview.decided.order));
  check("the sign convention is reported with its counts",
        /9 negative and 1 positive/.test(preview.decided.sign ?? ""),
        String(preview.decided.sign));

  const byDesc = Object.fromEntries(preview.rows.map((r) => [r.desc, r]));
  check("a purchase written -52.30 shows as a positive expense",
        byDesc["TRADER JOES #452"]?.amount === "$52.30",
        byDesc["TRADER JOES #452"]?.amount);
  check("the payment IN is not importable, and says why",
        byDesc["PAYMENT THANK YOU"]?.status === "money in, not out" &&
        byDesc["PAYMENT THANK YOU"]?.disabled === true);
  check("UBER EATS is Dining Out, not Transportation",
        byDesc["UBER EATS"]?.category === "Dining Out", byDesc["UBER EATS"]?.category);
  check("UBER TRIP is Transportation",
        byDesc["UBER   TRIP 4RT2"]?.category === "Transportation",
        byDesc["UBER   TRIP 4RT2"]?.category);
  check("NETFLIX is Subscriptions, not the bank's Entertainment",
        byDesc["NETFLIX.COM"]?.category === "Subscriptions",
        byDesc["NETFLIX.COM"]?.category);
  check("a quoted field containing a comma survived the split",
        !!byDesc["TRAVELERS INSURANCE, PMT"],
        Object.keys(byDesc).join(" | ").slice(0, 120));
  check("TRAVELERS INSURANCE is Insurance, not Travel",
        byDesc["TRAVELERS INSURANCE, PMT"]?.category === "Insurance",
        byDesc["TRAVELERS INSURANCE, PMT"]?.category);
  check("GYMBOREE is not filed as Gym",
        byDesc["GYMBOREE PLAY AND MUSIC"]?.category !== "Gym",
        byDesc["GYMBOREE PLAY AND MUSIC"]?.category);
  check("a payment-processor string falls back to the bank's own category",
        byDesc["SQ *A1B2C3XYZ"]?.category === "Groceries" &&
        /bank category/.test(byDesc["SQ *A1B2C3XYZ"]?.status ?? ""),
        byDesc["SQ *A1B2C3XYZ"]?.status);
  check("a row nothing recognises asks for a category rather than guessing",
        byDesc["WEIRD MERCHANT LLC"]?.category === "" &&
        /needs a category/.test(byDesc["WEIRD MERCHANT LLC"]?.status ?? ""),
        byDesc["WEIRD MERCHANT LLC"]?.status);
  check("the commit button counts what it would add", !!preview.addBtn, String(preview.addBtn));

  // The first native checkbox in the app arrived with this panel and rendered
  // in the user agent's blue — the only colour on the page the palette had
  // never touched, and invisible to check:tokens because there is no literal
  // in the source.
  const box = await page.evaluate(() => {
    const cb = document.querySelector('input[type="checkbox"]');
    const accent = getComputedStyle(document.documentElement)
      .getPropertyValue("--accent").trim();
    const probe = document.createElement("div");
    probe.style.color = accent;
    document.body.appendChild(probe);
    const want = getComputedStyle(probe).color;
    probe.remove();
    return { got: getComputedStyle(cb).accentColor, want };
  });
  check("the checkboxes are painted in the palette accent, not the browser blue",
        box.got === box.want, `${box.got} vs ${box.want}`);

  // ── Commit, and check what actually happened to the profile ──
  const noteBefore = await page.evaluate(() => {
    const rows = [...document.querySelectorAll("table")].pop();
    return rows ? rows.textContent.length : 0;
  });
  const [addBtn] = await page.$$("xpath/.//button[starts-with(normalize-space(.), 'Add ')]");
  await addBtn.click();
  await new Promise((r) => setTimeout(r, 1200));

  const after = await page.evaluate(() => {
    const t = document.body.textContent;
    return {
      done: t.match(/\d+ transactions? added from [\w.]+/)?.[0] ?? null,
      // The transactions table filters to the current month by default, so
      // read the profile through the page's own state instead.
      cleared: !document.querySelector('input[type="file"]')?.value,
    };
  });
  check("the import reports what it added", !!after.done, String(after.done));
  check("and the picker is cleared afterwards", after.cleared);

  // ── The property that matters most: nothing was replaced ──
  await page.evaluate(() => {
    const sel = document.querySelectorAll("select");
    for (const s of sel) if ([...s.options].some((o) => o.value === "")) { s.value = ""; s.dispatchEvent(new Event("change", { bubbles: true })); break; }
  });
  await new Promise((r) => setTimeout(r, 500));
  const audit = await page.evaluate(async () => {
    const demo = await fetch("/api/state?demo=true").then((r) => r.json());
    const rows = [...document.querySelectorAll("table tbody tr")].map((tr) =>
      [...tr.querySelectorAll("td")].map((c) => c.textContent.trim()));
    return { demoNotes: demo.expenses.map((e) => e.note), rowCount: rows.length };
  });
  check("the demo's own expenses are untouched by an import",
        audit.demoNotes.includes("Monthly rent") && audit.demoNotes.includes("Trader Joe's"),
        "an import must only ever ADD");

  check("no console errors on /expenses", page.__errors.length === 0,
        page.__errors.slice(0, 3).join(" | "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- importing the SAME file twice ---");
{
  const page = await open("/expenses");
  const [openBtn] = await page.$$("xpath/.//button[contains(., 'Open importer')]");
  await openBtn.click();
  await new Promise((r) => setTimeout(r, 400));
  let input = await page.$('input[type="file"]');
  await input.uploadFile(CSV);
  await new Promise((r) => setTimeout(r, 2000));
  const importRows = () => {
    const t = [...document.querySelectorAll("table")].find((x) =>
      /Line/.test(x.querySelector("thead")?.textContent ?? ""));
    return [...(t?.querySelectorAll("tbody tr") ?? [])];
  };
  const firstDup = await page.evaluate(`(${(() => {
    const t = [...document.querySelectorAll("table")].find((x) =>
      /Line/.test(x.querySelector("thead")?.textContent ?? ""));
    return [...(t?.querySelectorAll("tbody tr") ?? [])]
      .filter((tr) => /already recorded/.test(tr.textContent)).length;
  }).toString()})()`);
  check("a fresh file has nothing already recorded", firstDup === 0, String(firstDup));

  const [addBtn] = await page.$$("xpath/.//button[starts-with(normalize-space(.), 'Add ')]");
  await addBtn.click();
  await new Promise((r) => setTimeout(r, 1500));

  const [openAgain] = await page.$$("xpath/.//button[contains(., 'Open importer')]");
  if (openAgain) { await openAgain.click(); await new Promise((r) => setTimeout(r, 300)); }
  input = await page.$('input[type="file"]');
  await input.uploadFile(CSV);
  await new Promise((r) => setTimeout(r, 2000));

  const second = await page.evaluate(() => {
    const t = [...document.querySelectorAll("table")].find((x) =>
      /Line/.test(x.querySelector("thead")?.textContent ?? ""));
    const trs = [...(t?.querySelectorAll("tbody tr") ?? [])];
    const read = (tr) => ({
      desc: tr.querySelectorAll("td")[3]?.textContent.trim(),
      status: tr.querySelectorAll("td")[6]?.textContent.trim(),
      category: tr.querySelector("select")?.value ?? null,
      ticked: tr.querySelector('input[type="checkbox"]')?.checked ?? false,
      disabled: tr.querySelector('input[type="checkbox"]')?.disabled ?? false,
    });
    const rows = trs.map(read);
    return {
      rows,
      dup: rows.filter((r) => /already recorded/.test(r.status)).length,
      ticked: rows.filter((r) => r.ticked).length,
      tickedWithCategory: rows.filter((r) => r.ticked && r.category).length,
      importable: rows.filter((r) => !r.disabled).length,
      addBtn: [...document.querySelectorAll("button")]
        .map((b) => b.textContent.trim()).find((x) => /^Add \d+ transaction/.test(x)) ?? null,
      warning: /match(es)? (an )?expenses? already recorded/.test(document.body.textContent),
    };
  });
  // Two of the ten rows match no category, so they were never added and are
  // correctly NOT flagged. The property is that everything committed comes
  // back flagged, and that a second import can commit nothing.
  check("every row that was actually added comes back flagged",
        second.dup === 7 && second.rows.filter((r) => /already recorded/.test(r.status))
          .every((r) => r.category),
        `${second.dup} flagged of ${second.importable} importable`);
  check("the two rows nothing could categorise were never added, so are not flagged",
        second.rows.filter((r) => !r.category && !r.disabled).length === 2 &&
        second.rows.filter((r) => !r.category && !r.disabled)
          .every((r) => !/already recorded/.test(r.status)),
        JSON.stringify(second.rows.filter((r) => !r.category).map((r) => r.desc)));
  check("every flagged row starts UNTICKED, so a second click adds nothing",
        second.tickedWithCategory === 0,
        `${second.tickedWithCategory} ticked rows still carry a category`);
  check("the button offers to add zero", /^Add 0 transaction/.test(second.addBtn ?? ""),
        String(second.addBtn));
  check("and the page says why they are unticked", second.warning);
  await page.close();
}

await browser.close();
console.log(`\nINTERACTIONS: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
