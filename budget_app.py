import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import uuid
import math
import time
from datetime import datetime, date, timedelta
from copy import deepcopy
from supabase import create_client

# The maths lives in calculations.py — stdlib only, so tests and any future
# backend import the same code this app runs. See that module's docstring.
from calculations import (
    COL_INDEX,
    FEDERAL_BRACKETS_2026,
    FILING_STATUSES,
    STANDARD_DEDUCTION_2026,
    STATE_TAX_DATA,
    FICA_SS_RATE,
    FICA_SS_CAP,
    FICA_MEDICARE_RATE,
    FICA_MEDICARE_SURTAX,
    FICA_MEDICARE_SURTAX_THRESHOLDS,
    SALT_CAP_BASE,
    SALT_CAP_FLOOR,
    SALT_PHASEOUT_THRESHOLD,
    SALT_PHASEOUT_RATE,
    calc_salt_cap,
    calc_bracket_tax,
    calc_social_security,
    calc_student_loan_deduction,
    calc_federal_tax,
    calc_itemized_total,
    _get_state_brackets_for_filing,
    calc_state_marginal_rate,
    emergency_fund_months,
    monthly_debt_service,
    calc_state_tax,
    calc_fica,
    get_marginal_rate,
    marginal_fica_rate,
    project_investment,
    payoff_order,
    simulate_payoff,
)

# ──────────────────────────────────────────────
# PAGE CONFIG & THEME
# ──────────────────────────────────────────────

st.set_page_config(
    page_title="Budget Tracker — Mason Bennett",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# SUPABASE CLIENT
# ──────────────────────────────────────────────
#
# Two rules here, both learned the hard way, both fail silently when broken.
#
# 1. This must NEVER raise at import time. It used to read st.secrets directly at
#    module scope, so a missing or mistyped secret took every page down at once —
#    and with showErrorDetails=false in config.toml the visitor got a bare error
#    screen with no cause. The app needs no database to work: budgeting, tax, FIRE
#    and the JSON export are all local. Cloud sync is the only thing that should
#    fail when the backend is unreachable.
#
# 2. The anon client below is @st.cache_resource, which means ONE object shared by
#    every visitor of the deployed app. Calling postgrest.auth() on it would put
#    one user's JWT on another user's request. Authenticated database work goes
#    through _db(), which builds a client owned by a single session.

@st.cache_resource
def _init_supabase():
    """The anon client. Used only for sign-up / sign-in, which carry no user JWT.

    Returns None rather than raising: a missing secret must degrade to local-only,
    never take the app down. create_client makes no network call, so a client
    coming back from here is not evidence that the backend is reachable.
    """
    try:
        cfg = st.secrets["supabase"]
        url, key = cfg["url"], cfg["key"]
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception:
        return None


supabase = _init_supabase()


def cloud_configured() -> bool:
    """Whether the app has credentials at all. Says nothing about reachability."""
    return supabase is not None


def _is_unreachable(exc: Exception) -> bool:
    """Tell 'the service is down' apart from 'those credentials were wrong'.

    This distinction is the whole point of the rewrite. The project this app
    shipped against was deleted, and because auth_sign_in caught every exception
    and returned one message, every visitor was told their PASSWORD was wrong.
    People retype it, reset it, and give up, while the real cause is that there is
    no server. A wrong password and a dead host must never read the same.
    """
    name = type(exc).__name__.lower()
    text = str(exc).lower()
    signals = ("connect", "timeout", "resolve", "getaddrinfo", "network",
               "unreachable", "temporarily", "ssl", "dns")
    return any(s in name for s in signals) or any(s in text for s in signals)


def _store_session(user, session):
    """The single place that writes auth state, so the two tokens can't drift."""
    st.session_state["user"] = {"id": user.id, "email": user.email}
    st.session_state["access_token"] = session.access_token
    st.session_state["refresh_token"] = getattr(session, "refresh_token", None)


def _db():
    """A client bound to THIS session's signed-in user, or None.

    Deliberately not cached across sessions. postgrest.auth() mutates the client,
    so a shared client would carry whichever token was attached last — under two
    concurrent users that is one person's data returned to another. Building a
    client is object construction with no network call, so a per-session one is
    cheap; it lives in session_state and is rebuilt only when the token changes.
    """
    if supabase is None:
        return None
    token = st.session_state.get("access_token")
    if not token:
        return None
    if st.session_state.get("_db_token") != token:
        try:
            cfg = st.secrets["supabase"]
            client = create_client(cfg["url"], cfg["key"])
            client.postgrest.auth(token)
        except Exception:
            return None
        st.session_state["_db_client"] = client
        st.session_state["_db_token"] = token
    return st.session_state.get("_db_client")


def _refresh_session() -> bool:
    """Trade the refresh token for a new access token. False if it can't be done.

    Access tokens expire after an hour by default, which is well inside a session
    someone leaves open on a budgeting app. Without this, a save an hour in fails
    with a 401 that looks exactly like a permissions problem.
    """
    refresh = st.session_state.get("refresh_token")
    if supabase is None or not refresh:
        return False
    try:
        res = supabase.auth.refresh_session(refresh)
        if res and res.session:
            _store_session(res.user, res.session)
            return True
    except Exception:
        pass
    return False


# ──────────────────────────────────────────────
# AUTHENTICATION
# ──────────────────────────────────────────────

SERVICE_DOWN = ("Can't reach the account service right now. Your data is safe in this "
                "browser — use Download Backup to keep a copy.")


def auth_sign_up(email: str, password: str) -> dict:
    if supabase is None:
        return {"success": False, "error": SERVICE_DOWN}
    try:
        response = supabase.auth.sign_up({"email": email, "password": password})
        if response.user and response.session:
            _store_session(response.user, response.session)
            return {"success": True}
        if response.user:
            # Supabase returns a user with no session when email confirmation is on.
            return {"success": False, "error": "Check your email to confirm the account, then log in."}
        return {"success": False, "error": "Sign up failed — try a different email."}
    except Exception as e:
        if _is_unreachable(e):
            return {"success": False, "error": SERVICE_DOWN}
        msg = str(e)
        if "already registered" in msg.lower() or "already been registered" in msg.lower():
            return {"success": False, "error": "An account with this email already exists."}
        return {"success": False, "error": msg}


def auth_sign_in(email: str, password: str) -> dict:
    if supabase is None:
        return {"success": False, "error": SERVICE_DOWN}
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user and response.session:
            _store_session(response.user, response.session)
            return {"success": True}
        return {"success": False, "error": "Invalid email or password."}
    except Exception as e:
        # Only claim the credentials were wrong when the server actually said so.
        if _is_unreachable(e):
            return {"success": False, "error": SERVICE_DOWN}
        return {"success": False, "error": "Invalid email or password."}


def auth_sign_out():
    if supabase is not None:
        try:
            supabase.auth.sign_out()
        except Exception:
            pass
    for key in ["user", "access_token", "refresh_token", "_db_client", "_db_token",
                "_last_cloud_save", "_cloud_error"]:
        st.session_state.pop(key, None)


def is_logged_in() -> bool:
    return "user" in st.session_state and st.session_state["user"] is not None


def get_user_id():
    return st.session_state["user"]["id"] if is_logged_in() else None


# ──────────────────────────────────────────────
# CLOUD SAVE / LOAD
# ──────────────────────────────────────────────

def _expired(exc: Exception) -> bool:
    """Whether a PostgREST failure is an expired JWT rather than a real denial."""
    text = str(exc).lower()
    return "jwt" in text and ("expired" in text or "invalid" in text)


def cloud_save(save_data: dict) -> tuple[bool, str]:
    """Write this user's blob. Returns (ok, message) — the caller decides how loud to be.

    Goes through _db(), so the request carries the user's own JWT and row-level
    security applies. The previous version used the shared anon client, which meant
    every write ran as the public key: with RLS on it would have failed for everyone,
    and with RLS off any visitor could read or overwrite any other user's row.
    """
    user_id = get_user_id()
    if not user_id:
        return False, "Not signed in."
    for attempt in (1, 2):
        db = _db()
        if db is None:
            return False, SERVICE_DOWN
        try:
            payload = json.loads(json.dumps(save_data, default=str))
            response = (
                db.table("user_data")
                .upsert({"user_id": user_id, "app_data": payload}, on_conflict="user_id")
                .execute()
            )
            return (len(response.data) > 0), ""
        except Exception as e:
            if attempt == 1 and _expired(e) and _refresh_session():
                continue  # new token, one retry
            if _is_unreachable(e):
                return False, SERVICE_DOWN
            return False, f"Save failed: {e}"
    return False, "Save failed."


def cloud_load():
    user_id = get_user_id()
    if not user_id:
        return None
    for attempt in (1, 2):
        db = _db()
        if db is None:
            return None
        try:
            response = (
                db.table("user_data")
                .select("app_data")
                .eq("user_id", user_id)
                .maybe_single()
                .execute()
            )
            return response.data["app_data"] if response and response.data else None
        except Exception as e:
            if attempt == 1 and _expired(e) and _refresh_session():
                continue
            return None
    return None


def _migrate_imported(imported):
    """Apply schema migrations to loaded data (handles old saves)."""
    _ensure_expense_ids(imported.get("expenses", []))
    inc = imported.get("income", {})
    if "filing_status" not in inc:
        inc["filing_status"] = "Single"
    if "student_loan_interest" not in inc:
        inc["student_loan_interest"] = 0
    if "recurring_templates" not in imported:
        imported["recurring_templates"] = []
    if "itemized" not in imported:
        imported["itemized"] = {"salt": 0, "mortgage_interest": 0, "charitable": 0, "medical": 0}
    return imported


def auto_save_debounced(save_data: dict, interval: float = 10.0):
    """Background save. Runs on every page render, so it must stay quiet.

    A failure here is recorded, not shouted: the old version let cloud_save call
    st.error() directly, which put a red banner on the page for something the user
    did not ask for and could not act on. The sidebar reads _cloud_error and shows
    one line instead, so the state is visible without the app crying wolf.
    """
    if not is_logged_in():
        return
    now = time.time()
    last = st.session_state.get("_last_cloud_save", 0)
    if now - last < interval:
        return
    ok, msg = cloud_save(save_data)
    if ok:
        st.session_state["_last_cloud_save"] = now
        st.session_state.pop("_cloud_error", None)
    else:
        # Back off so an unreachable service isn't retried on every rerun.
        st.session_state["_last_cloud_save"] = now
        st.session_state["_cloud_error"] = msg


# Color palette — light theme (matches portfolio app)
GREEN = "#2ECC71"
RED = "#E74C3C"
BLUE = "#2E86AB"
YELLOW = "#F18F01"
PURPLE = "#9B59B6"
BG_DARK = "#FFFFFF"
BG_CARD = "#FFFFFF"
BG_SURFACE = "#F1F5F9"
TEXT = "#1B2A4A"
TEXT_DIM = "#6C7A96"

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* ── Base ── */
:root {
    --primary: #1B2A4A; --accent: #2E86AB; --green: #2ECC71; --red: #E74C3C;
    --yellow: #F18F01; --text: #1B2A4A; --text-dim: #6C7A96;
    --bg: #FFFFFF; --surface: #F8F9FC; --card: #FFFFFF;
    --border: #E2E8F0; --radius: 0.75rem;
    --ease: cubic-bezier(0.4, 0, 0.2, 1);
}
html, body, [class*="css"] { font-family: 'Inter', -apple-system, sans-serif; }
.block-container { padding-top: 1rem; max-width: 1200px; }

/* ── Typography ── */
h1 { font-family: 'Space Grotesk', sans-serif; font-weight: 700; letter-spacing: -0.02em; color: var(--primary); }
h2, h3 { font-family: 'Space Grotesk', sans-serif; font-weight: 600; color: var(--primary); }
.mono { font-family: 'Inter', monospace; }

/* ── Cards ── */
.card {
    background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
    padding: 1.5rem; margin-bottom: 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: border-color 0.3s var(--ease), box-shadow 0.3s var(--ease);
}
.card:hover { border-color: var(--accent); box-shadow: 0 4px 12px rgba(0,0,0,0.08); }

/* ── Section divider ── */
.section-divider {
    height: 3px; background: linear-gradient(90deg, #2E86AB, #F18F01);
    border: none; border-radius: 2px; margin: 0.25rem 0 1rem 0; opacity: 0.7;
}

/* ── Badges ── */
.badge {
    display:inline-block; padding:0.2rem 0.6rem; border-radius:1rem;
    font-size:0.8rem; font-weight:600; font-family:'Inter',monospace;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B2A4A 0%, #243B63 100%);
}
section[data-testid="stSidebar"] * { color: #E2E8F0; }
section[data-testid="stSidebar"] button {
    transition: all 0.25s var(--ease); border-radius: 0.5rem; margin-bottom: 2px;
}
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.1);
    color: #CBD5E1;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: rgba(255,255,255,0.12); border-color: rgba(255,255,255,0.25);
    color: #FFFFFF;
}
section[data-testid="stSidebar"] button[kind="primary"] {
    background: rgba(46,134,171,0.3); border: 1px solid rgba(46,134,171,0.5);
    color: #7DD3FC; font-weight: 600;
}
section[data-testid="stSidebar"] div[data-testid="stFileUploaderDropzone"] span,
section[data-testid="stSidebar"] div[data-testid="stFileUploaderDropzone"] small,
section[data-testid="stSidebar"] div[data-testid="stFileUploaderDropzone"] button span,
section[data-testid="stSidebar"] div[data-testid="stFileUploaderDropzone"] p {
    color: #000000 !important;
}

/* ── Metrics ── */
div[data-testid="stMetric"] {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    padding: 1.25rem; transition: all 0.3s var(--ease);
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
div[data-testid="stMetric"]:hover {
    border-color: var(--accent); transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}
div[data-testid="stMetricValue"] {
    font-family: 'Inter', monospace; font-weight: 700;
    font-size: 1.25rem; color: var(--primary);
}
div[data-testid="stMetricDelta"] { font-family: 'Inter', monospace; font-size: 0.78rem; }
div[data-testid="stMetricLabel"] p {
    text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.78rem;
    color: var(--text-dim); font-weight: 500;
}

/* ── Inputs ── */
div[data-testid="stNumberInput"] input,
div[data-testid="stTextInput"] input {
    font-family: 'Inter', -apple-system, sans-serif; border-radius: 8px;
    transition: border-color 0.2s var(--ease), box-shadow 0.2s var(--ease);
}
input:focus, div[data-baseweb="input"]:focus-within {
    border-color: var(--accent); box-shadow: 0 0 0 3px rgba(46,134,171,0.15);
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0; background: var(--surface); border-radius: 12px; padding: 4px;
}
.stTabs [data-baseweb="tab"] {
    background: transparent; border-radius: 8px;
    padding: 0.5rem 1rem; color: var(--text-dim); font-weight: 500;
    transition: all 0.2s var(--ease);
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: var(--card); color: var(--primary); font-weight: 600;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] { display: none; }

/* ── Expanders ── */
div[data-testid="stExpander"] {
    background: var(--card); border: 1px solid var(--border); border-radius: 10px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04); transition: border-color 0.25s var(--ease);
}
div[data-testid="stExpander"]:hover { border-color: var(--accent); }

/* ── Dividers ── */
hr { border: none; border-top: 1px solid var(--border); margin: 1.5rem 0; }

/* ── Dataframes ── */
div[data-testid="stDataFrame"] {
    border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
}

/* ── Charts ── */
div[data-testid="stPlotlyChart"] {
    background: var(--card); border: 1px solid var(--border); border-radius: 12px;
    padding: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

/* ── Buttons ── */
button[kind="primary"] { transition: all 0.25s var(--ease); }
button[kind="primary"]:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(46,134,171,0.25); }
button[kind="secondary"] { transition: all 0.25s var(--ease); }
button[kind="secondary"]:hover { border-color: var(--accent); color: var(--accent); }

/* ── Alerts ── */
div[data-testid="stAlert"] { border-radius: 10px; }

/* ── Hide default footer ── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }

/* ── Mobile ── */
@media (max-width: 768px) {
    .block-container { padding: 0.75rem; }
    div[data-testid="stMetric"] { padding: 0.75rem; }
    div[data-testid="stMetricValue"] { font-size: 1.1rem; }
    .card { padding: 1rem; }
}
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────
# ──────────────────────────────────────────────
# REUSABLE HELPERS
# ──────────────────────────────────────────────

def default_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=TEXT, size=12),
        margin=dict(l=50, r=50, t=50, b=60),
        legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.15,
                    font=dict(size=11, color=TEXT)),
        xaxis=dict(gridcolor="rgba(226,232,240,0.6)", linecolor="#E2E8F0", linewidth=1,
                   title_font=dict(size=12, color=TEXT_DIM), tickfont=dict(size=11, color=TEXT_DIM)),
        yaxis=dict(gridcolor="rgba(226,232,240,0.6)", linecolor="#E2E8F0", linewidth=1,
                   title_font=dict(size=12, color=TEXT_DIM), tickfont=dict(size=11, color=TEXT_DIM)),
        hovermode="x unified",
        hoverlabel=dict(bgcolor="#FFFFFF", font_size=12, font_color=TEXT, bordercolor="#E2E8F0"),
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


