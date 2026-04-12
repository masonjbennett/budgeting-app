import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import uuid
import math
from datetime import datetime, date, timedelta
from copy import deepcopy

# ──────────────────────────────────────────────
# PAGE CONFIG & THEME
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Budget Tracker — Mason Bennett",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Color palette
GREEN = "#34d399"
RED = "#f87171"
BLUE = "#60a5fa"
YELLOW = "#fbbf24"
PURPLE = "#a78bfa"
BG_DARK = "#0f1117"
BG_CARD = "#1a1d29"
BG_SURFACE = "#252836"
TEXT = "#e2e8f0"
TEXT_DIM = "#94a3b8"

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ── Base ── */
:root {
    --bg-dark: #0f1117; --bg-card: #1a1d29; --bg-surface: #252836;
    --green: #34d399; --red: #f87171; --blue: #60a5fa;
    --yellow: #fbbf24; --text: #e2e8f0; --text-dim: #94a3b8;
    --border: #2d3348; --radius: 0.75rem;
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
}
.stApp { background-color: var(--bg-dark); }

/* ── Content width ── */
div[data-testid="stMainBlockContainer"] { max-width: 1200px; margin: 0 auto; }

/* ── Typography ── */
h1 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; letter-spacing: -0.02em; }
h2, h3 { font-family: 'Space Grotesk', sans-serif; font-weight: 600; }
p, span, label, div { color: var(--text); }
.mono { font-family: 'JetBrains Mono', monospace; }
div[data-testid="stCaptionContainer"] { color: var(--text-dim); opacity: 0.85; }

/* ── Cards ── */
.card {
    background: linear-gradient(145deg, #1a1d29, #151823);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 1.5rem; margin-bottom: 1rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25);
    transition: border-color 0.3s var(--ease), box-shadow 0.3s var(--ease);
    animation: fadeIn 0.35s ease-out;
}
.card:hover { border-color: rgba(52,211,153,0.3); box-shadow: 0 8px 24px rgba(0,0,0,0.35); }
@keyframes fadeIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:translateY(0); } }

/* ── Badges ── */
.badge {
    display:inline-block; padding:0.2rem 0.6rem; border-radius:1rem;
    font-size:0.8rem; font-weight:600; font-family:'JetBrains Mono',monospace;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1d29 0%, #151823 100%);
    border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] button {
    transition: all 0.25s var(--ease); border-radius: 0.5rem;
}
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent; border: 1px solid transparent; color: var(--text-dim);
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.2); color: var(--text);
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: rgba(52,211,153,0.15); border: 1px solid rgba(52,211,153,0.3);
    color: var(--green); font-weight: 600;
}

/* ── Metrics ── */
div[data-testid="stMetric"] {
    background: linear-gradient(145deg, #1a1d29, #151823);
    border: 1px solid var(--border); border-radius: var(--radius);
    padding: 1.25rem; transition: all 0.3s var(--ease);
}
div[data-testid="stMetric"]:hover {
    border-color: rgba(52,211,153,0.25); transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(0,0,0,0.3);
}
div[data-testid="stMetricValue"] { font-family: 'JetBrains Mono', monospace; font-weight: 600; }
div[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace; }
div[data-testid="stMetricLabel"] p {
    text-transform: uppercase; letter-spacing: 0.05em; font-size: 0.78rem;
    color: var(--text-dim); font-weight: 500;
}

/* ── Inputs ── */
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {
    font-family: 'JetBrains Mono', monospace; color: var(--text);
    transition: border-color 0.2s var(--ease), box-shadow 0.2s var(--ease);
}
input:focus, div[data-baseweb="input"]:focus-within {
    border-color: var(--green); box-shadow: 0 0 0 3px rgba(52,211,153,0.12);
}
div[data-baseweb="select"] > div { color: var(--text); }
li[role="option"] { color: var(--text); }
li[role="option"]:hover { background: rgba(52,211,153,0.1); }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] { gap: 0.25rem; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 0.5rem 0.5rem 0 0;
    padding: 0.6rem 1.2rem; color: var(--text-dim);
    border-bottom: 2px solid transparent; transition: all 0.25s var(--ease);
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text); background: rgba(52,211,153,0.05); }
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--green); border-bottom-color: var(--green); background: rgba(52,211,153,0.08);
}

/* ── Expanders ── */
div[data-testid="stExpander"] {
    background: linear-gradient(145deg, #1a1d29, #151823);
    border: 1px solid var(--border); border-radius: var(--radius);
    transition: border-color 0.25s var(--ease);
}
div[data-testid="stExpander"]:hover { border-color: rgba(52,211,153,0.25); }

/* ── Dividers ── */
hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }

/* ── Dataframes ── */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border); border-radius: 0.5rem; overflow: hidden;
}

/* ── Buttons ── */
button[kind="primary"] { transition: all 0.25s var(--ease); }
button[kind="primary"]:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(52,211,153,0.25); }
button[kind="secondary"] { transition: all 0.25s var(--ease); }
button[kind="secondary"]:hover { border-color: var(--green); color: var(--green); }

/* ── Alerts ── */
div[data-testid="stAlert"] { border-radius: 0.5rem; }

/* ── Hide default footer ── */
footer { visibility: hidden; }

/* ── Mobile ── */
@media (max-width: 768px) {
    div[data-testid="stMainBlockContainer"] { padding: 0.75rem; }
    div[data-testid="stMetric"] { padding: 0.75rem; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem; }
    .card { padding: 1rem; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# TAX DATA (2026 estimates)
# ──────────────────────────────────────────────

FEDERAL_BRACKETS_2026 = {
    # Source: IRS Revenue Procedure 2025-32 (official 2026 brackets)
    "Single": [
        (12_400, 0.10), (50_400, 0.12), (105_700, 0.22),
        (201_775, 0.24), (256_225, 0.32), (640_600, 0.35),
        (float("inf"), 0.37),
    ],
    "Married Filing Jointly": [
        (24_800, 0.10), (100_800, 0.12), (211_400, 0.22),
        (403_550, 0.24), (512_450, 0.32), (768_700, 0.35),
        (float("inf"), 0.37),
    ],
    "Married Filing Separately": [
        (12_400, 0.10), (50_400, 0.12), (105_700, 0.22),
        (201_775, 0.24), (256_225, 0.32), (384_350, 0.35),
        (float("inf"), 0.37),
    ],
    "Head of Household": [
        (17_700, 0.10), (67_450, 0.12), (105_700, 0.22),
        (201_775, 0.24), (256_200, 0.32), (640_600, 0.35),
        (float("inf"), 0.37),
    ],
}

STANDARD_DEDUCTION_2026 = {
    # Source: IRS Revenue Procedure 2025-32
    "Single": 16_100,
    "Married Filing Jointly": 32_200,
    "Married Filing Separately": 16_100,
    "Head of Household": 24_150,
}

FILING_STATUSES = list(FEDERAL_BRACKETS_2026.keys())

STATE_TAX_DATA = {
    "Alabama": {"brackets": [(500, 0.02), (3000, 0.04), (float("inf"), 0.05)], "deduction": 3000},
    "Alaska": {"brackets": [], "deduction": 0},
    "Arizona": {"brackets": [(float("inf"), 0.025)], "deduction": 14600},
    "Arkansas": {"brackets": [(4400, 0.02), (8800, 0.04), (float("inf"), 0.044)], "deduction": 2340},
    "California": {"brackets": [(10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06), (68350, 0.08), (349137, 0.093), (418961, 0.103), (698271, 0.113), (float("inf"), 0.123)], "deduction": 5540},
    "Colorado": {"brackets": [(float("inf"), 0.044)], "deduction": 15700},
    "Connecticut": {"brackets": [(10000, 0.03), (50000, 0.05), (100000, 0.055), (200000, 0.06), (250000, 0.065), (500000, 0.069), (float("inf"), 0.0699)], "deduction": 0},
    "Delaware": {"brackets": [(2000, 0.0), (5000, 0.022), (10000, 0.039), (20000, 0.048), (25000, 0.052), (60000, 0.0555), (float("inf"), 0.066)], "deduction": 3250},
    "Florida": {"brackets": [], "deduction": 0},
    "Georgia": {"brackets": [(float("inf"), 0.0519)], "deduction": 12000},
    "Hawaii": {"brackets": [(2400, 0.014), (4800, 0.032), (9600, 0.055), (14400, 0.064), (19200, 0.068), (24000, 0.072), (36000, 0.076), (48000, 0.079), (150000, 0.0825), (175000, 0.09), (200000, 0.10), (float("inf"), 0.11)], "deduction": 2200},
    "Idaho": {"brackets": [(float("inf"), 0.058)], "deduction": 14700},
    "Illinois": {"brackets": [(float("inf"), 0.0495)], "deduction": 0},
    "Indiana": {"brackets": [(float("inf"), 0.0295)], "deduction": 0},
    "Iowa": {"brackets": [(6210, 0.044), (31050, 0.0482), (float("inf"), 0.057)], "deduction": 2210},
    "Kansas": {"brackets": [(15000, 0.031), (30000, 0.0525), (float("inf"), 0.057)], "deduction": 3500},
    "Kentucky": {"brackets": [(float("inf"), 0.035)], "deduction": 3160},
    "Louisiana": {"brackets": [(12500, 0.0185), (50000, 0.035), (float("inf"), 0.0425)], "deduction": 0},
    "Maine": {"brackets": [(24500, 0.058), (58050, 0.0675), (float("inf"), 0.0715)], "deduction": 14600},
    "Maryland": {"brackets": [(1000, 0.02), (2000, 0.03), (3000, 0.04), (100000, 0.0475), (125000, 0.05), (150000, 0.0525), (250000, 0.055), (float("inf"), 0.0575)], "deduction": 2550},
    "Massachusetts": {"brackets": [(float("inf"), 0.05)], "deduction": 0},
    "Michigan": {"brackets": [(float("inf"), 0.0405)], "deduction": 5400},
    "Minnesota": {"brackets": [(31690, 0.0535), (104090, 0.068), (183340, 0.0785), (float("inf"), 0.0985)], "deduction": 14575},
    "Mississippi": {"brackets": [(10000, 0.04), (float("inf"), 0.04)], "deduction": 2300},
    "Missouri": {"brackets": [(1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035), (6035, 0.04), (7242, 0.045), (8449, 0.05), (float("inf"), 0.048)], "deduction": 14600},
    "Montana": {"brackets": [(20500, 0.047), (float("inf"), 0.0565)], "deduction": 14600},
    "Nebraska": {"brackets": [(3700, 0.0246), (22170, 0.0351), (35730, 0.0455), (float("inf"), 0.0455)], "deduction": 8200},
    "Nevada": {"brackets": [], "deduction": 0},
    "New Hampshire": {"brackets": [], "deduction": 0},
    "New Jersey": {"brackets": [(20000, 0.014), (35000, 0.0175), (40000, 0.035), (75000, 0.05525), (500000, 0.0637), (1000000, 0.0897), (float("inf"), 0.1075)], "deduction": 0},
    "New Mexico": {"brackets": [(5500, 0.017), (11000, 0.032), (16000, 0.047), (210000, 0.049), (float("inf"), 0.059)], "deduction": 14600},
    "New York": {"brackets": [(8500, 0.04), (11700, 0.045), (13900, 0.0525), (80650, 0.055), (215400, 0.06), (1077550, 0.0685), (5000000, 0.0965), (25000000, 0.103), (float("inf"), 0.109)], "deduction": 8000},
    "North Carolina": {"brackets": [(float("inf"), 0.0399)], "deduction": 14600},
    "North Dakota": {"brackets": [(44725, 0.0195), (float("inf"), 0.025)], "deduction": 14600},
    "Ohio": {"brackets": [(26050, 0.0), (float("inf"), 0.0275)], "deduction": 0},
    "Oklahoma": {"brackets": [(1000, 0.0025), (3750, 0.015), (float("inf"), 0.045)], "deduction": 7350},
    "Oregon": {"brackets": [(4050, 0.0475), (10200, 0.0675), (125000, 0.0875), (float("inf"), 0.099)], "deduction": 2745},
    "Pennsylvania": {"brackets": [(float("inf"), 0.0307)], "deduction": 0},
    "Rhode Island": {"brackets": [(73450, 0.0375), (166950, 0.0475), (float("inf"), 0.0599)], "deduction": 10550},
    "South Carolina": {"brackets": [(3460, 0.0), (17340, 0.03), (float("inf"), 0.064)], "deduction": 14600},
    "South Dakota": {"brackets": [], "deduction": 0},
    "Tennessee": {"brackets": [], "deduction": 0},
    "Texas": {"brackets": [], "deduction": 0},
    "Utah": {"brackets": [(float("inf"), 0.0465)], "deduction": 0},
    "Vermont": {"brackets": [(45400, 0.0335), (110450, 0.066), (229550, 0.076), (float("inf"), 0.0875)], "deduction": 7050},
    "Virginia": {"brackets": [(3000, 0.02), (5000, 0.03), (17000, 0.05), (float("inf"), 0.0575)], "deduction": 4500},
    "Washington": {"brackets": [], "deduction": 0},
    "West Virginia": {"brackets": [(10000, 0.0236), (25000, 0.0315), (40000, 0.0354), (60000, 0.0472), (float("inf"), 0.0512)], "deduction": 0},
    "Wisconsin": {"brackets": [(14320, 0.0354), (28640, 0.0465), (315310, 0.0527), (float("inf"), 0.0765)], "deduction": 13230},
    "Wyoming": {"brackets": [], "deduction": 0},
    "District of Columbia": {"brackets": [(10000, 0.04), (40000, 0.06), (60000, 0.065), (250000, 0.085), (500000, 0.0925), (1000000, 0.0975), (float("inf"), 0.1075)], "deduction": 14600},
}

FICA_SS_RATE = 0.062
FICA_SS_CAP = 184_500  # 2026 Social Security wage base (SSA official)
FICA_MEDICARE_RATE = 0.0145
FICA_MEDICARE_SURTAX = 0.009
FICA_MEDICARE_SURTAX_THRESHOLD = 200_000
SALT_CAP = 40_400  # 2026 OBBBA increased from $10K; phases out above $500K MAGI


def calc_bracket_tax(taxable_income, brackets):
    tax = 0.0
    prev = 0
    for ceiling, rate in brackets:
        if taxable_income <= 0:
            break
        span = min(taxable_income, ceiling - prev)
        tax += span * rate
        taxable_income -= span
        prev = ceiling
    return tax


def calc_federal_tax(gross, deductions_401k=0, other_pretax=0, filing="Single"):
    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])
    standard = STANDARD_DEDUCTION_2026.get(filing, 15_700)
    agi = gross - deductions_401k - other_pretax
    taxable = max(0, agi - standard)
    tax = calc_bracket_tax(taxable, brackets)
    return tax, agi, taxable, standard


