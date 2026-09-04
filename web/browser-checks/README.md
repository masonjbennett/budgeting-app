# browser-checks

Checks that need a real Chrome and a running dev server. **They are not part of
`npm run build` and they are not in CI** — nothing here has a headless browser
or a dev server, which is why they were left out of the repo for a while.

That was the wrong call, and this directory is the correction. "CI cannot run
them" is an argument about CI, not about storage. Twice now a session has had
to rebuild them from a paragraph of prose in `../README.md`, and the second
rebuild shipped a check that **could not fail** — it searched computed styles
for a literal `var(`, which an undefined custom property never produces,
because it resolves to `unset` and the element inherits a colour instead. That
is exactly the defect it was written to catch, and it would have reported clean
forever. Storing the working versions costs a directory.

## Running them

```bash
# once
npm install

# two servers, from the website working folder
preview_start "budget-api"     # port 8000  (or: uvicorn index:app --app-dir api --port 8000)
preview_start "budget-web"     # port 3000  (or: npm run dev)
```

**Restart the API server after adding a route — uvicorn is not watching.**

Every check takes an optional `BASE`, so the same assertions run against a
deployment rather than localhost — which is how production was verified on the
first deploy:

```bash
BASE=https://your-app.vercel.app npm run sweep
```

```bash
npm run selftest      # prove the sweep can fail, FIRST
npm run sweep         # every route, both themes
npm run interact      # drive the newest features
npm run regress       # things already fixed once, that must stay fixed
npm run mobile        # the phone, measured (carries its own selftest)
npm run big           # generate a year-sized statement and measure the importer
npm run streamlit     # the OTHER front end still works (needs port 8502)
```

`npm run all` is selftest → sweep → interact → regress → mobile, which is the
set worth running after any change under `src/`.

## What each one is for

| File | What it asserts |
|---|---|
| `sweep.mjs` | Every route × both themes: every `var(--x)` referenced in CSS has a value, every rendered text node clears 3:1 against what is actually behind it (**SVG text by `fill`, not `color`** — see below), no chart is empty, no chart label loses ink to its own `overflow: hidden` surface, every colour a chart paints with is a palette token, no console errors. **156 assertions.** |
| `selftest.mjs` | Injects a fault for each of the five sweep checks into a real healthy page and requires the check to fire. **Run this before trusting a sweep run.** |
| `interact.mjs` | Drives the three features: the savings-rate curve and its marker, `/year`'s caveat and shaded months and budget rule, the CSV importer end to end including a second import of the same file. Also 375px and print, that the dashboard and `/year` agree to the dollar about this month, and that a profile with nothing logged reports null rather than zero. **63 assertions.** |
| `regression.mjs` | Behaviour already fixed once, where the fix is invisible in the source: the cascade-layer fix by COMPUTED VALUE, the mobile drawer at 375px (focus return, scroll lock, close on Escape and on navigation), the theme toggle across a reload, and a real Monte Carlo run. **21 assertions.** |
| `bigimport.mjs` | Measures the importer on a year-sized file. Reports DOM size, page height, and tick-to-paint. |
| `bigcorrect.mjs` | Paging and filtering must not change WHAT gets imported — walks every page, then commits and counts what actually landed. **11 assertions.** |
| `mobile.mjs` | The phone, as NUMBERS: every text-entry control is >= 16px on a coarse pointer (and still 14px on a mouse), no section slug overflows or loses its hairline, no page scrolls sideways at any of TEN widths (320/360/375/390/414/639/640/768/1024/1440 — a responsive bug does not live at the widths people pick, and `/goals` overflowed in a 50px band nothing sampled), no table scrolls sideways from 360px up, nothing is under 24x24, and **the importer — which is behind a button, so a route sweep never opens it** — stacks into cards with every field labelled. It also checks the surfaces that exist ONLY on a phone — the importer's cards and the cash-flow list that replaces the Sankey — **in both themes**, which `sweep.mjs` cannot: it does both themes at desktop width only. `--selftest` injects a fault for each of the six and requires it to fire. **33 assertions.** |
| `streamlit.mjs` | The Streamlit front end still renders every page against the shared engine. Run before pushing anything that touches `calculations.py`. |

## Three things that cost a cycle each

**The Browser pane is not reliable for this app.** It screenshotted a font
comparison with none of the webfonts applied while its own DOM reported them
loaded, and on another occasion returned blank paper while reporting the image
in viewport at opacity 1. These use `puppeteer-core` against the system Chrome
for that reason. When the pane and the DOM disagree, capture elsewhere.