def render_footer():
    st.markdown(f"""
    <div style="text-align:center; padding:2rem 0 1rem; margin-top:3rem; border-top:1px solid #E2E8F0;">
        <p style="color:{TEXT_DIM}; font-size:0.8rem; margin:0;">
            <a href="https://masonjbennett.com" target="_blank" style="color:{BLUE}; text-decoration:none; font-weight:500;">Mason Bennett</a>
            &nbsp;&middot;&nbsp; Streamlit + Plotly &nbsp;&middot;&nbsp;
            <a href="https://github.com/masonjbennett/budgeting-app" target="_blank" style="color:{TEXT_DIM}; text-decoration:none;">GitHub</a>
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
            "student_loan_interest": 0,
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


def _generate_demo_data():
    """Generate demo data with dates relative to today so it's always fresh."""
    today = date.today()
    cur_month_1st = today.replace(day=1)
    prev_month_1st = (cur_month_1st - timedelta(days=1)).replace(day=1)
    def _d(day_offset):
        return (today - timedelta(days=day_offset)).isoformat()
    def _month_start(months_ago):
        d = cur_month_1st
        for _ in range(months_ago):
            d = (d - timedelta(days=1)).replace(day=1)
        return d.isoformat()

    return {
    "income": {
        "gross_salary": 95000,
        "state": "New York",
        "filing_status": "Single",
        "contribution_401k": 6,
        "health_insurance": 180,
        "hsa": 100,
        "bonus_amount": 10000,
        "bonus_type": "Annual (spread monthly)",
        "student_loan_interest": 0,
    },
    "budget": {
        "needs": {
            "Rent": 1900, "Utilities": 130, "Groceries": 380,
            "Transportation": 127, "Insurance": 90,
            "Min. Debt Payments": 485, "Phone": 75,
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
        # Current month expenses
        {"id": "demo-01", "date": cur_month_1st.isoformat(), "amount": 1900, "category": "Rent", "note": "Monthly rent"},
        {"id": "demo-02", "date": _d(max(today.day - 2, 0)), "amount": 52.30, "category": "Groceries", "note": "Trader Joe's"},
        {"id": "demo-03", "date": _d(max(today.day - 3, 0)), "amount": 45.00, "category": "Dining Out", "note": "Dinner with friends"},
        {"id": "demo-04", "date": _d(max(today.day - 4, 0)), "amount": 127.00, "category": "Transportation", "note": "Monthly metro pass"},
        {"id": "demo-05", "date": _d(max(today.day - 5, 0)), "amount": 15.99, "category": "Subscriptions", "note": "Spotify + iCloud"},
        {"id": "demo-06", "date": _d(max(today.day - 6, 0)), "amount": 68.40, "category": "Groceries", "note": "Whole Foods"},
        {"id": "demo-07", "date": _d(max(today.day - 7, 0)), "amount": 22.00, "category": "Entertainment", "note": "Movie tickets"},
        {"id": "demo-08", "date": _d(max(today.day - 8, 0)), "amount": 130.00, "category": "Utilities", "note": "Electric + Internet"},
        {"id": "demo-09", "date": _d(max(today.day - 9, 0)), "amount": 89.99, "category": "Shopping", "note": "Running shoes"},
        {"id": "demo-10", "date": _d(max(today.day - 10, 0)), "amount": 35.50, "category": "Dining Out", "note": "Lunch meeting"},
        {"id": "demo-11", "date": _d(max(today.day - 11, 0)), "amount": 75.00, "category": "Phone", "note": "Monthly bill"},
        {"id": "demo-12", "date": _d(max(today.day - 12, 0)), "amount": 45.00, "category": "Gym", "note": "Monthly membership"},
        {"id": "demo-21", "date": _d(max(today.day - 13, 0)), "amount": 485.00, "category": "Min. Debt Payments", "note": "Card + car + student loan minimums"},
        # Previous month expenses
        {"id": "demo-13", "date": prev_month_1st.isoformat(), "amount": 1900, "category": "Rent", "note": "Monthly rent"},
        {"id": "demo-14", "date": (prev_month_1st + timedelta(days=4)).isoformat(), "amount": 95.20, "category": "Groceries", "note": "Weekly groceries"},
        {"id": "demo-15", "date": (prev_month_1st + timedelta(days=9)).isoformat(), "amount": 127.00, "category": "Transportation", "note": "Metro pass"},
        {"id": "demo-16", "date": (prev_month_1st + timedelta(days=11)).isoformat(), "amount": 62.00, "category": "Dining Out", "note": "Brunch"},
        {"id": "demo-17", "date": (prev_month_1st + timedelta(days=14)).isoformat(), "amount": 130.00, "category": "Utilities", "note": "Electric + Internet"},
        {"id": "demo-18", "date": (prev_month_1st + timedelta(days=19)).isoformat(), "amount": 45.00, "category": "Gym", "note": "Monthly membership"},
        {"id": "demo-19", "date": (prev_month_1st + timedelta(days=21)).isoformat(), "amount": 210.00, "category": "Shopping", "note": "New jacket"},
        {"id": "demo-20", "date": (prev_month_1st + timedelta(days=27)).isoformat(), "amount": 75.00, "category": "Phone", "note": "Monthly bill"},
        {"id": "demo-22", "date": (prev_month_1st + timedelta(days=13)).isoformat(), "amount": 485.00, "category": "Min. Debt Payments", "note": "Card + car + student loan minimums"},
    ],
    "recurring_templates": [
        {"name": "Rent", "amount": 1900, "category": "Rent", "day": 1},
        {"name": "Metro Pass", "amount": 127, "category": "Transportation", "day": 4},
        {"name": "Gym Membership", "amount": 45, "category": "Gym", "day": 12},
        {"name": "Phone Bill", "amount": 75, "category": "Phone", "day": 11},
    ],
    "net_worth_snapshots": [
        {"date": _month_start(3), "assets": 17500, "liabilities": 19900, "net_worth": -2400},
        {"date": _month_start(2), "assets": 19200, "liabilities": 19300, "net_worth": -100},
        {"date": _month_start(1), "assets": 21800, "liabilities": 18700, "net_worth": 3100},
        {"date": cur_month_1st.isoformat(), "assets": 23500, "liabilities": 18100, "net_worth": 5400},
    ],
    "assets": {
        "Checking": 6200, "Savings": 9500, "401(k)": 4800,
        "Roth IRA": 2500, "Brokerage": 1800, "Property": 0,
    },
    # Liabilities used to be all zero while the debt list carried $35,000, so demo
    # net worth ignored the debt entirely and the trend chart was an assets-only line.
    "liabilities": {
        "Student Loans": 11300, "Car Loan": 2600, "Credit Cards": 4200,
    },
    # Rate order and balance order deliberately disagree: avalanche opens on the
    # credit card (22.9%), snowball on the car loan (smallest balance). With ONE
    # debt — which is what this shipped with — the two strategies are identical by
    # definition, so the page's whole reason for existing rendered as two matching
    # bars for anyone opening the live demo.
    "debts": [
        {"name": "Credit Card", "balance": 4200, "rate": 22.9, "min_payment": 110},
        {"name": "Car Loan", "balance": 2600, "rate": 5.9, "min_payment": 240},
        {"name": "Student Loan", "balance": 11300, "rate": 6.8, "min_payment": 135},
    ],
    "savings_goals": [
        {"name": "Emergency Fund", "target": 15000, "current": 9500,
         "deadline": (today + timedelta(days=600)).isoformat(), "priority": 1},
        {"name": "Vacation Fund", "target": 3000, "current": 800,
         "deadline": (today + timedelta(days=250)).isoformat(), "priority": 2},
        {"name": "Down Payment", "target": 50000, "current": 1800,
         "deadline": (today + timedelta(days=1500)).isoformat(), "priority": 3},
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
        st.session_state.data = _generate_demo_data()
        _ensure_expense_ids(st.session_state.data["expenses"])
        st.session_state.is_demo = True
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
    sl_interest = d.get("student_loan_interest", 0)
    pretax = contrib_401k_annual + health_annual + hsa_annual

    try:
        itemized_input = data.get("itemized", {}) or {}
    except (NameError, AttributeError):
        itemized_input = {}
    charitable = itemized_input.get("charitable", 0)

    # The itemized total depends on AGI, and AGI does not depend on it, so run the
    # federal calculation once to get AGI, work out the itemized total against it,
    # then run it again with that total. Two passes rather than one because the
    # 0.5% charitable and 7.5% medical floors are both percentages OF AGI.
    _, agi_only, _, _ = calc_federal_tax(
        annual_gross, contrib_401k_annual, health_annual + hsa_annual, filing,
        sl_interest, charitable)
    itemized = calc_itemized_total(itemized_input, agi_only, filing)
    fed_tax, agi, taxable, deduction_taken = calc_federal_tax(
        annual_gross, contrib_401k_annual, health_annual + hsa_annual, filing,
        sl_interest, charitable, itemized["total"])
    state_tax = calc_state_tax(annual_gross, d["state"], contrib_401k_annual, health_annual + hsa_annual, filing)
    fica = calc_fica(annual_gross, filing)

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
        "std_ded": STANDARD_DEDUCTION_2026.get(filing, 15_700),
        "deduction_taken": deduction_taken,
        "itemized_total": itemized["total"],
        "itemizing": deduction_taken > STANDARD_DEDUCTION_2026.get(filing, 15_700),
        "effective_rate": (total_tax / annual_gross * 100) if annual_gross else 0,
        "marginal_fed": get_marginal_rate(taxable, brackets),
        # Read off the same base as state_tax above, not the state's top bracket.
        "marginal_state": calc_state_marginal_rate(
            annual_gross, d["state"], contrib_401k_annual, health_annual + hsa_annual, filing),
        "filing": filing,
    }




# ──────────────────────────────────────────────
# SIDEBAR NAVIGATION
# ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; margin-bottom:1.5rem; padding-bottom:1rem; border-bottom:1px solid rgba(255,255,255,0.08);">
        <p style="color:#7DD3FC; font-size:1.5rem; margin:0; font-family:'Space Grotesk',sans-serif; font-weight:700; letter-spacing:-0.02em;">Budget Tracker</p>
        <p style="color:#E2E8F0; font-size:0.82rem; margin:0.35rem 0 0.25rem; font-style:italic; opacity:0.85;">Track your money. Plan your future.</p>
        <p style="color:#94A3C0; font-size:0.72rem; margin:0;">
            by <a href="https://masonjbennett.com" target="_blank" style="color:#CBD5E1; text-decoration:none; font-weight:500;">Mason Bennett</a>
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
            st.markdown(f'<p style="color:#94A3C0; font-size:0.65rem; text-transform:uppercase; letter-spacing:0.12em; margin:1rem 0 0.4rem 0.25rem; padding-top:0.75rem; border-top:1px solid rgba(255,255,255,0.08); font-weight:600;">{group_label}</p>', unsafe_allow_html=True)
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

    # Auth + cloud save
    if is_logged_in():
        user_email = st.session_state["user"]["email"]
        sync_err = st.session_state.get("_cloud_error")
        dot, dot_label = ("#E74C3C", "sync paused") if sync_err else ("#2ECC71", "synced")
        st.sidebar.markdown(f'''<div style="padding:0.25rem 0 0.5rem;">
            <span style="color:{dot};">●</span>
            <span style="color:#CBD5E1; font-size:0.82rem;">{user_email}</span>
            <span style="color:#94A3C0; font-size:0.72rem;"> · {dot_label}</span>
        </div>''', unsafe_allow_html=True)
        if sync_err:
            st.sidebar.caption(sync_err)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.button("💾 Save", use_container_width=True, key="cloud_save_btn"):
                ok, msg = cloud_save(data)
                if ok:
                    st.session_state.pop("_cloud_error", None)
                    st.toast("Saved to cloud!", icon="✅")
                else:
                    st.session_state["_cloud_error"] = msg
                    st.sidebar.error(msg)
        with c2:
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
                auth_sign_out()
                st.rerun()
        # JSON backup download
        json_str = json.dumps(data, indent=2, default=str)
        st.sidebar.download_button("📥 Download Backup", data=json_str,
            file_name=f"budget_backup_{date.today().isoformat()}.json",
            mime="application/json", use_container_width=True)
    elif not cloud_configured():
        # No credentials at all. Offering a login form here would be a form that
        # cannot succeed — the app says so plainly instead, and the local save
        # below is the whole feature set that still works.
        st.sidebar.markdown(
            '<p style="color:#94A3C0; font-size:0.78rem; line-height:1.45; margin:0 0 0.5rem;">'
            'Accounts are unavailable on this deployment. Everything else works — '
            'use Save as JSON to keep your data.</p>',
            unsafe_allow_html=True,
        )
        json_str = json.dumps(data, indent=2, default=str)
        st.sidebar.download_button("💾 Save as JSON", data=json_str,
            file_name=f"budget_save_{date.today().isoformat()}.json",
            mime="application/json", use_container_width=True)
    else:
        auth_mode = st.sidebar.radio("Account", ["Login", "Sign Up"],
                                      horizontal=True, label_visibility="collapsed")
        if auth_mode == "Login":
            email = st.sidebar.text_input("Email", key="login_email")
            password = st.sidebar.text_input("Password", type="password", key="login_pw")
            if st.sidebar.button("Log In", type="primary", use_container_width=True):
                if email and password:
                    result = auth_sign_in(email, password)
                    if result["success"]:
                        saved = cloud_load()
                        if saved:
                            st.session_state.data = _migrate_imported(saved)
                            st.session_state.is_demo = False
                            st.toast("Data loaded from cloud!", icon="📂")
                        st.rerun()
                    else:
                        st.sidebar.error(result["error"])
                else:
                    st.sidebar.warning("Enter email and password")
        else:
            email = st.sidebar.text_input("Email", key="signup_email")
            pw = st.sidebar.text_input("Password", type="password", key="signup_pw")
            pw2 = st.sidebar.text_input("Confirm", type="password", key="signup_pw2")
            if st.sidebar.button("Create Account", type="primary", use_container_width=True):
                if not email or not pw:
                    st.sidebar.warning("Enter email and password")
                elif pw != pw2:
                    st.sidebar.error("Passwords don't match")
                elif len(pw) < 6:
                    st.sidebar.error("Password must be 6+ characters")
                else:
                    result = auth_sign_up(email, pw)
                    if result["success"]:
                        st.toast("Account created!", icon="🎉")
                        st.rerun()
                    else:
                        st.sidebar.error(result["error"])
        st.sidebar.caption("Create an account to save your data to the cloud.")
        # Still offer JSON save for anonymous users
        json_str = json.dumps(data, indent=2, default=str)
        st.sidebar.download_button("💾 Save as JSON", data=json_str,
            file_name=f"budget_save_{date.today().isoformat()}.json",
            mime="application/json", use_container_width=True)

    st.sidebar.markdown(
        '<p style="color:#94A3C0; font-size:0.75rem; text-align:center;">v4.0</p>',
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

    # Welcome banner for first-time users
    if st.session_state.get("is_demo"):
        st.markdown(f'''<div class="card" style="border-left:3px solid {BLUE}; padding:1.25rem;">
            <p style="font-weight:600; margin:0 0 0.5rem 0;">Welcome — you're viewing sample data</p>
            <p style="color:{TEXT_DIM}; margin:0 0 0.75rem; font-size:0.9rem;">Get started in 3 steps:</p>
            <p style="color:{TEXT_DIM}; margin:0 0 0.3rem; font-size:0.88rem;">
                <strong style="color:{BLUE};">1.</strong> <strong>Income Setup</strong> — enter your salary and deductions<br>
                <strong style="color:{BLUE};">2.</strong> <strong>Budget Builder</strong> — allocate your take-home pay<br>
                <strong style="color:{BLUE};">3.</strong> <strong>Expense Tracker</strong> — start logging what you spend
            </p>
            <p style="color:{TEXT_DIM}; margin:0.5rem 0 0; font-size:0.82rem;">
                Everything else builds on those three. You can reset to this demo anytime from Data Management.
            </p>
        </div>''', unsafe_allow_html=True)

    monthly_income = th["monthly_take_home"]
    budget_cats = {**data["budget"]["needs"], **data["budget"]["wants"], **data["budget"]["savings"]}
    total_budgeted = sum(budget_cats.values())

    now = datetime.now()
    # Month selector
    available_months = sorted(set(e["date"][:7] for e in data["expenses"]), reverse=True)
    if not available_months:
        available_months = [now.strftime("%Y-%m")]
    if now.strftime("%Y-%m") not in available_months:
        available_months = [now.strftime("%Y-%m")] + available_months
    dash_month = st.selectbox("View Month", available_months, key="dash_month")
    cur_month = dash_month

    # Determine previous month relative to selected month
    sel_date = datetime.strptime(cur_month + "-01", "%Y-%m-%d")
    prev_month = (sel_date - timedelta(days=1)).strftime("%Y-%m")

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

    # Debt service comes from the debts the user actually entered, falling back to
    # the budget category only when there are none. Reading the category alone
    # reported 0.0% "Healthy" for anyone who had not also filled that line in.
    monthly_debt_payments, debt_source = monthly_debt_service(
        data["debts"], data["budget"]["needs"])

    # Lenders define debt-to-income against GROSS income, which is what the
    # 20% / 36% bands on this card are calibrated for. Dividing by take-home — a
    # denominator roughly a quarter smaller — graded people a whole category
    # harsher than a lender would.
    gross_monthly = th["annual_gross"] / 12 if th["annual_gross"] else 0
    dti = (monthly_debt_payments / gross_monthly * 100) if gross_monthly else 0

    monthly_needs = sum(data["budget"]["needs"].values())
    ef_months, ef_counted = emergency_fund_months(data["assets"], monthly_needs)

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
        dti_note = ("Measured against gross income, as lenders do. Below 20% is great. "
                    "20-36% is manageable. Above 36% limits borrowing.")
        if debt_source == "budget":
            dti_note += " Using your budgeted debt payments — add your debts on the Debt Payoff page for a figure from the actual balances."
        st.markdown(metric_card_html("Debt-to-Income", f"{dti:.1f}%", status, color,
            dti_note), unsafe_allow_html=True)
    with c3:
        # None means "could not be measured", which must not render as 0.0 months.
        if ef_months is None:
            note = ("No cash or savings account recognised among your assets, so this "
                    "cannot be measured. Name one with 'Checking', 'Savings' or 'Cash'."
                    if not ef_counted else
                    "Add your essential monthly expenses on the Budget Builder page to measure this.")
            st.markdown(metric_card_html("Emergency Fund", "—", "Not measured", TEXT_DIM,
                note), unsafe_allow_html=True)
        else:
            color = GREEN if ef_months >= 6 else (YELLOW if ef_months >= 3 else RED)
            status = "Strong" if ef_months >= 6 else ("Building" if ef_months >= 3 else "Priority")
            st.markdown(metric_card_html("Emergency Fund", f"{ef_months:.1f} mo", status, color,
                "6+ months of essential expenses is the gold standard. 3-6 is a solid start. "
                f"Counting {', '.join(ef_counted)}."), unsafe_allow_html=True)

    st.divider()

    # YTD Summary — based on actual logged expenses, not extrapolated
    cur_year = now.strftime("%Y")
    ytd_expenses = [e for e in data["expenses"] if e["date"][:4] == cur_year]
    ytd_spent = sum(e["amount"] for e in ytd_expenses)
    # Count months with actual expense data this year
    ytd_months_with_data = len(set(e["date"][:7] for e in ytd_expenses)) or 1
    ytd_est_income = monthly_income * ytd_months_with_data
    ytd_saved = ytd_est_income - ytd_spent

    st.markdown("### Year-to-Date Summary")
    st.caption(f"Based on {ytd_months_with_data} month{'s' if ytd_months_with_data != 1 else ''} of logged expenses.")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric(f"Est. Income ({ytd_months_with_data}mo)", fmt(ytd_est_income))
    with c2:
        st.metric("Total Spending", fmt(ytd_spent))
    with c3:
        st.metric("Est. Saved", fmt(ytd_saved))
    with c4:
        ytd_rate = (ytd_saved / ytd_est_income * 100) if ytd_est_income else 0
        st.metric("Savings Rate", f"{ytd_rate:.1f}%")

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
            textfont=dict(family="Inter", size=13),
        ))
        fig.update_layout(**default_layout(), height=450, showlegend=False, yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("### Spending by Category (MTD)")
        if cat_spending:
            cats = list(cat_spending.keys())
            vals = list(cat_spending.values())
            colors = [GREEN if cat in data["budget"]["savings"] else
                      (BLUE if cat in data["budget"]["needs"] else YELLOW)
                      for cat in cats]
            total = sum(vals)
            pull_vals = [0.08 if (v / total) < 0.06 else 0 for v in vals] if total > 0 else [0]*len(vals)
            fig = go.Figure(data=[go.Pie(
                labels=cats, values=vals, hole=0.45,
                marker=dict(colors=colors, line=dict(color="#FFFFFF", width=2)),
                textinfo="percent",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>%{value:$,.2f}<br>%{percent}<extra></extra>",
                textfont=dict(family="Inter", size=12),
                pull=pull_vals,
            )])
            pie_layout = default_layout()
            pie_layout["margin"] = dict(l=10, r=10, t=10, b=10)
            fig.update_layout(**pie_layout, height=450, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f'<p style="text-align:center; color:{TEXT_DIM}; font-size:0.85rem; margin-top:-0.5rem;">Total: <strong>{fmt(total_spent)}</strong></p>', unsafe_allow_html=True)
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
        mom_layout = default_layout()
        mom_layout["legend"] = dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=1.05, x=0.5, xanchor="center")
        mom_layout["margin"] = dict(l=50, r=20, t=40, b=100)
        fig.update_layout(**mom_layout, height=400, barmode="group",
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
            fillcolor="rgba(46,204,113,0.1)",
        ))
        fig.update_layout(**default_layout(), height=300, yaxis_title="Net Worth ($)",
                         yaxis_tickprefix="$", yaxis_tickformat=",")
        st.plotly_chart(fig, use_container_width=True)

    # Savings goals progress
    if data["savings_goals"]:
        st.markdown("### Savings Goals Progress")
        for goal in sorted(data["savings_goals"], key=lambda g: g.get("priority", 99)):
            st.markdown(render_savings_goal_card(goal), unsafe_allow_html=True)

    auto_save_debounced(data)
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
        new_salary = st.number_input(
            "Annual Gross Salary ($)", value=data["income"]["gross_salary"],
            min_value=0, step=1000, format="%d",
        )
        if new_salary != data["income"]["gross_salary"]:
            st.session_state.is_demo = False
        data["income"]["gross_salary"] = new_salary
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
        hsa_annual_check = data["income"]["hsa"] * 12
        if hsa_annual_check > 4400:
            st.warning(f"Your HSA contribution (${hsa_annual_check:,}/yr) exceeds the 2026 individual limit of $4,400.")
        data["income"]["student_loan_interest"] = st.number_input(
            "Student Loan Interest ($/year)", value=data["income"].get("student_loan_interest", 0),
            min_value=0, max_value=2500, step=100, format="%d",
            help="Above-the-line deduction, max $2,500/yr. Phases out at $85K-$100K (Single) or $175K-$205K (MFJ).",
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
        textfont=dict(family="Inter", size=11),
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
        state_m = th_local["marginal_state"] / 100
        # FICA on the RAISE, not the average rate across the whole salary. Above
        # the SS wage base the marginal rate drops from 7.65% to 1.45%, so the
        # average overstates the tax on an increment for exactly the earners this
        # modeller is aimed at.
        fica_rate = marginal_fica_rate(base, negotiated, th_local["filing"])
        after_tax_diff = lifetime_diff * (1 - marginal - state_m - fica_rate)

        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Year 1 Difference", fmt(neg_increase), delta=f"+{fmt(neg_increase * (1 - marginal - state_m - fica_rate))} after tax")
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
                                fillcolor="rgba(46,134,171,0.1)"))
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

    auto_save_debounced(data)
    render_footer()


