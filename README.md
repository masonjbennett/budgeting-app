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
- **Debt Payoff Planner** — Avalanche vs snowball strategy comparison with amortization schedules and payoff timeline charts

### Plan
- **Investment Growth Projector** — Compound growth across conservative/moderate/aggressive scenarios, cost-of-waiting analysis, 401(k) employer match calculator, and inflation-adjusted returns toggle
- **FIRE Calculator** — Financial independence timeline, savings rate sensitivity chart, what-if scenarios, and FIRE number calculation based on safe withdrawal rate
- **Tax Estimator** — Federal + state tax liability with effective/marginal rate breakdown, standard vs itemized deduction comparison (with updated SALT cap), 401(k) tax savings modeling, and bracket visualization

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
- **Plotly** for interactive, professional charts
- **Pandas** for data manipulation
- Dark theme with custom CSS (Space Grotesk + JetBrains Mono typography)
- Uses `st.session_state` + JSON export/import for data persistence (no database required)

## Deployment

1. Push to GitHub
2. Connect to [Streamlit Cloud](https://streamlit.io/cloud)
3. Deploy — no configuration needed

## Local Development

```bash
pip install -r requirements.txt
streamlit run budget_app.py
```

## Live Demo

[Open the app on Streamlit Cloud](https://masonbennett-budget.streamlit.app/)

## License

MIT
