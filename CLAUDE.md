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

## Sep 3 2026 — the phone, measured (web/, committed NOT pushed)

First session after the deploy. The handoff's item 1 was "whatever Mason hits on
his phone"; he has not exercised it beyond logging in, so there were no reports
and **measurement was the only evidence available**. Its item 3 — engine
capabilities no page asks for — came up EMPTY and is worth not re-deriving:
every `calculations.py` function with no caller in `api/index.py` is an internal
helper called by another engine function, the routes pass engine returns through
wholesale rather than dropping fields, and every schema field the API returns is
read somewhere in `src/`. The API surface is fully consumed.

**Four defects, all live, all invisible to a green suite — and three of them
invisible to a screenshot as well.** `web/README.md` rule 8 has the detail.

- **Every text-entry control was 14px**, and the two `/expenses` filters 11px —
  74 of them across 10 routes. Mobile Safari zooms the viewport on focus below
  16px and does not zoom back out on blur, so adding an expense left you
  pinching. **This one cannot be seen at all**: headless Chrome does not
  implement the zoom, so the page renders perfectly and the defect exists only
  in the computed font-size. Every earlier lesson in this project is "green
  suite, wrong page"; this is one step past it. Fixed under
  `@media (pointer: coarse)` — a DEVICE query, not a width, because an iPad at
  1024px zooms and a narrowed desktop window does not — and placed in
  `@layer utilities`, because `.t-micro` is in `components` and a layer cannot
  be beaten by specificity from an earlier one. Verified by computed value:
  74/74 at 16px on touch, still 11px×2 + 14px×72 on a mouse.
  **`maximum-scale=1` was rejected**: it stops the zoom by disabling pinch-zoom,
  a WCAG 1.4.4 failure that takes magnification from the people who need it to
  spare everyone else an annoyance.
- **`Section`'s slug did not wrap** — `/expenses` ran 107px past the right edge
  of a phone, the one page-level horizontal overflow in the app, and the
  existing overflow checks only ever covered `/` and `/year`. The hairline is
  `flex-1` with a basis of 0, so **it surrenders its width silently**: two more
  headers measured at EXACTLY the available width with a rule of zero, one
  character from overflowing, with nothing reporting it. A minimum on the rule
  is what makes the row wrap before it overflows. Desktop is untouched — 0 of
  152 header renders wrap at 768 or 1440.
- **Four tables scrolled sideways and the hidden columns were the answer.** A
  table inside `overflow-x-auto` does not overflow the PAGE, so every
  horizontal-overflow check in this repo passes on it — correctly, and none of
  them can ask whether the column carrying the number is on screen. `/expenses`
  hid **Amount**; `/year` hid Spent, Of budget and Variance, i.e. every figure
  it reports. On Mason's call, secondary columns are `hidden sm:table-cell` and
  the cell gutters drop 14px → 8px below 640px, worth 48px on a four-column
  table — enough that nothing had to be hidden merely for margin. **639 and 640
  are both asserted**, because that pair is where a column could return before
  the table fits.
- **The delete buttons in the two tables were 11x21** — bare glyphs with no
  sizing, the smallest controls in the app, for a destructive action with no
  confirmation. Every other remove control was already 30x32 via `.btn-remove`.
  `.btn-remove-quiet` is the same box with no chrome, because thirteen bordered
  boxes down a transaction table read as a column of their own. 69 under-24
  targets → 0.

**Two mistakes of mine worth keeping, both about checks rather than code.**
- **A probe reported "0 problems" over an app where all 13 routes were 500ing.**
  A JSX comment inside an `action={...}` expression (`{/* */}` is only valid
  where CHILDREN are expected) broke the parse, and the probe counted FAILURES
  without ever counting SUBJECTS. `mobile.mjs` now asserts what a healthy run
  must FIND — ~74 controls, ~150 header renders, ~130 tap targets — before it
  asserts anything about them. The cheapest possible bug in a check is a
  selector that matches nothing.
- **The first section-header probe was right for an unwrappable row and wrong
  the moment the row could wrap**: it summed the children's widths against one
  line, so on two lines it exceeded by construction and reported three failures
  on a page with no overflow at all. It measures the row's own right edge now.
  Same family as the `display:none` `<th>` whose zero rect an earlier table
  probe reported as "off screen at -20" — the check inventing the defect it
  exists to find.