# ══════════════════════════════════════════════
# PAGE: BUDGET BUILDER
# ══════════════════════════════════════════════

def page_budget():
    st.markdown("# Budget Builder")
    st.caption("Allocate your take-home pay using the 50/30/20 framework — or customize it to fit your life.")
    monthly_income = th["monthly_take_home"]

    col_city = st.selectbox("Your Metro Area (for cost-of-living context)", list(COL_INDEX.keys()), index=0, key="col_city")
    col_factor = COL_INDEX[col_city] / 100
    if col_city != "National Average":
        adj = "above" if col_factor > 1 else "below"
        st.caption(f"{col_city} is {abs(COL_INDEX[col_city] - 100):.0f}% {adj} the national average cost of living. "
                   f"The 50/30/20 guideline amounts below are adjusted for your location.")
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
        textfont=dict(family="Inter", size=14, color="white"),
    ))
    fig.add_trace(go.Scatter(
        name="50/30/20 Guideline", x=["Needs", "Wants", "Savings"],
        y=[50, 30, 20], mode="markers+text",
        marker=dict(color=TEXT, size=12, symbol="diamond"),
        text=["50%", "30%", "20%"], textposition="top center",
        textfont=dict(family="Inter", size=12, color=TEXT_DIM),
    ))
    fig.update_layout(**default_layout(), height=350, barmode="group",
                     yaxis_title="% of Budget",
)
    st.plotly_chart(fig, use_container_width=True)
    auto_save_debounced(data)
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

    # CSV bulk import
    with st.expander("📄 Import Expenses from CSV"):
        st.caption("Upload a CSV with columns: `date`, `amount`, `category`, `note` (optional). Dates should be YYYY-MM-DD format.")
        csv_file = st.file_uploader("Choose CSV file", type=["csv"], key="csv_import")
        if csv_file:
            try:
                import_df = pd.read_csv(csv_file)
                required_cols = {"date", "amount", "category"}
                if not required_cols.issubset(set(import_df.columns)):
                    st.error(f"CSV must have columns: {', '.join(required_cols)}. Found: {', '.join(import_df.columns)}")
                else:
                    st.dataframe(import_df.head(10), use_container_width=True, hide_index=True)
                    st.caption(f"{len(import_df)} expenses found in file.")
                    if st.button(f"Import {len(import_df)} Expenses", type="primary"):
                        count = 0
                        for _, row in import_df.iterrows():
                            try:
                                amt = float(row["amount"])
                                if amt > 0:
                                    data["expenses"].append({
                                        "id": _make_id(),
                                        "date": str(row["date"])[:10],
                                        "amount": amt,
                                        "category": str(row["category"]),
                                        "note": str(row.get("note", "")) if pd.notna(row.get("note")) else "",
                                    })
                                    count += 1
                            except (ValueError, TypeError):
                                continue
                        st.success(f"Imported {count} expenses.")
                        st.rerun()
            except Exception as e:
                st.error(f"Could not read CSV: {e}")

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
            pie_colors = [GREEN, BLUE, YELLOW, RED, PURPLE, "#f472b6", "#38bdf8", "#fb923c", "#a3e635", "#e879f9", "#22d3ee", "#fca5a5"][:len(cats)]
            pie_total = sum(vals)
            pie_pull = [0.08 if (v / pie_total) < 0.06 else 0 for v in vals] if pie_total > 0 else [0]*len(vals)
            pie_text = [f"{v/pie_total*100:.0f}%" if pie_total > 0 and v/pie_total >= 0.05 else "" for v in vals]
            fig = go.Figure(data=[go.Pie(
                labels=cats, values=vals, hole=0.45,
                text=pie_text, textinfo="text",
                textposition="inside",
                hovertemplate="<b>%{label}</b><br>%{value:$,.2f}<br>%{percent}<extra></extra>",
                textfont=dict(family="Inter", size=13),
                marker=dict(colors=pie_colors, line=dict(color="#FFFFFF", width=2)),
                pull=pie_pull,
            )])
            layout2 = default_layout()
            layout2["margin"] = dict(l=10, r=10, t=10, b=10)
            fig.update_layout(**layout2, height=450, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
            st.markdown(f'<p style="text-align:center; color:{TEXT_DIM}; font-size:0.85rem; margin-top:-0.5rem;">Total: <strong>{fmt(total_spent)}</strong></p>', unsafe_allow_html=True)

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

    auto_save_debounced(data)
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
        with st.expander("Add / Remove Asset"):
            new_name = st.text_input("Asset Name", key="new_asset_name")
            new_val = st.number_input("Value ($)", value=0, min_value=0, step=100, key="new_asset_val")
            if st.button("Add Asset") and new_name:
                data["assets"][new_name] = new_val
                st.rerun()
            if len(data["assets"]) > 1:
                remove_asset = st.selectbox("Remove Asset", list(data["assets"].keys()), key="rm_asset")
                if st.button("Remove", key="rm_asset_btn"):
                    del data["assets"][remove_asset]
                    st.rerun()

    with c2:
        st.markdown("### Liabilities")
        for name in list(data["liabilities"].keys()):
            data["liabilities"][name] = st.number_input(
                name, value=data["liabilities"][name], min_value=0, step=100,
                format="%d", key=f"liability_{name}")
        with st.expander("Add / Remove Liability"):
            new_name = st.text_input("Liability Name", key="new_liab_name")
            new_val = st.number_input("Balance ($)", value=0, min_value=0, step=100, key="new_liab_val")
            if st.button("Add Liability") and new_name:
                data["liabilities"][new_name] = new_val
                st.rerun()
            if len(data["liabilities"]) > 1:
                remove_liab = st.selectbox("Remove Liability", list(data["liabilities"].keys()), key="rm_liab")
                if st.button("Remove", key="rm_liab_btn"):
                    del data["liabilities"][remove_liab]
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

    auto_save_debounced(data)
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
            Calculations use standard amortization math with monthly compounding.
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

        months_av, interest_av, sched_av, payoffs_av = simulate_payoff(data["debts"], extra, "avalanche")
        months_sn, interest_sn, sched_sn, payoffs_sn = simulate_payoff(data["debts"], extra, "snowball")

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
            # Add payoff markers for each debt (Avalanche strategy)
            marker_colors = [GREEN, BLUE, YELLOW, RED, PURPLE]
            for i, (debt_name, month) in enumerate(sorted(payoffs_av.items(), key=lambda x: x[1])):
                clr = marker_colors[i % len(marker_colors)]
                fig.add_vline(x=month, line_dash="dot", line_color=clr, line_width=1)
                fig.add_annotation(x=month, y=0, text=f"{debt_name} paid off",
                                  showarrow=True, arrowhead=2, arrowsize=0.8,
                                  ax=0, ay=-30, font=dict(size=10, color=clr),
                                  bgcolor="rgba(255,255,255,0.9)", bordercolor=clr, borderwidth=1)
            fig.update_layout(**default_layout(), height=400,
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

    auto_save_debounced(data)
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

    auto_save_debounced(data)
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

    c1, c2, c3 = st.columns(3)
    with c1:
        show_real = st.toggle("Inflation-adjusted returns", value=False,
                              help="Subtracts ~3% assumed inflation from nominal returns")
    with c2:
        taxable_account = st.toggle("Taxable account (not 401k/IRA)", value=False,
                                     help="Applies ~0.7% annual tax drag for capital gains and dividends in taxable brokerage accounts")
    with c3:
        income_growth = st.number_input("Income Growth (%/yr)", value=3.0, min_value=0.0,
                                         max_value=20.0, step=0.5, format="%.1f", key="income_growth",
                                         help="Contributions grow with salary. 3-5% typical; IB/PE early career 8-15%.")
    inflation = 3.0 if show_real else 0.0
    tax_drag = 0.7 if taxable_account else 0.0  # ~0.7% annual drag for index funds in taxable

    inv = data["investment"]
    years = inv["time_horizon"]

    scenarios = [
        ("Conservative (5%)", 5.0 - inflation - tax_drag, BLUE),
        ("Moderate (7%)", 7.0 - inflation - tax_drag, GREEN),
        ("Aggressive (10%)", 10.0 - inflation - tax_drag, YELLOW),
    ]

    adjustments = []
    if show_real: adjustments.append("Inflation-Adjusted")
    if taxable_account: adjustments.append("After Tax Drag")
    adj_label = f" ({', '.join(adjustments)})" if adjustments else ""
    st.markdown(f"### Scenario Comparison{adj_label}")
    fig = go.Figure()
    x_vals = list(range(years + 1))

    for name, rate, color in scenarios:
        values, contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], max(rate, 0), years, income_growth)
        yearly_vals = [values[y * 12] for y in range(years + 1)]
        fig.add_trace(go.Scatter(
            x=x_vals, y=yearly_vals, name=name,
            line=dict(color=color, width=2),
            hovertemplate="%{text}<extra></extra>",
            text=[f"{name}<br>Year {y}: {fmt(v)}" for y, v in zip(x_vals, yearly_vals)],
        ))

    _, base_contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], 0, years, income_growth)
    yearly_contribs_base = [base_contribs[y * 12] for y in range(years + 1)]
    fig.add_trace(go.Scatter(x=x_vals, y=yearly_contribs_base, name="Total Contributions",
                            line=dict(color=TEXT_DIM, width=1, dash="dash")))
    fig.update_layout(**default_layout(), height=400, xaxis_title="Years", yaxis_title="Portfolio Value",
                     yaxis_tickprefix="$", yaxis_tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    # Final values
    c1, c2, c3 = st.columns(3)
    for col, (name, rate, color) in zip([c1, c2, c3], scenarios):
        vals, contribs = project_investment(inv["starting_amount"], inv["monthly_contribution"], max(rate, 0), years, income_growth)
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
    rate = max(inv["annual_return"] - inflation - tax_drag, 0)
    fig = go.Figure()
    colors_cow = [GREEN, BLUE, YELLOW, RED]
    for delay, clr in zip(delays, colors_cow):
        effective_years = max(0, years - delay)
        if effective_years == 0:
            padded = [inv["starting_amount"]] * (years + 1)
        else:
            vals, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, effective_years, income_growth)
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
        vals_now, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, years, income_growth)
        vals_5yr, _ = project_investment(inv["starting_amount"], inv["monthly_contribution"], rate, years - 5, income_growth)
        cost = vals_now[-1] - vals_5yr[-1]
        st.warning(f"Waiting 5 years costs you approximately **{fmt(cost)}** in potential growth.")

    # Employer match
    st.markdown("### 401(k) Employer Match")
    st.caption("Your employer match is free money — the highest guaranteed return you'll ever get.")
    salary = data["income"]["gross_salary"]
    your_contrib_pct = data["income"]["contribution_401k"]
    match_pct = inv["employer_match_pct"]
    match_limit = inv["employer_match_limit"]

    your_annual = min(salary * your_contrib_pct / 100, 24_500)  # capped at IRS limit
    matchable = salary * match_limit / 100
    employer_annual = min(your_annual, matchable) * match_pct / 100
    employer_monthly = employer_annual / 12

    # Career-lifetime free money calculation
    career_years = 35  # typical career
    _, career_contribs = project_investment(0, employer_monthly, rate, career_years)
    career_match_total = career_contribs[-1]  # total employer contributions
    career_match_with_growth, _ = project_investment(0, employer_monthly, rate, career_years)
    career_match_value = career_match_with_growth[-1]

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Your Annual 401(k)", fmt(your_annual))
    with c2:
        st.metric("Employer Match / Year", fmt(employer_annual), help="Free money from your employer!")
    with c3:
        total_401k_monthly = your_annual / 12 + employer_monthly
        vals_with, _ = project_investment(inv["starting_amount"], total_401k_monthly, rate, years)
        vals_without, _ = project_investment(inv["starting_amount"], your_annual / 12, rate, years)
        match_value = vals_with[-1] - vals_without[-1]
        st.metric(f"Match Growth ({years}yr)", fmt(match_value),
                  help=f"Extra portfolio value from employer match over {years} years")
    with c4:
        st.metric("Career Free Money (35yr)", fmt(career_match_value),
                  help=f"Total value of employer match invested at {rate:.0f}% over a 35-year career")

    if employer_annual > 0:
        st.markdown(f'''<div class="card" style="border-left:3px solid {GREEN};">
            <p style="font-weight:600; margin:0;">Your employer gives you {fmt(employer_annual)}/year for free.</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0 0; font-size:0.88rem;">
                Invested at {rate:.0f}% over a 35-year career, that match alone grows to
                <span class="mono" style="color:{GREEN}; font-weight:600;">{fmt(career_match_value)}</span>.
                That's money you never contributed — pure employer subsidy compounded over time.
            </p>
        </div>''', unsafe_allow_html=True)

    if your_contrib_pct < match_limit:
        max_employer = salary * match_limit / 100 * match_pct / 100
        missed = max_employer - employer_annual
        st.warning(f"You're contributing {your_contrib_pct}% but your employer matches up to {match_limit}%. "
                   f"You're leaving **{fmt(missed)}**/year on the table!")

    auto_save_debounced(data)
    render_footer()


