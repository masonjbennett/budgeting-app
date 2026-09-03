# web/ — the Next.js + FastAPI front end

The Streamlit app at the repo root and this one are two front ends over **one**
calculation engine. This directory is the second front end. It exists because a
budgeting app is a consumer product where polish is part of whether it seems
good, and a `*.streamlit.app` URL with a Fork button reads as a class project.

Deployed as its own Vercel project at **budget.masonjbennett.com**. The
Streamlit app stays live and unchanged until this one is genuinely better.

```
budgeting-app/
  calculations.py       ← the maths. ONE copy. Read by both front ends.
  app_data.py           ← the starting and demo profiles. ONE copy.
  budget_app.py         ← Streamlit front end (deploys to Streamlit Cloud)
  test_calc / test_cloud / test_stress    413 assertions
  test_calc_mutations.py  22 engine defects, each required to fail test_calc
  web/                  ← THIS. Vercel Root Directory.
    api/index.py        one Vercel Function, fourteen routes, no arithmetic
    api/calculations.py GENERATED at build time. Gitignored. Never edit.
    api/app_data.py     GENERATED at build time. Gitignored. Never edit.
    scripts/sync-calculations.mjs
    src/                Next.js App Router, Tailwind 4, Recharts
    test_api.py         106 assertions against the shipping routes
    test_api_mutations.py   11 shipped bugs, each required to fail the suite
    DEPLOY.md           the click-by-click for the first deploy
```

## Running it locally

Two processes: `next dev` has no Python runtime, so `next.config.ts` proxies
`/api` to a local uvicorn **in development only**.

```bash
# once
npm install
py -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt

# api  (port 8000)
.venv/Scripts/python.exe -m uvicorn index:app --app-dir api --port 8000
# web  (port 3000)
npm run dev
```

Or from the website working folder: `preview_start "budget-api"` then
`preview_start "budget-web"`.

```bash
npm run build          # sync, then check:tokens, then next build
npm run check:tokens   # colour literals and missing tokens, on its own
npx eslint src         # must be clean
.venv/Scripts/python.exe test_api.py
.venv/Scripts/python.exe test_api_mutations.py
```

**The suites are not enough here and never have been.** Every defect this
project has found lately was invisible to a green suite and visible on a
rendered page: dead CSS rules, a chart with no paths, white-on-white in the
other theme, three Sankey ribbons painted grey because a gradient id contained
a space. The browser checks used during the re-skin live in the session
scratchpad rather than the repo (they need a real Chrome and a running dev
server, which CI here does not have) and are worth rebuilding rather than
skipping:

- **every route in both themes** — every `var(--x)` referenced in CSS has a
  value, every rendered text node clears 3:1, charts have paths, every painted
  chart colour is a palette token, no console errors. 130 assertions over 13
  routes;
- **the interactions** — the cascade-layer fix by computed value, the mobile
  drawer at 375px including focus and body-scroll, the theme toggle across a
  reload, a real Monte Carlo run;
- **print emulation in both themes**, which is how a print rule usually ships
  dead.

Break each on purpose and watch it fail before trusting it. **This is not
ceremony — a check written from a description passes on a healthy page whether
or not it is looking at anything.** Rebuilding the sweep in September, one of
its five checks could not fail: it searched computed styles for a literal
`var(`, and an undefined custom property does not survive into computed style
at all — it resolves to `unset` and the element INHERITS a colour, which is
exactly why that defect is invisible. It was replaced with one that reads the
stylesheets, collects every `var(--x)` actually referenced, and asks the root
whether it has a value. Two of the print check's own first failures were also
the check's fault rather than the code's.

## The rules this codebase is built around

Each of these is here because the opposite already shipped and was wrong.

### 1. There is one copy of the maths, and it is not in this directory

`api/calculations.py` and `api/app_data.py` are **generated**, **gitignored**,
and rewritten from the repo root on every `npm run build` and `npm run dev`.

Vercel bundles a Python function from files inside the Root Directory (`web/`)
and cannot reach a sibling of it — `includeFiles` globs cannot escape it either.
So the file has to be copied, and the only question was how to make the copy
incapable of going stale:

- it is never committed, so exactly one copy is in version control;
- if the sync does not run, the file is **absent** and the API fails to import
  — loudly, at deploy — rather than serving different numbers from an old copy;
- it is regenerated from the same commit that is being built;
- the sync verifies afterwards that what it wrote is its header plus the source,
  byte for byte, and `test_api.py` checks the same thing.

The precedent: this maths had drifted into three implementations that disagreed,
and one of them was a Next.js backend exactly like this one. Its debt engine
reported **79 months and $10,194** of interest where the real one says **56 and
$8,458**, and its `compute_take_home` had no state marginal rate at all.

### 2. No arithmetic in TypeScript

Not a ratio, not a rate, not a threshold. `src/lib/api.ts` is the only way a
number enters the app. The one thing the client does is add up figures a user
typed, because totalling a column of assets is not a rule anyone can get wrong
in a way that misleads.

This is not fastidiousness. Both earlier versions computed debt-to-income and
emergency-fund coverage in the display layer and both got them wrong the same
two ways:

- **DTI** read a single budget CATEGORY NAME, so someone with $35,000 of student
  loans and a zero in that row saw *"0.0% — Debt-Free"*. It also divided by
  take-home while grading against the 20%/36% bands, which lenders define on
  gross — a denominator a quarter too small.
- **Emergency fund** looked up the literal asset key `"Savings"`, so renaming
  that row to "High-Yield Savings" read 0.0 months as though it had been
  measured.

Both now come from `/api/dashboard`, and `test_api_mutations.py` reintroduces
each one and requires the suite to fail.

### 3. Nothing is invented

If a number is not known, it is `null` and the UI says which. `null` and `0.0`
are different answers: "could not be measured" is not "measured, and it is
zero". Every card has a written state for that case.

The scaffold this replaced drew dashboard sparklines from hardcoded arrays —
`[2100, 2300, 1900, 2600, 2400, 2200, totalSpent]` — and printed
**"+$1,700 from last month"** as a literal next to a real balance. Month-over-
month now comes from the expenses actually recorded, and says "no prior month to
compare" when there is none. The net-worth trend only draws from snapshots the
user has logged.

### 4. Auth is browser-side; the API is a pure calculator

The browser talks to Supabase directly and row-level security enforces isolation
(policies in `../SUPABASE_SETUP.md`). The Python function therefore never sees a
credential or holds a JWT — which is exactly the failure the Streamlit app's
`_db()` was rebuilt to avoid, where one shared cached client carried whichever
user's token was attached last.

**That is only safe while every route stays a pure calculator over numbers the
caller supplies.** Nothing in `api/` may read or write `user_data`. If something
ever needs to, it needs authentication first. `test_api.py` asserts this against
the parsed AST, not the file text — the first version of that check matched the
module docstring's own sentence saying `user_data` must not appear, and failed
on a file that was already correct.

### 5. Colour lives in globals.css, and a check enforces it

Every colour is a CSS custom property defined once, in three theme states
(light on bare `:root`, `prefers-color-scheme` guarded with
`:not([data-theme="light"])`, and an explicit `[data-theme="dark"]` so the
toggle wins both ways). No component may hold one.

That is not self-enforcing: a `#5b8def` typed into a component works perfectly
in the theme it was typed for and silently renders one theme's ink on the
other theme's paper — no error, no warning, no failing test. So
`scripts/check-tokens.mjs` fails the build on a hex, on `rgb()`/`hsl()`, and on
Tailwind's **stock palette**, because `text-slate-400` is `#94a3b8` with a
friendlier spelling and there were 30 of them. It also asserts that every token
`tokens.ts` can NAME exists in all three theme blocks — `cssVar("s9")` type-
checks, renders `var(--s9)` and paints *nothing*, which is worse than a literal
because there is nothing to grep for.

The re-skin began with 116 literals across `src/`. The count is zero.

