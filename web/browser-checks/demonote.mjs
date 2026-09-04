/**
 * The demo note: appears once, retires itself, and never lies.
 *
 * The states that matter are the ones where it must NOT show — after an edit,
 * after a dismissal, after a reload of an edited profile — because a note
 * saying "these are examples" over somebody's real figures is worse than no
 * note at all.
 */
import puppeteer from "puppeteer-core";

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
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

async function fresh() {
  const ctx = await browser.createBrowserContext();
  const page = await ctx.newPage();
  await page.setViewport({ width: 1400, height: 1000, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.log(`     [pageerror] ${String(e).slice(0, 120)}`));
  return { ctx, page };
}
async function go(page, route) {
  await page.goto(BASE + route, { waitUntil: "networkidle0", timeout: 60000 });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 1400));
}
const note = (page) => page.evaluate(() =>
  [...document.querySelectorAll(".card")].some((c) => /example figures/i.test(c.textContent)));
const reload = async (page) => {
  await page.reload({ waitUntil: "networkidle0" });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 1500));
};

/* 1. a first visit ─────────────────────────────────────────────────────── */
{
  const { ctx, page } = await fresh();
  await go(page, "/");
  check("a first visit sees the note", await note(page));
  check("and it offers a way to empty the app", await page.evaluate(() =>
    [...document.querySelectorAll("button")].some((b) => /start empty/i.test(b.textContent))));

  // dismissing
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => /got it/i.test(x.textContent));
    if (b) b.click();
  });
  await new Promise((r) => setTimeout(r, 700));
  check("dismissing removes it", !(await note(page)));
  await reload(page);
  check("and it stays gone after a reload", !(await note(page)));
  await ctx.close();
}

/* 2. an edit retires it, without being dismissed ───────────────────────── */
{
  const { ctx, page } = await fresh();
  await go(page, "/");
  check("note present before any edit", await note(page));

  await go(page, "/budget");
  await page.click('input[placeholder="Add a category…"]');
  await page.type('input[placeholder="Add a category…"]', "ZZMine", { delay: 10 });
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => x.textContent.trim() === "Add");
    if (b && !b.disabled) b.click();
  });
  await new Promise((r) => setTimeout(r, 1200));

  await go(page, "/");
  check("one edit retires the note", !(await note(page)));
  await reload(page);
  check("and it does not come back on a reload of edited figures", !(await note(page)));
  await ctx.close();
}

/* 3. Start empty ───────────────────────────────────────────────────────── */
{
  const { ctx, page } = await fresh();
  await go(page, "/");
  await page.evaluate(() => {
    const b = [...document.querySelectorAll("button")].find((x) => /start empty/i.test(x.textContent));
    if (b) b.click();
  });
  await new Promise((r) => setTimeout(r, 3000));
  check("Start empty clears the note", !(await note(page)));
  const emptied = await page.evaluate(() => {
    const t = document.body.innerText;
    // The demo's rent line is the most distinctive figure it ships.
    return !/1,900/.test(t);
  });
  check("and the demo figures are gone", emptied);
  await reload(page);
  check("the empty profile survives a reload", await page.evaluate(() => !/1,900/.test(document.body.innerText)));
  check("and the note does not reappear over it", !(await note(page)));
  await ctx.close();
}

/* 4. Reset to demo brings it back, because it IS the demo again ────────── */
{
  const { ctx, page } = await fresh();
  await go(page, "/data");
  for (let i = 0; i < 2; i++) {
    await page.evaluate(() => {
      const b = [...document.querySelectorAll("button")].find((x) => /load demo profile/i.test(x.textContent));
      if (b) b.click();
    });
    await new Promise((r) => setTimeout(r, 900));
  }
  await new Promise((r) => setTimeout(r, 2000));
  await go(page, "/");
  check("resetting to the demo brings the note back", await note(page));
  await ctx.close();
}

/* 5. it is not on every page ───────────────────────────────────────────── */
{
  const { ctx, page } = await fresh();
  await go(page, "/budget");
  check("it is not on /budget", !(await note(page)));
  await go(page, "/expenses");
  check("nor on /expenses", !(await note(page)));
  await ctx.close();
}

await browser.close();
console.log(`\nDEMO NOTE: ${pass} passed, ${fails.length} failed`);
for (const f of fails) console.log(`  [BROKEN] ${f}`);
process.exit(fails.length ? 1 : 0);