# ══════════════════════════════════════════════
# PAGE: FIRE CALCULATOR
# ══════════════════════════════════════════════

def page_fire():
    st.markdown("# FIRE Calculator")
    st.caption("Financial Independence, Retire Early — calculate when your portfolio can sustain your lifestyle. "
               "Based on the 4% safe withdrawal rate from the Trinity Study, with inflation-adjusted FIRE targets.")

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
        fire_age = st.number_input("Current Age", value=24, min_value=18, max_value=80,
                                    step=1, format="%d", key="fire_age")
        fire_withdrawal = st.number_input("Safe Withdrawal Rate (%)", value=4.0, min_value=1.0, max_value=10.0,
                                           step=0.25, format="%.2f", key="fire_swr",
                                           help="4% is the classic 'Trinity Study' rule. 3.5% is more conservative.")
        fire_inflation = st.number_input("Inflation (%)", value=3.0, min_value=0.0, max_value=10.0,
                                          step=0.5, format="%.1f", key="fire_inflation")

    # Healthcare costs for early retirees (pre-65, ACA unsubsidized averages)
    # 2026 ACA unsubsidized estimates (Silver plan, post-enhanced-subsidy expiration)
    healthcare_defaults = {(18,29): 6000, (30,39): 7200, (40,49): 9600, (50,59): 13200, (60,64): 18000, (65,80): 3000}
    default_hc = next((v for (lo, hi), v in healthcare_defaults.items() if lo <= fire_age <= hi), 7200)
    fire_healthcare = st.number_input("Annual Healthcare Cost ($)", value=default_hc,
        min_value=0, step=500, format="%d", key="fire_healthcare",
        help="Pre-65 retirees need private insurance. Estimate based on your age. After 65, Medicare reduces this significantly.")

    total_fire_expenses = fire_expenses + fire_healthcare
    annual_savings = fire_income - fire_expenses  # healthcare only applies in retirement
    savings_rate = (annual_savings / fire_income * 100) if fire_income > 0 else 0
    fire_number = (total_fire_expenses / (fire_withdrawal / 100)) if fire_withdrawal > 0 else 0
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
        hc_note = f" (includes {fmt(fire_healthcare)}/yr healthcare)" if fire_healthcare > 0 else ""
        st.markdown(metric_card_html("FIRE Number", fmt(fire_number), f"At {fire_withdrawal:.1f}% SWR", BLUE,
            f"Portfolio needed to cover {fmt(total_fire_expenses)}/yr{hc_note}."), unsafe_allow_html=True)
    with c3:
        if years_to_fire > 0:
            fi_age = fire_age + years_to_fire
            st.markdown(metric_card_html("Years to FIRE", str(years_to_fire), f"Age {fi_age}", GREEN,
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
                            fillcolor="rgba(46,204,113,0.1)"))
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
            fi_target = fi_num * (1 + fire_inflation / 100) ** y
            if p >= fi_target:
                yrs = y
                break
        years_list.append(yrs if yrs > 0 else 100)

    fig = go.Figure()
    bar_colors = [GREEN if y <= 15 else (YELLOW if y <= 30 else (BLUE if y <= 50 else RED)) for y in years_list]
    fig.add_trace(go.Bar(x=[f"{r}%" for r in rates], y=years_list, marker_color=bar_colors,
                        text=[f"{y}yr" for y in years_list], textposition="outside",
                        textfont=dict(family="Inter", size=10)))
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
                               "FIRE Age": f"Age {fire_age + yrs}" if yrs > 0 else "N/A"})

    st.dataframe(pd.DataFrame(scenarios_data), use_container_width=True, hide_index=True)

    st.markdown(f'''<div class="card" style="border-left:3px solid {YELLOW};">
        <p style="font-weight:600; margin:0;">Key Insight</p>
        <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.9rem;">
            Your savings rate matters more than your return rate. Going from 20% to 40% savings
            cuts your working years nearly in half. Every dollar of expenses you cut permanently
            reduces your FIRE number <em>and</em> increases your savings rate — a double win.
        </p>
    </div>''', unsafe_allow_html=True)

    # Monte Carlo simulation
    st.divider()
    st.markdown("### Monte Carlo Retirement Simulation")
    st.caption("Runs randomized market scenarios with correlated stock/bond returns to test your plan's resilience across accumulation and retirement phases.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mc_stock_pct = st.slider("Stock Allocation", 0, 100, 80, 5, format="%d%%", key="mc_stocks")
    with c2:
        mc_retire_age = st.number_input("Retirement Age", 25, 80,
            value=min(80, fire_age + years_to_fire) if years_to_fire > 0 else 65,
            key="mc_retire_age")
    with c3:
        mc_end_age = st.number_input("Plan Through Age", 70, 100, 95, key="mc_end_age")
    with c4:
        mc_n_sims = st.selectbox("Simulations", [500, 1000, 2000, 5000], index=1, key="mc_nsims")

    if st.button("Run Simulation", type="primary", key="mc_run"):
        with st.spinner("Running simulation..."):
            stock_alloc = mc_stock_pct / 100
            bond_alloc = 1.0 - stock_alloc
            total_mc_years = mc_end_age - fire_age
            yrs_to_retire = mc_retire_age - fire_age
            inflation_mean = fire_inflation / 100

            # Correlated returns via Cholesky decomposition
            corr_matrix = np.array([[1.0, 0.05], [0.05, 1.0]])
            cholesky = np.linalg.cholesky(corr_matrix)

            paths = np.zeros((mc_n_sims, total_mc_years + 1))
            paths[:, 0] = fire_portfolio
            failure_ages = []

            for sim in range(mc_n_sims):
                portfolio = float(fire_portfolio)
                failed = False
                for year in range(1, total_mc_years + 1):
                    if failed:
                        paths[sim, year] = 0
                        continue
                    z = np.random.normal(size=2)
                    correlated = cholesky @ z
                    stock_ret = 0.10 + 0.18 * correlated[0]
                    bond_ret = 0.05 + 0.06 * correlated[1]
                    port_ret = stock_alloc * stock_ret + bond_alloc * bond_ret
                    yr_inflation = max(0, np.random.normal(inflation_mean, 0.015))

                    age = fire_age + year
                    if age <= mc_retire_age:
                        inf_factor = (1 + inflation_mean) ** year
                        portfolio = portfolio * (1 + port_ret) + annual_savings * inf_factor
                    else:
                        yrs_retired = age - mc_retire_age
                        inf_factor = (1 + yr_inflation) ** yrs_retired
                        portfolio = portfolio * (1 + port_ret) - total_fire_expenses * inf_factor

                    if portfolio <= 0:
                        portfolio = 0
                        failed = True
                        failure_ages.append(age)
                    paths[sim, year] = portfolio

            success_count = int(np.sum(paths[:, -1] > 0))
            success_rate = success_count / mc_n_sims * 100
            ages = list(range(fire_age, mc_end_age + 1))
            p5 = np.percentile(paths, 5, axis=0)
            p10 = np.percentile(paths, 10, axis=0)
            p25 = np.percentile(paths, 25, axis=0)
            p50 = np.percentile(paths, 50, axis=0)
            p75 = np.percentile(paths, 75, axis=0)
            p90 = np.percentile(paths, 90, axis=0)
            p95 = np.percentile(paths, 95, axis=0)
            ending = paths[:, -1]

        # Store in session so user can scroll without re-running
        st.session_state.mc_results = {
            "paths": paths, "ages": ages, "success_rate": success_rate,
            "success_count": success_count, "n_sims": mc_n_sims,
            "p5": p5, "p10": p10, "p25": p25, "p50": p50, "p75": p75, "p90": p90, "p95": p95,
            "ending": ending, "failure_ages": failure_ages,
            "retire_age": mc_retire_age, "stock_pct": mc_stock_pct,
        }

    # Display results if available
    if "mc_results" in st.session_state:
        r = st.session_state.mc_results
        sr = r["success_rate"]

        # Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sr_color = GREEN if sr >= 85 else (YELLOW if sr >= 70 else RED)
            sr_status = "Strong" if sr >= 85 else ("Moderate" if sr >= 70 else "At Risk")
            st.markdown(metric_card_html("Success Rate", f"{sr:.0f}%", sr_status, sr_color,
                f"Plan survives in {r['success_count']:,} of {r['n_sims']:,} scenarios."), unsafe_allow_html=True)
        with c2:
            st.metric("Median Ending Balance", fmt(float(np.median(r["ending"]))))
        with c3:
            st.metric("Worst 10% Scenario", fmt(max(0, float(np.percentile(r["ending"], 10)))),
                      help="90% of outcomes are better than this")
        with c4:
            st.metric("Best 10% Scenario", fmt(float(np.percentile(r["ending"], 90))))

        # Fan chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p90"].tolist(), mode="lines", line=dict(width=0),
                                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p10"].tolist(), mode="lines", line=dict(width=0),
                                fill="tonexty", fillcolor="rgba(46,134,171,0.12)",
                                name="10th-90th percentile", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p75"].tolist(), mode="lines", line=dict(width=0),
                                showlegend=False, hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p25"].tolist(), mode="lines", line=dict(width=0),
                                fill="tonexty", fillcolor="rgba(46,134,171,0.25)",
                                name="25th-75th percentile", hoverinfo="skip"))
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p50"].tolist(), mode="lines",
                                line=dict(color=BLUE, width=2.5), name="Median",
                                hovertemplate="Age %{x}: %{y:$,.0f}<extra></extra>"))
        fig.add_trace(go.Scatter(x=r["ages"], y=r["p5"].tolist(), mode="lines",
                                line=dict(color=RED, width=1.5, dash="dot"),
                                name="5th percentile", hovertemplate="Age %{x}: %{y:$,.0f}<extra></extra>"))
        fig.add_vline(x=r["retire_age"], line_dash="dash", line_color=YELLOW, line_width=1.5,
                     annotation_text="Retirement", annotation_position="top")
        fig.add_hline(y=0, line_dash="dash", line_color=RED, line_width=1, opacity=0.5)
        fig.update_layout(**default_layout(), height=450, xaxis_title="Age",
                         yaxis_title="Portfolio Value", yaxis_tickformat="$,.0f")
        st.plotly_chart(fig, use_container_width=True)

        # Histogram + sample paths
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Ending Balance Distribution")
            successes = r["ending"][r["ending"] > 0]
            failures = r["ending"][r["ending"] <= 0]
            fig2 = go.Figure()
            if len(successes) > 0:
                fig2.add_trace(go.Histogram(x=successes, nbinsx=40, marker_color=BLUE, opacity=0.7, name="Survived"))
            if len(failures) > 0:
                fig2.add_trace(go.Histogram(x=failures, nbinsx=5, marker_color=RED, opacity=0.7, name="Ran out"))
            fig2.add_vline(x=float(np.median(r["ending"])), line_dash="dash", line_color=BLUE,
                          annotation_text="Median", annotation_position="top")
            fig2.update_layout(**default_layout(), height=350, xaxis_title="Ending Portfolio",
                             xaxis_tickformat="$,.0f", yaxis_title="Simulations", barmode="overlay",
                             showlegend=True)
            st.plotly_chart(fig2, use_container_width=True)

        with c2:
            st.markdown("#### Sample Paths")
            fig3 = go.Figure()
            sample_idx = np.random.choice(r["paths"].shape[0], size=min(50, r["paths"].shape[0]), replace=False)
            for i in sample_idx:
                fig3.add_trace(go.Scatter(x=r["ages"], y=r["paths"][i].tolist(), mode="lines",
                    line=dict(color=BLUE, width=0.5), opacity=0.15, showlegend=False, hoverinfo="skip"))
            fig3.add_trace(go.Scatter(x=r["ages"], y=r["p50"].tolist(), mode="lines",
                                    line=dict(color=BLUE, width=2.5), name="Median"))
            fig3.add_hline(y=0, line_dash="dash", line_color=RED, line_width=1)
            fig3.update_layout(**default_layout(), height=350, xaxis_title="Age",
                             yaxis_title="Portfolio Value", yaxis_tickformat="$,.0f", showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)

        # Interpretation card
        st.markdown(f'''<div class="card" style="border-left:3px solid {sr_color};">
            <p style="font-weight:600; margin:0;">What This Means</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.9rem;">
                Out of {r["n_sims"]:,} simulated market scenarios, your portfolio survived in
                <strong style="color:{sr_color};">{r["success_count"]:,}</strong> ({sr:.0f}%).
                The median ending balance was <strong>{fmt(float(np.median(r["ending"])))}</strong>,
                but in the worst 10% of scenarios it was {fmt(max(0, float(np.percentile(r["ending"], 10))))}.
            </p>
            <p style="color:{TEXT_DIM}; margin:0.5rem 0 0; font-size:0.82rem;">
                Assumes {r["stock_pct"]}% stocks / {100-r["stock_pct"]}% bonds with correlated returns
                (Cholesky decomposition). Stock returns: 10% mean, 18% stdev (S&P 500 historical).
                Bond returns: 5% mean, 6% stdev. Inflation randomized at 3% mean.
                Source: Trinity Study (1998), Shiller/Ibbotson historical data.
            </p>
        </div>''', unsafe_allow_html=True)
    else:
        st.info("Click 'Run Simulation' above to generate results.")

    # Social Security estimation
    st.divider()
    st.markdown("### Social Security Estimation")
    st.caption("Simplified estimate based on your current salary and 2026 bend points. Actual benefits depend on your full 35-year earnings history.")

    c1, c2 = st.columns(2)
    with c1:
        ss_salary = st.number_input("Salary for SS Estimate ($)", value=data["income"]["gross_salary"],
                                     min_value=0, step=1000, format="%d", key="ss_salary",
                                     help="Your current or expected average career salary")
    with c2:
        ss_claim_age = st.slider("Claiming Age", 62, 70, 67, key="ss_claim_age",
                                  help="62 = earliest (reduced). 67 = full retirement age. 70 = maximum (8%/yr bonus).")

    ss_monthly = calc_social_security(ss_salary, ss_claim_age)
    ss_annual = ss_monthly * 12

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Est. Monthly SS Benefit", fmt(ss_monthly))
    with c2:
        st.metric("Est. Annual SS Income", fmt(ss_annual))
    with c3:
        if fire_withdrawal > 0:
            ss_fire_reduction = ss_annual / (fire_withdrawal / 100)
            st.metric("Reduces FIRE Number By", fmt(ss_fire_reduction),
                      help="SS income means you need less from your portfolio")

    ages = [62, 64, 67, 70]
    ss_comparison = []
    for age in ages:
        monthly = calc_social_security(ss_salary, age)
        label = "Early" if age < 67 else ("FRA" if age == 67 else "Delayed")
        ss_comparison.append({"Claiming Age": age, "Type": label,
                              "Monthly": fmt(monthly), "Annual": fmt(monthly * 12)})
    st.dataframe(pd.DataFrame(ss_comparison), use_container_width=True, hide_index=True)

    auto_save_debounced(data)
    render_footer()


