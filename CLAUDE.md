# Budget Tracker App

## TWO FRONT ENDS, ONE ENGINE
`budget_app.py` (Streamlit, live at masonbennett-budget.streamlit.app) and
`web/` (Next.js + FastAPI, for budget.masonjbennett.com) are two front ends over
`calculations.py` and `app_data.py`. Both of those are stdlib-only and at the
repo root, one copy each. **web/api/calculations.py and web/api/app_data.py are
GENERATED at build time and gitignored — never edit or commit them.** Read
`web/README.md` before touching anything under `web/`.

The Streamlit app stays live and unchanged until the rebuild is genuinely
better. Do not retire it in passing.

## Overview
Personal finance web app with 11 pages: Dashboard, Income Setup, Budget Builder, Expense Tracker, Net Worth, Debt Payoff, Savings Goals, Investments, FIRE Calculator, Tax Estimator, Data Management. Single-file Streamlit app (~3,200 lines) with Supabase auth + cloud persistence.

**Live:** masonbennett-budget.streamlit.app
**Repo:** github.com/masonjbennett/budgeting-app
**Builder:** Mason Bennett (masonjbennett.com) — M.S. Finance, targeting IB/PE/TA

## Tech Stack
- **Frontend:** Python + Streamlit (light theme, Inter + Space Grotesk fonts)
- **Charts:** Plotly (all charts use `default_layout()` helper — never pass duplicate kwargs like `legend`, `margin`, `hovermode` directly)
- **Backend:** Supabase (auth + JSONB blob storage, one row per user)
- **Data:** pandas (numpy is no longer imported by the app — the Monte Carlo was
  rewritten stdlib-only when it moved into `calculations.py`; pandas still pulls
  numpy in transitively, and the test suite uses it as an ORACLE, never a source)
- **Deploy:** Streamlit Cloud (auto-deploys from GitHub master branch)

## Key Commands
```bash
py -m streamlit run budget_app.py     # Run locally
py test_stress.py                      # 168 calculation tests against the real code
py test_cloud.py                       # 42 auth/cloud tests against the real code
py test_calc.py                        # 67 calculation tests against the real code
git push origin master                 # Auto-deploys to Streamlit Cloud
```

## File Structure
This repo now lives INSIDE the website working folder, beside `filings-terminal/`
and `portfolio-app/`, so there is one canonical copy rather than a loose one in
Downloads. Run it with `preview_start "budget"` (launch.json entry, uses `.venv`).

```
Masonjbennett.com Website/budgeting-app/
  budget_app.py          # The entire app (single file)
  test_stress.py         # 168 stress tests for all calculations
  calculations.py        # ALL the maths — stdlib only, no framework imports
  test_calc.py           # 67 tests for the engine — drives the SHIPPING code
  test_cloud.py          # 42 tests for auth + cloud sync — drives the SHIPPING code
  SUPABASE_SETUP.md      # standing up the project, the table, and its RLS policies
  requirements.txt       # pinned: streamlit==1.62.0, plotly/pandas/supabase capped
  README.md              # Feature list with IRS source citations
  .streamlit/
    config.toml          # Light theme config
    secrets.toml         # Supabase URL + key (NEVER commit this)
  .gitignore             # Excludes secrets.toml, *.json, __pycache__
```

## Architecture (budget_app.py)
The file follows this order:
1. **Imports + Supabase client** (lines 1-130) — cached client, auth functions, cloud save/load
2. **Page config + CSS** (lines 130-210) — light theme, hover states, transitions
3. **Tax data constants** (lines 210-310) — federal brackets (4 filing statuses), 50 states + DC, FICA, SALT
4. **Calculation functions** (lines 310-460) — `calc_bracket_tax`, `calc_federal_tax`, `calc_state_tax`, `calc_fica`, `calc_social_security`, `calc_student_loan_deduction`, `calc_salt_cap`, `simulate_payoff`, `project_investment`
5. **Helpers** (lines 460-620) — `default_layout()`, `fmt()`, `progress_bar_html()`, `metric_card_html()`, `status_badge_html()`, `render_savings_goal_card()`, `render_footer()`
6. **Data model** (lines 620-830) — `get_default_state()`, `_generate_demo_data()` (relative dates), `init_state()`, and a thin `compute_take_home()` wrapper over the engine
7. **Sidebar** (lines 890-1000) — nav groups (OVERVIEW/MANAGE/GROW/PLAN), auth UI, save/load
8. **Page functions** (lines 1000-3100) — `page_dashboard` through `page_data`
9. **Router** (lines 3100-3110) — `PAGES[page]()`

