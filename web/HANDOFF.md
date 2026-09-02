# Handoff prompt — the budget app re-skin and extension

Paste everything below the line into a fresh Claude Code session opened on
`C:\Users\mason\Downloads\Masonjbennett.com Website`.

Written 2026-09-02. If work has happened since, check `git log` in
`budgeting-app/` before trusting the "state of play" section.

---

Redesign and extend budget.masonjbennett.com — the Next.js + FastAPI app in
`budgeting-app/web/`.

## Read first, in this order

1. `budgeting-app/web/README.md` — the rules this codebase is built around.
   Every one exists because the opposite already shipped and was wrong.
2. `budgeting-app/CLAUDE.md` — two front ends, one engine.
3. The root `CLAUDE.md` section on the paper/ink brand and design tokens.
4. `git log --oneline -8` in `budgeting-app/`, and `git show reskin-wip` — see
   "What is already done" below.

## State of play

The rebuild works and is committed. 11 pages, 10 API routes, 340 assertions
across four suites, eslint clean, `npm audit` clean. **It is not deployed.**

`master` is green: `npm run build`, `npx eslint src`, and all four suites pass.
Start from there.

The Streamlit app at masonbennett-budget.streamlit.app is still live, still
linked as recruiter-safe from masonjbennett.com, and **must stay that way** until
this replacement is genuinely better. Do not retire it in passing.

## What is already done — the `reskin-wip` branch

`git show reskin-wip` has three **complete** files that master does not.
The branch does **not** build, because nothing else has been migrated to them.
That is the job. Read the commit message on it first; it lists what remains.

- `web/src/app/globals.css` — the full paper/ink token system. Surfaces, text,
  semantic colour, an 8-step categorical series for charts, radii, type scale,
  controls, tables, badges, motion. All three theme states handled correctly
  (bare `:root` light, `prefers-color-scheme` guarded with
  `:not([data-theme="light"])`, explicit `[data-theme="dark"]`).
  `@theme inline` maps every Tailwind colour utility to `var()`, which is what
  makes theming a token change rather than a rewrite.
- `web/src/app/layout.tsx` — Instrument Serif + Space Grotesk + JetBrains Mono
  via `next/font`, plus a synchronous inline script that applies a stored theme
  before first paint. Deferring that is a visible flash of the wrong theme.
- `web/src/components/Nav.tsx` — replaces `Sidebar.tsx`. Rail at `lg`+, top bar
  and off-canvas drawer below, from one list of destinations. Closes on route
  change and Escape, locks body scroll, returns focus to the opener.

Either merge that branch and finish the migration, or take the files as a spec
and improve on them. Do not half-adopt it — a partial token layer is worse than
either end state.

## Hard constraints — do not break these

- **`calculations.py` and `app_data.py` at the repo root are the only copies**
  of the maths and the starting profiles. `web/api/calculations.py` and
  `web/api/app_data.py` are generated at build time, gitignored, and verified
  byte-for-byte. Never edit or commit them.
- **No arithmetic in TypeScript.** Not a ratio, not a threshold, not a rate.
  If a number needs working out it needs an API route. The client may total
  figures a user typed and nothing else. Both previous versions computed
  debt-to-income and emergency-fund coverage in the display layer and both got
  them wrong the same two ways — DTI keyed to a budget category NAME, so
  $35,000 of student loans read "0.0% — Debt-Free"; coverage keyed to the
  literal asset key "Savings".
- **Nothing invented.** `null` and `0.0` are different answers; every card needs
  a written state for "could not be measured". The scaffold this replaced drew
  sparklines from hardcoded arrays and printed "+$1,700 from last month" as a
  literal beside a real balance.
- **The API stays a pure calculator.** It holds no credential and touches no
  user data. Auth is browser-side Supabase with RLS, which is what keeps the
  Python function from ever holding a JWT.
- **Chart-library entry animations stay off.** Recharts renders a Pie's sectors
  as empty groups until its animation completes, and where it never completes
  the chart is silently blank forever — measured, 0 paths against 3 with the
  flag on and off. CSS transitions and React count-ups are fine; they cannot
  leave a blank.
- **Run all four suites after every change**, plus `web/test_api_mutations.py`,
  which reintroduces nine shipped bugs and requires the API suite to fail on
  each. Commit locally; **do not push without asking**.

## The work, in order

### 1 — Finish the re-skin (this is the whole first milestone)

Land the token layer and migrate everything to it. Nothing else until this is
done, because everything else sits on it.

- Migrate every page and component off the old utility names — `green`/`red`/
  `yellow` become `positive`/`critical`/`caution`; `bg`/`surface`/`primary`/
  `dim` become `paper`/`raise`/`ink`/`body`.
- Remove all **116 hard-coded hex literals** in `web/src/`. Point the chart
  series at the `--s1`…`--s8` tokens so charts follow the theme.
- Add a check that fails if a colour literal reappears in `src/` — the token
  layer is only real if something enforces it.
- Delete `Sidebar.tsx`. `AnimatedNumber` and `MetricCard` have **zero imports**:
  wire `AnimatedNumber` into the hero figure, delete `MetricCard`.
- Paper is the default; ship the light/dark/auto toggle that `Nav.tsx` already
  has.

Design intent: this is the site's brand adapted into an **instrument**, not a
copy of the newspaper. Same palette, same type trio, same hairline discipline;
none of the editorial furniture. Denser and quieter — operated, not read.
Radii 2–4px. Cards are a 1px rule on `--card`, never a tinted block. Claret and
bronze stay strictly semantic, or the alarm states stop reading as alarms.
JetBrains Mono with `tabular-nums` for every number.

