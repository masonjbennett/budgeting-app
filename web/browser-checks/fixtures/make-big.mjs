/**
 * A statement the size a real first import actually is.
 *
 * `bank.csv` is ten hand-written rows and every one of them tests a specific
 * rule — the payment IN, the quoted field with a comma, GYMBOREE, the
 * payment-processor string, the row nothing recognises. It proves the rules
 * and says nothing about SIZE, which is where the importer's other failure
 * mode lives: the first thing anyone does is export twelve months of one card.
 *
 * Generated rather than committed, and seeded rather than random, so the file
 * is reproducible without being 72KB of noise in the diff. The PRNG is a
 * mulberry32 — four lines, deterministic, and it avoids a dependency for
 * something this small.
 *
 * Run:  node fixtures/make-big.mjs        (writes fixtures/bank-big.csv)
 */
import { writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "%20".
const HERE = dirname(fileURLToPath(import.meta.url));

const ROWS = Number(process.env.ROWS ?? 1200);

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const rand = mulberry32(7);
const pick = (xs) => xs[Math.floor(rand() * xs.length)];

// Real merchant shapes, including the ones the category rules have to get
// right: UBER EATS against UBER, GYMBOREE against a Gym category, and a
// merchant nothing recognises.
const MERCHANTS = [
  "TRADER JOES #452", "UBER EATS", "STARBUCKS STORE 4471", "NETFLIX.COM",
  "SHELL OIL 5521", "AMAZON.COM*2K4RT", "WHOLE FOODS MKT", "PLANET FITNESS CLUB",
  "SPOTIFY USA", "CHIPOTLE 1182", "CVS PHARMACY 4471", "TARGET T-2245",
  "DOORDASH*SUSHI", "METRO TRANSIT AUTH", "COMCAST CABLE", "VERIZON WIRELESS",
  "GEICO AUTO PMT", "SQ *BLUE BOTTLE", "LYFT RIDE 4471", "HOME DEPOT 88",
  "KROGER #221", "DUNKIN #33417", "BEST BUY 0042", "WEIRD MERCHANT LLC",
  "GYMBOREE PLAY",
];

const pad = (n) => String(n).padStart(2, "0");
const lines = ["Transaction Date,Post Date,Description,Category,Type,Amount,Memo"];
const d = new Date(Date.UTC(2025, 8, 5));
for (let i = 0; i < ROWS; i++) {
  d.setUTCDate(d.getUTCDate() + pick([0, 0, 1, 1, 1, 2]));
  const stamp = `${pad(d.getUTCMonth() + 1)}/${pad(d.getUTCDate())}/${d.getUTCFullYear()}`;
  const amount = (3.5 + rand() * 236.5).toFixed(2);
  lines.push(`${stamp},${stamp},${pick(MERCHANTS)},Shopping,Sale,-${amount},`);
}

const out = join(HERE, "bank-big.csv");
writeFileSync(out, lines.join("\n") + "\n", "utf8");
console.log(`wrote ${out} — ${ROWS} rows`);