## Critical Rules
- **Never add duplicate kwargs** when calling `fig.update_layout(**default_layout(), ...)`. The `default_layout()` already sets `legend`, `margin`, `hovermode`, `xaxis`, `yaxis`. To override, modify the dict before spreading: `layout = default_layout(); layout["margin"] = ...; fig.update_layout(**layout, ...)`
- **Run all FOUR suites after every change** — `test_calc.py` (203),
  `test_cloud.py` (42), `test_stress.py` (168) and `web/test_api.py` (106) =
  519, plus TWO mutation harnesses: `web/test_api_mutations.py` (11 shipped
  bugs, each required to fail the API suite) and `test_calc_mutations.py` (22
  engine defects, each required to fail `test_calc.py`). All four suites import
  the shipping code; none redefines its subject.
  **The two harnesses are separate on purpose.** The API one mutates
  `web/api/index.py` only, because any edit to `web/api/calculations.py` also
  trips the byte-for-byte sync check — so a mutation there reports itself
  "caught" whatever the assertion aimed at it is worth. The engine one mutates
  the ROOT `calculations.py`, where no such check exists, so a mutation is
  caught only by an assertion that actually looks at the behaviour.
  **They are the floor, not the ceiling.** Every defect the September re-skin
  found was invisible to a green suite and visible on a rendered page — dead
  CSS rules, a chart with no paths, a gradient id containing a space. Anything
  touching `web/src` also needs a browser; see the block in `web/README.md`.
- **After adding a NEW name to `calculations.py`, REBOOT the deployed app.**
  Streamlit re-runs the script in a long-lived process, so `import calculations`
  can return the copy already in `sys.modules` — the one from before that name
  existed — and the deploy dies with an ImportError while both files are correct
  and import cleanly everywhere else. It happened on 2026-09-01 with
  `TOP_BRACKET_START`: production had been verified healthy one commit earlier.
  Fix is a full container restart: "Reboot app" in the Streamlit Cloud dashboard,
  or any edit to `requirements.txt`, which changes its hash and forces a fresh
  environment. **A green local run proves nothing about this**, which is why the
  production check after a push has to be a real page load, not a 200.
- **`app_data.py` holds the starting and demo profiles**, for the same reason
  `calculations.py` holds the maths: two front ends need them, and a demo
  retyped for the second one drifts. The abandoned scaffold's hand-written
  TypeScript copy had ONE debt, which makes avalanche and snowball identical by
  definition and silently kills the comparison the debt page exists for. Served
  to the web app by `GET /api/state`; `test_calc.py` and `web/test_api.py` both
  assert the multi-debt property.
- **All maths lives in `calculations.py`, and nothing else may hold a copy.**
  It had drifted into THREE implementations that disagreed: budget_app.py,
  test_stress.py's hand-copied mirror, and budget-app-v2's FastAPI backend. The
  mirror is why 64/64 stayed green from April to September while never executing
  the app — by then its `calc_fica` had no `filing` argument and its
  `project_investment` no `contribution_growth`, so both shipped features were
  untested. `calculations.py` is stdlib-only on purpose, so a future backend can
  import it rather than starting a fourth copy.
- **Prove any refactor of it with the grid, not just the suites.** A suite only
  covers the cases someone thought of. The extraction was verified by evaluating
  every pure function over 2,728 input combinations before and after and matching
  the hash — which is also how the two names left out of the import list would
  have been caught, had the browser sweep not caught them first.
