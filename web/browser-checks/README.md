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

```bash
npm run selftest      # prove the sweep can fail, FIRST
npm run sweep         # every route, both themes
npm run interact      # drive the newest features
npm run regress       # things already fixed once, that must stay fixed
npm run big           # generate a year-sized statement and measure the importer
npm run streamlit     # the OTHER front end still works (needs port 8502)
```

`npm run all` is selftest → sweep → interact → regress, which is the set worth
running after any change under `src/`.

## What each one is for

| File | What it asserts |
|---|---|
| `sweep.mjs` | Every route × both themes: every `var(--x)` referenced in CSS has a value, every rendered text node clears 3:1 against what is actually behind it, no chart is empty, every colour a chart paints with is a palette token, no console errors. **130 assertions.** |
| `selftest.mjs` | Injects a fault for each of the five sweep checks into a real healthy page and requires the check to fire. **Run this before trusting a sweep run.** |
| `interact.mjs` | Drives the three features: the savings-rate curve and its marker, `/year`'s caveat and shaded months and budget rule, the CSV importer end to end including a second import of the same file. Also 375px and print. **58 assertions.** |
| `regression.mjs` | Behaviour already fixed once, where the fix is invisible in the source: the cascade-layer fix by COMPUTED VALUE, the mobile drawer at 375px (focus return, scroll lock, close on Escape and on navigation), the theme toggle across a reload, and a real Monte Carlo run. **21 assertions.** |
| `bigimport.mjs` | Measures the importer on a year-sized file. Reports DOM size, page height, and tick-to-paint. |
| `bigcorrect.mjs` | Paging and filtering must not change WHAT gets imported — walks every page, then commits and counts what actually landed. **11 assertions.** |
| `streamlit.mjs` | The Streamlit front end still renders every page against the shared engine. Run before pushing anything that touches `calculations.py`. |

## Three things that cost a cycle each

**The Browser pane is not reliable for this app.** It screenshotted a font
comparison with none of the webfonts applied while its own DOM reported them
loaded, and on another occasion returned blank paper while reporting the image
in viewport at opacity 1. These use `puppeteer-core` against the system Chrome
for that reason. When the pane and the DOM disagree, capture elsewhere.

**Git Bash mangles a bare `/route` argument into a Windows path.**
`export MSYS_NO_PATHCONV=1` before `node sweep.mjs --only=/year`.

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