**And one caught by LOOKING, in my own fix.** Capping the filter selects at
`max-w-[48%]` truncated the value *inside* the control: the month filter read
**"September 202"** — a clipped date that still reads as a date, which is the
filings terminal's `'4,000,000` defect exactly. Unnecessary as well as wrong:
at their natural widths the two selects are 215px and 200px against 335px, so
wrapping already handles them and the cap now only bites when one select alone
cannot fit a phone.

`shortDate` builds from the date's PARTS, not `new Date(iso)` — a bare ISO date
parses as UTC midnight and renders as the day before for every reader west of
Greenwich, which on an expense list would put every row off by one and only
mislead at a month boundary.

**`web/browser-checks/mobile.mjs` is new and is in `npm run all`** — 15
assertions, with a `--selftest` that injects each of the four defects and
requires the check to fire. Counts after: **selftest 5/5 · sweep 130 · interact
63 · regression 21 · mobile 15**, and the Python is unchanged at **521 + 33
mutations** (nothing touched `calculations.py`, so the Streamlit backup is
unaffected and `streamlit.mjs` was not required). `npm run build`,
`check:tokens`, `eslint`, `tsc` all clean.

**Not done:** `/year`'s "Of budget" and "Bucket", `/debt`'s "Minimum" and
"Cleared" and `/expenses`' note are simply absent below 640px rather than
reachable some other way — that was the deliberate trade against a card-list
rendering, which stays available if the columns turn out to be missed.

**DEPLOYED the same day.** Verified against the real domain in a real browser:
`pointer: coarse` matching, smallest field 16px, page overflow 0, slug `wrap`,
13 delete controls at 32x32, and `/expenses` showing Date · Category · Amount
with 0px hidden; `/year` and `/debt` likewise.
**curl cannot verify this site.** It gets a 403 *Vercel Security Checkpoint*,
and so does headless Chrome — a script polled that challenge page for ten
minutes and concluded "the new build is not serving yet", which was a statement
about a page it never reached. A normal browser passes straight through, so
real visitors are unaffected; use the Browser pane, not curl and not puppeteer.
Also worth knowing: the handoff said master was "green at 1667f07, pushed" and
the remote was actually at 21b33d9 — that commit had never gone up. It was
CLAUDE.md only, so nothing functional was missing from production.

## Sep 3 2026 — the importer on a phone (web/, second pass)

The handoff's own question — "is the importer's table usable at all on a phone,
or should it degrade to a card list?" — answered by driving it. **It is the one
table in the app that cannot be fixed by dropping columns**, and it was
invisible to the first mobile check because it is collapsed behind a button: a
sweep that walks routes never opens it. Measured on opening it: **736px of
table in a 335px scroller, 401px off screen, and six 13x13 checkboxes** — the
app's only checkboxes and the importer's primary control.

- **Column-dropping cannot work here because the columns ARE the decision.**
  Each row carries a tick and a category `<select>`, and the select alone is
  ~146px at touch type size. So `table-cards` on a `<table>` stacks its rows
  into label/value lines below 640px, from `data-label` on each cell rather
  than a second block of JSX — one rendering, so a column cannot say one thing
  on a phone and another on a laptop. The cell is `flex` rather than
  `text-align`, or the `text-right` a cell already carries would push the LABEL
  to the right edge along with the value. Opt-in, because it is right only
  where a row is a decision and wrong for the four data tables.
- **What it costs, measured at 100 rows: 7,635px → 25,219px on a phone.** What
  it does not cost is what the September importer work bought: the DOM is
  unchanged at 3,608 nodes and 1,887 options either way, because this is CSS,
  and a tick still paints in under 20ms. Desktop is untouched — `npm run big`
  is 11/11 with 3,608 nodes and 7,635px against the 3,580 and 7,491px on
  record, and ticks at 16-19ms against 26-63ms.
- **Checkboxes were the user agent's 13x13.** `width: auto` was right as "do
  not take the 100% the text inputs get" and left the box at the browser
  default, half the 24px minimum. 18px now, 24px on a coarse pointer.
- Adding an expense at 375px was driven end to end and is fine: 16px field, a
  335x39 Add button, the row lands, no overflow.
- `mobile.mjs` 15 → **23 assertions**, and it now OPENS the importer and
  uploads a file. Five selftests, including one that strips `table-cards` and
  requires the overflow to reappear.

**And I hit the Bash-tool heredoc trap the handoff warns about.** Writing
`\n` inside `<< 'PYEOF'` collapsed it to a real newline, which broke
`mobile.mjs`'s parse. The handoff says to write scripts with the Write tool and
run them; I did it the other way and it cost a cycle. The docs edits after that
went through a file.

## Sep 3 2026 — the Sankey showed 2 of its 22 labels on a phone (web/)

The last thing on the dashboard wider than the phone, and the worst instance of
the pattern: **the panel wraps the diagram in `overflow-x-auto` with a
`min-w-[640px]` inner box**, so the page never overflows, no check ever fired,
and at 375px the scroller is **293px of a 640px diagram**. What a phone showed
was "Gross pay $8,750" and "FICA $669" — with "State tax $3" and "Federal tax
$" clipped mid-figure at the scroller's edge, a truncated number that still
reads as a number, for the THIRD time in this codebase (after Apple's
`'4,000,000` in filings-terminal and my own "September 202" this morning).
Every budget bucket was off screen: the half the panel exists for. And the
caption told the reader a thin band "names itself on hover", on a device that
has none.

- **A narrower Sankey was the wrong fix.** Its whole claim is that the widths
  are the money; squeezed to 293px the widths survive and the labels do not, so
  it keeps the claim and loses the reading. Below 640px it is replaced by
  `CashFlowList` — the same graph, DERIVED FROM THE SAME `links`: every node
  that is the source of a link becomes a group and its targets become the rows.
  Nothing is hardcoded about stages, so a change to `cash_flow`'s shape shows
  up in both renderings or in neither. **68 of 68 labels visible against 2 of
  22**, and the proportion is carried by a bar rather than dropped.
- **Swapped in CSS, not by a media-query hook.** A hook has no answer to give
  during server render, so the wrong rendering would paint first and correct
  itself. Both trees are in the DOM; the list is ~34 elements.
- **Rule 2 still holds.** The bar width is a proportion of its own group's
  total — layout in exactly the sense the Sankey's ribbon heights are layout —
  and no proportion is ever printed. Every figure on screen came from the
  engine. The denominator is what the group DISTRIBUTES rather than the
  parent's own value: equal wherever the flow balances, and where it is not, a
  bar against the parent would understate every row alike and look like
  rounding.
- **The hover sentence is now `sm:inline`.** The affordance it describes does
  not exist on a touch device, and the list needs no equivalent because every
  label is already written out.

