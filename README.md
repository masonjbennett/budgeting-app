# Personal Budgeting App

A comprehensive personal finance management tool built with Python and Streamlit. Designed for early-career finance professionals to track income, expenses, net worth, debt payoff strategies, savings goals, investment projections, and FIRE planning.

**Built by [Mason Bennett](https://masonjbennett.com)**

## Features

### Manage
- **Income Setup** — Gross salary, federal + state tax estimation (all 50 states + DC), pre-tax deductions, bonus modeling, filing status support, and a salary negotiation impact modeler
- **Budget Builder** — 50/30/20 framework with full customization, variance tracking, and unallocated income alerts
- **Expense Tracker** — Categorized expense logging with interactive charts, budget progress bars, category filters, recurring expense templates, and month-over-month comparison

### Grow
- **Net Worth Tracker** — Assets vs liabilities tracking with monthly snapshots and trend visualization
- **Savings Goals** — Goal tracking with progress bars, required monthly contributions, priority ranking, and quick-start templates
- **Debt Payoff Planner** — Avalanche vs snowball comparison with amortization schedules and payoff timeline charts. A cleared debt's minimum payment rolls onto the next target, which is what makes a snowball a snowball

### Plan
- **Investment Growth Projector** — Compound growth across conservative/moderate/aggressive scenarios, cost-of-waiting analysis, 401(k) employer match calculator, and inflation-adjusted returns toggle
- **FIRE Calculator** — Financial independence timeline, savings rate sensitivity chart, what-if scenarios, and FIRE number calculation based on safe withdrawal rate
- **Tax Estimator** — Federal + state liability with effective and marginal rate breakdown, standard vs itemized comparison (SALT cap and phase-out, the OBBBA charitable floors), 401(k) tax savings at your real marginal rate, and bracket visualization. Whichever deduction is larger flows back into take-home, so the rest of the app agrees with the advice

### Overview & Tools
- **Financial Health Dashboard** — Monthly cash flow, YTD summary, budget adherence score, savings rate, debt-to-income ratio, emergency fund coverage, net worth trend, and savings goals progress
- **Data Management** — JSON export/import with validation, CSV expense export, demo data loader, and full reset with confirmation

## Tax Data

All tax calculations use **official IRS 2026 data**:
- Federal brackets from [IRS Revenue Procedure 2025-32](https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill)
- SALT cap updated to $40,400 per the One Big Beautiful Bill Act
- 401(k) limit: $24,500 ([IRS Notice 2025-67](https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500))
- SS wage base: $184,500
- HSA individual limit: $4,400
- State rates updated for 2026 changes (OH, NC, KY, IN, GA, OK, MS, MT, NE)

## Tech Stack

- **Python** + **Streamlit** for the web interface
- **Plotly** for interactive charts
- **Pandas** / **NumPy** for data and the Monte Carlo simulation
- **Supabase** for accounts and cloud persistence, with row-level security — every
  database call carries the signed-in user's own JWT, never the public anon key
- Light theme with custom CSS (Space Grotesk headings, Inter throughout)
- All calculations live in `calculations.py`, which imports no framework at all, so
  the tests exercise the same code the app runs rather than a copy of it
- JSON export/import and CSV export still work with no account, and the app degrades
  to local-only if the backend is ever unreachable

## Tests

Three suites, 210 assertions, all driving the shipping code:

```bash
python test_calc.py     #  29 — the debt engine, as properties rather than a re-implementation
python test_cloud.py    #  42 — auth and cloud sync, with streamlit and supabase stubbed
python test_stress.py   # 139 — tax, FICA, SALT, itemizing, investments, dashboard ratios
```

## Deployment

1. Push to GitHub
2. Connect to [Streamlit Cloud](https://streamlit.io/cloud)
3. Add the Supabase credentials under Settings → Secrets (see `SUPABASE_SETUP.md`).
   Without them the app runs fine; only accounts and cloud sync are unavailable.

## Local Development

```bash
pip install -r requirements.txt
streamlit run budget_app.py
```

## Live Demo

[Open the app on Streamlit Cloud](https://masonbennett-budget.streamlit.app/)

## License

MIT
