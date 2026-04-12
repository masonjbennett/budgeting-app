# Personal Budgeting App

A comprehensive personal finance management tool built with Python and Streamlit. Designed for early-career finance professionals to track income, expenses, net worth, debt payoff strategies, savings goals, and investment projections.

**Built by [Mason Bennett](https://masonjbennett.com)**

## Features

- **Financial Health Dashboard** — Cash flow summary, budget adherence, key ratios, color-coded status indicators
- **Income Setup** — Gross salary, federal + state tax estimation, pre-tax deductions, bonus modeling
- **Budget Builder** — 50/30/20 framework with full customization and variance tracking
- **Expense Tracker** — Categorized expense logging with interactive Plotly charts and budget progress bars
- **Net Worth Tracker** — Assets vs liabilities tracking with trend visualization
- **Debt Payoff Planner** — Avalanche vs snowball comparison with amortization schedules
- **Savings Goals** — Goal tracking with progress bars and required monthly contribution calculations
- **Investment Growth Projector** — Compound growth modeling with scenario comparison and cost-of-waiting analysis
- **Tax Estimator** — Federal + state tax liability with effective/marginal rate breakdown and 401(k) tax savings modeling
- **Data Management** — JSON export/import, CSV expense export, full data backup and restore

## Tech Stack

- **Python** + **Streamlit** for the web interface
- **Plotly** for interactive, professional charts
- **Pandas** for data manipulation
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

## Screenshot

![App Screenshot](screenshot.png)

## License

MIT