- **Cloud sync must never be load-bearing.** The Supabase project this app
  originally shipped against was deleted while nobody was looking, and because
  the client is built without a network call the app booted fine and told every
  visitor their *password* was wrong. Three rules came out of that, all tested:
  `_init_supabase()` returns `None` rather than raising, so a missing secret
  degrades to local-only instead of blanking every page; `_is_unreachable()`
  keeps "the service is down" apart from "those credentials were wrong"; and
  `_db()` builds a per-session client, because the shared `@st.cache_resource`
  one would carry whichever user's JWT was attached last — one person's data
  returned to another.
- **`cloud_save()` returns `(ok, message)`**, not a bool. Both callers destructure it.
- **Database calls go through `_db()`, never `supabase` directly.** The bare client
  holds the public anon key; `_db()` carries the signed-in user's JWT, which is what
  makes the row-level security policies in `SUPABASE_SETUP.md` actually apply.
- **Never commit `.streamlit/secrets.toml`** — it's in .gitignore
- **`_generate_demo_data()` uses relative dates** — expenses are always current/previous month. Never hardcode dates.
- **All tax data is official IRS 2026** from Rev. Proc. 2025-32 + OBBBA. Don't change tax numbers without a verified source.
- **`compute_take_home` is in `calculations.py`; what is left in the app is a
  four-line wrapper.** It used to live in budget_app.py and read the module-global
  `data` dict for the itemized deductions, which meant nothing could import it
  without importing Streamlit — so the single most load-bearing function on the
  site (take-home, savings rate, dashboard cash flow, the budget page's income
  line, the FIRE timeline all run through it) was covered by **zero** of the
  assertions. It now takes `(income, itemized)` and is covered by 13. The wrapper
  exists only to supply the session's two dicts, and `test_calc.py` monkeypatches
  the engine and requires the wrapper's answer to move — testing the engine alone
  would not notice a wrapper that had grown a second copy.
- **The Monte Carlo is `calculations.run_monte_carlo`, stdlib-only.** It was a
  block inside the FIRE page's button callback — not a function — which is why it
  was the one calculation with no assertions behind it, and why numpy was a
  dependency of the whole app. numpy supplied four things: normal draws, a 2x2
  Cholesky of a CONSTANT matrix (worked out by hand, once), percentiles, and array
  storage. Measured at the largest setting the UI offers, 5,000 sims x 71 years:
  **0.91s**. Three things are load-bearing. (1) **The randomness is kept out of
  the recurrence** — `simulate_path` takes its return and inflation sequences as
  arguments, so the money arithmetic is exactly testable and only the drawing is
  stochastic. (2) `percentile` reproduces `numpy.percentile`'s default linear
  interpolation, because it replaced np.percentile on a shipping page and those
  numbers must not move; the suite checks it against real numpy over 2,200
  comparisons. (3) The 50 sample paths are drawn IN the simulation, not at render
  time — the page used `np.random.choice` while drawing the chart, so every widget
  touch redrew a different fifty — and it is also why the full matrix is not
  returned: 355,000 numbers to show 50 paths, several megabytes over HTTP.
- **Contribution limits are `K401_LIMIT` and `HSA_INDIVIDUAL_LIMIT`.** They were
  literals in seven places (six copies of `24_500`, one of `4_400`), which made the
  January refresh a hunt rather than an edit.
- **Badge text is computed, not hardcoded.** `status_badge_html` puts a brand
  colour on a 15% tint of ITSELF, which for this palette is a colour on a paler
  version of itself — GREEN measured 1.87:1 and YELLOW 2.13:1. `readable_on_tint`
  darkens until 4.5:1, so a new palette entry cannot quietly ship an illegible
  badge. The suite asserts on the RENDERED MARKUP, not just the helper: reverting
  the badge to the raw colour passed every assertion about `readable_on_tint`.