**Paper is the default, and this was decided rather than inherited.** The two
design leaders in this category sit at opposite poles — Copilot at `#000814`
deep navy, Monarch at `#F6F5F3` warm paper with a serif display face — so dark
is not a requirement of the category, and warm paper is the leading position in
it rather than the quaint one. The reason to go paper here is not continuity for
its own sake: a distinctive house style is worth more to a portfolio piece than
a well-executed genre style, and filings.masonjbennett.com already proves this
palette carries a dense data tool. Ship dark as a first-class toggle. Be aware
that light is the less forgiving ground — dark hides weak spacing and
low-contrast type, paper does not — so the polish has to be earned in hairline
precision, spacing and type rather than in the palette.

**You have room to deviate where the instrument register calls for it.** It does
not have to match the site exactly. Two specific things to decide with your eyes
on the rendered page rather than by inheriting my spec:

- **Whether the hero figure is Instrument Serif at all.** It is a display serif,
  and it is right for page titles. For a large money figure it may well read
  better as JetBrains Mono or Space Grotesk at display size — more instrument,
  less masthead. Render all three at ~52px against real data and pick; do not
  assume the site's answer transfers.
- **How much serif to use overall.** The site is a newspaper and leans on it.
  This is a control panel, and the right amount is probably less. Titles only,
  possibly titles-and-nothing-else.

### 2 — Dashboard hierarchy

One hero figure at display size, everything else demoted — right now it is a
4-up grid of identically weighted numbers and the eye has nowhere to land.
Abbreviate large figures (`$36.0M`) with the exact value on hover; the FIRE page
currently shows `$36,033,288` beside `$148,039,029` and at a glance they read
the same. Real sparklines from the stored monthly expenses. Per-category budget
progress bars.

### 3 — The Sankey

`gross → federal / state / FICA / pre-tax / take-home`, then
`take-home → needs / wants / savings`, then into categories. It is the
category's signature chart (Monarch's most-loved feature), it is the one nobody
else can draw as precisely because they have no tax engine, and it is the
obvious hero for the dashboard or a new Cash Flow page.

### 4 — The free wins

Tested Python that no page uses:

| Capability | What it unlocks |
|---|---|
| `COL_INDEX` | Cost of living by metro. Already served by `/api/reference`. |
| `marginal_fica_rate` | Raise modelling. Above the wage base the marginal rate drops 7.65% → 1.45%, so the average overstates a raise's tax by up to 5×. |
| `recurring_templates` | A bills calendar. The data shape already exists in the profile. |
| `TOP_BRACKET_START` | The OBBBA 2/37 itemised-deduction limitation warning. |
| Employer match | The inputs render; the projection ignores them. |

### 5 — Scenario comparison

Save a named copy of the profile, change one thing, view both side by side —
state, salary, filing status, contribution rate, city. **No competitor does
this**, because none of them models tax well enough for the comparison to mean
anything. It is the answer to "why not just use Monarch", and it is the screen
that reads as analyst work rather than a CRUD app. New API route over existing
Python; a scenario is a named copy of the object the Settings page already
exports as JSON.

### 6 — Then

CSV transaction import (the cheap answer to having no bank sync), a print
stylesheet producing a one-page summary, and the Streamlit sections the rebuild
dropped: cost of waiting, savings-rate vs years-to-FIRE, the Monte Carlo
ending-balance histogram, year-to-date summary.

## Do not build

- **Bank sync.** Plaid costs per connected item, turns this into a tracker it
  cannot win at, and puts other people's bank credentials behind a personal
  project linked from a recruiting site.
- **AI insights.** The main site vetoed auto-published AI analysis on trust
  grounds and the reasoning transfers exactly. The credibility of this app is
  that every number traces to a tested function and a citable source.
- **Monarch feature parity** — subscription detection, bill negotiation, shared
  household budgets. All of it needs the bank connection that is not being built.

## Deploying

Not deployed yet, deliberately. Sequence:

1. **Preview URL first**, no domain. Three Vercel settings, all in
   `web/README.md`: Root Directory `web/`, **"Include source files outside of
   the Root Directory in the Build Step" ON** (without it the sync cannot see
   `../calculations.py` and the build exits non-zero saying so), and the two
   `NEXT_PUBLIC_SUPABASE_*` variables pointing at the live project
   `shxjjqcuuhqlvgpbujby`. Reuse it; do not create another.
2. Confirm `GET /api/health` returns `{"status":"ok"}`. If it 404s, Vercel is
   serving `api/index.py` at the exact path `/api` only — see the note in
   `web/README.md` about the production rewrite that was deliberately removed.
3. Attach `budget.masonjbennett.com` only after milestones 1 and 2 land, and
   only then update the recruiter-safe link on the main site.

## How I want this done

Verify in a real browser, not just with tests — three defects on Sep 1 and four
more during the rebuild were invisible to a green suite and only showed on a
rendered page. Assert that the code **reads** a rule, not just that the rule is
right. Do not report something verified unless the check could actually have
failed; where practical, break it on purpose and watch it fail. The Browser
pane's compositor goes out of sync on chart-heavy pages — when it and the DOM
disagree, capture with headless Chrome instead (`puppeteer-core` against
`C:\Program Files\Google\Chrome\Application\chrome.exe`).