**Charts read resolved values through `usePalette`, not `var()` strings.**
Handing Recharts `"var(--s1)"` does work — an SVG presentation attribute is
parsed as CSS in Chromium, verified — but whether Safari and Firefox agree
cannot be checked from here, and the failure mode is a chart drawn in black on
a phone. Our own SVG (the Sankey) uses the `style` prop, where a custom
property is guaranteed.

The engine emits tone names as plain strings, which TypeScript cannot follow
across HTTP, so `test_api.py` reads the map out of the shipping `tokens.ts` and
requires every tone the engine can emit to be in it.

### 6. globals.css is inside cascade layers, and that is load-bearing

Element rules go in `@layer base`, component classes in `@layer components`.
Tailwind's utilities live in `@layer utilities`, and **unlayered CSS beats
every layered rule** no matter how weak its selector — so an unlayered
`.card { padding: 1.25rem }` silently beat `p-0`, and
`thead th { text-align: left }` silently beat `text-right`.

Both were really happening before the re-skin: a `card p-0` probe computed
`18px 20px` of padding, and every right-aligned table header rendered left.
Same family as the `pl-7` that lost to `input[type="number"]`. If you add a
rule here, put it in a layer.

### 7. A rule that can only be tested in Python belongs in Python, and the
### mutation harness for the engine is a SEPARATE file

`web/test_api_mutations.py` cannot mutate `api/calculations.py`: any edit there
also trips the byte-for-byte sync check, so the mutation reports itself caught
whatever the assertion aimed at it is worth. Its own header says so.

`../test_calc_mutations.py` therefore mutates the ROOT `calculations.py` and
requires `test_calc.py` to fail. There is no sync check between those two, so a
mutation is caught only by an assertion that looks at the behaviour. It found
two assertions that were decoration on the day it was written:

- *"TRAVELERS INSURANCE is not Travel"* passed with the word-boundary rule
  REMOVED, because "insurance" is longer than "travel" and won anyway. The
  cases that discriminate are ones with no longer match to rescue them —
  GYMBOREE, PARENTS MAGAZINE, the METROPOLITAN MUSEUM, a TOLLHOUSE BAKERY.
- *"the longest match wins"* passed with the ordering REVERSED, because
  `suggest_category` had a comparison per source and the mutation only reversed
  one of them. It now scores both on one list with one comparison.

## Things measured, with the numbers

**Recharts, not Plotly.** `plotly.js-dist-min` was 4.51 MB in one chunk, **944
KB brotli**, for five trace types out of the forty-odd it ships — lazily loaded
but paid for on the dashboard, which is the landing page. The entire app now,
React and Next and Supabase and every page included, is **336 KB brotli**.

**Chart entry animations are off everywhere, and that is a correctness
decision.** Recharts renders a Pie's sectors as EMPTY `<g>` groups until its
entry animation finishes: ten sector groups with no `<path>` inside them, a
correctly sized SVG, and nothing in the console. Where the animation does not
run to completion the chart is permanently, silently blank. Measured side by
side on one page: identical pies with `isAnimationActive` on and off rendered
**0 paths and 3 paths**. Same family as an IntersectionObserver that never fires
in a throttled surface — a visual nicety whose failure mode is an empty panel
where a number should be.

**Input padding is an inline style, not a `pl-7` class.** `globals.css` styles
`input[type="number"]` by element+attribute (specificity 0,1,1), which beats a
`.pl-7` utility (0,1,0) — so the class was dead and the `$` prefix rendered
directly on top of the value. Measured: padding stayed at 12px and the prefix's
right edge sat at exactly the x where the text began. Same shape as the
Streamlit sidebar rules that lost to a matched descendant selector.

**The Monte Carlo needs no numpy.** It supplied normal draws, a 2×2 Cholesky of
a constant matrix, percentiles and array storage; none of that needs a
dependency. The largest run the UI offers — 5,000 sims × 71 years — takes
**0.91s** in pure Python, against a 60s function limit. So `requirements.txt` is
two lines and `calculations.py` stays stdlib-only.

