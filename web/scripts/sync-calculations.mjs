#!/usr/bin/env node
/**
 * Copy the one calculations.py into the serverless function's directory.
 *
 * WHY THIS EXISTS, AND WHY IT IS NOT A SECOND COPY.
 *
 * The maths had drifted into three implementations that disagreed, and one of
 * them was a Next.js backend exactly like this one -- forked in April, still
 * carrying a debt-payoff bug that reported 79 months and $10,194 of interest
 * against a true 56 and $8,458. So the rule is that ../calculations.py at the
 * repo root is the only copy, and everything else imports it.
 *
 * Vercel bundles a Python function from files inside the project's Root
 * Directory, which is `web/`. It cannot reach a sibling of that directory, and
 * `includeFiles` globs cannot escape it either. So the file has to be brought
 * in, and the only question is how to make the brought-in version incapable of
 * being stale or edited.
 *
 * Three things do that:
 *
 *   1. `web/api/calculations.py` is GITIGNORED. It is never committed, so there
 *      is exactly one copy in version control and no second file for anyone to
 *      edit or for a reviewer to mistake for source. If this script does not
 *      run, the file is ABSENT and the API fails to import -- loudly, at deploy
 *      -- rather than serving different numbers from a stale copy. Absence is a
 *      much better failure mode than staleness, which is what actually happened
 *      before and went unnoticed for five months.
 *
 *   2. It is regenerated on every `npm run build` and every `npm run dev`
 *      (prebuild/predev), from the same commit that is being built. There is no
 *      window in which the copy is from a different revision than the source.
 *
 *   3. The header below is prepended, so anyone who opens the file is told not
 *      to edit it. The script verifies afterwards that what it wrote is the
 *      header followed by the source byte for byte.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(here, "..");
// Both stdlib-only modules at the repo root. calculations.py is the maths;
// app_data.py is the starting and demo profiles, which the two front ends must
// agree on — the abandoned scaffold retyped the demo in TypeScript and its copy
// shipped one debt, making the two payoff strategies identical by definition.
const MODULES = ["calculations.py", "app_data.py"];

const HEADER = `# ---------------------------------------------------------------------------
# GENERATED FILE -- DO NOT EDIT, AND DO NOT COMMIT.
#
# Copied verbatim from the repo root by scripts/sync-calculations.mjs,
# which runs on every build. Edits here are silently discarded on the next
# build; edit the source at the repo root instead, where the Streamlit app and
# all 291 assertions read from.
# ---------------------------------------------------------------------------
`;

const missing = MODULES.filter((m) => !existsSync(resolve(WEB, "..", m)));
if (missing.length) {
  console.error(
    `sync-calculations: cannot find ${missing.join(", ")} at the repo root.\n` +
      `The Vercel project's Root Directory must be "web/" with "Include source ` +
      `files outside of the Root Directory" enabled, so the build can see the ` +
      `repo root. Without it the API has no maths and must not deploy.`,
  );
  process.exit(1);
}

const head = Buffer.from(HEADER, "utf8");
for (const name of MODULES) {
  const from = resolve(WEB, "..", name);
  const to = join(WEB, "api", name);
  const source = readFileSync(from);
  mkdirSync(dirname(to), { recursive: true });
  writeFileSync(to, Buffer.concat([head, source]));

  // Prove what landed is the header plus the source, unmodified.
  const written = readFileSync(to);
  const ok =
    written.length === head.length + source.length &&
    written.subarray(0, head.length).equals(head) &&
    written.subarray(head.length).equals(source);
  if (!ok) {
    console.error(`sync-calculations: ${name} does not match its source. Refusing to continue.`);
    process.exit(1);
  }
  console.log(
    `sync-calculations: api/${name} <- ../${name} ` +
      `(${source.length.toLocaleString()} bytes, verified byte-for-byte)`,
  );
}