- **Sidebar button colours must cover their DESCENDANTS.** Streamlit renders each
  label as a nested `<p>`, which `section[data-testid="stSidebar"] *` matches
  directly — and a matched rule beats an inherited one, so both button colour
  rules were dead and every label rendered #E2E8F0. The active-page highlight
  (#7DD3FC) had never once appeared. Any new sidebar colour rule needs the
  `, ... *` half or it is decoration.
- **Take-home itemizes when itemizing is better.** `calc_federal_tax` used to
  force the standard deduction, so the Tax page could tell someone itemizing saved
  them money while take-home, savings rate, dashboard cash flow and the FIRE
  timeline all quietly assumed they had not. `calc_itemized_total` is the single
  implementation of the floors and caps, shared by both. Two things are load-bearing:
  the OBBBA above-the-line charitable deduction is for NON-itemizers only (an
  itemizer deducts charity inside the itemized total, so granting both deducts the
  same donation twice), and the 4th return value is now the deduction ACTUALLY
  taken — which equals `standard` whenever the itemized total is 0, so every
  pre-existing caller is unaffected.
- **Dashboard ratios must not be coupled to a category name or an asset label.**
  Debt-to-income read ONLY the budget line "Min. Debt Payments", so a user with
  real debts who left that line at zero saw 0.0%, "Healthy" — the demo data did
  exactly that against $35,000 of student loans. It now reads `monthly_debt_service`,
  which prefers the entered debts and falls back to the category, and says which.
  It also divided by TAKE-HOME while grading against the 20%/36% bands, which are
  lender bands defined on GROSS — a denominator a quarter too small, grading people
  a whole category harsher than a lender would.
- **Emergency-fund coverage returns None when it cannot be measured, and None is
  not 0.0.** It used to look up the literal asset key `"Savings"`: rename that row
  to "High-Yield Savings" and coverage read 0.0 months as though measured. Name
  matching is unavoidable (there is no liquidity flag in the schema) and imprecise,
  so the card PRINTS which assets it counted, and says so plainly when it counted
  none. Illiquid hints are tested before liquid ones, or "Roth IRA Savings" counts.
- **Marginal rates come from `th["marginal_fed"]` and `th["marginal_state"]`, never
  from a bracket table directly.** Three call sites used to read
  `sdata["brackets"][-1][1]` — the state's TOP bracket — and label it the user's
  marginal rate, overstating the 401(k) tax saving by $1,200 (17%) at $110K in New
  York and $1,073 in New Jersey. It survived five months because Arkansas at $85K
  is already top-bracket, so the error is exactly zero on the author's own data.
  `calc_state_marginal_rate` mirrors `calc_state_tax`'s signature deliberately: the
  rate must be read off the same taxable base as the tax, and sharing the argument
  list is what stops them drifting apart.
- **FICA on a raise uses `marginal_fica_rate`, not the average rate.** Above the
  $184,500 wage base the marginal rate falls from 7.65% to 1.45%, so the average
  overstates the tax on an increment by up to 5x — for exactly the earners the
  salary negotiation modeller is aimed at.
- **State tax supports filing status** via `_get_state_brackets_for_filing()`. 8 states have custom MFJ brackets (NY, NJ, CT, MD, MN, NM, OK, WI). All others auto-double.
- **Medicare surtax thresholds differ by filing status** — $200K Single, $250K MFJ, $125K MFS. Stored in `FICA_MEDICARE_SURTAX_THRESHOLDS` dict.
- **`simulate_payoff` returns 4 values** — months, interest, schedule, payoff_months. All callers must destructure all 4.
- **The monthly payment budget is `extra + sum(mins)`, not `extra`.** A cleared
  debt's minimum rolls onto the next target — that rolling IS the snowball, and
  avalanche works the same way. The original engine started from `extra` alone and
  let a freed minimum simply stop being spent: on the demo data it reported payoff
  at 114 months and $7,532 of interest against a true 45 months and $3,445, and it
  penalised snowball hardest, so the page's headline comparison showed an avalanche
  advantage that did not exist.
- **Attack order comes from `payoff_order()` and is fixed for the whole run.**
  Re-deriving it from live balances lets the target change when another debt's own
  large minimum drags it below the one being attacked. Testing `payoff_order` alone
  does NOT cover this — a mutation that re-sorted inside the loop left it intact and
  passed every other assertion. `test_calc.py` monkeypatches `payoff_order` and
  requires the answer to move, which is what enforces that the engine reads it.
- **`auto_save_debounced(data)`** is called before `render_footer()` on every page. Saves to Supabase every 10 seconds if logged in.
- **A stubbed oracle is worse than no oracle.** `test_calc.py` installs a fake
  numpy in `sys.modules` so budget_app.py can be exec'd without one, and a fake
  module returns `None` from every call. The percentile check read numpy through
  that stub and was comparing against nothing; it only surfaced because
  `float(None)` raises. The block now loads the real module past the stub and
  **refuses to run unless `numpy.percentile([1,2,3], 50) == 2.0`** — proving the
  oracle is real before trusting it, rather than skipping silently.
- **Mutation-test the assertions, not just the code.** Seven plausible ways the
  September extraction could have gone wrong were applied to the shipping engine
  one at a time and the suite required to fail on each. Six were caught; the
  seventh — spending compounding over calendar years rather than years retired —
  **survived**, because every retirement case in the suite used
  `retire_age == current_age`, where the two are the same number. The assertion
  that catches it retires at 35 of a run from 30 to 40.

## Tax Data Sources
- Federal brackets: IRS Rev. Proc. 2025-32 (OBBBA amended)
- Standard deductions: Single $16,100 / MFJ $32,200 / MFS $16,100 / HoH $24,150
- SS wage base: $184,500 (SSA official)
- 401(k) limit: $24,500 (IRS Notice 2025-67)
- HSA individual: $4,400 (Rev. Proc. 2025-19)
- SALT cap: $40,400 base, phases out 30% above $505K MAGI, floor $10K (OBBBA)
- Student loan deduction: $2,500 max, phases out $85-100K Single / $175-205K MFJ
- Charitable: 0.5% AGI floor for itemizers, $1K/$2K non-itemizer above-the-line (OBBBA)

## Streamlit Cloud Config
Secrets must be added manually in Streamlit Cloud dashboard (Settings > Secrets):
```toml
[supabase]
url = "..."
key = "..."
```

## Common Patterns
- **Adding a new page:** Create `def page_name():`, add to `nav_groups` list, add to `PAGES` dict, add `auto_save_debounced(data)` + `render_footer()` at end
- **Adding a new input field:** Add to `get_default_state()`, `_generate_demo_data()`, and migration in `_migrate_imported()`
- **New chart:** Use `fig.update_layout(**default_layout(), height=400, ...)` — never duplicate keys from default_layout
- **New tax feature:** Update the calculation function, add to `compute_take_home()` if it affects AGI, add tests to `test_stress.py`


## The rebuild (September 2026)
`web/` is a Next.js 16 + FastAPI front end for **budget.masonjbennett.com**, a
separate Vercel project from the same repo (Root Directory `web/`). Built
because the Streamlit app is correct but presents badly, and a budgeting app is
a consumer product where polish is part of whether it seems good.

Read **`web/README.md`** — it carries the rules, each of which exists because
the opposite already shipped. In short: no arithmetic in TypeScript; generated
copies of the two shared modules, gitignored and verified byte-for-byte;
`null` is not `0.0` and every card has a written state for it; the API is a pure
calculator holding no credential.

Three things measured during the build that are worth not re-deriving:
- **Recharts, not Plotly.** plotly.js-dist-min was 944 KB brotli for five trace
  types out of forty. The entire app is 336 KB brotli.
- **Chart entry animations are OFF, as a correctness decision.** Recharts renders
  a Pie's sectors as empty `<g>` groups until the animation completes; where it
  does not complete the chart is silently blank forever, with a correctly sized
  SVG and nothing in the console. Identical pies side by side, animation on and
  off: 0 paths and 3 paths.
- **The Monte Carlo needs no numpy.** 5,000 sims x 71 years in 0.91s of pure
  Python, against a 60s Vercel function limit — which is why `requirements.txt`
  is two lines.

**NOT YET DEPLOYED.** Three Vercel settings and two first-deploy checks are in
`web/README.md`. The Supabase project is the LIVE one (`shxjjqcuuhqlvgpbujby`) —
reuse it, do not create another.

## The re-skin and the five features after it (September 2026)

`web/` is now paper and ink, mobile-usable, and carries the screens the review
in `project-notes` asked for. Read `web/README.md` rules 5 and 6 before
touching any styling — both exist because the opposite was measurably shipping.

- **Colour lives in globals.css and `npm run check:tokens` enforces it**,
  including Tailwind's stock palette (`text-slate-400` is a literal with a
  friendlier spelling) and including tokens TypeScript can name but CSS does
  not define, which paint *nothing*. 116 literals to zero.