**A gap I had created and closed the same session: `sweep.mjs` does both themes
at ONE width.** So every surface that renders only below 640px — the importer's
cards, this list — had never been contrast-checked in either theme. `mobile.mjs`
now sweeps the phone dashboard in light and dark (0 nodes under 3:1 in both)
and asserts every flow bar resolved to a real colour, because a bar drawn from
an unresolved custom property paints NOTHING and there is no literal to grep
for. **A new mobile-only surface is a new set of colours nobody has measured.**

`mobile.mjs` 23 -> **33 assertions**, six of them proved able to fail against an
injected fault (the sixth puts the Sankey back on the phone). Counts: selftest
5/5, sweep 130, interact 63, regression 21, mobile 33, big 11; Python unchanged
at 521 + 33 mutations.

## Sep 3 2026 — the widths nobody picks (web/)

Two things came out of asking what a phone actually IS, rather than assuming
375. One was a page-level overflow that had been shipping since the re-skin.

- **`/goals` pushed the page sideways from 640px to about 690px, by up to
  34px.** Its `sm:grid-cols-4` puts a date input beside a fixed 30px remove
  button in a cell 127-137px wide, and **Chrome will not draw a date input
  below 149px** — that is what mm/dd/yyyy plus the picker icon costs. A grid
  item and a flex item both default to `min-width: auto`, so neither the track
  nor the `flex-1` shrank. Now `sm:grid-cols-2 lg:grid-cols-4`.
  **`min-w-0` is the tempting fix and is worse**: the cell shrinks, and the
  date input then clips its own segments — trading a page overflow for a
  control nobody can read.
  **The band is 50px wide, which is the whole lesson.** Every check in this
  repo ran at 375, 414, 768 or 1440, and a responsive bug does not live at the
  widths people pick. `mobile.mjs` now tests page overflow at TEN widths:
  320, 360, 375, 390, 414, 639, 640, 768, 1024, 1440. Confirmed pre-existing
  by stashing globals.css back to its committed state and measuring the same
  34px.
- **320px, and where the floor honestly is.** Table gutters 8px -> 6px below
  640 was worth 8px on a four-column table and closed a 3px miss on `/year` at
  360. From **360px up every table fits**. At 320 — iPhone 5 / SE 1st gen,
  2016 hardware — two tables fall back to their own scroller with no page
  overflow. The check COUNTS those and prints the count rather than failing,
  so the day it gets worse is visible; deforming the layout for a ten-year-old
  device would cost the readable one.

**And a finding of my own that was a false positive, caught by looking.**
A chart sweep flagged `2026-09-01` as text painted outside its SVG on two
routes, and the SVG really is `overflow: hidden` — so it read as a clipped
date, the truncation defect this project keeps meeting. **Cropped at 6x device
scale it reads `2026-09-01` in full**: the 2px overhang is the glyph's trailing
side bearing, inside the advance width and carrying no ink. Nothing was
changed. A bounding rect is not ink, and the rule that a failing check is
guilty until proven innocent held for the third time this session.
Getting that crop took two wrong pictures first — `getBoundingClientRect` is
VIEWPORT-relative and puppeteer's screenshot `clip` is PAGE-relative, so
without `window.scrollY` the crop lands wherever that offset points. A clean
picture of the wrong part of the page is the visual form of measuring nothing.

`mobile.mjs` 33 -> **35 assertions**, seven proved able to fail. Counts:
selftest 5/5, sweep 130, interact 63, regression 21, mobile 35, big 11; Python
unchanged at 521 + 33 mutations.

## Sep 4 2026 — `color` is not what SVG paints with (web/)

Chasing the last gap I had left — `mobile.mjs` swept contrast on `/` only, and
`sweep.mjs` does both themes at ONE width — turned up one real defect, one
latent hole in the primary check, and **three false positives of my own**,
which is the more useful number.

- **THE HOLE. `sweep.mjs` measured every text node on
  `getComputedStyle(el).color`, including the ones inside charts, and SVG text
  is painted with `fill`.** On a Recharts tick the two differ: the tspan
  INHERITS the body ink through `color` while `fill` carries the grey it is
  actually drawn in. So every chart label was scored as body-ink-against-card,
  which passes comfortably in either theme no matter what the label is really
  painted. **Measured: a label given its own card's colour — invisible — scores
  1.00 by fill and 14.8 by the old method.** 165 real labels per theme clear
  3:1, so nothing was hiding behind it; but nothing could have been seen if it
  were. Fixed in `sweep.mjs` and `mobile.mjs`, and `selftest.mjs` now injects
  exactly that label and requires the check to fire — 5/5 -> **6/6**.
- **THE DEFECT, and it is the same shape.** The mobile header's breadcrumb
  separator is the ONLY `text-faint` text node in the app (the other use is an
  SVG icon), and it measured **2.57:1** on paper against the sweep's own 3:1
  rule. It survived because the header is `lg:hidden` and every contrast check
  ran at desktop width. `text-muted` now. Exempting it as decorative because it
  carries `aria-hidden` was the alternative and is worse: it makes the rule
  negotiable. `mobile.mjs` sweeps contrast over EVERY route in both themes at
  375px now, not just the dashboard.

**Three false positives, all mine, all caught before changing anything.**
- **A chart axis label at 1.19:1 in dark mode, on nine routes** — my probe read
  `color` (the same bug as above) and fell back to WHITE for the background
  even in dark mode. Two wrong inputs, one alarming number.
- **The landscape drawer: "9 of 12 nav links unreachable".** Two errors in one
  investigation. The probe queried `aside`; the drawer is a `div`, so it
  measured a zero-size element — which made every link "visible" (top >= 0 and
  bottom <= 375 are both trivially true of a zero rect) AND reported no
  scrolling ancestor, two opposite wrong answers from one wrong selector. Then
  the corrected version sampled only the top and bottom of the scroll range and
  called the middle of the list unreachable. Sampled properly: **12 of 12
  reachable**, `flex-1 overflow-y-auto` doing its job. Landscape is fine.
