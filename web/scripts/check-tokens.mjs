/**
 * The token layer is only real if something enforces it.
 *
 * Every colour in this app has to come from globals.css, so that switching
 * theme is a variable change rather than a rewrite. Nothing about that is
 * self-enforcing: a `#5b8def` typed into a component works perfectly in the
 * theme it was typed for and silently renders one theme's ink on the other
 * theme's paper. There is no error, no console warning and no failing test —
 * which is exactly the shape of every defect this project keeps finding by
 * looking at a rendered page instead of at a green suite.
 *
 * So this fails the build. `npm run build` runs it before `next build`.
 *
 * THE TAILWIND STOCK PALETTE COUNTS. `text-slate-400` is `#94a3b8` with a
 * friendlier spelling and follows no theme; the app had 30 of them. The check
 * for those is a list of Tailwind's own palette NAMES rather than a hex
 * pattern, because that is what they look like in the source.
 *
 * WHAT IS ALLOWED, and each is a deliberate hole rather than an oversight:
 *   - globals.css itself, which is where the values are DEFINED;
 *   - `currentColor`, `transparent`, `none`, `inherit` — keywords that carry no
 *     colour of their own and therefore follow the theme by construction;
 *   - `var(--x)` in any form.
 *
 * Run it on its own with `npm run check:tokens`.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not URL.pathname: this repo lives under a directory with a
// space in its name, and the pathname form hands back "Masonjbennett.com%20Website".
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const SRC = join(ROOT, "src");

/** Files whose whole job is to hold colour values. */
const ALLOWED_FILES = new Set(["src/app/globals.css"]);

/** Tailwind's stock palette. A utility in one of these families is a literal. */
const STOCK_PALETTE = [
  "slate", "gray", "zinc", "neutral", "stone",
  "orange", "amber", "lime", "emerald", "teal", "cyan", "sky",
  "blue", "indigo", "violet", "purple", "fuchsia", "pink", "rose",
];
/** Utility prefixes that take a colour. */
const COLOUR_PREFIX =
  "bg|text|border|fill|stroke|from|to|via|ring|shadow|placeholder|decoration|outline|divide|accent|caret";

const RULES = [
  {
    name: "hex colour literal",
    // #rgb / #rrggbb / #rrggbbaa. Word-boundaried so a "#" in prose is fine.
    re: /#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})\b/g,
  },
  {
    name: "rgb()/hsl() colour literal",
    re: /\b(?:rgba?|hsla?)\(\s*[\d.]/g,
  },
  {
    name: "Tailwind stock-palette utility",
    // e.g. text-slate-400, bg-blue-500/10, border-white/[0.08]
    re: new RegExp(
      `\\b(?:${COLOUR_PREFIX})-(?:white|black|${STOCK_PALETTE.join("|")})(?:-\\d{2,3})?(?:\\/[\\w.[\\]]+)?\\b`,
      "g",
    ),
  },
];

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(tsx?|css)$/.test(entry)) out.push(full);
  }
  return out;
}

const findings = [];
for (const file of walk(SRC)) {
  const rel = relative(ROOT, file).split(sep).join("/");
  if (ALLOWED_FILES.has(rel)) continue;
  const lines = readFileSync(file, "utf8").split(/\r?\n/);
  lines.forEach((line, i) => {
    for (const rule of RULES) {
      rule.re.lastIndex = 0;
      let m;
      while ((m = rule.re.exec(line)) !== null) {
        findings.push({ rel, line: i + 1, rule: rule.name, text: m[0], src: line.trim() });
      }
    }
  });
}

if (findings.length) {
  console.error(`\ncheck-tokens: ${findings.length} colour literal(s) in src/\n`);
  for (const f of findings) {
    console.error(`  ${f.rel}:${f.line}  ${f.rule}: ${f.text}`);
    console.error(`      ${f.src.slice(0, 110)}`);
  }
  console.error(
    "\nColours live in src/app/globals.css. Use a token utility (bg-card, text-critical),\n" +
      "cssVar() for a style prop, or usePalette() where a chart needs the resolved value.\n",
  );
  process.exit(1);
}

console.log("check-tokens: no colour literals in src/");
