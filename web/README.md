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
a space, a note describing bars that were never drawn.

**The browser checks are in `browser-checks/`** — see its README. They are not
part of the build and not in CI, because nothing there has a headless browser
or a dev server. They used to be left in the session scratchpad for that
reason, which was the wrong call: "CI cannot run them" is an argument about CI,
not about storage, and two sessions rebuilt them from the paragraph below
before one of the rebuilds shipped a check that could not fail. What they
cover:

- **every route in both themes** — every `var(--x)` referenced in CSS has a
  value, every rendered text node clears 3:1, charts have paths, every painted
  chart colour is a palette token, no console errors. 130 assertions over 13
  routes;
- **the interactions** — the cascade-layer fix by computed value, the mobile
  drawer at 375px including focus and body-scroll, the theme toggle across a
  reload, a real Monte Carlo run;
- **print emulation in both themes**, which is how a print rule usually ships
  dead;
- **the phone as numbers** (`mobile.mjs`) — the focus-zoom threshold, the
  section slug, every table fitting its scroller, the 24x24 tap floor. See rule
  8: none of these can be caught by looking, and one of them cannot be caught
  in a browser that is not Safari.

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

### 8. The phone is a set of numbers, not a screenshot

Three things were shipping on the live site in September 2026 that were
invisible to a green suite AND to looking at the page:

- **Every text-entry control was 14px** (the two `/expenses` filters, 11px).
  Mobile Safari zooms the viewport on focus below 16px and does not zoom back
  out, so adding an expense left you pinching. **Headless Chrome does not
  implement that zoom**, so there was never anything to see — the defect exists
  only in the computed font-size. `globals.css` now sets 16px under
  `@media (pointer: coarse)`, in `@layer utilities` because `.t-micro` is in
  `components` and a layer cannot be beaten by specificity from an earlier one.
  A width query would have been wrong: the zoom is a property of the DEVICE, so
  an iPad at 1024px zooms and a narrowed desktop window does not.

  The alternative fix, `maximum-scale=1` on the viewport meta, stops the zoom by
  disabling pinch-zoom outright. That is a WCAG 1.4.4 failure that takes
  magnification away from the people who most need it in order to spare
  everyone else an annoyance. The meta tag stays as it is.

- **`Section`'s slug did not wrap**, so `/expenses` ran 107px past the right
  edge of a phone — the one page-level horizontal overflow in the app, and the
  existing overflow checks only ever covered `/` and `/year`. The hairline is
  `flex-1` with a basis of 0, so it gives up its width silently: two more
  headers were measured at exactly the available width with a rule of ZERO, one
  character from overflowing and with nothing reporting it. The rule now has a
  minimum, which is what makes the row wrap BEFORE it overflows.

- **Four tables scrolled sideways and the hidden columns were the answer.** A
  table inside `overflow-x-auto` does not overflow the page, so every
  horizontal-overflow check passes on it, correctly — none of them can ask
  whether the column carrying the number is on screen. `/expenses` hid AMOUNT;
  `/year` hid Spent, Of budget and Variance, which is every figure it reports.
  Secondary columns are now `hidden sm:table-cell` and the cell gutters drop
  from 14px to 8px below 640px, which is worth 48px on a four-column table —
  enough that nothing had to be hidden merely for margin. All of it returns at
  640px, where the content area is ~600px and every table fits.

- **The importer could not be fixed by dropping columns, and it was invisible
  to the first pass of this check.** It is collapsed behind a button, so a
  sweep that walks routes never opened it: measured, 736px of table in a 335px
  scroller with 401px off screen, and six 13x13 checkboxes — the app's only
  checkboxes, and its primary control. Column-dropping cannot save it because
  the columns ARE the decision: each row carries a tick and a category
  `<select>`, and the select alone is ~146px at touch type size.

  So `table-cards` on a `<table>` stacks its rows into label/value lines below
  640px, driven by `data-label` on each cell rather than a second block of JSX
  — one rendering, so a column cannot say one thing on a phone and another on a
  laptop. The cell is `flex`, not `text-align`, or the `text-right` a cell
  already carries would push the label to the right edge along with the value.
  It is opt-in for a reason: it is right only where a row is a DECISION, and
  wrong for the four data tables, which read better as a grid.

  What it costs, measured at 100 rows: the page goes 7,635px to 25,219px on a
  phone. What it does NOT cost is the thing the September work bought — the DOM
  is unchanged (3,608 nodes, 1,887 options either way, because this is CSS) and
  a tick still paints in under 20ms. A long scroll is the right trade against a
  table with more than half of itself off screen.

- **Checkboxes were the user agent's 13x13.** `width: auto` was correct as
  "do not take the 100% the text inputs get" and left the box at the browser
  default, half the 24px minimum. 18px, and 24px on a coarse pointer.

- **The dashboard's Sankey showed two of its twenty-two labels.** Same shape
  as the tables and the worst instance of it, on the landing page: the panel
  wraps the diagram in `overflow-x-auto` with a `min-w-[640px]` inner box, so
  the page never overflows and every check passed — while at 375px the
  scroller is **293px of a 640px diagram**. A phone saw "Gross pay $8,750" and
  "FICA $669", with "State tax $3" and "Federal tax $" clipped mid-figure at
  the edge (a truncated number that still reads as a number, for the third
  time in this codebase). Every budget bucket — the half the panel is FOR —
  was off screen. The caption also told the reader that a thin band "names
  itself on hover", on a device with no hover.

  A Sankey's claim is that the widths are the money, so narrowing it keeps the
  claim and loses the labels. Below 640px it is replaced by `CashFlowList`,
  **the same graph derived from the same `links`**: every node that is the
  source of a link becomes a group and its targets become the rows, so a
  change to `cash_flow`'s shape appears in both renderings or in neither.
  68 of 68 labels visible, against 2 of 22. Swapped in CSS rather than by a
  media-query hook, because a hook has no answer during server render and
  would paint the wrong one first. The bar widths are layout in exactly the
  sense the Sankey's ribbon heights are layout, and no proportion is ever
  printed as a figure — rule 2 still holds.