- **A `2026-09-01` axis label "painted outside its SVG"** on two routes, and the
  SVG really is `overflow: hidden` — cropped at 6x it reads in full. The 2px is
  the glyph's trailing side bearing, which carries no ink.

The generalisation worth keeping: **every one of these was a probe reading the
wrong property, the wrong element, or too few samples.** The rule that a
failing check is guilty until proven innocent held four times in two days, and
the one time a check was RIGHT about something invisible, it was right for the
wrong reason and would have missed the real version.

Counts: selftest 5/5 -> **6/6**, sweep 130, interact 63, regression 21,
mobile 35, big 11; Python unchanged at 521 + 33 mutations.

## Sep 4 2026 — /fire was arguing with itself (web/)

The most complex page, gone over on Mason's pick. Two real defects, both of
the kind this project keeps meeting: a page ASSERTING something it had not
computed.

- **The Monte Carlo results were stale, and the sentences under them were
  MISLABELLED.** `/fire` runs the simulation behind a button while the
  savings-rate curve above refetches on a 220ms debounce; `setResult` was only
  ever called on success and never cleared. So the page's own documented claim
  — "the deterministic curve and the stochastic simulation on one page
  describe ONE world, move the slider and both follow" — held only until you
  pressed Run. **Measured: allocation 80% -> 20% moved the curve (7 months
  sooner -> 11) and left the success rate at the 80% run's 97%.**
  The worse half is that two sentences read `age ${endAge}` from LIVE STATE
  beside counts from the stored run, so changing the horizon 95 -> 100
  produced **"Money left at age 100 in 966 of 1,000 paths"** — a simulation
  nobody ran, over a horizon five years longer than those 966 paths survived.
  The same defect sat in the histogram's note.
  Fixed with `ranWith`, the settings the run on screen actually used; both
  sentences quote those and never the controls. The block is KEPT rather than
  cleared so two settings can be compared, and a caution banner NAMES the
  inputs that moved — "your settings changed" would leave the reader hunting
  for which one, and the point is that the numbers belong to the old value.
  Verified by driving: 10 assertions covering appears / names only what moved
  / accumulates a second change / disappears when the settings are put back /
  clears on re-run with the card then quoting the NEW horizon.
- **"Retirement" was cut in half by the chart it lives in.** Recharts draws a
  `position: "top"` reference label ABOVE the plot area and the surface is
  `overflow: hidden`; the fan chart had `margin.top: 8` against a 13px label,
  so the label started **7px above the SVG's own top edge** and its glyph tops
  were sliced. It read as nonsense on the app's headline chart. `margin.top`
  is 20 now.
  **This is the opposite verdict to yesterday's axis-date finding and the
  distinction is the point**: that one overhung horizontally by 2px, which is
  the glyph's trailing side bearing and carries no ink (confirmed at 6x). This
  one loses real ink vertically. `sweep.mjs` now reports VERTICAL overhang
  only, over every text node in every chart: **261 across 13 routes, 0
  clipped** after the fix. Sweep 130 -> **156**, selftest 6/6 -> **7/7**.
  The selftest's first version translated a label by a fixed -14px and did not
  fire — the label it grabbed was nowhere near the top edge, so it reported
  the CHECK broken when the FAULT was. It computes the shift now.

Also driven and found sound: the age-ordering guard (Run disabled with a
warning naming the rule), and the state where results are already on screen
when the ages become invalid — banner and warning both show, consistently, no
console errors.

Counts: selftest **7/7**, sweep **156**, interact 63, regression 21, mobile 35,
big 11; Python unchanged at 521 + 33 mutations.

**Then the same shape, generalised.** /fire's defect was a stored result
outliving its inputs, so every other page was checked for it — and the audit
is worth keeping because most of it came up CLEAN.

- **Only /fire had the button pattern.** Every other page refetches from a
  `useEffect`, so a stored result cannot outlive a control change.
- **The six dependency keys are clean, and they were the real risk.** All six
  effects use `}, [key])` with `key = JSON.stringify([...])`, which eslint
  cannot see through — a value the effect reads but the key omits would go
  stale silently, the same defect with its dependencies hidden inside a
  string. All six cover what they read: `/investments` names only the two
  income fields it actually sends (deliberately, so typing on the Income page
  does not refetch it), `/compare` and `/year` key on the request payload
  itself, and the importer's omission of `existing` cannot bite because
  committing calls `reset()`. `/debt` derives `shown = debts.length ? result :
  null`, so a result from a previous set of debts can never be shown against
  an empty one.
- **What DID come up: a failed REFETCH leaves the figures unexplained.**
  `/debt` and `/investments` render `{error && <card>}` inline and never clear
  the stored result, so the error sits directly above figures computed from
  the previous inputs. Measured by aborting the route after a good load and
  changing an input: on `/investments` the error appeared and all three
  projections — **$635,236 / $938,688 / $1,420,880** — were still the old
  ones. The figures are KEPT rather than dropped, because a network blip
  emptying the page is worse than a labelled stale number; what was missing
  was the label. `/compare` was already right (`rows.length > 1 && !error`),
  and `/year` and the cash-flow panel replace their content outright.
  `regression.mjs` 21 -> **27**, driving it by request interception. Proof it
  can fail is empirical rather than injected: the same probe measured
  `saysStale: false` before the fix and `true` after.