- **globals.css is inside cascade layers.** Unlayered CSS beats every Tailwind
  utility: `.card p-0` really was rendering 18px of padding and every
  right-aligned `th` really was rendering left, on master, before this.
- **The hero figure is JetBrains Mono, measured not assumed.** Instrument Serif
  has no tabular figures — 65.3px of width swing across a count-up, which
  `tabular-nums` cannot fix because the feature is absent from the font.
- **The Sankey (`/api/cash-flow`) balances by construction**, because
  `compute_take_home` defines take-home as the remainder. A stage that did not
  sum would be undetectable by eye, so `balanced` comes back with the data and
  the panel refuses to draw a false one.
- **Scenario comparison (`/api/compare`)** restates take-home in
  national-average dollars — the row the screen exists for, since take-home
  alone ranks the dearest city first. Scenarios live in the profile, so they
  save and export through machinery that already exists.
- **Five capabilities that existed in Python and rendered nowhere** are now on
  pages: employer match (the projection ignored the inputs it rendered), the
  OBBBA 2/37 disclosure, marginal-FICA raise modelling, cost of living, and the
  bills calendar.

Counts: **377 assertions** across the four suites (81 + 42 + 168 + 86), 11 API
mutations each required to fail the suite, plus browser checks that are NOT in
the repo — 158 over every route in both themes, 36 interaction, 35 print. The
Python is the floor here, not the ceiling: every defect found during this work
was invisible to a green suite and visible on a rendered page.

