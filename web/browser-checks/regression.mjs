/**
 * The things that were already working, and must keep working.
 *
 * `interact.mjs` drives the features added most recently. This one holds the
 * checks for behaviour that has already been fixed once, where the fix is
 * invisible in the source and only measurable in a browser:
 *
 *   - the cascade-layer fix, by COMPUTED VALUE. Unlayered CSS beat every
 *     Tailwind utility, so `.card p-0` really did render 18px of padding and
 *     every right-aligned `<th>` really did render left. Reading the source
 *     proves nothing here; the computed style is the only witness.
 *   - the mobile drawer at 375px, including focus return and the body scroll
 *     lock — a drawer that leaves the page scrollable behind it is the classic
 *     way this breaks and it looks fine in a screenshot.
 *   - the theme toggle ACROSS A RELOAD, which is where a theme that is only
 *     held in React state falls back to the OS.
 *   - a real Monte Carlo run, because the chart with the most ways to render
 *     empty is the one behind a button nobody clicks in a smoke test.
 */
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
// BASE is overridable so the same checks can be run against a
// deployment: BASE=https://... node sweep.mjs
const BASE = process.env.BASE ?? "http://localhost:3000";

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

async function open(route, { width = 1440, theme = "light" } = {}) {
  const page = await browser.newPage();
  await page.setViewport({ width, height: 1000 });
  await page.evaluateOnNewDocument((t) => {
    try { localStorage.setItem("mjb_budget_theme", t); } catch {}
  }, theme);
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 600));
  return page;
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- cascade layers: a utility in the markup must win ---");
{
  const page = await open("/");
  const measured = await page.evaluate(() => {
    // The exact probe that measured 18px 20px before globals.css moved into
    // @layer base / @layer components.
    const probe = document.createElement("div");
    probe.className = "card p-0";
    document.body.appendChild(probe);
    const cs = getComputedStyle(probe);
    const padding = [cs.paddingTop, cs.paddingRight, cs.paddingBottom, cs.paddingLeft];
    probe.remove();

    const th = document.createElement("table");
    th.innerHTML = '<thead><tr><th class="text-right">x</th></tr></thead>';
    document.body.appendChild(th);
    const align = getComputedStyle(th.querySelector("th")).textAlign;
    th.remove();

    return { padding, align };
  });
  check("`card p-0` computes to zero padding, not the card's own 18px 20px",
        measured.padding.every((p) => p === "0px"), measured.padding.join(" "));
  check("a right-aligned <th> computes to right, not the element rule's left",
        measured.align === "right", measured.align);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the mobile drawer at 375px ---");
{
  const page = await open("/", { width: 375 });

  const closed = await page.evaluate(() => ({
    // At 375 the rail is gone and page content is under the top-left area.
    atPoint: document.elementFromPoint(60, 300)?.closest("aside") === null,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    bodyOverflow: getComputedStyle(document.body).overflow,
  }));
  check("no sidebar under the content at 375px", closed.atPoint);
  check("and no horizontal overflow", closed.overflow <= 1, String(closed.overflow));

  const opener = await page.$('[aria-label="Open navigation"]');
  check("there is an opener", !!opener);
  await opener.click();
  await new Promise((r) => setTimeout(r, 450));

  const open1 = await page.evaluate(() => ({
    dialog: (document.querySelector('[aria-label="Navigation"]')
      ?.getBoundingClientRect().left ?? -999) >= 0,
    // A drawer that leaves the page scrolling behind it looks right and is not.
    locked: getComputedStyle(document.body).overflow === "hidden" ||
            getComputedStyle(document.documentElement).overflow === "hidden",
    focusInside: !!document.activeElement?.closest('[aria-label="Navigation"]'),
  }));
  check("the drawer slides on screen", open1.dialog);
  check("the page behind it does not scroll", open1.locked);
  check("and focus moves into it", open1.focusInside);

  await page.keyboard.press("Escape");
  await new Promise((r) => setTimeout(r, 450));
  const afterEsc = await page.evaluate(() => ({
    gone: (document.querySelector('[aria-label="Navigation"]')
      ?.getBoundingClientRect().right ?? 0) <= 0,
    focusOnOpener: document.activeElement?.getAttribute("aria-label") === "Open navigation",
    unlocked: getComputedStyle(document.body).overflow !== "hidden",
  }));
  check("Escape slides it off canvas", afterEsc.gone);
  check("focus returns to the opener", afterEsc.focusOnOpener);
  check("and the scroll lock is released", afterEsc.unlocked);

  // Navigating from inside the drawer must close it, or the next page renders
  // underneath an open drawer.
  const opener2 = await page.$('[aria-label="Open navigation"]');
  await opener2.click();
  await new Promise((r) => setTimeout(r, 450));
  await page.evaluate(() => {
    const link = [...document.querySelectorAll('[aria-label="Navigation"] a')]
      .find((a) => a.getAttribute("href") === "/year");
    link?.click();
  });
  await new Promise((r) => setTimeout(r, 900));
  const afterNav = await page.evaluate(() => ({
    gone: (document.querySelector('[aria-label="Navigation"]')
      ?.getBoundingClientRect().right ?? 0) <= 0,
    path: location.pathname,
  }));
  check("navigating closes the drawer", afterNav.gone && afterNav.path === "/year",
        `${afterNav.path}, drawer gone: ${afterNav.gone}`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- the theme toggle survives a reload ---");
{
  // Opened WITHOUT the localStorage injection `open()` does.
  // `evaluateOnNewDocument` runs on EVERY navigation, including the reload
  // below — so it was overwriting the very choice this block exists to check
  // had persisted, and reporting the app as broken when the check was.
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  await page.goto(BASE + "/", { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 600));

  const before = await page.evaluate(() => {
    const btn = [...document.querySelectorAll('[aria-label="Colour theme"] button')]
      .find((b) => /dark/i.test(b.textContent));
    btn?.click();
    return { clicked: !!btn };
  });
  check("there is a dark option to click", before.clicked);
  await new Promise((r) => setTimeout(r, 400));

  const set = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute("data-theme"),
    paper: getComputedStyle(document.documentElement).getPropertyValue("--paper").trim(),
  }));
  check("choosing dark stamps data-theme and repaints", set.attr === "dark",
        JSON.stringify(set));

  await page.reload({ waitUntil: "networkidle0" });
  await new Promise((r) => setTimeout(r, 700));
  const after = await page.evaluate(() => ({
    attr: document.documentElement.getAttribute("data-theme"),
    paper: getComputedStyle(document.documentElement).getPropertyValue("--paper").trim(),
    // The inline script in layout.tsx has to stamp this BEFORE first paint, or
    // the page flashes the other theme on every load.
    stampedEarly: document.documentElement.getAttribute("data-theme") === "dark",
  }));
  check("and it is still dark after a reload", after.attr === "dark", JSON.stringify(after));
  check("with the same palette it had before the reload", after.paper === set.paper,
        `${set.paper} -> ${after.paper}`);
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- a real Monte Carlo run ---");
{
  const page = await open("/fire");
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  const [run] = await page.$$("xpath/.//button[contains(., 'Run Monte Carlo')]");
  check("the run button is there", !!run);
  await run.click();
  await page.waitForFunction(
    () => /scenarios/i.test(document.body.textContent), { timeout: 180000 });
  await new Promise((r) => setTimeout(r, 1200));

  const res = await page.evaluate(() => {
    const svgs = [...document.querySelectorAll(".recharts-wrapper svg")];
    return {
      charts: svgs.length,
      // Recharts renders an empty <g> when an entry animation does not
      // complete: a correctly sized SVG with nothing inside it and nothing in
      // the console. Counting the SVGs proves nothing; counting paths does.
      pathsPerChart: svgs.map((s) => s.querySelectorAll("path").length),
      successRate: document.body.textContent.match(/(\d+\.?\d*)%/)?.[0] ?? null,
      hasHistogram: /Where the paths end up/.test(document.body.textContent),
      hasSocialSecurity: /Social Security estimate/.test(document.body.textContent),
      reducesBy: document.body.textContent.match(/Reduces FIRE number by/) !== null,
    };
  });
  check("every chart the run produces has paths in it",
        res.charts >= 4 && res.pathsPerChart.every((n) => n > 0),
        `${res.charts} charts, paths: ${res.pathsPerChart.join(",")}`);
  check("the histogram renders", res.hasHistogram);
  check("the Social Security block renders with its capital equivalent",
        res.hasSocialSecurity && res.reducesBy);
  check("no page errors during the run", errors.length === 0,
        errors.slice(0, 2).join(" | "));
  await page.close();
}

// ═══════════════════════════════════════════════════════════════════
console.log("\n--- a failed refetch must not leave figures unexplained ---");
{
  /* `/debt` and `/investments` do NOT clear their stored result when a
     refetch fails, so the error card sits directly above figures computed
     from the previous inputs. Measured on /investments by failing the route
     after a good load and changing the monthly contribution: the error
     appeared and all three projections were still the old ones.

     The figures are kept deliberately — a network blip emptying the page is
     worse than a labelled stale number — so what this has to prove is that
     the LABEL is there. Invisible in the source: the sentence is greppable,
     the condition gating it is not. */
  for (const [route, endpoint, change] of [
    ["/debt", "/api/debt-payoff", () => {
      const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
      const el = document.querySelector('input[type="range"]');
      d.set.call(el, "700");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }],
    ["/investments", "/api/investment", () => {
      const d = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value");
      const el = [...document.querySelectorAll('input[type="number"]')][1];
      d.set.call(el, "3210");
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }],
  ]) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 1000 });
    let failing = false;
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      if (failing && req.url().includes(endpoint)) return req.abort("failed");
      req.continue();
    });
    await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
    await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
      .catch(() => {});
    await new Promise((r) => setTimeout(r, 1500));

    const before = await page.evaluate(() =>
      [...document.querySelectorAll(".font-num")].map((n) => n.textContent.trim())
        .filter(Boolean).slice(0, 12).join("|"));
    check(`${route}: it had figures that could go stale`, before.length > 0);

    failing = true;
    await page.evaluate(change);
    await new Promise((r) => setTimeout(r, 2500));

    const res = await page.evaluate(() => {
      const card = [...document.querySelectorAll(".mark-critical")]
        .find((d) => /could not|failed/i.test(d.textContent));
      return {
        errored: !!card,
        saysStale: card ? /from before it failed/i.test(card.textContent) : false,
      };
    });
    check(`${route}: a failed refetch surfaces an error`, res.errored);
    check(`${route}: and says the figures under it are the previous ones`, res.saysStale);
    await page.close();
  }
}

await browser.close();
console.log(`\nREGRESSION: ${pass} passed, ${fails.length} failed`);
process.exit(fails.length ? 1 : 0);