def calc_state_tax(gross, state, deductions_401k=0, other_pretax=0):
    sdata = STATE_TAX_DATA.get(state)
    if not sdata or not sdata["brackets"]:
        return 0.0
    agi = gross - deductions_401k - other_pretax
    taxable = max(0, agi - sdata["deduction"])
    return calc_bracket_tax(taxable, sdata["brackets"])


def calc_fica(gross):
    ss = min(gross, FICA_SS_CAP) * FICA_SS_RATE
    medicare = gross * FICA_MEDICARE_RATE
    if gross > FICA_MEDICARE_SURTAX_THRESHOLD:
        medicare += (gross - FICA_MEDICARE_SURTAX_THRESHOLD) * FICA_MEDICARE_SURTAX
    return ss + medicare


# ──────────────────────────────────────────────
# REUSABLE HELPERS
# ──────────────────────────────────────────────

def default_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="JetBrains Mono, monospace", color=TEXT, size=12),
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15),
        xaxis=dict(gridcolor="#2d3348", zerolinecolor="#2d3348"),
        yaxis=dict(gridcolor="#2d3348", zerolinecolor="#2d3348"),
        hovermode="x unified",
    )


def fmt(val, prefix="$", decimals=0):
    if decimals == 0:
        return f"{prefix}{val:,.0f}"
    return f"{prefix}{val:,.{decimals}f}"


def progress_bar_html(pct, color, height="8px"):
    w = min(pct, 100)
    return f'''<div style="background:{BG_SURFACE}; border-radius:0.5rem; height:{height}; margin:0.5rem 0;">
        <div style="background:{color}; border-radius:0.5rem; height:100%; width:{w:.0f}%; transition:width 0.3s;"></div>
    </div>'''


def metric_card_html(label, value, status, color, description=""):
    desc = f'<p style="color:{TEXT_DIM}; margin:0.5rem 0 0; font-size:0.75rem;">{description}</p>' if description else ''
    return f'''<div class="card">
        <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">{label}</p>
        <p class="mono" style="color:{color}; font-size:1.8rem; margin:0.25rem 0;">{value}</p>
        <p style="color:{color}; margin:0; font-size:0.85rem;">&#9679; {status}</p>
        {desc}
    </div>'''


def status_badge_html(text, color):
    return f'<span class="badge" style="background:rgba({_hex_rgb(color)},0.15); color:{color};">{text}</span>'


def _hex_rgb(hex_color):
    h = hex_color.lstrip("#")
    return f"{int(h[0:2],16)},{int(h[2:4],16)},{int(h[4:6],16)}"


def goal_progress_info(goal):
    pct = (goal["current"] / goal["target"] * 100) if goal["target"] else 0
    remaining = goal["target"] - goal["current"]
    days_left = (datetime.strptime(goal["deadline"], "%Y-%m-%d") - datetime.now()).days
    if days_left < 0:
        monthly_needed = 0
        deadline_label = "OVERDUE"
        color = RED
    else:
        months_left = max(1, days_left / 30.44)
        monthly_needed = remaining / months_left if remaining > 0 else 0
        deadline_label = f"{days_left} days left"
        color = GREEN if pct >= 75 else (YELLOW if pct >= 40 else BLUE)
    if pct >= 100:
        color = GREEN
        deadline_label = "COMPLETE"
    return pct, color, monthly_needed, deadline_label


def render_savings_goal_card(goal):
    pct, color, monthly_needed, deadline_label = goal_progress_info(goal)
    badge = status_badge_html(deadline_label, color)
    return f'''<div class="card" style="padding:1rem;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <span style="font-weight:600;">{goal['name']}</span>
            <span class="mono" style="color:{TEXT_DIM};">{fmt(goal['current'])} / {fmt(goal['target'])}</span>
        </div>
        {progress_bar_html(pct, color)}
        <div style="display:flex; justify-content:space-between; font-size:0.8rem; color:{TEXT_DIM};">
            <span>{pct:.0f}% complete</span>
            <span>{fmt(monthly_needed)}/mo needed &middot; {badge}</span>
        </div>
    </div>'''


def project_investment(start, monthly, rate, years):
    values = [start]
    contributions = [start]
    r = rate / 100 / 12
    for m in range(1, years * 12 + 1):
        prev = values[-1]
        values.append(prev * (1 + r) + monthly)
        contributions.append(contributions[-1] + monthly)
    return values, contributions


def simulate_payoff(debts, extra, strategy):
    balances = {d["name"]: float(d["balance"]) for d in debts}
    rates = {d["name"]: d["rate"] / 100 / 12 for d in debts}
    mins = {d["name"]: float(d["min_payment"]) for d in debts}
    total_interest = 0
    months = 0
    schedule = []
    max_months = 600

    # Check if payments can make progress
    total_min = sum(mins.values()) + extra
    total_monthly_interest = sum(b * r for b, r in zip(balances.values(), rates.values()) if b > 0)
    if total_min <= 0:
        return -1, 0, []  # No payments = can't pay off
    if total_min <= total_monthly_interest and total_monthly_interest > 0:
        return -1, 0, []  # Can't cover interest

    while any(b > 0.01 for b in balances.values()) and months < max_months:
        months += 1
        month_interest = 0
        for name in balances:
            if balances[name] > 0:
                interest = balances[name] * rates[name]
                balances[name] += interest
                month_interest += interest
                total_interest += interest

        remaining_extra = extra
        for name in balances:
            if balances[name] > 0:
                payment = min(mins[name], balances[name])
                balances[name] -= payment

        if strategy == "avalanche":
            order = sorted([n for n in balances if balances[n] > 0], key=lambda n: rates[n], reverse=True)
        else:
            order = sorted([n for n in balances if balances[n] > 0], key=lambda n: balances[n])

        for name in order:
            if remaining_extra <= 0:
                break
            if balances[name] > 0:
                payment = min(remaining_extra, balances[name])
                balances[name] -= payment
                remaining_extra -= payment

        schedule.append({
            "month": months,
            "total_balance": sum(max(0, b) for b in balances.values()),
            "interest": month_interest,
        })

    return months, total_interest, schedule


