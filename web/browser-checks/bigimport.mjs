/**
 * What a REAL first import feels like.
 *
 * The ten-row fixture proves the rules. It says nothing about the shape of the
 * thing a person actually does first, which is to export a year of one card —
 * several hundred to a couple of thousand rows — and hand the whole lot over
 * at once. Every one of those rows renders a checkbox and a <select> carrying
 * every budget category, and every tick re-renders the lot.
 */
import { mkdirSync } from "node:fs";
import puppeteer from "puppeteer-core";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "out");
mkdirSync(OUT, { recursive: true });

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const CSV = join(HERE, "fixtures", "bank-big.csv");

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 900000,
});
const page = await browser.newPage();
await page.setViewport({ width: 1440, height: 1100 });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

await page.goto(`${process.env.BASE ?? "http://localhost:3000"}/expenses`, { waitUntil: "networkidle0" });
await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
  .catch(() => {});
await new Promise((r) => setTimeout(r, 700));

const [openBtn] = await page.$$("xpath/.//button[contains(., 'Open importer')]");
await openBtn.click();
await new Promise((r) => setTimeout(r, 400));

const t0 = Date.now();
const input = await page.$('input[type="file"]');
await input.uploadFile(CSV);
await page.waitForFunction(
  () => {
    const t = [...document.querySelectorAll("table")].find((x) =>
      /Line/.test(x.querySelector("thead")?.textContent ?? ""));
    return /\d+ rows · \d+ to add/i.test(document.body.textContent);
  },
  { timeout: 180000 },
).catch(() => {});
const tPreview = Date.now() - t0;

const shape = await page.evaluate(() => {
  const t = [...document.querySelectorAll("table")].find((x) =>
    /Line/.test(x.querySelector("thead")?.textContent ?? ""));
  const rows = t?.querySelectorAll("tbody tr").length ?? 0;
  return {
    rows,
    selects: document.querySelectorAll("select").length,
    options: document.querySelectorAll("option").length,
    domNodes: document.querySelectorAll("*").length,
    pageHeight: document.documentElement.scrollHeight,
    summary: document.body.textContent.match(/\d+ ROWS · \d+ TO ADD · \$[\d,]+/i)?.[0]
      ?? document.body.textContent.match(/\d+ rows · \d+ to add · \$[\d,.]+/i)?.[0] ?? null,
  };
});

console.log(`preview built in ${tPreview}ms`);
console.log(JSON.stringify(shape, null, 1));

// Tick one checkbox and time the re-render. This is the interaction a person
// does dozens of times while reviewing an import.
const tickTimes = [];
for (let i = 0; i < 3; i++) {
  const ms = await page.evaluate(async () => {
    const t = [...document.querySelectorAll("table")].find((x) =>
      /Line/.test(x.querySelector("thead")?.textContent ?? ""));
    const boxes = [...t.querySelectorAll('input[type="checkbox"]')];
    const box = boxes[Math.floor(boxes.length / 2)];
    const start = performance.now();
    box.click();
    // Wait for React to commit and the browser to paint.
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
    return performance.now() - start;
  });
  tickTimes.push(Math.round(ms));
  await new Promise((r) => setTimeout(r, 250));
}
console.log("tick -> paint (ms):", tickTimes.join(", "));

// Changing a category on one row.
const catMs = await page.evaluate(async () => {
  const t = [...document.querySelectorAll("table")].find((x) =>
    /Line/.test(x.querySelector("thead")?.textContent ?? ""));
  const sel = t.querySelectorAll("select")[20];
  const start = performance.now();
  sel.value = [...sel.options].find((o) => o.value)?.value ?? "";
  sel.dispatchEvent(new Event("change", { bubbles: true }));
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return performance.now() - start;
});
console.log("category change -> paint (ms):", Math.round(catMs));

console.log("errors:", errors.length ? errors.slice(0, 3) : "none");
await page.screenshot({ path: join(OUT, "shot-bigimport.png") });
await browser.close();