**The hero figure is JetBrains Mono, and that was measured.** All three faces
were rendered at 52px against real figures. Instrument Serif carries no tabular
figures, so the string width swings **65.3px** across the digits a count-up
passes through and `font-variant-numeric: tabular-nums` cannot fix it — the
feature is absent from the font. Space Grotesk swings 68.9px and IS fixed by
that property, so it was the runner-up. Mono is 0px by construction, is already
the convention for every other number, and is the widest of the three at size
(312px against the serif's 189px for one figure) — so it reads as the largest
thing on the page, which is the job. Page titles stay Instrument Serif.

**The Sankey is hand-rolled, and the layout fits by measuring.** Recharts'
Sankey solves for arbitrary graphs; this one has four fixed columns whose
children sum exactly to their parent, so stacking each node's children from its
own top edge cannot produce a crossing. Reserving gaps from the column counts
over-reserves — the gaps that accumulate are along the DEEPEST path, not the
widest column, and that left 110px of a 634px box empty. It lays out, measures
what the box did not spend on money, and gives the rest back.

**The Monte Carlo histogram isolates the failures into their own bar.** A path
that runs out stays at zero, so every failure ends at the same value; ordinary
binning drops them into a bucket spanning $0 to several million alongside paths
that merely did badly, and that bar cannot honestly be coloured either way.
Measured at four retirement ages, the claret was all of the chart or none of
it, never the mixture it exists for.

**The paths chart shares the fan chart's axis.** Uncapped, one lucky path an
order of magnitude above the median set the scale and flattened the median and
the whole accumulation phase onto the zero line. It is capped at the fan chart's
p90 ceiling and prints how many paths run above it.

## Deploying

Not yet deployed. **`DEPLOY.md` is the click-by-click**, in order, with what to
check after each step. What follows is the reasoning behind those settings.

Vercel project settings this needs:

1. **Root Directory** = `web/`, with **"Include source files outside of the Root
   Directory in the Build Step"** ON. Without it the sync script cannot see
   `../calculations.py`, and it exits non-zero saying so rather than building an
   API with no maths.
2. Environment variables `NEXT_PUBLIC_SUPABASE_URL` and
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` — the same live project the Streamlit app
   uses (`shxjjqcuuhqlvgpbujby`). Reuse it; do not create a new one.
3. Domain `budget.masonjbennett.com`.

### There is deliberately NO production rewrite for /api

`vercel.json` configures the function (bundle excludes, `maxDuration`) and
nothing else. Vercel routes `/api` requests to the Python function itself —
its own Next.js + Python guide is explicit that the rewrite in that setup is for
local development only, which is why ours lives in `next.config.ts` gated on
`NODE_ENV === "development"`.

A production `{"source": "/api/:path*", "destination": "/api"}` was in here and
was removed before the first deploy. It is the pattern most FastAPI-on-Vercel
posts show, and here it would have been **silently wrong**: the routes are
declared as `/api/take-home`, so handing the function a rewritten path of `/api`
matches nothing and every call 404s. Without the rewrite the deploy either works
or fails loudly on the first request — which is the failure worth having.

### Confirm on the FIRST deploy

Two things cannot be tested locally. Both fail loudly rather than silently,
which is why deploying to a preview URL early is cheap:

- **Routing.** `GET /api/health` should return `{"status":"ok"}`. If it 404s,
  Vercel is serving `api/index.py` at the exact path `/api` only, and the fix is
  one line — mount the FastAPI app at the root and let the platform prefix, or
  reinstate a rewrite that preserves the path.
- **Sync ordering.** The build-time copy must run before the function is
  bundled. If it does not, the deploy fails on a missing import of
  `calculations` — which is the intended failure, not a silent stale copy.

### Suggested sequence

Deploy to a **preview URL first** and leave `budget.masonjbennett.com`
unattached until it has been looked at in a browser that is not this one.

The two blockers that made that advice conditional are gone: the mobile
navigation and the re-skin have both landed. The app is a rail at `lg` and up
and an off-canvas drawer below it, verified at 375px — `elementFromPoint(60,
300)` returns page content rather than a sidebar element, there is no
horizontal overflow, and the drawer closes on Escape, on navigation and on the
backdrop, returning focus to the opener. The Streamlit app is still live and
still the recruiter-safe link; swap it only once the preview has been used in
anger.