**Two probe errors of mine in this round, both caught by reading the output
rather than the headline.** The `/debt` run reported "error replaces content"
because the figure that changed was the SLIDER'S OWN LABEL — client-side text,
not a fetched number — while the payoff results were stale like everything
else. And the `/year` row of that same table said "no error surfaced", which
proves nothing: the change function fired a `resize` event, which triggers no
refetch, so nothing was ever tested there. /year's clearing path is verified
by reading, not by driving, and is recorded as such.

## Sep 4 2026 — a signed-out visitor's figures now survive a refresh (web/)

A functional pass over the pages nothing had DRIVEN yet — /budget, /goals,
/net-worth, /income, /tax, /compare, /data — plus the feature it turned up.

**The app is functionally sound and all three "failures" were my probes**,
which is the sixth, seventh and eighth of this session:
- "the dashboard does not reflect a salary change" — the dashboard has no
  gross-salary figure at all. Its labels are Net worth, Take-home, Spent,
  Net savings, Budgeted, Financial health. I asserted on something the page
  never claims to show.
- "a goal cannot be added" — "Add goal" needs a name AND a target above zero,
  and the probe filled the wrong number field. A disabled click is a no-op
  that looks exactly like a broken feature.
- "a budget category does not persist" — measured with `page.goto()`, which is
  a FULL RELOAD. Clicking the nav link, which is how people move, keeps it and
  /expenses offers it immediately. I measured the harshest path and called it
  the normal one.

**But the third one was half right, and that is the feature.** `persist()`
writes to Supabase and returned immediately without a user, and there was no
localStorage anywhere — so for a signed-out visitor, the default and what
anyone following the link is, **nothing was written down at all**. A reload
lost everything, and the app's own copy on /data said the figures were "gone
when you close it", which understated a refresh, a deep link and a restored
session.

`web/src/lib/localProfile.ts` keeps them now. Four guards, each a lesson this
project has already paid for: nothing empty or malformed is written or read
back; the key is VERSIONED, which is the only way to invalidate a copy already
sitting in a browser in the wild; every access is wrapped, because private
mode and a full quota THROW rather than returning null and an exception on
boot would blank the app; and **the account still wins** — the local copy is
read only when there is no user and is cleared on sign-in, so it cannot shadow
somebody's account on a shared machine.

**A bug in my own new code, found by testing the guards rather than the
feature**: the first version dropped a payload that failed the shape check but
left UNPARSEABLE JSON in place. The app rendered correctly off the served
profile, so nothing looked wrong, while a dead entry sat in that browser
forever failing to parse on every load. Both routes out of the read clean up
now.

The /data copy was rewritten to match, and deliberately still says an account
is what carries figures to another browser — the sentence must not drift into
implying local storage is a substitute for signing in.

`web/browser-checks/persistence.mjs` is new and in `npm run all`: 17
assertions over the feature, a reset clearing the stored copy, and five bad
payloads plus storage that throws, each of which must leave the app rendering
AND be dropped.

**Also this session: the Streamlit check now points at the live fallback.**
`streamlit.mjs` was hardcoded to localhost:8502, so it verified the CODE and
had never looked at the deployed app — the thing that is supposed to catch a
Vercel outage. It takes `BASE` now and adds Streamlit Cloud's `/~/+/` iframe
path itself, because a probe pointed at the bare host measures an empty
document and calls a healthy app dead. **Live result: 17/17, 308 widgets, 0
Python exceptions, all eleven pages — the fallback works.** Two defects in the
check itself fell out of pointing it somewhere new: a flat 5s pause that was
ample against localhost and reported "0 plotly charts" against an app waking
from sleep (it polls now; measured, charts appear 2s after `stApp`), and an
unhandled TimeoutError instead of a report when there is no app at the URL.

## Sep 4 2026 — the demo now says it is the demo (web/)

Mason asked whether the app should load BLANK, or grow a reset button. Neither,
and the reasoning is worth keeping.

- **A reset already existed** — /data has "Start over" with Load demo profile
  and Start empty, behind a two-click confirm. It works; nothing was missing.
- **Loading blank would gut the recruiting value.** This app is charts and
  derived figures: empty means the Sankey, the fan chart, the histogram, the
  year view and every table render as empty states, and someone following the
  link from masonjbennett.com sees a shell. The demo is also LOAD-BEARING for
  one feature — it ships three debts whose rate order and balance order
  conflict, which is the only reason avalanche and snowball differ at all.
- **The actual gap was that nothing said the figures were examples.** That is
  what made them read as "random values all over the place".

So: one line on the dashboard, `Start empty` and `Got it` inline, retiring
itself on the first edit. Not a modal, not on all thirteen pages.

**The flag is set, never inferred.** It goes on when the SERVED profile loads
and off in `update()`. Comparing the loaded figures against the demo's would
be wrong the moment somebody edited a value back to what it was, and would
need the demo shipped twice. It is a separate localStorage key rather than a
field on `Profile`, because Profile is the schema the engine and the
export/import path both speak and a UI flag would ride into every exported
file.

**Three states, not two, and the third is the whole reason dismissal works.**
Dismissing first REMOVED the key — indistinguishable from never having seen
it. A visitor who dismisses has by definition not edited anything, so nothing
is stored locally, so the next load fetches the served demo, calls it a first
visit and shows the note again. Measured: dismissed, reloaded, back. `"0"`
records the decision, absent means unseen, and an explicit reset to the demo
re-arms it.

`web/browser-checks/demonote.mjs` — 14 assertions, and most of them are about
the states where it must NOT show, because a note saying "these are examples"
over somebody's real figures is worse than no note at all: after an edit,
after a dismissal, after a reload of edited figures, over an emptied profile,
and on any page that is not the dashboard.

