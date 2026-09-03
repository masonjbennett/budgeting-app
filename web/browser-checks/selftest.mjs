/**
 * Prove the sweep can fail.
 *
 * Each fault below is injected into a real, healthy page and the corresponding
 * check is required to fire. A check that has only ever passed has proved
 * nothing — it may be looking at the wrong thing, or at nothing at all.
 */
import puppeteer from "puppeteer-core";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));

const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const src = readFileSync(join(HERE, "sweep.mjs"), "utf8");
const PROBE_SRC = src.slice(src.indexOf("const PROBE = () =>") + "const PROBE = ".length,
                            src.indexOf("const browser = await puppeteer.launch"))
                     .trim().replace(/;$/, "");

const FAULTS = [
  ["contrast", () => {
    const p = document.createElement("p");
    p.textContent = "invisible on purpose";
    p.style.cssText = "color:#faf3ea;background:#fffaf3;padding:4px";
    document.body.appendChild(p);
  }, (r) => r.low.length > 0],

  ["empty chart", () => {
    const svg = document.querySelector(".recharts-wrapper svg");
    svg.querySelectorAll("path,rect,circle,line,g").forEach((n) => n.remove());
  }, (r) => r.emptyCharts.length > 0],

  ["off-palette chart colour", () => {
    const p = document.querySelector(".recharts-wrapper svg path");
    p.setAttribute("fill", "#ff00ff");
  }, (r) => r.offPalette.length > 0],

  ["a var(--x) with no value behind it", () => {
    // A STYLESHEET rule, not an inline style: this is the shape the defect
    // actually takes — someone names a token TypeScript allows and CSS does
    // not define, and the element quietly inherits a colour instead.
    const sheet = document.createElement("style");
    sheet.textContent = ".probe-missing-token { color: var(--s9); }";
    document.head.appendChild(sheet);
  }, (r) => r.unresolved.includes("--s9")],

  ["a gradient is READ, not walked past", () => {
    // White text on a navy gradient is fine. A probe that reads only
    // backgroundColor scores it as white-on-white and invents a defect —
    // which is what an earlier version of this check did, 57 times.
    const d = document.createElement("div");
    d.style.cssText =
      "background:linear-gradient(90deg, rgb(31,90,158), rgb(13,109,86));padding:8px";
    const p = document.createElement("p");
    p.textContent = "white on navy";
    p.style.color = "rgb(255,255,255)";
    d.appendChild(p);
    document.body.appendChild(d);
  }, (r) => r.low.every((l) => l.text !== "white on navy")],
];

const browser = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox"], protocolTimeout: 600000,
});

let ok = 0;
const bad = [];
for (const [name, fault, fires] of FAULTS) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 1000 });
  await page.evaluateOnNewDocument(() => {
    try { localStorage.setItem("mjb_budget_theme", "light"); } catch {}
  });
  await page.goto("http://localhost:3000/year", { waitUntil: "networkidle0" });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), { timeout: 30000 })
    .catch(() => {});
  await new Promise((r) => setTimeout(r, 600));

  const clean = await page.evaluate(`(${PROBE_SRC})()`);
  await page.evaluate(fault);
  const dirty = await page.evaluate(`(${PROBE_SRC})()`);

  const cleanOk = name.includes("gradient") ? true
    : !fires(clean);                      // the healthy page must NOT fire
  const dirtyOk = fires(dirty);           // the faulty page MUST
  if (cleanOk && dirtyOk) { ok++; console.log(`  [can fail] ${name}`); }
  else bad.push(`${name} (clean fires: ${!cleanOk}, dirty fires: ${dirtyOk})`);
  await page.close();
}

await browser.close();
console.log(`\nSELF-TEST: ${ok}/${FAULTS.length} checks proved they can fail`);
for (const b of bad) console.log("  [BROKEN CHECK] " + b);
process.exit(bad.length ? 1 : 0);