**Git Bash mangles a bare `/route` argument into a Windows path.**
`export MSYS_NO_PATHCONV=1` before `node sweep.mjs --only=/year`.

**`sweep.mjs` does both themes and one width.** Anything that renders only
below 640px — the importer's cards, the cash-flow list — had never been
contrast-checked in either theme until `mobile.mjs` grew a pass at 375px. A
new mobile-only surface is a new set of colours nobody has measured.

**`color` is not what SVG paints with, and this check read it for six
months.** Every text node was measured on `getComputedStyle(el).color`,
including the ones inside charts — but SVG text is painted with `fill`. On a
Recharts tick the two differ: the tspan INHERITS the body ink through `color`
while `fill` carries the grey it is drawn in. So every chart label was scored
as body-ink-against-card, which passes comfortably in either theme whatever
the label is really painted. Measured: a label given its own card's colour —
invisible — scores **1.00 by fill and 14.8 by the old method**. 165 real
labels per theme clear 3:1, so nothing was hiding behind it; but nothing
could have been seen if it were. `selftest.mjs` now injects exactly that
label and requires the check to fire.

**A label can be clipped by the chart it lives in.** Recharts draws a
`position: "top"` reference label ABOVE the plot area, and the surface is
`overflow: hidden` — so a chart whose top margin is smaller than the label
slices it and says nothing. The fan chart on `/fire` had `margin.top: 8`
against a 13px label: **"Retirement" was cut by 7px**, its glyph tops gone,
and it read as nonsense on the app's most complex page. `sweep.mjs` now
reports VERTICAL overhang only — a horizontal pixel or two is side bearing,
which carries no ink, confirmed at 6x on the axis dates.

**A bounding rect is not ink.** `charts.mjs` flagged a `2026-09-01` axis
label as painted outside its SVG on two routes, and the SVG really is
`overflow: hidden`, so it looked like a clipped date — the truncation defect
this project keeps meeting. Cropped at 6x device scale it reads `2026-09-01`
in full: the 2px overhang is the glyph's trailing side bearing, which is
inside the advance width and carries no ink. Measure the pixels before
believing the rectangle.

**A route sweep does not see what is behind a button.** The first version of
`mobile.mjs` walked all 13 routes and reported clean, while the importer — the
biggest table in the app and the only place it has checkboxes — sat collapsed
behind "Open importer" with 401px of itself off screen and six 13x13 ticks.
Anything gated behind a click has to be clicked.

**A check that reports zero problems may have looked at nothing.** During the
mobile work a probe printed "0 problems" across all 13 routes while every page
was a 500 from a JSX parse error — it counted FAILURES and never counted
subjects. `mobile.mjs` therefore asserts what a healthy run must FIND (~74
controls, ~150 header renders, ~130 tap targets, ~25 table renders) before it
asserts anything about them. Any new check here should do the same: the
cheapest possible bug in a check is that its selector matches nothing.

**A screenshot is not enough either, and that is newer.** Every earlier lesson
here is "the suite was green and the page was wrong". The focus-zoom defect is
one step past that: **headless Chrome does not implement Safari's zoom**, so the
page renders perfectly and the defect exists only in the computed font-size.
There was nothing to see. Some things can only be caught as a number.

**A check that fails is guilty until proven innocent.** Of the nine failures
these turned up on their first runs, seven were the check's fault: a nav button
matched exactly when its label carries an emoji prefix, a row count that read
the page's other table, a duplicate count that forgot two rows were never
imported, a drawer asserted to leave the DOM when it slides on a transform, and
a theme check whose own localStorage injection ran again on the reload and
overwrote the choice it was testing. Read the failure before touching the app.

**Recharts 3 does not render what the selector you expect.** A `Rectangle` is a
`<path>`, not a `<rect>`; a reference label lives in a sibling
`<g class="recharts-label">` rather than inside the reference layer. Three
checks reported failures that were entirely their own before this was written
down. Read the chart's rendered `<text>` where you can — it is both simpler and
closer to what a person sees.

## The rule these exist to serve

Every defect this project has found lately was invisible to a green suite and
visible on a rendered page: dead CSS rules, a chart with no paths, a gradient
id containing a space, a note describing bars that were never drawn, a budget
rule silently outside the axis, a checkbox in the browser's own blue.

So: **do not report something verified unless the check could actually have
failed.** Break it on purpose and watch it fail. A check that passes on its
first run has proved nothing yet.