## Sep 4 2026 — /compare, the page the DEMO DATA hid (web/)

The handoff's next open thread: `/compare` had been read but never driven. Two
real defects, both live since the re-skin, and the reason neither was ever seen
is the part worth keeping.

**The served demo ships no `scenarios`.** So `/compare` renders its empty state,
and the side-by-side table — the whole reason the screen exists — does not
exist to be measured. `sweep.mjs` and `mobile.mjs` both walk the route, at ten
widths between them, and **both were right to report it clean**. This is the
importer's lesson one step further on: there a button REVEALED the table, here
it creates it. The generalisation for the next reader is *ask what a route looks
like with data in it* — a check hidden by the fixture is indistinguishable from
a check that passes.

- **A scenario column was off screen on every phone.** 375px with two
  scenarios: **171px of a 504px table hidden**; with three, 313px; and the
  hidden column is a whole scenario, carrying Take-home and Worth — the answer.
  The clipped edge read **"$105," and "$70,"**, a truncated number that still
  reads as a number, for the FOURTH time in this codebase.
  **One column per scenario means the width this table needs is DATA**, so no
  fixed breakpoint answers it. Measured with the two text rows wrapping:
  3 columns fit from 323px, 4 from 424px, 5 from 525px, 6 from 738px. Stacking
  at 640 like the importer would still hide a column from four scenarios
  between 640 and 737 — the /goals band again — and would stack a single
  scenario at 375px where the grid fits and reads better, which is what the
  page is for. So the page MEASURES its own scroller and stacks when the grid
  would overflow it: `hidden` is now 0 at all ten widths for 1–4 scenarios.
  **It is layout, not arithmetic** (rule 2 holds as it does for the Sankey's
  ribbon heights), and **it cannot paint the wrong thing first** — the
  objection that sent the Sankey to CSS — because the table exists only after
  `/api/compare` answers, so there is no server render of it to disagree with,
  and the measure runs in a layout effect, before paint. The needed width is
  REMEMBERED, because stacked the table is `display: block` and its scrollWidth
  is merely the scroller's own width, so a naive re-measure could never unstack.
- **A NAME IS NOT AN IDENTITY, and the page painted two winners.** Scenarios are
  numbered `Scenario ${scenarios.length + 1}`, so add two, remove the first, add
  again → two "Scenario 2", a duplicate nobody typed. Columns were keyed on the
  name and the winner marked with `result.best === r.name`, so React logged
  **eleven duplicate-key errors** and the winner's green landed on EVERY column
  carrying the winning name: measured, **a $49,438 column and a $133,988 column
  both marked best in one table**. The engine returns `best_index` /
  `best_take_home_index` now and the paint follows them; `col_changes_answer`
  compares by index too, or a flipped winner between two columns sharing a
  label reports "nothing changed". Generated names skip what is taken
  (including the baseline's own), so the collision no longer arises; a name
  typed twice is allowed and renders correctly. Also: a blank name left the
  remove button announcing **"Remove "**.
- **Two smaller things, both about a page describing itself.** The Difference
  row printed **"baseline"** under any column within 50c of the baseline rather
  than under the baseline — and since a new scenario is a COPY of the baseline,
  two columns both labelled "baseline" was the page's own first state after
  clicking Add. A scenario that ties now reports "no change", which is the
  different claim it is actually making. And my check measured the TABLE's
  overflow at ten widths but never the PAGE's: `mobile.mjs` does measure that on
  `/compare`, and has only ever seen the empty state — the session's own blind
  spot, one layer in. Measured with scenarios on screen at all ten widths and
  1–4 scenarios: **0px**, so the three `<select>`s in each scenario card are
  fine. That is a measurement now rather than an assumption.
- **Proved able to fail, by hand, because neither mutation harness reaches
  this.** `compare_scenarios` is engine code tested only in `test_api.py`, and
  `test_calc_mutations.py` requires `test_calc.py` to fail while
  `test_api_mutations.py` cannot touch `calculations.py` without tripping the
  sync check. So the two name-based versions were put back one at a time and
  `test_api.py` required to fail on each: it does, the second reporting
  `changed=False best=0 raw=1` — the shipped defect exactly.

**One failure in my own new check, and it was the check.** It asserted the
stacked layout matches the importer's card layout property for property (the
two CSS blocks have the same declarations under different gates — a media query
cannot add a class and a class cannot carry a media query — so something has to
stop them drifting). It reported `null`: the importer's table exists only once a
FILE has been read, and clicking "Open importer" is not enough. Ninth probe
error in three sessions, same family as the rest.

**And I put a NUL BYTE in a .tsx and shipped it through a green check.** The
handoff warns that the Bash tool mangles backslashes inside a quoted heredoc;
it has now cost three sessions. The new part is the failure MODE. Writing
`join("\\u0000")` through `bash <<'PY'` delivered a single backslash to Python,
which then interpreted the escape and wrote a real U+0000 into
`src/app/compare/page.tsx`. It was a perfectly good separator, so:
**tsc passed, eslint passed, the build passed, and all 30 browser assertions
passed.** The only symptom was `grep` reporting "Binary file ... matches" and
refusing to search the file — which is how it was found, while reading the diff
rather than running anything.

Two things follow. **Write patch scripts with the Write tool and run them** —
the handoff says so, I did it the other way for speed, and it cost a cycle for
the third time. And **a source file is worth sweeping for control characters
after any scripted edit**: every `.ts`, `.tsx` and `.css` under `src/` was
checked and this was the only one. The replacement needs no escape at all —
`JSON.stringify(names)` has no separator to smuggle.

