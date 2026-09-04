"""The app's starting data — the empty profile, and the demo profile.

Data, not maths, so it is here rather than in calculations.py. It is a separate
stdlib-only module for the same reason that one is: budget_app.py (Streamlit)
and web/api/index.py (the Next.js backend) both need it, and a demo profile
retyped for the second front end is a demo profile that drifts. The abandoned
2026 scaffold had already done exactly that, and its copy shipped ONE debt —
which makes avalanche and snowball identical by definition and silently removes
the comparison the debt page exists to show. test_calc.py asserts against that.

The demo's dates are RELATIVE to today, always. Hardcoding them gives a demo
that reads as abandoned within a month.
"""

import uuid
from datetime import date, timedelta


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


def _zeroed(value):
    """Every number in a nested structure, set to zero; every list emptied.

    Generic rather than a second literal profile, and that is the point: a
    money field added to `get_default_state` later is zeroed here without
    anybody remembering to, whereas a hand-written copy would quietly ship the
    new field's default as a "simulated value". Strings survive, because a
    state and a filing status are selections rather than figures.
    """
    if isinstance(value, dict):
        return {k: _zeroed(v) for k, v in value.items()}
    if isinstance(value, list):
        return []
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return value
    return 0


def empty_profile():
    """The profile behind "Start empty" — the same shape, with no figures.

    Derived from `get_default_state` so the two cannot drift apart in SHAPE,
    which is the property both front ends and the import path depend on.

    Two things are deliberately not zero, because zero is not "unset" for
    either and a zero would make the page they drive nonsense rather than
    empty: the expected RETURN and the HORIZON on the investment projection.
    They are assumptions, not money — a 0% return over 0 years is not a blank
    projection, it is a broken one.
    """
    base = get_default_state()
    out = _zeroed(base)
    for k in ("annual_return", "time_horizon"):
        out["investment"][k] = base["investment"][k]
    return out


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


def _make_id():
    return str(uuid.uuid4())[:8]


def _ensure_expense_ids(expenses):
    for e in expenses:
        if "id" not in e:
            e["id"] = _make_id()
    return expenses