## The last three features (September 2026)

CSV import, the savings-rate curve and the year-to-date summary — the three
items the review left open. All three are RULES, so all three are in
`calculations.py`; the pages draw what it returns and decide nothing.

- **`/api/fire` and the savings-rate curve** (`/fire`). The page had held five
  figures of its own arithmetic including a `const SWR = 0.04` that no test
  could see. All five now come from `fire_projection`. The curve's expected
  return is DERIVED from the Monte Carlo's own `MC_STOCK_MEAN`/`MC_BOND_MEAN`
  and the page's stock and inflation controls, so the deterministic curve and
  the stochastic simulation on one page describe ONE world — move the slider
  and both follow. `years_to_target` is closed-form and checked against a
  year-by-year loop, which is a genuinely different method and therefore an
  oracle rather than a mirror.
  - **The clamp hid a plan funded from nowhere.** `annual_savings` is clamped
    at zero so a negative rate can still be plotted, and passing the CLAMPED
    figure to `years_to_target` left someone overspending by $61,581/yr with a
    portfolio quietly compounding to the target in 85 years. Passing the raw
    figure makes the existing drawdown guard return None, which is the truth.
  - The marker must sit ON the line, so the suite asserts the page's savings
    rate and the curve's agree to 1e-6 — a dot floating beside the curve says
    nothing about which of the two is wrong.