def render_footer():
    st.markdown(f"""
    <div style="text-align:center; padding:2rem 0 1rem; margin-top:3rem; border-top:1px solid #2d3348;">
        <p style="color:{TEXT_DIM}; font-size:0.8rem; margin:0;">
            Built by <a href="https://masonjbennett.com" target="_blank" style="color:{GREEN}; text-decoration:none;">Mason Bennett</a>
            &nbsp;&middot;&nbsp; Powered by Streamlit + Plotly
        </p>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# SESSION STATE INITIALIZATION
# ──────────────────────────────────────────────

def _make_id():
    return str(uuid.uuid4())[:8]


def get_default_state():
    return {
        "income": {
            "gross_salary": 100000,
            "state": "New York",
            "filing_status": "Single",
            "contribution_401k": 6,
            "health_insurance": 200,
            "hsa": 0,
            "bonus_amount": 0,
            "bonus_type": "None",
        },
        "budget": {
            "needs": {
                "Rent": 1800, "Utilities": 150, "Groceries": 400,
                "Transportation": 150, "Insurance": 100,
                "Min. Debt Payments": 0, "Phone": 80,
            },
            "wants": {
                "Dining Out": 300, "Entertainment": 100,
                "Subscriptions": 50, "Shopping": 150,
                "Travel": 200, "Gym": 50,
            },
            "savings": {
                "Emergency Fund": 300, "Student Loans (Extra)": 0,
                "Investing": 400, "Short-Term Goals": 200,
            },
        },
        "expenses": [],
        "recurring_templates": [],
        "net_worth_snapshots": [],
        "assets": {
            "Checking": 5000, "Savings": 8000, "401(k)": 3500,
            "Roth IRA": 2000, "Brokerage": 1500, "Property": 0,
        },
        "liabilities": {
            "Student Loans": 0, "Car Loan": 0, "Credit Cards": 0,
        },
        "debts": [],
        "savings_goals": [],
        "investment": {
            "starting_amount": 5000,
            "monthly_contribution": 500,
            "annual_return": 7.0,
            "time_horizon": 30,
            "employer_match_pct": 50,
            "employer_match_limit": 6,
        },
        "itemized": {
            "salt": 0, "mortgage_interest": 0,
            "charitable": 0, "medical": 0,
        },
    }


DEMO_DATA = {
    "income": {
        "gross_salary": 95000,
        "state": "New York",
        "filing_status": "Single",
        "contribution_401k": 6,
        "health_insurance": 180,
        "hsa": 100,
        "bonus_amount": 10000,
        "bonus_type": "Annual (spread monthly)",
    },
    "budget": {
        "needs": {
            "Rent": 1900, "Utilities": 130, "Groceries": 380,
            "Transportation": 127, "Insurance": 90,
            "Min. Debt Payments": 0, "Phone": 75,
        },
        "wants": {
            "Dining Out": 280, "Entertainment": 90,
            "Subscriptions": 45, "Shopping": 120,
            "Travel": 175, "Gym": 45,
        },
        "savings": {
            "Emergency Fund": 350, "Student Loans (Extra)": 0,
            "Investing": 450, "Short-Term Goals": 150,
        },
    },
    "expenses": [
        {"id": "demo-01", "date": "2026-04-01", "amount": 1900, "category": "Rent", "note": "April rent"},
        {"id": "demo-02", "date": "2026-04-02", "amount": 52.30, "category": "Groceries", "note": "Trader Joe's"},
        {"id": "demo-03", "date": "2026-04-03", "amount": 45.00, "category": "Dining Out", "note": "Dinner with friends"},
        {"id": "demo-04", "date": "2026-04-04", "amount": 127.00, "category": "Transportation", "note": "Monthly metro pass"},
        {"id": "demo-05", "date": "2026-04-05", "amount": 15.99, "category": "Subscriptions", "note": "Spotify + iCloud"},
        {"id": "demo-06", "date": "2026-04-06", "amount": 68.40, "category": "Groceries", "note": "Whole Foods"},
        {"id": "demo-07", "date": "2026-04-07", "amount": 22.00, "category": "Entertainment", "note": "Movie tickets"},
        {"id": "demo-08", "date": "2026-04-08", "amount": 130.00, "category": "Utilities", "note": "Electric + Internet"},
        {"id": "demo-09", "date": "2026-04-09", "amount": 89.99, "category": "Shopping", "note": "Running shoes"},
        {"id": "demo-10", "date": "2026-04-10", "amount": 35.50, "category": "Dining Out", "note": "Lunch meeting"},
        {"id": "demo-11", "date": "2026-04-11", "amount": 75.00, "category": "Phone", "note": "Monthly bill"},
        {"id": "demo-12", "date": "2026-04-12", "amount": 45.00, "category": "Gym", "note": "Monthly membership"},
        {"id": "demo-13", "date": "2026-03-01", "amount": 1900, "category": "Rent", "note": "March rent"},
        {"id": "demo-14", "date": "2026-03-05", "amount": 95.20, "category": "Groceries", "note": "Weekly groceries"},
        {"id": "demo-15", "date": "2026-03-10", "amount": 127.00, "category": "Transportation", "note": "Metro pass"},
        {"id": "demo-16", "date": "2026-03-12", "amount": 62.00, "category": "Dining Out", "note": "Brunch"},
        {"id": "demo-17", "date": "2026-03-15", "amount": 130.00, "category": "Utilities", "note": "Electric + Internet"},
        {"id": "demo-18", "date": "2026-03-20", "amount": 45.00, "category": "Gym", "note": "Monthly membership"},
        {"id": "demo-19", "date": "2026-03-22", "amount": 210.00, "category": "Shopping", "note": "New jacket"},
        {"id": "demo-20", "date": "2026-03-28", "amount": 75.00, "category": "Phone", "note": "Monthly bill"},
    ],
    "recurring_templates": [
        {"name": "Rent", "amount": 1900, "category": "Rent", "day": 1},
        {"name": "Metro Pass", "amount": 127, "category": "Transportation", "day": 4},
        {"name": "Gym Membership", "amount": 45, "category": "Gym", "day": 12},
        {"name": "Phone Bill", "amount": 75, "category": "Phone", "day": 11},
    ],
    "net_worth_snapshots": [
        {"date": "2026-01-01", "assets": 17500, "liabilities": 0, "net_worth": 17500},
        {"date": "2026-02-01", "assets": 19200, "liabilities": 0, "net_worth": 19200},
        {"date": "2026-03-01", "assets": 21800, "liabilities": 0, "net_worth": 21800},
        {"date": "2026-04-01", "assets": 23500, "liabilities": 0, "net_worth": 23500},
    ],
    "assets": {
        "Checking": 6200, "Savings": 9500, "401(k)": 4800,
        "Roth IRA": 2500, "Brokerage": 1800, "Property": 0,
    },
    "liabilities": {
        "Student Loans": 0, "Car Loan": 0, "Credit Cards": 0,
    },
    "debts": [
        {"name": "Example Student Loan", "balance": 35000, "rate": 5.5, "min_payment": 370},
    ],
    "savings_goals": [
        {"name": "Emergency Fund", "target": 15000, "current": 9500, "deadline": "2027-12-31", "priority": 1},
        {"name": "Vacation Fund", "target": 3000, "current": 800, "deadline": "2026-12-31", "priority": 2},
        {"name": "Down Payment", "target": 50000, "current": 1800, "deadline": "2030-06-30", "priority": 3},
    ],
    "investment": {
        "starting_amount": 4800,
        "monthly_contribution": 500,
        "annual_return": 7.0,
        "time_horizon": 30,
        "employer_match_pct": 50,
        "employer_match_limit": 6,
    },
    "itemized": {
        "salt": 0, "mortgage_interest": 0,
        "charitable": 0, "medical": 0,
    },
}


def _ensure_expense_ids(expenses):
    for e in expenses:
        if "id" not in e:
            e["id"] = _make_id()
    return expenses


def init_state():
    if "data" not in st.session_state:
        st.session_state.data = deepcopy(DEMO_DATA)
        _ensure_expense_ids(st.session_state.data["expenses"])
    if "current_page" not in st.session_state:
        st.session_state.current_page = "Dashboard"


init_state()
data = st.session_state.data

# ──────────────────────────────────────────────
# COMPUTE TAKE-HOME
# ──────────────────────────────────────────────

def compute_take_home(d=None):
    if d is None:
        d = data["income"]
    gross = d["gross_salary"]
    bonus = d.get("bonus_amount", 0)
    bonus_type = d.get("bonus_type", "None")
    filing = d.get("filing_status", "Single")
    annual_gross = gross + (bonus if bonus_type != "None" else 0)

    contrib_401k_annual = min(gross * d["contribution_401k"] / 100, 24_500)  # 2026 IRS limit
    health_annual = d["health_insurance"] * 12
    hsa_annual = d["hsa"] * 12
    pretax = contrib_401k_annual + health_annual + hsa_annual

    fed_tax, agi, taxable, std_ded = calc_federal_tax(annual_gross, contrib_401k_annual, health_annual + hsa_annual, filing)
    state_tax = calc_state_tax(annual_gross, d["state"], contrib_401k_annual, health_annual + hsa_annual)
    fica = calc_fica(annual_gross)

    total_tax = fed_tax + state_tax + fica
    annual_take_home = annual_gross - pretax - total_tax
    monthly_take_home = annual_take_home / 12

    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])

    return {
        "annual_gross": annual_gross,
        "contrib_401k": contrib_401k_annual,
        "health": health_annual,
        "hsa": hsa_annual,
        "pretax": pretax,
        "fed_tax": fed_tax,
        "state_tax": state_tax,
        "fica": fica,
        "total_tax": total_tax,
        "annual_take_home": annual_take_home,
        "monthly_take_home": monthly_take_home,
        "agi": agi,
        "taxable": taxable,
        "std_ded": std_ded,
        "effective_rate": (total_tax / annual_gross * 100) if annual_gross else 0,
        "marginal_fed": get_marginal_rate(taxable, brackets),
        "filing": filing,
    }


def get_marginal_rate(taxable, brackets):
    prev = 0
    for ceiling, rate in brackets:
        if taxable <= ceiling:
            return rate * 100
        prev = ceiling
    return brackets[-1][1] * 100


# ──────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; margin-bottom:1.5rem;">
        <h2 style="color:{GREEN}; margin:0; font-family:'Space Grotesk',sans-serif;">Budget Tracker</h2>
        <p style="color:{TEXT_DIM}; font-size:0.85rem; margin:0;">
            <a href="https://masonjbennett.com" target="_blank" style="color:{TEXT_DIM}; text-decoration:none;">masonjbennett.com</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

    nav_groups = [
        ("OVERVIEW", [("📊", "Dashboard")]),
        ("MANAGE", [("💰", "Income Setup"), ("📋", "Budget Builder"), ("💳", "Expense Tracker")]),
        ("GROW", [("📈", "Net Worth"), ("🎯", "Savings Goals"), ("🏦", "Debt Payoff")]),
        ("PLAN", [("📈", "Investments"), ("🔥", "FIRE Calculator"), ("🧾", "Tax Estimator")]),
        ("", [("💾", "Data Management")]),
    ]

    pages = []
    for group_label, items in nav_groups:
        if group_label:
            st.markdown(f'<p style="color:{TEXT_DIM}; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.1em; margin:0.75rem 0 0.25rem 0.5rem; font-weight:600;">{group_label}</p>', unsafe_allow_html=True)
        for icon, name in items:
            pages.append(name)
            if st.sidebar.button(
                f"{icon}  {name}", key=f"nav_{name}",
                use_container_width=True,
                type="primary" if st.session_state.current_page == name else "secondary",
            ):
                st.session_state.current_page = name
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f'<p style="color:{TEXT_DIM}; font-size:0.75rem; text-align:center;">v3.0</p>',
        unsafe_allow_html=True,
    )

page = st.session_state.current_page
th = compute_take_home()


# ══════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════

def page_dashboard():
    st.markdown("# Financial Health Dashboard")
    st.caption("Your financial overview at a glance — updated as you log expenses and adjust your budget.")

    monthly_income = th["monthly_take_home"]
    budget_cats = {**data["budget"]["needs"], **data["budget"]["wants"], **data["budget"]["savings"]}
    total_budgeted = sum(budget_cats.values())

    now = datetime.now()
    cur_month = now.strftime("%Y-%m")
    prev_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    month_expenses = [e for e in data["expenses"] if e["date"][:7] == cur_month]
    prev_expenses = [e for e in data["expenses"] if e["date"][:7] == prev_month]
    total_spent = sum(e["amount"] for e in month_expenses)
    prev_spent = sum(e["amount"] for e in prev_expenses)
    net_savings = monthly_income - total_spent

    # Budget adherence
    cat_spending = {}
    for e in month_expenses:
        cat_spending[e["category"]] = cat_spending.get(e["category"], 0) + e["amount"]
    on_track = sum(1 for cat, b in budget_cats.items() if b == 0 or cat_spending.get(cat, 0) <= b)
    total_cats = len(budget_cats)
    adherence = (on_track / total_cats * 100) if total_cats else 100

    # Net worth
    total_assets = sum(data["assets"].values())
    total_liabilities = sum(data["liabilities"].values())
    net_worth = total_assets - total_liabilities

    # Key ratios
    savings_rate = (net_savings / monthly_income * 100) if monthly_income else 0
    monthly_debt_payments = data["budget"]["needs"].get("Min. Debt Payments", 0)
    dti = (monthly_debt_payments / monthly_income * 100) if monthly_income else 0
    monthly_needs = sum(data["budget"]["needs"].values())
    ef_months = data["assets"].get("Savings", 0) / monthly_needs if monthly_needs else 0

    # Key metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Monthly Take-Home", fmt(monthly_income),
                  help="Net pay after taxes and pre-tax deductions")
    with c2:
        spend_delta = total_spent - prev_spent if prev_spent else 0
        delta_str = f"{'+'if spend_delta>0 else ''}{fmt(spend_delta)} vs last mo"
        st.metric("Spent (MTD)", fmt(total_spent), delta=delta_str,
                  delta_color="inverse")
    with c3:
        st.metric("Net Worth", fmt(net_worth))
    with c4:
        st.metric("Budget Adherence", f"{adherence:.0f}%",
                  help="Percentage of budget categories on track this month")

    st.divider()

    # Financial health ratios
    c1, c2, c3 = st.columns(3)
    with c1:
        color = GREEN if savings_rate >= 20 else (YELLOW if savings_rate >= 10 else RED)
        status = "Excellent" if savings_rate >= 20 else ("Good" if savings_rate >= 10 else "Needs Work")
        st.markdown(metric_card_html("Savings Rate", f"{savings_rate:.1f}%", status, color,
            "20%+ is excellent. 10-20% is solid. Below 10% needs attention."), unsafe_allow_html=True)
    with c2:
        color = GREEN if dti <= 20 else (YELLOW if dti <= 36 else RED)
        status = "Healthy" if dti <= 20 else ("Manageable" if dti <= 36 else "High Risk")
        st.markdown(metric_card_html("Debt-to-Income", f"{dti:.1f}%", status, color,
            "Below 20% is great. 20-36% is manageable. Above 36% limits borrowing."), unsafe_allow_html=True)
    with c3:
        color = GREEN if ef_months >= 6 else (YELLOW if ef_months >= 3 else RED)
        status = "Strong" if ef_months >= 6 else ("Building" if ef_months >= 3 else "Priority")
        st.markdown(metric_card_html("Emergency Fund", f"{ef_months:.1f} mo", status, color,
            "6+ months of essential expenses is the gold standard. 3-6 is a solid start."), unsafe_allow_html=True)

    st.divider()

    # YTD Summary
    cur_year = now.strftime("%Y")
    ytd_expenses = [e for e in data["expenses"] if e["date"][:4] == cur_year]
    ytd_spent = sum(e["amount"] for e in ytd_expenses)
    ytd_income = monthly_income * now.month
    ytd_saved = ytd_income - ytd_spent
    months_elapsed = now.month

    st.markdown("### Year-to-Date Summary")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(f"YTD Income ({months_elapsed}mo)", fmt(ytd_income))
    with c2:
        st.metric("YTD Spending", fmt(ytd_spent))
    with c3:
        st.metric("YTD Saved", fmt(ytd_saved))
    with c4:
        ytd_rate = (ytd_saved / ytd_income * 100) if ytd_income else 0
        st.metric("YTD Savings Rate", f"{ytd_rate:.1f}%")

    st.divider()

    # Charts
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Monthly Cash Flow")
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=["Income", "Spent", "Net Savings"],
            y=[monthly_income, total_spent, net_savings],
            marker_color=[GREEN, RED, BLUE if net_savings >= 0 else RED],
            text=[fmt(monthly_income), fmt(total_spent), fmt(net_savings)],
            textposition="outside",
            textfont=dict(family="JetBrains Mono", size=13),
        ))
        fig.update_layout(**default_layout(), height=350, showlegend=False, yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("### Spending by Category (MTD)")
        if cat_spending:
            cats = list(cat_spending.keys())
            vals = list(cat_spending.values())
            colors = [GREEN if cat in data["budget"]["savings"] else
                      (BLUE if cat in data["budget"]["needs"] else YELLOW)
                      for cat in cats]
            fig = go.Figure(data=[go.Pie(
                labels=cats, values=vals, hole=0.5,
                marker=dict(colors=colors),
                textinfo="label+percent",
                textfont=dict(family="JetBrains Mono", size=11),
            )])
            fig.update_layout(**default_layout(), height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown(f'''<div class="card" style="text-align:center; padding:3rem;">
                <p style="font-size:2rem; margin:0;">💳</p>
                <p style="color:{TEXT_DIM}; margin:0.5rem 0;">No expenses logged this month yet.</p>
                <p style="color:{TEXT_DIM}; font-size:0.85rem;">Head to the Expense Tracker to add your first entry.</p>
            </div>''', unsafe_allow_html=True)

    # Month-over-month comparison
    if prev_expenses and month_expenses:
        st.markdown("### Month-over-Month Comparison")
        prev_cat = {}
        for e in prev_expenses:
            prev_cat[e["category"]] = prev_cat.get(e["category"], 0) + e["amount"]

        all_cats_union = sorted(set(list(cat_spending.keys()) + list(prev_cat.keys())))
        cur_vals = [cat_spending.get(c, 0) for c in all_cats_union]
        prev_vals = [prev_cat.get(c, 0) for c in all_cats_union]

        fig = go.Figure()
        fig.add_trace(go.Bar(name="This Month", x=all_cats_union, y=cur_vals, marker_color=GREEN, opacity=0.8))
        fig.add_trace(go.Bar(name="Last Month", x=all_cats_union, y=prev_vals, marker_color=BLUE, opacity=0.5))
        fig.update_layout(**default_layout(), height=350, barmode="group",
                         yaxis_tickprefix="$", yaxis_tickformat=",",
                         xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # Net worth trend
    if data["net_worth_snapshots"]:
        st.markdown("### Net Worth Trend")
        nw_df = pd.DataFrame(data["net_worth_snapshots"])
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=nw_df["date"], y=nw_df["net_worth"],
            mode="lines+markers", line=dict(color=GREEN, width=3),
            marker=dict(size=8), fill="tozeroy",
            fillcolor="rgba(52,211,153,0.1)",
        ))
        fig.update_layout(**default_layout(), height=300, yaxis_title="Net Worth ($)",
                         yaxis_tickprefix="$", yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    # Savings goals progress
    if data["savings_goals"]:
        st.markdown("### Savings Goals Progress")
        for goal in sorted(data["savings_goals"], key=lambda g: g.get("priority", 99)):
            st.markdown(render_savings_goal_card(goal), unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: INCOME SETUP
# ══════════════════════════════════════════════

def page_income():
    st.markdown("# Income Setup")
    st.caption("Configure your salary, deductions, and tax situation to calculate your true take-home pay.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Salary & Location")
        data["income"]["gross_salary"] = st.number_input(
            "Annual Gross Salary ($)", value=data["income"]["gross_salary"],
            min_value=0, step=1000, format="%d",
        )
        data["income"]["state"] = st.selectbox(
            "State", options=sorted(STATE_TAX_DATA.keys()),
            index=sorted(STATE_TAX_DATA.keys()).index(data["income"]["state"]),
            help="Used for state income tax estimation",
        )
        data["income"]["filing_status"] = st.selectbox(
            "Filing Status", options=FILING_STATUSES,
            index=FILING_STATUSES.index(data["income"].get("filing_status", "Single")),
            help="Affects federal tax brackets and standard deduction amount",
        )

        st.markdown("### Bonus")
        data["income"]["bonus_type"] = st.selectbox(
            "Bonus Type", ["None", "Annual (spread monthly)", "Signing (lump sum)"],
            index=["None", "Annual (spread monthly)", "Signing (lump sum)"].index(data["income"]["bonus_type"]),
        )
        if data["income"]["bonus_type"] != "None":
            data["income"]["bonus_amount"] = st.number_input(
                "Bonus Amount ($)", value=data["income"]["bonus_amount"],
                min_value=0, step=1000, format="%d",
            )

    with c2:
        st.markdown("### Pre-Tax Deductions")
        data["income"]["contribution_401k"] = st.slider(
            "401(k) Contribution (%)", 0, 100, data["income"]["contribution_401k"],
            help="Percentage of base salary. 2026 employee limit: $24,500. Employer match is separate.",
        )
        contrib_dollar = data["income"]["gross_salary"] * data["income"]["contribution_401k"] / 100
        if contrib_dollar > 24500:
            st.warning(f"Your 401(k) contribution ({fmt(contrib_dollar)}) exceeds the 2026 limit of $24,500.")

        data["income"]["health_insurance"] = st.number_input(
            "Health Insurance ($/month)", value=data["income"]["health_insurance"],
            min_value=0, step=10, format="%d",
        )
        data["income"]["hsa"] = st.number_input(
            "HSA Contribution ($/month)", value=data["income"]["hsa"],
            min_value=0, step=25, format="%d",
            help="2026 individual limit: $4,400/year. Only available with HDHP.",
        )

    st.divider()
    st.markdown("### Take-Home Pay Breakdown")
    st.caption("Your estimated net pay after all taxes and deductions.")
    th_local = compute_take_home(data["income"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Annual Gross", fmt(th_local["annual_gross"]))
    with c2:
        st.metric("Total Tax", fmt(th_local["total_tax"]),
                  delta=f"-{th_local['effective_rate']:.1f}% effective")
    with c3:
        st.metric("Annual Take-Home", fmt(th_local["annual_take_home"]))
    with c4:
        st.metric("Monthly Take-Home", fmt(th_local["monthly_take_home"]))

    fig = go.Figure(go.Waterfall(
        x=["Gross Salary", "Bonus", "401(k)", "Health Ins.", "HSA",
           "Federal Tax", "State Tax", "FICA", "Take-Home"],
        y=[
            data["income"]["gross_salary"],
            data["income"].get("bonus_amount", 0) if data["income"]["bonus_type"] != "None" else 0,
            -th_local["contrib_401k"], -th_local["health"], -th_local["hsa"],
            -th_local["fed_tax"], -th_local["state_tax"], -th_local["fica"], 0,
        ],
        measure=["absolute", "relative", "relative", "relative", "relative",
                  "relative", "relative", "relative", "total"],
        connector=dict(line=dict(color="#2d3348")),
        increasing=dict(marker=dict(color=GREEN)),
        decreasing=dict(marker=dict(color=RED)),
        totals=dict(marker=dict(color=BLUE)),
        textposition="outside",
        text=[fmt(data["income"]["gross_salary"]),
              fmt(data["income"].get("bonus_amount", 0) if data["income"]["bonus_type"] != "None" else 0),
              fmt(-th_local["contrib_401k"]), fmt(-th_local["health"]), fmt(-th_local["hsa"]),
              fmt(-th_local["fed_tax"]), fmt(-th_local["state_tax"]),
              fmt(-th_local["fica"]), fmt(th_local["annual_take_home"])],
        textfont=dict(family="JetBrains Mono", size=11),
    ))
    fig.update_layout(**default_layout(), height=400, title="Annual Pay Breakdown")
    st.plotly_chart(fig, use_container_width=True)

    # Salary Negotiation Modeler
    st.divider()
    with st.expander("### Salary Negotiation Modeler", expanded=False):
        st.caption("See how negotiating a higher salary compounds over your career.")

        c1, c2, c3 = st.columns(3)
        with c1:
            neg_increase = st.number_input("Negotiated Raise ($)", value=10000, min_value=0, step=1000, format="%d",
                                            key="neg_raise", help="How much more you'd negotiate")
        with c2:
            neg_years = st.slider("Career Horizon (years)", 1, 40, 25, key="neg_years")
        with c3:
            annual_raise_pct = st.number_input("Annual Raise (%)", value=3.0, min_value=0.0, step=0.5, format="%.1f",
                                                key="neg_annual_raise", help="Expected annual salary increases")

        base = data["income"]["gross_salary"]
        negotiated = base + neg_increase

        base_cum, neg_cum = 0, 0
        base_series, neg_series = [], []
        for y in range(neg_years):
            base_year = base * (1 + annual_raise_pct / 100) ** y
            neg_year = negotiated * (1 + annual_raise_pct / 100) ** y
            base_cum += base_year
            neg_cum += neg_year
            base_series.append(base_cum)
            neg_series.append(neg_cum)

        lifetime_diff = neg_cum - base_cum
        marginal = th_local["marginal_fed"] / 100
        state_d = STATE_TAX_DATA.get(data["income"]["state"])
        state_m = state_d["brackets"][-1][1] if (state_d and state_d.get("brackets")) else 0
        after_tax_diff = lifetime_diff * (1 - marginal - state_m - 0.0765)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Year 1 Difference", fmt(neg_increase), delta=f"+{fmt(neg_increase * (1 - marginal - state_m - 0.0765))} after tax")
        with c2:
            st.metric(f"Lifetime Delta ({neg_years}yr)", fmt(lifetime_diff))
        with c3:
            st.metric("After-Tax Impact", fmt(after_tax_diff),
                      help="Approximate after federal, state, and FICA taxes")

        fig = go.Figure()
        x = list(range(1, neg_years + 1))
        fig.add_trace(go.Scatter(x=x, y=neg_series, name=f"Negotiated ({fmt(negotiated)})",
                                line=dict(color=GREEN, width=2), fill="tonexty"))
        fig.add_trace(go.Scatter(x=x, y=base_series, name=f"Current ({fmt(base)})",
                                line=dict(color=BLUE, width=2), fill="tozeroy",
                                fillcolor="rgba(96,165,250,0.1)"))
        fig.update_layout(**default_layout(), height=300, xaxis_title="Years",
                         yaxis_title="Cumulative Earnings", yaxis_tickprefix="$", yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(f'''<div class="card" style="border-left:3px solid {GREEN};">
            <p style="margin:0; font-weight:600;">Bottom Line</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.9rem;">
                Negotiating <span class="mono" style="color:{GREEN};">{fmt(neg_increase)}</span> more today is worth
                <span class="mono" style="color:{GREEN}; font-weight:600;">{fmt(after_tax_diff)}</span> after taxes over {neg_years} years
                — assuming {annual_raise_pct:.0f}% annual raises compound on the higher base.
            </p>
        </div>''', unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: BUDGET BUILDER
# ══════════════════════════════════════════════

def page_budget():
    st.markdown("# Budget Builder")
    st.caption("Allocate your take-home pay using the 50/30/20 framework — or customize it to fit your life.")
    monthly_income = th["monthly_take_home"]
    total_all = sum(sum(data["budget"][c].values()) for c in ["needs", "wants", "savings"])
    remaining = monthly_income - total_all

    # Unallocated banner
    if remaining > 0:
        st.markdown(f'''<div class="card" style="border-left:3px solid {GREEN}; padding:1rem 1.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-weight:600;">Monthly Take-Home: </span>
                    <span class="mono" style="color:{GREEN};">{fmt(monthly_income)}</span>
                </div>
                <div>
                    <span style="color:{TEXT_DIM};">Unallocated: </span>
                    <span class="mono" style="color:{GREEN}; font-weight:600;">{fmt(remaining)}</span>
                </div>
            </div>
        </div>''', unsafe_allow_html=True)
    elif remaining < 0:
        st.markdown(f'''<div class="card" style="border-left:3px solid {RED}; padding:1rem 1.5rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <span style="font-weight:600;">Monthly Take-Home: </span>
                    <span class="mono">{fmt(monthly_income)}</span>
                </div>
                <div>
                    <span style="color:{RED}; font-weight:600;">OVER BUDGET by </span>
                    <span class="mono" style="color:{RED}; font-weight:600;">{fmt(abs(remaining))}</span>
                </div>
            </div>
        </div>''', unsafe_allow_html=True)
    else:
        st.success("Every dollar is allocated!")

    st.info(f"50/30/20 guideline: **{fmt(monthly_income*0.5)}** needs / **{fmt(monthly_income*0.3)}** wants / **{fmt(monthly_income*0.2)}** savings", icon="💡")

    tabs = st.tabs(["🏠 Needs (50%)", "🎉 Wants (30%)", "💎 Savings & Debt (20%)"])
    targets = {"needs": 0.50, "wants": 0.30, "savings": 0.20}

    for idx, (category, target_pct) in enumerate(targets.items()):
        with tabs[idx]:
            target = monthly_income * target_pct
            items = data["budget"][category]
            total = sum(items.values())
            diff = target - total

            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Budgeted", fmt(total))
            with c2:
                st.metric(f"Guideline ({int(target_pct*100)}%)", fmt(target))
            with c3:
                color = "normal" if diff >= 0 else "inverse"
                st.metric("Variance", fmt(abs(diff)),
                         delta=f"{'Under' if diff >= 0 else 'Over'} by {fmt(abs(diff))}",
                         delta_color=color)

            pct = (total / target * 100) if target else 0
            bar_color = GREEN if pct <= 100 else RED
            st.markdown(progress_bar_html(pct, bar_color, "12px"), unsafe_allow_html=True)

            cols = st.columns(2)
            for i, (name, amount) in enumerate(items.items()):
                with cols[i % 2]:
                    new_val = st.number_input(name, value=amount, min_value=0, step=10,
                                             format="%d", key=f"budget_{category}_{name}")
                    data["budget"][category][name] = new_val

            with st.expander("Add Custom Category"):
                new_name = st.text_input("Category Name", key=f"new_cat_{category}")
                new_amt = st.number_input("Amount ($)", value=0, min_value=0, step=10, key=f"new_amt_{category}")
                if st.button("Add", key=f"add_{category}") and new_name:
                    data["budget"][category][new_name] = new_amt
                    st.rerun()

    # Summary chart
    st.divider()
    st.markdown("### Budget Summary")
    needs_total = sum(data["budget"]["needs"].values())
    wants_total = sum(data["budget"]["wants"].values())
    savings_total = sum(data["budget"]["savings"].values())
    grand_total = needs_total + wants_total + savings_total

    actual_pcts = [
        needs_total / grand_total * 100 if grand_total else 0,
        wants_total / grand_total * 100 if grand_total else 0,
        savings_total / grand_total * 100 if grand_total else 0,
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Your Budget", x=["Needs", "Wants", "Savings"], y=actual_pcts,
        marker_color=[BLUE, YELLOW, GREEN],
        text=[f"{p:.0f}%" for p in actual_pcts], textposition="inside",
        textfont=dict(family="JetBrains Mono", size=14, color="white"),
    ))
    fig.add_trace(go.Scatter(
        name="50/30/20 Guideline", x=["Needs", "Wants", "Savings"],
        y=[50, 30, 20], mode="markers+text",
        marker=dict(color="white", size=12, symbol="diamond"),
        text=["50%", "30%", "20%"], textposition="top center",
        textfont=dict(family="JetBrains Mono", size=12, color=TEXT_DIM),
    ))
    fig.update_layout(**default_layout(), height=350, barmode="group",
                     yaxis_title="% of Budget",
)
    st.plotly_chart(fig, use_container_width=True)
    render_footer()


# ══════════════════════════════════════════════
# PAGE: EXPENSE TRACKER
# ══════════════════════════════════════════════

def page_expenses():
    st.markdown("# Expense Tracker")
    st.caption("Log expenses, track spending against your budget, and spot trends over time.")

    all_cats = (list(data["budget"]["needs"].keys()) +
                list(data["budget"]["wants"].keys()) +
                list(data["budget"]["savings"].keys()))

    # Recurring templates
    if data.get("recurring_templates"):
        with st.expander("🔄 Recurring Templates"):
            now = datetime.now()
            cur_month = now.strftime("%Y-%m")
            existing_notes = {e.get("note", "") for e in data["expenses"] if e["date"][:7] == cur_month}

            templates_due = []
            for t in data["recurring_templates"]:
                note = f"{t['name']} (auto)"
                if note not in existing_notes and now.day >= t["day"]:
                    templates_due.append(t)

            if templates_due:
                st.markdown(f"**{len(templates_due)} template(s) due this month:**")
                for t in templates_due:
                    st.markdown(f"- {t['name']}: {fmt(t['amount'])} ({t['category']}) on day {t['day']}")
                if st.button("Apply All Due Templates", type="primary"):
                    for t in templates_due:
                        day = min(t["day"], 28)
                        exp_date = now.replace(day=day).strftime("%Y-%m-%d")
                        data["expenses"].append({
                            "id": _make_id(), "date": exp_date,
                            "amount": t["amount"], "category": t["category"],
                            "note": f"{t['name']} (auto)",
                        })
                    st.rerun()
            else:
                st.success("All recurring templates applied for this month.")

            # Manage templates
            st.markdown("**Manage Templates:**")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                t_name = st.text_input("Template Name", key="tmpl_name")
            with c2:
                t_amount = st.number_input("Amount ($)", value=0, min_value=0, step=10, key="tmpl_amt")
            with c3:
                t_cat = st.selectbox("Category", all_cats, key="tmpl_cat")
            with c4:
                t_day = st.number_input("Day of Month", value=1, min_value=1, max_value=28, key="tmpl_day")
            if st.button("Add Template") and t_name and t_amount > 0:
                if "recurring_templates" not in data:
                    data["recurring_templates"] = []
                data["recurring_templates"].append({"name": t_name, "amount": t_amount, "category": t_cat, "day": t_day})
                st.rerun()

    # Add expense
    with st.expander("Add New Expense", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            exp_date = st.date_input("Date", value=date.today())
            exp_cat = st.selectbox("Category", all_cats)
        with c2:
            exp_amount = st.number_input("Amount ($)", value=0.0, min_value=0.0, step=0.01, format="%.2f")
            exp_note = st.text_input("Note (optional)")

        if st.button("Add Expense", type="primary"):
            if exp_amount > 0:
                data["expenses"].append({
                    "id": _make_id(), "date": exp_date.isoformat(),
                    "amount": exp_amount, "category": exp_cat, "note": exp_note,
                })
                st.success(f"Added {fmt(exp_amount, decimals=2)} to {exp_cat}")
                st.rerun()
            else:
                st.warning("Enter an amount greater than $0.")

    # Monthly filter + category filter
    now = datetime.now()
    months = sorted(set(e["date"][:7] for e in data["expenses"]), reverse=True)
    if not months:
        months = [now.strftime("%Y-%m")]

    c1, c2 = st.columns([1, 2])
    with c1:
        selected_month = st.selectbox("View Month", months)
    with c2:
        cat_filter = st.multiselect("Filter by Category", all_cats, default=[],
                                     help="Leave empty to show all categories")

    month_expenses = [e for e in data["expenses"] if e["date"][:7] == selected_month]
    if cat_filter:
        month_expenses = [e for e in month_expenses if e["category"] in cat_filter]
    total_spent = sum(e["amount"] for e in month_expenses)

    st.metric("Total Spent", fmt(total_spent, decimals=2))

    if month_expenses:
        st.markdown("### Category Budget Progress")
        cat_spending = {}
        for e in month_expenses:
            cat_spending[e["category"]] = cat_spending.get(e["category"], 0) + e["amount"]

        budget_cats = {**data["budget"]["needs"], **data["budget"]["wants"], **data["budget"]["savings"]}

        for cat in sorted(cat_spending.keys()):
            spent = cat_spending[cat]
            budgeted = budget_cats.get(cat, 0)
            if budgeted > 0:
                pct = spent / budgeted * 100
                if pct >= 100:
                    color, label = RED, "OVER"
                elif pct >= 80:
                    color, label = YELLOW, f"{pct:.0f}%"
                else:
                    color, label = GREEN, f"{pct:.0f}%"
            else:
                pct = 0
                color, label = (TEXT_DIM, "No budget") if spent == 0 else (YELLOW, "Unbudgeted")

            st.markdown(f'''<div style="margin-bottom:0.75rem;">
                <div style="display:flex; justify-content:space-between; margin-bottom:0.25rem;">
                    <span>{cat}</span>
                    <span class="mono" style="color:{color};">{fmt(spent, decimals=2)} / {fmt(budgeted)} — {label}</span>
                </div>
                {progress_bar_html(pct, color)}
            </div>''', unsafe_allow_html=True)

        st.markdown("")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### Spending by Category")
            cats = list(cat_spending.keys())
            vals = list(cat_spending.values())
            fig = go.Figure(data=[go.Pie(
                labels=cats, values=vals, hole=0.5,
                textinfo="label+percent",
                textfont=dict(family="JetBrains Mono", size=11),
                marker=dict(colors=[GREEN, BLUE, YELLOW, RED, PURPLE, "#f472b6", "#38bdf8", "#fb923c", "#a3e635", "#e879f9", "#22d3ee", "#fca5a5"][:len(cats)]),
            )])
            fig.update_layout(**default_layout(), height=350, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("### Daily Spending Trend")
            df = pd.DataFrame(month_expenses)
            df["amount"] = df["amount"].astype(float)
            daily = df.groupby("date")["amount"].sum().reset_index().sort_values("date")
            daily["cumulative"] = daily["amount"].cumsum()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily["date"], y=daily["amount"], name="Daily",
                                marker_color=BLUE, opacity=0.6))
            fig.add_trace(go.Scatter(x=daily["date"], y=daily["cumulative"], name="Cumulative",
                                    line=dict(color=GREEN, width=2), yaxis="y2"))
            fig.update_layout(**default_layout(), height=350,
                yaxis2=dict(overlaying="y", side="right", gridcolor="rgba(0,0,0,0)",
                           tickprefix="$", tickformat=","),
                yaxis_tickprefix="$", yaxis_tickformat=",")
            st.plotly_chart(fig, use_container_width=True)

        # Transaction table
        st.markdown("### Transactions")
        df = pd.DataFrame(month_expenses).sort_values("date", ascending=False)
        display_df = df[["date", "category", "amount", "note"]].copy()
        display_df["amount"] = display_df["amount"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # Delete expense by ID
        with st.expander("🗑️ Delete an Expense"):
            options = [f"{e['date']}  —  {e['category']}  —  ${e['amount']:.2f}  —  {e.get('note','')}"
                       for e in month_expenses]
            to_delete = st.selectbox("Select expense to remove", options)
            if st.button("Delete Selected", type="secondary"):
                idx = options.index(to_delete)
                target_id = month_expenses[idx].get("id")
                if target_id:
                    data["expenses"] = [e for e in data["expenses"] if e.get("id") != target_id]
                else:
                    target = month_expenses[idx]
                    data["expenses"].remove(target)
                st.rerun()
    else:
        st.markdown(f'''<div class="card" style="text-align:center; padding:3rem;">
            <p style="font-size:2rem; margin:0;">📝</p>
            <p style="font-weight:600; margin:0.5rem 0;">No expenses for this month</p>
            <p style="color:{TEXT_DIM}; font-size:0.85rem;">Add your first expense using the form above, or apply recurring templates.</p>
        </div>''', unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: NET WORTH
# ══════════════════════════════════════════════

def page_net_worth():
    st.markdown("# Net Worth Tracker")
    st.caption("Track your assets, liabilities, and net worth over time. Log monthly snapshots to see your progress.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Assets")
        for name in list(data["assets"].keys()):
            data["assets"][name] = st.number_input(
                name, value=data["assets"][name], min_value=0, step=100,
                format="%d", key=f"asset_{name}")
        with st.expander("Add Asset"):
            new_name = st.text_input("Asset Name", key="new_asset_name")
            new_val = st.number_input("Value ($)", value=0, min_value=0, step=100, key="new_asset_val")
            if st.button("Add Asset") and new_name:
                data["assets"][new_name] = new_val
                st.rerun()

    with c2:
        st.markdown("### Liabilities")
        for name in list(data["liabilities"].keys()):
            data["liabilities"][name] = st.number_input(
                name, value=data["liabilities"][name], min_value=0, step=100,
                format="%d", key=f"liability_{name}")
        with st.expander("Add Liability"):
            new_name = st.text_input("Liability Name", key="new_liab_name")
            new_val = st.number_input("Balance ($)", value=0, min_value=0, step=100, key="new_liab_val")
            if st.button("Add Liability") and new_name:
                data["liabilities"][new_name] = new_val
                st.rerun()

    total_assets = sum(data["assets"].values())
    total_liabilities = sum(data["liabilities"].values())
    net_worth = total_assets - total_liabilities

    st.divider()

    # Show change from last snapshot
    last_nw = data["net_worth_snapshots"][-1]["net_worth"] if data["net_worth_snapshots"] else None
    nw_delta = net_worth - last_nw if last_nw is not None else None
    nw_pct = (nw_delta / last_nw * 100) if last_nw and nw_delta is not None else None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Assets", fmt(total_assets))
    with c2:
        st.metric("Total Liabilities", fmt(total_liabilities))
    with c3:
        delta_str = f"{'+' if nw_delta > 0 else ''}{fmt(nw_delta)} ({nw_pct:+.1f}%)" if nw_delta is not None else None
        st.metric("Net Worth", fmt(net_worth), delta=delta_str,
                  help="Change since last snapshot" if delta_str else None)

    # Bar chart
    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(data["assets"].keys()), y=list(data["assets"].values()),
                         name="Assets", marker_color=GREEN))
    if any(v != 0 for v in data["liabilities"].values()):
        fig.add_trace(go.Bar(x=list(data["liabilities"].keys()),
                             y=[-v for v in data["liabilities"].values()],
                             name="Liabilities", marker_color=RED))
    fig.update_layout(**default_layout(), height=350, barmode="relative",
                     yaxis_tickprefix="$", yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    # Log snapshot
    st.markdown("### Log Monthly Snapshot")
    snap_date = st.date_input("Snapshot Date", value=date.today(), key="nw_snap_date")
    if st.button("Save Snapshot", type="primary"):
        data["net_worth_snapshots"].append({
            "date": snap_date.isoformat(),
            "assets": total_assets, "liabilities": total_liabilities, "net_worth": net_worth,
        })
        st.success(f"Snapshot saved: Net worth {fmt(net_worth)} on {snap_date}")

    # Trend
    if data["net_worth_snapshots"]:
        st.markdown("### Net Worth Over Time")
        nw_df = pd.DataFrame(data["net_worth_snapshots"]).sort_values("date")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=nw_df["date"], y=nw_df["assets"], name="Assets",
                                line=dict(color=GREEN, width=2), stackgroup="one"))
        if nw_df["liabilities"].sum() > 0:
            fig.add_trace(go.Scatter(x=nw_df["date"], y=nw_df["liabilities"], name="Liabilities",
                                    line=dict(color=RED, width=2)))
        fig.add_trace(go.Scatter(x=nw_df["date"], y=nw_df["net_worth"], name="Net Worth",
                                line=dict(color=BLUE, width=3)))
        fig.update_layout(**default_layout(), height=350,
                         yaxis_tickprefix="$", yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: DEBT PAYOFF PLANNER
# ══════════════════════════════════════════════

def page_debt():
    st.markdown("# Debt Payoff Planner")
    st.caption("Compare payoff strategies and see how extra payments accelerate your path to debt-free.")

    st.markdown(f'''<div class="card">
        <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">
            <strong>How it works:</strong> Enter your debts and an optional extra monthly payment.
            Compare two strategies:
            <strong style="color:{GREEN};">Avalanche</strong> (highest interest first — saves the most money) vs
            <strong style="color:{BLUE};">Snowball</strong> (smallest balance first — fastest psychological wins).
        </p>
    </div>''', unsafe_allow_html=True)

    with st.expander("➕ Add / Edit Debts", expanded=not data["debts"]):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            d_name = st.text_input("Debt Name", value="", key="debt_name")
        with c2:
            d_balance = st.number_input("Balance ($)", value=0, min_value=0, step=100, key="debt_bal")
        with c3:
            d_rate = st.number_input("Interest Rate (%)", value=5.0, min_value=0.0, step=0.1, format="%.1f", key="debt_rate")
        with c4:
            d_min = st.number_input("Min Payment ($)", value=0, min_value=0, step=10, key="debt_min")

        if st.button("Add Debt", type="primary") and d_name and d_balance > 0:
            data["debts"].append({"name": d_name, "balance": d_balance, "rate": d_rate, "min_payment": d_min})
            st.rerun()

    if data["debts"]:
        df = pd.DataFrame(data["debts"])
        df_display = df.copy()
        df_display["balance"] = df_display["balance"].apply(lambda x: f"${x:,.0f}")
        df_display["rate"] = df_display["rate"].apply(lambda x: f"{x:.1f}%")
        df_display["min_payment"] = df_display["min_payment"].apply(lambda x: f"${x:,.0f}")
        st.dataframe(df_display.rename(columns={"name": "Debt", "balance": "Balance", "rate": "Rate", "min_payment": "Min Payment"}),
                     use_container_width=True, hide_index=True)

        with st.expander("🗑️ Remove a Debt"):
            to_remove = st.selectbox("Select debt", [d["name"] for d in data["debts"]], key="remove_debt")
            if st.button("Remove"):
                data["debts"] = [d for d in data["debts"] if d["name"] != to_remove]
                st.rerun()

        extra = st.number_input("Extra Monthly Payment ($)", value=200, min_value=0, step=50,
                                help="Amount above minimum payments to accelerate payoff")

        months_av, interest_av, sched_av = simulate_payoff(data["debts"], extra, "avalanche")
        months_sn, interest_sn, sched_sn = simulate_payoff(data["debts"], extra, "snowball")

        if months_av == -1:
            st.error("Your minimum payments plus extra don't cover the monthly interest. Increase payments to make progress.")
        else:
            st.markdown("### Strategy Comparison")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f'''<div class="card" style="border-color:{GREEN};">
                    <h4 style="color:{GREEN}; margin:0;">⛰️ Avalanche</h4>
                    <p style="color:{TEXT_DIM}; font-size:0.85rem;">Highest interest rate first</p>
                    <p class="mono" style="font-size:1.5rem; margin:0.5rem 0;">{months_av} months ({months_av/12:.1f} yrs)</p>
                    <p class="mono" style="color:{RED};">Total Interest: {fmt(interest_av)}</p>
                </div>''', unsafe_allow_html=True)
            with c2:
                st.markdown(f'''<div class="card" style="border-color:{BLUE};">
                    <h4 style="color:{BLUE}; margin:0;">☃️ Snowball</h4>
                    <p style="color:{TEXT_DIM}; font-size:0.85rem;">Smallest balance first</p>
                    <p class="mono" style="font-size:1.5rem; margin:0.5rem 0;">{months_sn} months ({months_sn/12:.1f} yrs)</p>
                    <p class="mono" style="color:{RED};">Total Interest: {fmt(interest_sn)}</p>
                </div>''', unsafe_allow_html=True)

            savings = interest_sn - interest_av
            if savings > 0:
                st.success(f"Avalanche saves you **{fmt(savings)}** in interest!")

            fig = go.Figure()
            df_av = pd.DataFrame(sched_av)
            df_sn = pd.DataFrame(sched_sn)
            fig.add_trace(go.Scatter(x=df_av["month"], y=df_av["total_balance"],
                                    name="Avalanche", line=dict(color=GREEN, width=2)))
            fig.add_trace(go.Scatter(x=df_sn["month"], y=df_sn["total_balance"],
                                    name="Snowball", line=dict(color=BLUE, width=2)))
            fig.update_layout(**default_layout(), height=350,
                             xaxis_title="Months", yaxis_title="Remaining Balance",
                             yaxis_tickprefix="$", yaxis_tickformat=",")
            st.plotly_chart(fig, use_container_width=True)

            with st.expander("📋 Amortization Schedule (Avalanche)"):
                if sched_av:
                    am_df = pd.DataFrame(sched_av)
                    am_df["total_balance"] = am_df["total_balance"].apply(lambda x: f"${x:,.2f}")
                    am_df["interest"] = am_df["interest"].apply(lambda x: f"${x:,.2f}")
                    st.dataframe(am_df.rename(columns={"month": "Month", "total_balance": "Balance", "interest": "Monthly Interest"}),
                                use_container_width=True, hide_index=True)
    else:
        st.markdown(f'''<div class="card" style="text-align:center; padding:3rem;">
            <p style="font-size:2rem; margin:0;">🎉</p>
            <p style="color:{GREEN}; font-weight:600; margin:0.5rem 0;">Debt-free is a great place to be!</p>
            <p style="color:{TEXT_DIM}; font-size:0.85rem;">This planner is ready when you need it. Common debts: student loans, car payments, credit cards.</p>
        </div>''', unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: SAVINGS GOALS
# ══════════════════════════════════════════════

def page_savings_goals():
    st.markdown("# Savings Goals")
    st.caption("Set targets, track your progress, and see exactly how much to save each month to stay on track.")

    with st.expander("➕ Add New Goal", expanded=not data["savings_goals"]):
        c1, c2 = st.columns(2)
        with c1:
            g_name = st.text_input("Goal Name", key="goal_name")
            g_target = st.number_input("Target Amount ($)", value=10000, min_value=0, step=500, key="goal_target")
        with c2:
            g_current = st.number_input("Current Savings ($)", value=0, min_value=0, step=100, key="goal_current")
            g_deadline = st.date_input("Deadline", value=date(2027, 12, 31), key="goal_deadline",
                                       min_value=date.today())
        g_priority = st.slider("Priority (1 = highest)", 1, 10, 1, key="goal_priority")

        if st.button("Add Goal", type="primary") and g_name and g_target > 0:
            data["savings_goals"].append({
                "name": g_name, "target": g_target, "current": g_current,
                "deadline": g_deadline.isoformat(), "priority": g_priority,
            })
            st.rerun()

    # Quick-add templates
    if not data["savings_goals"]:
        st.markdown("### Quick Start")
        c1, c2, c3 = st.columns(3)
        templates = [
            ("Emergency Fund", 15000, "2027-12-31"),
            ("Vacation Fund", 3000, "2026-12-31"),
            ("Down Payment", 50000, "2030-06-30"),
        ]
        for col, (name, target, deadline) in zip([c1, c2, c3], templates):
            with col:
                st.markdown(f'''<div class="card" style="text-align:center; padding:1.5rem;">
                    <p style="font-size:1.5rem; margin:0;">{"🛡️" if "Emergency" in name else "✈️" if "Vacation" in name else "🏠"}</p>
                    <p style="font-weight:600; margin:0.5rem 0;">{name}</p>
                    <p class="mono" style="color:{TEXT_DIM};">{fmt(target)}</p>
                </div>''', unsafe_allow_html=True)
                if st.button(f"Add {name}", key=f"quick_{name}", use_container_width=True):
                    data["savings_goals"].append({
                        "name": name, "target": target, "current": 0,
                        "deadline": deadline, "priority": len(data["savings_goals"]) + 1,
                    })
                    st.rerun()

    if data["savings_goals"]:
        for i, goal in enumerate(sorted(data["savings_goals"], key=lambda g: g.get("priority", 99))):
            pct, color, monthly_needed, deadline_label = goal_progress_info(goal)

            c1, c2 = st.columns([3, 1])
            with c1:
                badge = status_badge_html(deadline_label, color)
                st.markdown(f'''<div class="card">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:0.5rem;">
                        <div>
                            <span style="font-weight:700; font-size:1.1rem;">{goal['name']}</span>
                            <span style="color:{TEXT_DIM}; margin-left:0.5rem; font-size:0.8rem;">Priority #{goal.get('priority', '—')}</span>
                        </div>
                        <span class="mono" style="color:{color}; font-size:1.2rem;">{pct:.0f}%</span>
                    </div>
                    {progress_bar_html(pct, color, "14px")}
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:{TEXT_DIM};">
                        <span class="mono">{fmt(goal['current'])} / {fmt(goal['target'])}</span>
                        <span>{fmt(monthly_needed)}/mo needed &middot; {badge}</span>
                    </div>
                </div>''', unsafe_allow_html=True)

            with c2:
                new_current = st.number_input("Update Balance", value=goal["current"], min_value=0,
                                             step=100, key=f"goal_bal_{i}")
                if new_current != goal["current"]:
                    for g in data["savings_goals"]:
                        if g["name"] == goal["name"]:
                            g["current"] = new_current
                    st.rerun()

        with st.expander("🗑️ Remove a Goal"):
            to_remove = st.selectbox("Select goal", [g["name"] for g in data["savings_goals"]], key="remove_goal")
            if st.button("Remove Goal"):
                data["savings_goals"] = [g for g in data["savings_goals"] if g["name"] != to_remove]
                st.rerun()

    render_footer()


# ══════════════════════════════════════════════
# PAGE: INVESTMENT PROJECTOR
# ══════════════════════════════════════════════

def page_investments():
    st.markdown("# Investment Growth Projector")
    st.caption("Model compound growth across scenarios and see the true cost of waiting to invest.")

    c1, c2, c3 = st.columns(3)
    with c1:
        data["investment"]["starting_amount"] = st.number_input(
            "Starting Amount ($)", value=data["investment"]["starting_amount"],
            min_value=0, step=500, format="%d")
        data["investment"]["monthly_contribution"] = st.number_input(
            "Monthly Contribution ($)", value=data["investment"]["monthly_contribution"],
            min_value=0, step=50, format="%d")
    with c2:
        data["investment"]["annual_return"] = st.number_input(
            "Expected Annual Return (%)", value=data["investment"]["annual_return"],
            min_value=0.0, max_value=30.0, step=0.5, format="%.1f")
        data["investment"]["time_horizon"] = st.slider(
            "Time Horizon (years)", 1, 50, data["investment"]["time_horizon"])
    with c3:
        data["investment"]["employer_match_pct"] = st.number_input(
            "Employer Match (%)", value=data["investment"]["employer_match_pct"],
            min_value=0, max_value=100, step=10, format="%d",
            help="E.g., 50% = employer contributes $0.50 per $1 you contribute")
        data["investment"]["employer_match_limit"] = st.number_input(
            "Match Up To (% of salary)", value=data["investment"]["employer_match_limit"],
            min_value=0, max_value=100, step=1, format="%d",
            help="Employer matches up to this % of your salary")

    show_real = st.toggle("Show inflation-adjusted (real) returns", value=False,
                          help="Subtracts ~3% assumed inflation from nominal returns")
    inflation = 3.0 if show_real else 0.0

    inv = data["investment"]
    years = inv["time_horizon"]

    scenarios = [
        ("Conservative (5%)", 5.0 - inflation, BLUE),
        ("Moderate (7%)", 7.0 - inflation, GREEN),
        ("Aggressive (10%)", 10.0 - inflation, YELLOW),
    ]

    st.markdown("### Scenario Comparison" + (" (Inflation-Adjusted)" if show_real else ""))
    fig = go.Figure()
    x_vals = list(range(years + 1))

    for name, rate, color in scenarios:
        values, contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], max(rate, 0), years)
        yearly_vals = [values[y * 12] for y in range(years + 1)]
        fig.add_trace(go.Scatter(
            x=x_vals, y=yearly_vals, name=name,
            line=dict(color=color, width=2),
            hovertemplate="%{text}<extra></extra>",
            text=[f"{name}<br>Year {y}: {fmt(v)}" for y, v in zip(x_vals, yearly_vals)],
        ))

    _, base_contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], 0, years)
    yearly_contribs_base = [base_contribs[y * 12] for y in range(years + 1)]
    fig.add_trace(go.Scatter(x=x_vals, y=yearly_contribs_base, name="Total Contributions",
                            line=dict(color=TEXT_DIM, width=1, dash="dash")))
    fig.update_layout(**default_layout(), height=400, xaxis_title="Years", yaxis_title="Portfolio Value",
                     yaxis_tickprefix="$", yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    # Final values
    c1, c2, c3 = st.columns(3)
    for col, (name, rate, color) in zip([c1, c2, c3], scenarios):
        vals, contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], max(rate, 0), years)
        final = vals[-1]
        total_contrib = contribs[-1]
        growth = final - total_contrib
        with col:
            st.markdown(f'''<div class="card" style="border-left:3px solid {color};">
                <p style="color:{color}; font-weight:600; margin:0;">{name}</p>
                <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(final)}</p>
                <p style="color:{TEXT_DIM}; font-size:0.85rem; margin:0;">
                    Contributed: {fmt(total_contrib)}<br>
                    Growth: <span style="color:{GREEN};">{fmt(growth)}</span>
                </p>
            </div>''', unsafe_allow_html=True)

    # Cost of waiting
    st.markdown("### Cost of Waiting")
    delays = [0, 1, 3, 5]
    rate = max(inv["annual_return"] - inflation, 0)
    fig = go.Figure()
    colors_cow = [GREEN, BLUE, YELLOW, RED]
    for delay, clr in zip(delays, colors_cow):
        effective_years = max(0, years - delay)
        if effective_years == 0:
            padded = [inv["starting_amount"]] * (years + 1)
        else:
            vals, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, effective_years)
            yearly = [vals[min(y * 12, len(vals) - 1)] for y in range(effective_years + 1)]
            padded = [0] * delay + yearly
            padded = padded[:years + 1]
            while len(padded) < years + 1:
                padded.append(padded[-1] if padded else 0)

        label = "Start Now" if delay == 0 else f"Wait {delay} yr{'s' if delay > 1 else ''}"
        fig.add_trace(go.Scatter(x=list(range(years + 1)), y=padded, name=label,
                                line=dict(color=clr, width=2)))

    fig.update_layout(**default_layout(), height=350, xaxis_title="Years", yaxis_title="Portfolio Value",
                     yaxis_tickprefix="$", yaxis_tickformat=",",
                     title=f"Impact of Delaying at {inv['annual_return']:.0f}% Return")
    st.plotly_chart(fig, use_container_width=True)

    if years > 5:
        vals_now, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, years)
        vals_5yr, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, years - 5)
        cost = vals_now[-1] - vals_5yr[-1]
        st.warning(f"Waiting 5 years costs you approximately **{fmt(cost)}** in potential growth.")

    # Employer match
    st.markdown("### 401(k) Employer Match")
    salary = data["income"]["gross_salary"]
    your_contrib_pct = data["income"]["contribution_401k"]
    match_pct = inv["employer_match_pct"]
    match_limit = inv["employer_match_limit"]

    your_annual = salary * your_contrib_pct / 100
    matchable = salary * match_limit / 100
    employer_annual = min(your_annual, matchable) * match_pct / 100
    employer_monthly = employer_annual / 12

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Your Annual 401(k)", fmt(your_annual))
    with c2:
        st.metric("Employer Match", fmt(employer_annual), help="Free money from your employer!")
    with c3:
        total_401k_monthly = your_annual / 12 + employer_monthly
        vals_with, _ = project_investment(inv["starting_amount"], total_401k_monthly, rate, years)
        vals_without, _ = project_investment(inv["starting_amount"], your_annual / 12, rate, years)
        match_value = vals_with[-1] - vals_without[-1]
        st.metric("Match Value Over Time", fmt(match_value),
                  help=f"Extra growth from employer match over {years} years")

    if your_contrib_pct < match_limit:
        max_employer = salary * match_limit / 100 * match_pct / 100
        missed = max_employer - employer_annual
        st.warning(f"You're contributing {your_contrib_pct}% but your employer matches up to {match_limit}%. "
                   f"You're leaving **{fmt(missed)}**/year on the table!")

    render_footer()


# ══════════════════════════════════════════════
# PAGE: FIRE CALCULATOR
# ══════════════════════════════════════════════

def page_fire():
    st.markdown("# FIRE Calculator")
    st.caption("Financial Independence, Retire Early — calculate when your portfolio can sustain your lifestyle.")

    monthly_income = th["monthly_take_home"]

    c1, c2, c3 = st.columns(3)
    with c1:
        fire_income = st.number_input("Annual Take-Home ($)", value=int(th["annual_take_home"]),
                                       min_value=0, step=1000, format="%d", key="fire_income",
                                       help="Your annual after-tax income")
        fire_expenses = st.number_input("Annual Expenses ($)", value=int(sum(
            sum(data["budget"][c].values()) for c in ["needs", "wants"]) * 12),
            min_value=0, step=1000, format="%d", key="fire_expenses",
            help="Your total annual spending (needs + wants)")
    with c2:
        fire_portfolio = st.number_input("Current Portfolio ($)", value=int(sum(data["assets"].values())),
                                          min_value=0, step=1000, format="%d", key="fire_portfolio")
        fire_return = st.number_input("Expected Return (%)", value=7.0, min_value=0.0, max_value=20.0,
                                       step=0.5, format="%.1f", key="fire_return")
    with c3:
        fire_withdrawal = st.number_input("Safe Withdrawal Rate (%)", value=4.0, min_value=1.0, max_value=10.0,
                                           step=0.25, format="%.2f", key="fire_swr",
                                           help="4% is the classic 'Trinity Study' rule. 3.5% is more conservative.")
        fire_inflation = st.number_input("Inflation (%)", value=3.0, min_value=0.0, max_value=10.0,
                                          step=0.5, format="%.1f", key="fire_inflation")

    annual_savings = fire_income - fire_expenses
    savings_rate = (annual_savings / fire_income * 100) if fire_income > 0 else 0
    fire_number = (fire_expenses / (fire_withdrawal / 100)) if fire_withdrawal > 0 else 0
    real_return = fire_return - fire_inflation

    # Calculate years to FIRE
    portfolio = fire_portfolio
    years_to_fire = 0
    fire_reached = False
    trajectory = [{"year": 0, "portfolio": portfolio, "fire_number": fire_number}]

    for y in range(1, 101):
        portfolio = portfolio * (1 + real_return / 100) + annual_savings
        fi_num = fire_number * (1 + fire_inflation / 100) ** y  # inflation-adjusted FIRE number
        trajectory.append({"year": y, "portfolio": portfolio, "fire_number": fi_num})
        if portfolio >= fi_num and not fire_reached:
            years_to_fire = y
            fire_reached = True
            break

    if not fire_reached:
        years_to_fire = -1

    # Key metrics
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        sr_color = GREEN if savings_rate >= 50 else (YELLOW if savings_rate >= 20 else RED)
        sr_status = "Excellent" if savings_rate >= 50 else ("Good" if savings_rate >= 20 else "Low")
        st.markdown(metric_card_html("Savings Rate", f"{savings_rate:.1f}%", sr_status, sr_color,
            "50%+ = FIRE in ~17 yrs. 25% = ~32 yrs. Higher is dramatically better."), unsafe_allow_html=True)
    with c2:
        st.markdown(metric_card_html("FIRE Number", fmt(fire_number), f"At {fire_withdrawal:.1f}% SWR", BLUE,
            f"Portfolio needed to withdraw {fmt(fire_expenses)}/yr safely."), unsafe_allow_html=True)
    with c3:
        if years_to_fire > 0:
            fire_age = 24 + years_to_fire  # approximate
            st.markdown(metric_card_html("Years to FIRE", str(years_to_fire), f"~Age {fire_age}", GREEN,
                f"When your portfolio covers {fmt(fire_expenses)}/yr at {fire_withdrawal:.1f}% withdrawal."), unsafe_allow_html=True)
        else:
            st.markdown(metric_card_html("Years to FIRE", "100+", "Increase savings", RED,
                "Your current savings rate won't reach FIRE. Increase income or reduce expenses."), unsafe_allow_html=True)
    with c4:
        monthly_passive = fire_number * fire_withdrawal / 100 / 12
        st.markdown(metric_card_html("Passive Income at FIRE", fmt(monthly_passive) + "/mo", "From portfolio", GREEN,
            f"What your portfolio generates at {fire_withdrawal:.1f}% withdrawal rate."), unsafe_allow_html=True)

    # Trajectory chart
    st.markdown("### Path to Financial Independence")
    traj_df = pd.DataFrame(trajectory)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=traj_df["year"], y=traj_df["portfolio"], name="Your Portfolio",
                            line=dict(color=GREEN, width=3), fill="tozeroy",
                            fillcolor="rgba(52,211,153,0.1)"))
    fig.add_trace(go.Scatter(x=traj_df["year"], y=traj_df["fire_number"], name="FIRE Number",
                            line=dict(color=RED, width=2, dash="dash")))
    if fire_reached:
        fig.add_vline(x=years_to_fire, line_dash="dot", line_color=YELLOW, annotation_text=f"FIRE! Year {years_to_fire}")
    fig.update_layout(**default_layout(), height=400, xaxis_title="Years from Now",
                     yaxis_title="Portfolio Value", yaxis_tickprefix="$", yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    # Savings rate sensitivity
    st.markdown("### Savings Rate vs. Years to FIRE")
    st.caption("How your savings rate dramatically affects your timeline — the math is non-linear.")

    rates = list(range(10, 85, 5))
    years_list = []
    for sr in rates:
        ann_save = fire_income * sr / 100
        ann_spend = fire_income - ann_save
        fi_num = (ann_spend / (fire_withdrawal / 100)) if fire_withdrawal > 0 else 0
        p = fire_portfolio
        yrs = 0
        for y in range(1, 101):
            p = p * (1 + real_return / 100) + ann_save
            if p >= fi_num:
                yrs = y
                break
        years_list.append(yrs if yrs > 0 else 100)

    fig = go.Figure()
    bar_colors = [GREEN if y <= 15 else (YELLOW if y <= 30 else (BLUE if y <= 50 else RED)) for y in years_list]
    fig.add_trace(go.Bar(x=[f"{r}%" for r in rates], y=years_list, marker_color=bar_colors,
                        text=[f"{y}yr" for y in years_list], textposition="outside",
                        textfont=dict(family="JetBrains Mono", size=10)))
    # Mark current savings rate
    fig.update_layout(**default_layout(), height=350, xaxis_title="Savings Rate",
                     yaxis_title="Years to FIRE", xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)

    # What-if scenarios
    st.markdown("### What-If Scenarios")
    scenarios_data = []
    for label, extra_savings in [("Current", 0), ("+$500/mo", 6000), ("+$1,000/mo", 12000), ("+$2,000/mo", 24000)]:
        adj_savings = annual_savings + extra_savings
        p = fire_portfolio
        yrs = 0
        for y in range(1, 101):
            p = p * (1 + real_return / 100) + adj_savings
            fi_target = fire_number * (1 + fire_inflation / 100) ** y
            if p >= fi_target:
                yrs = y
                break
        scenarios_data.append({"Scenario": label, "Annual Savings": fmt(adj_savings),
                               "Years to FIRE": f"{yrs if yrs > 0 else '100+'}",
                               "FIRE Age": f"~{24 + yrs}" if yrs > 0 else "N/A"})

    st.dataframe(pd.DataFrame(scenarios_data), use_container_width=True, hide_index=True)

    st.markdown(f'''<div class="card" style="border-left:3px solid {YELLOW};">
        <p style="font-weight:600; margin:0;">Key Insight</p>
        <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.9rem;">
            Your savings rate matters more than your return rate. Going from 20% to 40% savings
            cuts your working years nearly in half. Every dollar of expenses you cut permanently
            reduces your FIRE number <em>and</em> increases your savings rate — a double win.
        </p>
    </div>''', unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: TAX ESTIMATOR
# ══════════════════════════════════════════════

def page_tax():
    st.markdown("# Tax Estimator")
    st.caption("Estimate your federal and state tax liability, compare deduction strategies, and optimize 401(k) contributions.")

    th_local = compute_take_home(data["income"])
    gross = th_local["annual_gross"]
    filing = th_local["filing"]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Federal Tax", fmt(th_local["fed_tax"]))
    with c2:
        st.metric("State Tax", fmt(th_local["state_tax"]), help=f"State: {data['income']['state']}")
    with c3:
        st.metric("FICA", fmt(th_local["fica"]),
                  help=f"Social Security (6.2% up to ${FICA_SS_CAP:,}) + Medicare (1.45%). "
                       f"Additional 0.9% Medicare surtax on income over $200K.")
    with c4:
        st.metric("Total Tax", fmt(th_local["total_tax"]))

    st.markdown("")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Tax Rates")
        st.markdown(f'''<div class="card">
            <div style="display:flex; justify-content:space-between; margin-bottom:1rem;">
                <div>
                    <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">Effective Tax Rate</p>
                    <p class="mono" style="font-size:1.5rem; margin:0; color:{YELLOW};">{th_local['effective_rate']:.1f}%</p>
                    <p style="color:{TEXT_DIM}; margin:0; font-size:0.75rem;">Total tax / gross income — what you actually pay overall.</p>
                </div>
                <div>
                    <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">Marginal Federal Rate</p>
                    <p class="mono" style="font-size:1.5rem; margin:0; color:{RED};">{th_local['marginal_fed']:.0f}%</p>
                    <p style="color:{TEXT_DIM}; margin:0; font-size:0.75rem;">Tax on your next dollar earned. Affects 401(k) savings.</p>
                </div>
            </div>
        </div>''', unsafe_allow_html=True)

    with c2:
        st.markdown("### Deduction Breakdown")
        st.markdown(f'''<div class="card">
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Filing Status:</span> <span class="mono">{filing}</span></p>
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">AGI:</span> <span class="mono">{fmt(th_local['agi'])}</span></p>
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Standard Deduction:</span> <span class="mono">-{fmt(th_local['std_ded'])}</span></p>
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Taxable Income:</span> <span class="mono" style="font-weight:600;">{fmt(th_local['taxable'])}</span></p>
        </div>''', unsafe_allow_html=True)

    # Standard vs Itemized comparison
    st.markdown("### Standard vs. Itemized Deduction")
    st.caption("Enter your potential itemized deductions to see which option saves you more.")

    if "itemized" not in data:
        data["itemized"] = {"salt": 0, "mortgage_interest": 0, "charitable": 0, "medical": 0}

    c1, c2 = st.columns(2)
    with c1:
        data["itemized"]["salt"] = st.number_input("State & Local Taxes (SALT)", value=data["itemized"]["salt"],
            min_value=0, step=100, format="%d",
            help=f"Capped at ${SALT_CAP:,} for federal purposes (state + property taxes)")
        data["itemized"]["mortgage_interest"] = st.number_input("Mortgage Interest", value=data["itemized"]["mortgage_interest"],
            min_value=0, step=100, format="%d")
    with c2:
        data["itemized"]["charitable"] = st.number_input("Charitable Donations", value=data["itemized"]["charitable"],
            min_value=0, step=100, format="%d")
        data["itemized"]["medical"] = st.number_input("Medical (above 7.5% AGI)", value=data["itemized"]["medical"],
            min_value=0, step=100, format="%d",
            help="Only the amount exceeding 7.5% of AGI is deductible")

    salt_capped = min(data["itemized"]["salt"], SALT_CAP)
    medical_threshold = max(0, th_local["agi"]) * 0.075
    medical_deductible = max(0, data["itemized"]["medical"] - medical_threshold) if th_local["agi"] > 0 else 0
    total_itemized = salt_capped + data["itemized"]["mortgage_interest"] + data["itemized"]["charitable"] + medical_deductible
    standard = th_local["std_ded"]

    better = "Standard" if standard >= total_itemized else "Itemized"
    diff = abs(standard - total_itemized)

    c1, c2 = st.columns(2)
    with c1:
        border = f"border-left:3px solid {GREEN}" if better == "Standard" else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Standard Deduction</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(standard)}</p>
            {"<p style='color:" + GREEN + "; margin:0; font-size:0.85rem;'>&#9989; Better option</p>" if better == "Standard" else ""}
        </div>''', unsafe_allow_html=True)
    with c2:
        border = f"border-left:3px solid {GREEN}" if better == "Itemized" else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Itemized Deductions</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(total_itemized)}</p>
            <p style="color:{TEXT_DIM}; font-size:0.8rem; margin:0;">SALT (capped): {fmt(salt_capped)} · Mortgage: {fmt(data["itemized"]["mortgage_interest"])} · Charity: {fmt(data["itemized"]["charitable"])} · Medical: {fmt(medical_deductible)}</p>
            {"<p style='color:" + GREEN + "; margin:0; font-size:0.85rem;'>&#9989; Better option</p>" if better == "Itemized" else ""}
        </div>''', unsafe_allow_html=True)

    if better == "Itemized":
        marginal_combined = th_local["marginal_fed"] / 100
        tax_savings = diff * marginal_combined
        st.success(f"Itemizing saves you **{fmt(diff)}** in deductions, worth approximately **{fmt(tax_savings)}** in tax savings at your {th_local['marginal_fed']:.0f}% marginal rate.")

    # Tax brackets
    st.markdown(f"### Federal Tax Brackets ({filing}, 2026)")
    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])
    bracket_data = []
    prev = 0
    for ceiling, rate in brackets:
        label = f"${prev:,}+" if ceiling == float("inf") else f"${prev:,}–${ceiling:,}"
        bracket_data.append({"Range": label, "Rate": f"{rate*100:.0f}%", "rate_num": rate * 100})
        prev = ceiling

    df_brackets = pd.DataFrame(bracket_data)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_brackets["Range"], y=df_brackets["rate_num"],
        marker_color=[GREEN if r <= 12 else (BLUE if r <= 24 else (YELLOW if r <= 32 else RED))
                      for r in df_brackets["rate_num"]],
        text=df_brackets["Rate"], textposition="inside",
        textfont=dict(family="JetBrains Mono", size=12, color="white"),
    ))
    fig.update_layout(**default_layout(), height=300, yaxis_title="Tax Rate (%)",
                     xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 401(k) tax savings
    st.markdown("### 401(k) Tax Savings Impact")
    contrib = th_local["contrib_401k"]
    marginal = th_local["marginal_fed"] / 100
    state_d = STATE_TAX_DATA.get(data["income"]["state"])
    state_marginal = 0
    if state_d and state_d.get("brackets"):
        state_marginal = state_d["brackets"][-1][1] if th_local["taxable"] > 0 else 0

    tax_saved = contrib * (marginal + state_marginal)

    st.markdown(f'''<div class="card" style="border-left:3px solid {GREEN};">
        <p style="font-weight:600; margin:0;">Current 401(k): {fmt(contrib)}/year ({data['income']['contribution_401k']}% of salary)</p>
        <p style="color:{GREEN}; font-size:1.3rem; margin:0.25rem 0;" class="mono">Saves you {fmt(tax_saved)} in taxes</p>
        <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">At your {marginal*100:.0f}% federal + {state_marginal*100:.1f}% state marginal rate</p>
    </div>''', unsafe_allow_html=True)

    scenarios = [0, 3, 6, 10, 15, 20]
    savings_data = []
    for pct in scenarios:
        c = min(data["income"]["gross_salary"] * pct / 100, 24500)
        s = c * (marginal + state_marginal)
        savings_data.append({"Contribution %": f"{pct}%", "Annual ($)": fmt(c), "Tax Savings": fmt(s)})
    st.dataframe(pd.DataFrame(savings_data), use_container_width=True, hide_index=True)

    render_footer()


# ══════════════════════════════════════════════
# PAGE: DATA MANAGEMENT
# ══════════════════════════════════════════════

REQUIRED_KEYS = {"income", "budget", "expenses", "assets", "liabilities", "debts", "savings_goals", "investment"}

def page_data():
    st.markdown("# Data Management")
    st.caption("Export your data as a backup, import a previous save, or reset to start fresh.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Export")
        json_str = json.dumps(data, indent=2, default=str)
        st.download_button("📥 Export All Data (JSON)", data=json_str,
            file_name=f"budget_backup_{date.today().isoformat()}.json",
            mime="application/json", use_container_width=True)

        if data["expenses"]:
            df = pd.DataFrame(data["expenses"])
            csv = df.to_csv(index=False)
            st.download_button("📥 Export Expenses (CSV)", data=csv,
                file_name=f"expenses_{date.today().isoformat()}.csv",
                mime="text/csv", use_container_width=True)
        else:
            st.info("No expenses to export.")

    with c2:
        st.markdown("### Import")
        uploaded = st.file_uploader("Upload JSON Backup", type=["json"])
        if uploaded:
            try:
                imported = json.load(uploaded)
                missing = REQUIRED_KEYS - set(imported.keys())
                if missing:
                    st.error(f"Invalid backup — missing keys: {', '.join(missing)}")
                elif not isinstance(imported.get("expenses"), list):
                    st.error("Invalid format: 'expenses' should be a list.")
                elif not isinstance(imported.get("budget"), dict):
                    st.error("Invalid format: 'budget' should be a dict.")
                else:
                    _ensure_expense_ids(imported.get("expenses", []))
                    if "filing_status" not in imported.get("income", {}):
                        imported["income"]["filing_status"] = "Single"
                    if "recurring_templates" not in imported:
                        imported["recurring_templates"] = []
                    if "itemized" not in imported:
                        imported["itemized"] = {"salt": 0, "mortgage_interest": 0, "charitable": 0, "medical": 0}

                    st.success(f"Valid backup: {len(imported['expenses'])} expenses, {len(imported['savings_goals'])} goals")
                    if st.button("📤 Load Imported Data", type="primary"):
                        st.session_state.data = imported
                        st.success("Data imported successfully!")
                        st.rerun()
            except json.JSONDecodeError:
                st.error("Invalid JSON file.")

    st.divider()
    st.markdown("### Reset Data")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔄 Load Demo Data", use_container_width=True):
            st.session_state.data = deepcopy(DEMO_DATA)
            st.success("Demo data loaded!")
            st.rerun()
    with c2:
        if st.button("🗑️ Reset All Data", use_container_width=True, type="secondary"):
            st.session_state.confirm_reset = True

        if st.session_state.get("confirm_reset"):
            st.warning("Are you sure? This will erase all your data.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Reset Everything", type="primary"):
                    st.session_state.data = get_default_state()
                    st.session_state.confirm_reset = False
                    st.rerun()
            with c2:
                if st.button("Cancel"):
                    st.session_state.confirm_reset = False
                    st.rerun()

    st.divider()
    st.markdown("### Data Summary")
    st.markdown(f'''<div class="card">
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Expenses logged:</span> <span class="mono">{len(data['expenses'])}</span></p>
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Net worth snapshots:</span> <span class="mono">{len(data['net_worth_snapshots'])}</span></p>
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Debts tracked:</span> <span class="mono">{len(data['debts'])}</span></p>
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Savings goals:</span> <span class="mono">{len(data['savings_goals'])}</span></p>
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Budget categories:</span> <span class="mono">{sum(len(v) for v in data['budget'].values())}</span></p>
        <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Recurring templates:</span> <span class="mono">{len(data.get('recurring_templates', []))}</span></p>
    </div>''', unsafe_allow_html=True)

    render_footer()


# ══════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════

PAGES = {
    "Dashboard": page_dashboard,
    "Income Setup": page_income,
    "Budget Builder": page_budget,
    "Expense Tracker": page_expenses,
    "Net Worth": page_net_worth,
    "Debt Payoff": page_debt,
    "Savings Goals": page_savings_goals,
    "Investments": page_investments,
    "FIRE Calculator": page_fire,
    "Tax Estimator": page_tax,
    "Data Management": page_data,
}

PAGES[page]()