`web/browser-checks/compare.mjs` is new and in `npm run all` — **33 assertions**,
five proved able to fail against an injected fault. `web/README.md` rule 10.
Counts after: **526 Python assertions** (203 + 42 + 168 + 113) and 33 mutations;
browser **selftest 7 · sweep 156 · interact 63 · compare 33 · regression 27 ·
persistence 17 · demonote 14 · mobile 35 · big 11 · streamlit 17**.

## Sep 4 2026 — the dashboard graded a month that was not over (web/)

The handoff's next tier — the dashboard, `/income`, `/tax`, `/net-worth`,
`/data` had only been driven shallowly. The landing page went first. Two
defects, and the comment sitting directly above the offending code said
*"Adding up what the user typed. Every RULE — thresholds, denominators,
classifications — is in Python; nothing below decides anything."* The twenty
lines beneath it computed a savings rate, an adherence percentage, and four
sets of bands.

- **THE MONTH IS NOT OVER, and both month-dependent cards graded it anyway —
  in the FLATTERING direction, which is the one nobody checks, because a green
  ring looks like the app working.** The savings ring is
  `1 - spent_so_far / take_home`, which starts every month at 100% and falls
  through it, so it grades a countdown. Measured on the 4th of September with a
  single rent charge logged: **70%, painted green**. On the shipped demo:
  **48% green**, against a budget that plans to keep **17%**. Budget adherence
  was the same defect one card over — a category with nothing logged against it
  counts as within budget — so a profile holding ONE expense scored **15/15,
  "On track"**.
  This is `year_to_date`'s own lesson arriving on the page `/year` calls *one
  month wide*: an expense log has holes and a hole looks exactly like a frugal
  month. `health_report` reports the figures for the month SO FAR and withholds
  the VERDICT until the month is complete. `verdict_withheld` carries the reason
  in WORDS rather than a flag, so the ring reads *"48% · Saved so far · 4 of 30
  days into the month"* in the ungraded tone instead of leaving an unexplained
  blank, and adherence reads *"16/16 so far"* with **"5 of them have nothing
  logged yet"** underneath. Pro-rating the budget by elapsed days was not open
  as an alternative: `year_to_date` measured it and it reported rent paid on the
  1st as thirty times over budget on the 2nd. Debt-to-income and the emergency
  fund are not month-dependent and keep their verdicts.
- **Every band moved into the engine**, as `savings_rate_verdict`,
  `dti_verdict` and `emergency_fund_verdict`. They had been a ternary on the
  dashboard and a DIFFERENT ternary on `/year` — **three tiers against four** —
  so one measure was graded by one set on one page and another set on the next;
  `/year` reads the same function now. Every state carries a tone AND a word,
  including the ungraded one, so the page renders what it is handed rather than
  deciding what "no verdict" looks like.
- **The route had never been given the data, which is WHY the two figures were
  in TypeScript.** `DashboardRequest` gained `expenses`, `budget` and the
  client's `today` — the same three `year_to_date` already took, for the same
  timezone reason. `localToday()` builds the date from its PARTS, because
  `toISOString()` is UTC and hands back yesterday for anyone west of Greenwich,
  which on the last day of a month would tell the engine the month is not over
  when it is.
- `ExpenseIn` had to move above `DashboardRequest` — a pydantic model cannot
  reference one defined below it, and the failure is at import, in production.

**`web/browser-checks/health.mjs` is new and in `npm run all` — 27 assertions,
four proved able to fail. It PATCHES THE CLOCK rather than the data**, because
the thing under test is what the page does as a month ends: mid-month the ring
must be the ungraded tone and say how far in, on the last day it must carry a
real verdict. Asserting only the first would pass on a page that never grades
anything. It also re-fetches `/api/dashboard` itself and requires the rendered
percentage to equal the engine's rounded, so the page cannot quietly start
computing one again.

Two smaller things: my own first probe reported the ring and the health cards as
**absent** — wrong selectors, the tenth probe error in this run of sessions —
and its second version tried to rewrite the profile in `localStorage`, which
holds nothing until the visitor edits something (rule 4a working as designed).
And the adherence description said "so far" even on a completed month, found by
reading the rendered output rather than the code.

Counts: **552 Python assertions** (221 + 42 + 168 + 121) and **40 mutations**
(29 + 11) — `test_calc_mutations.py` gained 7, one per new rule, each required
to fail `test_calc.py`. Browser: selftest 7 · sweep 156 · interact 63 ·
compare 33 · **health 27** · regression 27 · persistence 17 · demonote 14 ·
mobile 35 · big 11 · streamlit 17.


## Sep 4 2026 — four patterns from other budgeting apps (web/)

On Mason's instruction to look at what already exists before proposing visual
work. **Actual Budget has a no-account demo, so its real app UI was driven**
rather than read about; Monarch and Copilot are scroll-animation marketing
sites and yielded IA and copy only. One thing worth keeping from the survey:
**Lunch Money's palette is nearly this app's** — cream paper, dark green
primary, solo developer — which says the paper/ink direction is competitive
here rather than eccentric. And an anti-pattern: Actual paints "Avg Per
Transaction" in RED, colour as decoration rather than meaning, which this
codebase already has the better rule for.

All four shipped, in Mason's order of importance. `web/README.md` rule 12.

1. **Every figure names its span.** Four cards in one row, one type size, one
   "This month" heading — covering a monthly RATE, four days of records, and a
   PLAN for a month that has not happened.
2. **A month strip**, which is what makes rule 11's withheld verdict reachable
   at all: pinned to `new Date()`, the grade could appear on the last day of a
   month and never again. `health_report` takes `month` apart from `today`;
   clicking August moves the figures, the spans, the donut and the verdict
   together, and the monthly plan correctly does not move.