# ══════════════════════════════════════════════
# PAGE: TAX ESTIMATOR
# ══════════════════════════════════════════════

def page_tax():
    st.markdown("# Tax Estimator")
    st.caption("Estimate your federal and state tax liability, compare deduction strategies, and optimize 401(k) contributions.")
    st.markdown(f'''<div class="card" style="border-left:3px solid {BLUE}; padding:1rem 1.25rem;">
        <p style="color:{TEXT_DIM}; margin:0; font-size:0.82rem;">
            All brackets use official IRS 2026 data from
            <a href="https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill" target="_blank" style="color:{BLUE};">Revenue Procedure 2025-32</a>.
            SALT cap reflects the One Big Beautiful Bill Act ($40,400). State rates updated for 2026 changes.
        </p>
    </div>''', unsafe_allow_html=True)

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
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">{'Itemized' if th_local['itemizing'] else 'Standard'} Deduction:</span> <span class="mono">-{fmt(th_local['deduction_taken'])}</span></p>
            <p style="margin:0.25rem 0;"><span style="color:{TEXT_DIM};">Taxable Income:</span> <span class="mono" style="font-weight:600;">{fmt(th_local['taxable'])}</span></p>
        </div>''', unsafe_allow_html=True)

    # Standard vs Itemized comparison
    st.markdown("### Standard vs. Itemized Deduction")
    st.caption("Enter your potential itemized deductions to see which option saves you more.")

    if "itemized" not in data:
        data["itemized"] = {"salt": 0, "mortgage_interest": 0, "charitable": 0, "medical": 0}

    c1, c2 = st.columns(2)
    with c1:
        effective_salt_cap = calc_salt_cap(th_local["agi"], th_local["filing"])
        data["itemized"]["salt"] = st.number_input("State & Local Taxes (SALT)", value=data["itemized"]["salt"],
            min_value=0, step=100, format="%d",
            help=f"Your effective SALT cap: ${effective_salt_cap:,.0f} (phases out above ${SALT_PHASEOUT_THRESHOLD.get(th_local['filing'], 505_000):,} MAGI)")
        data["itemized"]["mortgage_interest"] = st.number_input("Mortgage Interest", value=data["itemized"]["mortgage_interest"],
            min_value=0, step=100, format="%d")
    with c2:
        data["itemized"]["charitable"] = st.number_input("Charitable Donations", value=data["itemized"]["charitable"],
            min_value=0, step=100, format="%d")
        data["itemized"]["medical"] = st.number_input("Medical (above 7.5% AGI)", value=data["itemized"]["medical"],
            min_value=0, step=100, format="%d",
            help="Only the amount exceeding 7.5% of AGI is deductible")

    # One implementation, shared with compute_take_home — so this page and the
    # rest of the app cannot disagree about the same taxpayer.
    _it = calc_itemized_total(data["itemized"], th_local["agi"], th_local["filing"])
    salt_capped = _it["salt"]
    medical_deductible = _it["medical"]
    charitable_deductible = _it["charitable"]
    total_itemized = _it["total"]
    standard = th_local["std_ded"]

    # OBBBA 2026: non-itemizer charitable deduction (above-the-line)
    non_itemizer_charitable_limit = 2000 if th_local["filing"] == "Married Filing Jointly" else 1000
    non_itemizer_charitable = min(data["itemized"]["charitable"], non_itemizer_charitable_limit)

    better = "Standard" if standard >= total_itemized else "Itemized"
    diff = abs(standard - total_itemized)

    c1, c2 = st.columns(2)
    with c1:
        border = f"border-left:3px solid {GREEN}" if better == "Standard" else ""
        non_itemizer_note = f"<br><span style='color:{BLUE};'>+ {fmt(non_itemizer_charitable)} non-itemizer charitable deduction (above-the-line)</span>" if non_itemizer_charitable > 0 and better == "Standard" else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Standard Deduction</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(standard)}</p>
            {"<p style='color:" + GREEN + "; margin:0; font-size:0.85rem;'>&#9989; Better option" + non_itemizer_note + "</p>" if better == "Standard" else ""}
        </div>''', unsafe_allow_html=True)
    with c2:
        border = f"border-left:3px solid {GREEN}" if better == "Itemized" else ""
        charity_note = f" (after 0.5% AGI floor)" if _it["charitable_floor"] > 0 and charitable_deductible < data["itemized"]["charitable"] else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Itemized Deductions</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(total_itemized)}</p>
            <p style="color:{TEXT_DIM}; font-size:0.8rem; margin:0;">SALT: {fmt(salt_capped)} · Mortgage: {fmt(data["itemized"]["mortgage_interest"])} · Charity: {fmt(charitable_deductible)}{charity_note} · Medical: {fmt(medical_deductible)}</p>
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
        textfont=dict(family="Inter", size=12, color="white"),
    ))
    fig.update_layout(**default_layout(), height=300, yaxis_title="Tax Rate (%)",
                     xaxis_tickangle=-45, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)

    # 401(k) tax savings
    st.markdown("### 401(k) Tax Savings Impact")
    contrib = th_local["contrib_401k"]
    marginal = th_local["marginal_fed"] / 100
    state_marginal = th_local["marginal_state"] / 100

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

    # Roth vs Traditional analysis
    st.divider()
    st.markdown("### Roth vs. Traditional 401(k) / IRA")
    st.caption("Should you contribute pre-tax (Traditional) or post-tax (Roth)? The answer depends on your current vs. future tax bracket.")

    c1, c2 = st.columns(2)
    with c1:
        roth_contribution = st.number_input("Annual Contribution ($)", value=int(min(contrib, 24500)),
            min_value=0, max_value=24500, step=500, format="%d", key="roth_contrib")
        roth_years = st.slider("Years Until Retirement", 1, 50, 30, key="roth_years")
    with c2:
        roth_return = st.number_input("Expected Return (%)", value=7.0, min_value=0.0, max_value=20.0,
            step=0.5, format="%.1f", key="roth_return")
        future_tax_rate = st.number_input("Expected Retirement Tax Rate (%)", value=15.0,
            min_value=0.0, max_value=50.0, step=1.0, format="%.1f", key="future_rate",
            help="Your expected marginal tax rate in retirement. Typically lower than working years.")

    current_rate = marginal + state_marginal
    future_rate_dec = future_tax_rate / 100
    r = roth_return / 100

    # Traditional: contribute pre-tax, grow, pay tax on withdrawal
    trad_contribution = roth_contribution  # same dollar amount, but pre-tax
    trad_future = trad_contribution * ((1 + r) ** roth_years - 1) / r * (1 + r) if r > 0 else trad_contribution * roth_years
    trad_after_tax = trad_future * (1 - future_rate_dec)

    # Roth: pay tax now, contribute less, grow tax-free
    roth_actual = roth_contribution * (1 - current_rate)  # what you actually invest after tax
    roth_future = roth_actual * ((1 + r) ** roth_years - 1) / r * (1 + r) if r > 0 else roth_actual * roth_years

    better = "Traditional" if trad_after_tax > roth_future else "Roth"
    diff = abs(trad_after_tax - roth_future)

    c1, c2 = st.columns(2)
    with c1:
        border = f"border-left:3px solid {GREEN}" if better == "Traditional" else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Traditional (Pre-Tax)</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(trad_after_tax)}</p>
            <p style="color:{TEXT_DIM}; font-size:0.82rem; margin:0;">
                Contribute {fmt(trad_contribution)}/yr pre-tax &rarr; grows to {fmt(trad_future)} &rarr;
                pay {future_tax_rate:.0f}% tax on withdrawal
            </p>
            {"<p style='color:" + GREEN + "; margin:0.5rem 0 0; font-size:0.85rem;'>Better by " + fmt(diff) + "</p>" if better == "Traditional" else ""}
        </div>''', unsafe_allow_html=True)
    with c2:
        border = f"border-left:3px solid {GREEN}" if better == "Roth" else ""
        st.markdown(f'''<div class="card" style="{border}">
            <p style="font-weight:600; margin:0;">Roth (Post-Tax)</p>
            <p class="mono" style="font-size:1.5rem; margin:0.25rem 0;">{fmt(roth_future)}</p>
            <p style="color:{TEXT_DIM}; font-size:0.82rem; margin:0;">
                Pay {current_rate*100:.0f}% tax now &rarr; contribute {fmt(roth_actual)}/yr &rarr;
                grows tax-free, no tax on withdrawal
            </p>
            {"<p style='color:" + GREEN + "; margin:0.5rem 0 0; font-size:0.85rem;'>Better by " + fmt(diff) + "</p>" if better == "Roth" else ""}
        </div>''', unsafe_allow_html=True)

    # Decision guidance
    if current_rate > future_rate_dec:
        st.markdown(f'''<div class="card" style="border-left:3px solid {BLUE};">
            <p style="font-weight:600; margin:0;">Recommendation: Traditional</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.88rem;">
                Your current marginal rate ({current_rate*100:.0f}%) is higher than your expected retirement rate ({future_tax_rate:.0f}%).
                Deferring taxes now and paying less later saves you <strong class="mono">{fmt(diff)}</strong> over {roth_years} years.
            </p>
        </div>''', unsafe_allow_html=True)
    elif current_rate < future_rate_dec:
        st.markdown(f'''<div class="card" style="border-left:3px solid {BLUE};">
            <p style="font-weight:600; margin:0;">Recommendation: Roth</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.88rem;">
                Your current marginal rate ({current_rate*100:.0f}%) is lower than your expected retirement rate ({future_tax_rate:.0f}%).
                Paying taxes now at the lower rate and withdrawing tax-free saves you <strong class="mono">{fmt(diff)}</strong>.
                Early career is typically the best time for Roth contributions.
            </p>
        </div>''', unsafe_allow_html=True)
    else:
        st.markdown(f'''<div class="card" style="border-left:3px solid {BLUE};">
            <p style="font-weight:600; margin:0;">Recommendation: Roth (slight edge)</p>
            <p style="color:{TEXT_DIM}; margin:0.25rem 0; font-size:0.88rem;">
                Your rates are roughly equal. Roth has a slight edge due to tax diversification in retirement
                and no Required Minimum Distributions (RMDs).
            </p>
        </div>''', unsafe_allow_html=True)

    auto_save_debounced(data)
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
                    if "student_loan_interest" not in imported.get("income", {}):
                        imported["income"]["student_loan_interest"] = 0
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
            st.session_state.data = _generate_demo_data()
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

    st.divider()
    st.markdown("### About This App")
    st.markdown(f'''<div class="card">
        <p style="margin:0 0 0.75rem;"><strong>Budget Tracker</strong> — a personal finance management tool built by
            <a href="https://masonjbennett.com" target="_blank" style="color:{BLUE}; text-decoration:none; font-weight:500;">Mason Bennett</a>.</p>
        <p style="color:{TEXT_DIM}; margin:0 0 0.5rem; font-size:0.85rem;">
            Designed for early-career finance professionals. Features 11 tools covering income planning,
            budgeting, expense tracking, net worth, debt payoff optimization, savings goals, investment modeling,
            FIRE planning, and tax estimation.
        </p>
        <p style="color:{TEXT_DIM}; margin:0 0 0.5rem; font-size:0.85rem;">
            <strong>Tax data:</strong> Official IRS 2026 brackets (Rev. Proc. 2025-32), all 50 states + DC,
            SALT cap updated per OBBBA. 401(k) limit $24,500, SS wage base $184,500, HSA $4,400.
        </p>
        <p style="color:{TEXT_DIM}; margin:0; font-size:0.85rem;">
            <strong>Built with:</strong> Python, Streamlit, Plotly, Pandas &nbsp;&middot;&nbsp;
            <a href="https://github.com/masonjbennett/budgeting-app" target="_blank" style="color:{BLUE}; text-decoration:none;">View source on GitHub</a>
        </p>
    </div>''', unsafe_allow_html=True)

    auto_save_debounced(data)
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