- **`/api/year-to-date` and `/year`** (a new route, in the Overview group
  beside the dashboard). Two things make it harder than a sum, and BOTH fail in
  the flattering direction:
  - **An expense log is not a bank statement — it has holes, and a hole looks
    exactly like a frugal month.** Eight months of budget against one month of
    records reads as **$36,007 under budget**. So the variance is measured only
    over COMPLETE months that hold records, `complete_record` says whether that
    is the whole year, and the page leads with the caveat naming the months and
    the figure it would otherwise have reported.
  - **A month in progress is not a short month.** Pro-rating the budget by day
    to match reported the demo's rent — paid on the 1st, read on the 2nd — as
    **$3,800 against $2,030 allowed, 30x over on a bill paid on time**.
    Counting it as a whole month just moves the lie the other way. The current
    month is out of the variance entirely and reported on its own.

- **CSV import** (`/expenses` → Open importer). Splitting the file into cells
  is TypeScript (`src/lib/csv.ts`) — it decides nothing and a mis-split is the
  most visible possible failure. Everything else is in Python because every one
  of these fails SILENTLY: a date order read backwards moves a year of spending
  by a month; a sign convention read backwards imports the refunds and drops
  the purchases; `1.234,56` read as US notation is a $1,234 charge landing as a
  rounding error; importing the same file twice doubles the year.
  - **Duplicates are COUNTED, not matched.** If the profile holds N expenses on
    a date for an amount, the first N rows carrying it are flagged and the rest
    are new. Matching instead refuses two real coffees bought on one day;
    counting handles both that and the re-imported file. Flagged rows are
    unticked, never dropped, and **an import only ever ADDS** — there is no
    merge step, because a merge is where a note somebody typed is replaced by a
    bank's description of the same charge.
  - **Category matching is ONE rule: the longest piece of the description that
    names a category wins**, scored across the person's own category names and
    the merchant table on one list with one comparison. The bank's own category
    column is the FALLBACK, not the winner — Chase files Netflix under
    "Entertainment" and an Uber ride under "Travel", and against a profile
    holding both Subscriptions and Entertainment, both Travel and
    Transportation, letting the column win put both in the wrong one. It earns
    its place on `SQ *A1B2C3XYZ`, which names nothing at all.
  - **The keyword table matches WHOLE WORDS.** As plain substrings, "gym"
    claimed GYMBOREE, "rent" claimed PARENTS MAGAZINE, "metro" claimed the
    METROPOLITAN MUSEUM and "toll" claimed a TOLLHOUSE BAKERY.
  - **`parse_amount` is permissive; DETECTION is not.** It strips non-digits,
    so `STARBUCKS STORE 4` parses as 4.0 — and sniffing a headerless Amex
    export by content, the description column tied with the real amount column
    and won on being further left, importing store numbers as charges.
    `looks_like_amount` is the strict test used for detection.

**Three defects were found by LOOKING, all invisible to a green suite:**
- **A zero-value bar is no element at all in Recharts.** Seven months with
  nothing logged rendered as empty space, under a note telling the reader to
  look for faint bars that had never existed. They are a shaded, labelled
  `ReferenceArea` now — marking an absence rather than drawing a false height.
- **`ReferenceLine` needs `ifOverflow="extendDomain"`.** Recharts sizes the Y
  axis from the data alone, so a $4,892 budget above every bar fell outside the
  domain and was silently dropped — the case of someone spending UNDER budget,
  which is the one the rule exists to show.
- **The first native checkbox in the app rendered in the user agent's blue**,
  the only colour on the page the palette had never touched. `check:tokens`
  cannot see it because there is no literal in the source to grep for;
  `accent-color: var(--accent)` in `@layer base` fixes it.