3. **A ledger card** for net savings — the one figure on that row that is a
   result rather than a reading. The total comes from the engine and is never
   summed in the component.
4. **Balances in the sidebar**, cut to three totals after measuring: the
   per-account version made the rail 896px against a 784px viewport and put
   the net-worth line below the fold on any laptop.

**Three things found by LOOKING, none of which a suite would have caught.**
`justify-end` inside `overflow-x-auto` puts the overflow at the START of the
scroller, where Chrome will not let you reach it — at 24 months that would have
hidden the oldest months outright. "AUG 26" reads as the 26th of August. And
the strip's visible capitals are a CSS transform, so the button's text content
is `Aug’26` with no separator — which is what a screen reader gets, and is why
it carries an `aria-label`.

**And the heredoc trap cost three more cycles.** Writing `\\u2013` and
`\\u0000` through `bash <<'PY'` mangles the backslash before Python sees it: one
patch silently matched nothing, another wrote `_re.compile` into a module that
does not import `re`. **The rule in the handoff is right and I broke it four
times in one session: write the script with the Write tool and run it.** A
related one worth keeping: an inline `str.replace` with no assertion reports
success having changed nothing, which is how the `_re` line got in.

**A stale mutation reports as a surviving one.** Task 2 rewrote the line a
health-report mutation was anchored on, so the harness printed `[SETUP FAIL]
pattern not found` and counted it survived — correct behaviour, and worth
knowing that "SURVIVED" in the summary can mean "the anchor moved" rather than
"the assertion is weak". Re-anchored, and the fix asserts the new anchor exists
in `calculations.py`.

**Four probe errors, all mine, all the same family.** The strip's month buttons
were matched with `/^[A-Z]{3}$/` against a `textContent` of `"Sep"` — the
capitals are CSS — so the click never landed and the dashboard "did not
respond". A sidebar probe measured the off-canvas DRAWER, which is zero-size at
desktop width, and reported every height as 0. And two task-1 assertions were
invalidated by tasks 3 and 4 rather than by any defect: the Net savings card
became a LedgerCard whose figure is a `span.font-num` not a `p.font-num`, and
the sidebar gained a second element whose label reads "Net worth". **Selecting
an element by its content alone found a second element with the same content
for the third time this session.**

Counts: **569 Python assertions** (234 + 42 + 168 + 125) and **44 mutations**
(33 + 11). Browser: selftest 7 · sweep 156 · interact 63 · compare 33 ·
**health 56** · regression 27 · persistence 17 · demonote 14 · mobile 35.


## Sep 4 2026 — "Start empty" had never started empty (web/)

Mason's report, with a screenshot: after Start empty the dashboard still read
take-home **$5,682**, net savings **$5,682**, budgeted **$4,430**, emergency
fund **4.9 months** and net worth **$20,000**.

Not a bug in the reset. `/api/state?demo=false` served `get_default_state()`,
which is a **starter template** — a $100,000 salary, 17 budget rows totalling
$4,430 and $20,000 across six asset rows. It has served that since the rebuild
and "Start empty" has never meant empty.

`app_data.empty_profile()` now does. Two things about how it is built:

- **Derived from `get_default_state`, not written out again.** The SHAPE is the
  property both front ends and the import path depend on, and a second literal
  profile is a second thing to keep in step — `test_api.py` has asserted the
  key sets match since the first deploy.
- **Zeroed GENERICALLY, by walking every numeric leaf.** A money field added to
  the default later is zeroed here without anybody remembering to; a hand-edited
  copy would quietly ship the new field's default as a simulated figure. Strings
  survive, because a state and a filing status are selections rather than
  figures.

Two values are deliberately NOT zero and the reason is the same one behind
`null` vs `0.0` everywhere else in this app: the projection's expected RETURN
and HORIZON are assumptions, not money, and 0% over 0 years is a broken
projection rather than a blank one.

**The row NAMES are kept**, which is the one judgement call here. A budget with
no categories is not a fresh start, it is a blank page that asks somebody to
invent "Groceries"; the names are a template and the report was about figures
that read as somebody's money. Easy to change if that is not what was wanted.

**What the empty app then does is the half worth checking.** This is charts and
derived figures, so "no data" is where a page has least to say and most ways to
say it wrongly. All thirteen routes render, 8 charts draw and none is empty, and
the dashboard says `—` where a figure cannot be MEASURED rather than `0.0%`:
no savings rate, no debt-to-income, no emergency-fund coverage, "No budget set"
on adherence, and the sidebar's balances block absent rather than a column of
`$0`. `web/browser-checks/empty.mjs`, 22 assertions, three proved able to fail.

**Two probe errors, both mine.** `<nextjs-portal>` is in the DOM on every page
in dev — it hosts the dev-tools indicator — so treating it as an error overlay
reported all thirteen routes broken with a silent console. And the empty-chart
selftest stripped marks from a chart on a page that, under an empty profile, has
none: it returned -1, the probe finding nothing rather than the detector
failing. It builds its own element now.

**One real regression of mine, caught by `sweep.mjs`:** the month strip's year
suffix was `text-faint`, which measures **2.58:1** on paper against this app's
own 3:1 rule. That is the same defect removed from the mobile breadcrumb in
September at 2.57:1, which had left the app with no `text-faint` TEXT at all —
and I put it straight back on a new element. `text-muted` now, which is what the
precedent chose.

Counts: **582 Python assertions** (244 + 42 + 168 + 128) and 44 mutations.
Browser: selftest 7 · sweep 156 · interact 63 · compare 33 · health 56 ·
**empty 22** · regression 27 · persistence 17 · demonote 14 · mobile 35.