- **`/goals` pushed the page sideways between 640px and 690px**, and had done
  since the re-skin. Its `sm:grid-cols-4` puts a date input beside a fixed
  30px remove button in a cell 127-137px wide, and Chrome will not draw a date
  input below **149px** — it needs that to fit mm/dd/yyyy and the picker icon.
  A grid item and a flex item both default to `min-width: auto`, which is why
  neither the track nor the `flex-1` shrank. `min-w-0` is the tempting fix and
  is worse: the cell then shrinks and the date input clips its own segments,
  trading a page overflow for a control nobody can read. It is
  `sm:grid-cols-2 lg:grid-cols-4` now.

  **The band is 50px wide, which is why nothing found it.** Every check in
  this repo ran at 375, 414, 768 or 1440. `mobile.mjs` now tests page overflow
  at **ten** widths — 320, 360, 375, 390, 414, 639, 640, 768, 1024, 1440 —
  because a responsive bug does not live at the widths people pick.

- **320px is reported, not asserted.** Table gutters went 8px to 6px below
  640px, which was worth 8px and closed a 3px miss on `/year` at 360. From
  360px up every table fits. At 320 — the iPhone 5 and SE 1st gen, 2016
  hardware — two tables still fall back to their own scroller, with no page
  overflow. The check counts those and prints the count rather than failing,
  so the day it gets worse is visible.

- **The only `text-faint` TEXT in the app lived where no check ran.** The
  mobile header's breadcrumb separator measured **2.57:1** against paper, and
  this app's own standard — asserted by the sweep — is that every rendered
  text node clears 3:1. It survived because the header is `lg:hidden` and
  every contrast check ran at desktop width. `text-muted` now. Exempting it
  as decorative because it is `aria-hidden` was the alternative and is worse:
  it makes the sweep's rule negotiable. `mobile.mjs` sweeps contrast over
  **every route in both themes at 375px**, not just the dashboard.

`mobile.mjs` holds all of this plus the 24x24 tap-target floor, with a
`--selftest` that injects each defect and requires the check to fire. **639 and
640 are both measured**, because that pair is where a column could come back
before the table fits — a gap invisible at any width anyone would think to try.
And it OPENS THE IMPORTER, because the first version of it walked routes only
and therefore never saw the worst table in the app.

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

**Deployed — budget.masonjbennett.com is live and is the primary**, and the
links on masonjbennett.com point here. This section used to open "Not yet
deployed"; it is kept accurate rather than rewritten, because the rest of it is
the reasoning behind the settings and the record of what the first deploy
found. **`DEPLOY.md` is the click-by-click**, in order, with what to check
after each step.

Vercel project settings this needs:

1. **Root Directory** = `web/`, with **"Include source files outside of the Root
   Directory in the Build Step"** ON. Without it the sync script cannot see
   `../calculations.py`, and it exits non-zero saying so rather than building an
   API with no maths.
2. Environment variables `NEXT_PUBLIC_SUPABASE_URL` and
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` — the same live project the Streamlit app
   uses (`shxjjqcuuhqlvgpbujby`). Reuse it; do not create a new one.
3. Domain `budget.masonjbennett.com`.

### The production rewrite for /api is REQUIRED, and this note used to say the opposite

`vercel.json` carries `{"source": "/api/(.*)", "destination": "/api"}`.

This section previously argued the rewrite should be left out, on the reasoning
that the routes are declared as `/api/take-home` and handing the function a
rewritten path of `/api` would match nothing. That was worked out on paper
before anything had been deployed, and production does the opposite. Measured
on the first real deploy:

- `/api` reached the function and FastAPI itself returned a 404 — the runtime
  log line reads `source: "serverless"`, `requestPath: "/api"`, no traceback.
- `/api/health` never reached it at all. Next.js owned the path, served its own
  404 page, and **no function was invoked**, so there was nothing in the runtime
  log to look at.

Vercel serves `api/index.py` at the EXACT path `/api` and nothing below it. The
rewrite's destination only selects WHICH function handles the request; the
function still receives the original URL, which is why the routes stay declared
as `/api/...` and nothing else changes.

The wider lesson is the one this file keeps repeating in other contexts: a
paragraph explaining why something is unnecessary is not evidence, and this one
survived because the thing it described had never been run.

### The other three things the first deploy found

None of them appeared as a red line in a build log.

1. **The framework preset must be set.** It rendered BLANK on the import screen,
   which looks like a loading skeleton and means "Other". The build then
   succeeded completely — sync verified, tokens checked, TypeScript passed, all
   sixteen pages generated, route table printed — and the deploy failed with
   `No Output Directory named "public" found after the Build completed`, which
   names a directory and never mentions the framework. Now pinned as
   `"framework": "nextjs"` so a fresh import cannot repeat it.

2. **`sys.path` does not include the entrypoint's own directory.** See rule 1;
   `test_api.py` now loads `api/index.py` by path, in a subprocess, with that
   directory removed.

3. **"Include source files outside of the Root Directory" was not needed.**
   Vercel included the parent anyway and the sync printed its verified line
   without the toggle. Check for that line rather than assuming either way.

**Use the CLI.** `vercel logs <url> --json` produced the `ModuleNotFoundError`
in one command after a long stretch of reading dashboard screenshots and
guessing. It is the first thing to reach for, not the last.

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