**The importer was measured on a file the size of a real one, and it did not
hold up.** A year of one card is over a thousand rows. At 1,200 the first
version rendered a `<select>` of every budget category PER ROW — **21,687
`<option>` elements, 35,469 DOM nodes and a page 60,190px tall** — and because
one `skipped` Set drove all of them, **ticking a single checkbox took 341–700ms
to paint**. Nobody reviews an import at half a second a click. Three changes,
each load-bearing at that size: the row is a memoized component so a tick
re-renders ONE row; the table pages at 100; and a filter (All · Needs a
category · Already recorded · Cannot import, with counts) puts the rows that
need a decision in front of the reader. Now **1,887 options, 3,580 nodes,
7,491px, 26–63ms a tick**, and the preview builds in 784ms.
The bug that fix could have introduced is the one worth guarding: **a commit
that acted on the page on screen** would import a hundred rows of twelve
hundred and report success. `bigcorrect.mjs` walks every page, checks all 1,200
line numbers appear exactly once, commits, and counts what actually landed.

**The browser checks are in the repo now — `web/browser-checks/`.** They were
left in the session scratchpad because CI cannot run them, which is an argument
about CI and not about storage; two sessions have since rebuilt them from a
paragraph of prose, and the second rebuild shipped a check that COULD NOT FAIL.
`npm run all` is selftest → sweep → interact → regress. `regression.mjs` covers
the things already fixed once whose fix is invisible in the source: the
cascade-layer fix by computed value, the drawer at 375px, the theme toggle
across a reload, a real Monte Carlo run. `streamlit.mjs` loads all eleven pages
of the OTHER front end — run it before pushing anything that touches
`calculations.py`, because Streamlit Cloud auto-deploys from master and that is
the live recruiter link.

Counts: **521 Python assertions** (203 + 42 + 168 + 108) and **33 mutations**
across the two harnesses; **225 browser assertions** in `web/browser-checks/`
— 130 sweep, 63 interact, 21 regression, 11 big-import — with each of the five
sweep checks proved able to fail against an injected fault before being
trusted. **Of the nine failures those turned up on their first runs, seven were
the CHECK's fault**, which is written up in that directory's README.

**The first deploy found what no suite could: `api/index.py` crashed on import
in production and every /api route 404d or 500d, with a completely green build
log.** `calculations` and `app_data` are siblings written beside it by the sync
script, and every local way of running the API had already put that directory
on `sys.path` without being asked — uvicorn via `--app-dir api`, test_api.py by
inserting it itself. Vercel does neither: it loads the entrypoint with
/var/task as the root. The bundle was correct and the sync had verified
byte-for-byte; the failure existed only at invocation, and only the runtime log
showed it. `api/index.py` now puts its own directory on the path, and
test_api.py loads the entrypoint BY PATH IN A SUBPROCESS with that directory
removed — a subprocess because this one has already imported both modules and
would resolve them from `sys.modules` whatever `sys.path` said, which is how an
in-process version of the check would pass on the broken code.

Three other things about that deploy, each of which cost a cycle: the framework
preset rendered BLANK on the import screen and meant "Other", so a perfect build
failed with `No Output Directory named "public"` — now pinned in `vercel.json`.
The outside-the-root-directory toggle turned out not to be needed. And the
Vercel CLI (`vercel logs <url> --json`) is what ended two hours of guessing from
screenshots; reach for it first next time.

## DEPLOYED — budget.masonjbennett.com is the primary (Sep 3 2026)

Live, and the link on masonjbennett.com now points here: the project card, the
recruiter-safe list and `llms.txt` all switched (dashboard commit 1bcee87).
Verified against the real domain, not localhost — 130 sweep + 63 interaction
assertions, every route 200 in under 0.6s, HSTS on, certificate issued.

**The Streamlit app is a BACKUP now.** Mason is not developing it any further.
It stays live and the keep-alive job still wakes it, and it is the fallback if
this one breaks, so **`calculations.py` must keep working for both** — the
stdlib-only rule and the one-copy-of-the-maths rule are unchanged, and
`web/browser-checks/streamlit.mjs` should still be run before pushing anything
that touches the engine. What HAS changed is that its front end no longer needs
new features, so a capability can land in `web/` alone.

`web/DEPLOY.md` is the click-by-click, now corrected by what actually happened.
