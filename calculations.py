"""Pure calculation engine for the budget app — tax, debt, investments.

Stdlib only, on purpose. Nothing here imports streamlit, plotly, pandas or
numpy, so it can be imported by the Streamlit app, by a test suite, or by an
HTTP backend if the front end is ever rebuilt.

WHY THIS MODULE EXISTS. This maths had drifted into three copies that no longer
agreed with each other:

  * budget_app.py               — the code that actually ran
  * test_stress.py              — a hand-copied mirror, which is why its 64
                                  assertions stayed green from April to
                                  September while never touching the app; by
                                  then its calc_fica had no filing-status
                                  argument and its project_investment had no
                                  contribution growth
  * budget-app-v2/backend/      — a second hand-copied mirror, forked in April
                                  for a Next.js rewrite, still carrying the
                                  debt-payoff bug and the state top-bracket bug

Three implementations, three answers. Everything below is now the only copy;
budget_app.py imports from here, and so does every test. Anything added here
must stay free of framework imports, or the next front end starts a fourth copy.

TAX DATA is official IRS 2026 — Rev. Proc. 2025-32 as amended by the OBBBA.
Do not change a number here without a source; see CLAUDE.md for the citations.
"""

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
    "California": {"brackets": [(10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06), (68350, 0.08), (349137, 0.093), (418961, 0.103), (698271, 0.113), (float("inf"), 0.123)], "deduction": 5540, "deduction_mfj": 11080},
    "Colorado": {"brackets": [(float("inf"), 0.044)], "deduction": 15700},
    "Connecticut": {"brackets": [(10000, 0.03), (50000, 0.05), (100000, 0.055), (200000, 0.06), (250000, 0.065), (500000, 0.069), (float("inf"), 0.0699)],
                     "brackets_mfj": [(20000, 0.03), (100000, 0.05), (200000, 0.055), (400000, 0.06), (500000, 0.065), (1000000, 0.069), (float("inf"), 0.0699)],
                     "deduction": 0, "deduction_mfj": 0},
    "Delaware": {"brackets": [(2000, 0.0), (5000, 0.022), (10000, 0.039), (20000, 0.048), (25000, 0.052), (60000, 0.0555), (float("inf"), 0.066)], "deduction": 3250},
    "Florida": {"brackets": [], "deduction": 0},
    "Georgia": {"brackets": [(float("inf"), 0.0519)], "deduction": 12000},
    "Hawaii": {"brackets": [(2400, 0.014), (4800, 0.032), (9600, 0.055), (14400, 0.064), (19200, 0.068), (24000, 0.072), (36000, 0.076), (48000, 0.079), (150000, 0.0825), (175000, 0.09), (200000, 0.10), (float("inf"), 0.11)], "deduction": 2200},
    "Idaho": {"brackets": [(float("inf"), 0.053)], "deduction": 14700},
    "Illinois": {"brackets": [(float("inf"), 0.0495)], "deduction": 0},
    "Indiana": {"brackets": [(float("inf"), 0.0295)], "deduction": 0},
    "Iowa": {"brackets": [(float("inf"), 0.0295)], "deduction": 2210},
    "Kansas": {"brackets": [(15000, 0.031), (30000, 0.0525), (float("inf"), 0.057)], "deduction": 3500},
    "Kentucky": {"brackets": [(float("inf"), 0.035)], "deduction": 3160},
    "Louisiana": {"brackets": [(float("inf"), 0.03)], "deduction": 0},
    "Maine": {"brackets": [(24500, 0.058), (58050, 0.0675), (float("inf"), 0.0715)], "deduction": 14600},
    "Maryland": {"brackets": [(1000, 0.02), (2000, 0.03), (3000, 0.04), (100000, 0.0475), (125000, 0.05), (150000, 0.0525), (250000, 0.055), (float("inf"), 0.0575)],
                  "brackets_mfj": [(1000, 0.02), (2000, 0.03), (3000, 0.04), (150000, 0.0475), (175000, 0.05), (225000, 0.0525), (300000, 0.055), (float("inf"), 0.0575)],
                  "deduction": 2550, "deduction_mfj": 5100},
    "Massachusetts": {"brackets": [(float("inf"), 0.05)], "deduction": 0},
    "Michigan": {"brackets": [(float("inf"), 0.0405)], "deduction": 5400},
    "Minnesota": {"brackets": [(33310, 0.0535), (109430, 0.068), (203150, 0.0785), (float("inf"), 0.0985)],
                   "brackets_mfj": [(48700, 0.0535), (193480, 0.068), (337930, 0.0785), (float("inf"), 0.0985)],
                   "deduction": 14575, "deduction_mfj": 29150},
    "Mississippi": {"brackets": [(10000, 0.04), (float("inf"), 0.04)], "deduction": 2300},
    "Missouri": {"brackets": [(1207, 0.02), (2414, 0.025), (3621, 0.03), (4828, 0.035), (6035, 0.04), (7242, 0.045), (8449, 0.05), (float("inf"), 0.048)], "deduction": 14600},
    "Montana": {"brackets": [(20500, 0.047), (float("inf"), 0.0565)], "deduction": 14600},
    "Nebraska": {"brackets": [(3700, 0.0246), (22170, 0.0351), (35730, 0.0455), (float("inf"), 0.0455)], "deduction": 8200},
    "Nevada": {"brackets": [], "deduction": 0},
    "New Hampshire": {"brackets": [], "deduction": 0},
    "New Jersey": {"brackets": [(20000, 0.014), (35000, 0.0175), (40000, 0.035), (75000, 0.05525), (500000, 0.0637), (1000000, 0.0897), (float("inf"), 0.1075)],
                    "brackets_mfj": [(20000, 0.014), (50000, 0.0175), (70000, 0.035), (80000, 0.05525), (150000, 0.0637), (500000, 0.0897), (1000000, 0.1075), (float("inf"), 0.1075)],
                    "deduction": 0, "deduction_mfj": 0},
    "New Mexico": {"brackets": [(5500, 0.015), (16500, 0.032), (33500, 0.043), (66500, 0.047), (210000, 0.049), (float("inf"), 0.059)],
                    "brackets_mfj": [(8000, 0.015), (25000, 0.032), (50000, 0.043), (100000, 0.047), (315000, 0.049), (float("inf"), 0.059)],
                    "deduction": 14600, "deduction_mfj": 29200},
    "New York": {"brackets": [(8500, 0.04), (11700, 0.045), (13900, 0.0525), (80650, 0.055), (215400, 0.06), (1077550, 0.0685), (5000000, 0.0965), (25000000, 0.103), (float("inf"), 0.109)],
                  "brackets_mfj": [(17150, 0.04), (23600, 0.045), (27900, 0.0525), (161550, 0.055), (323200, 0.06), (2155350, 0.0685), (5000000, 0.0965), (25000000, 0.103), (float("inf"), 0.109)],
                  "deduction": 8000, "deduction_mfj": 16050},
    "North Carolina": {"brackets": [(float("inf"), 0.0399)], "deduction": 14600},
    "North Dakota": {"brackets": [(44725, 0.0195), (float("inf"), 0.025)], "deduction": 14600},
    "Ohio": {"brackets": [(26050, 0.0), (float("inf"), 0.0275)], "deduction": 0},
    "Oklahoma": {"brackets": [(7200, 0.025), (12200, 0.035), (float("inf"), 0.045)],
                  "brackets_mfj": [(12200, 0.025), (24400, 0.035), (float("inf"), 0.045)],
                  "deduction": 7350, "deduction_mfj": 14700},
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
    "Wisconsin": {"brackets": [(14680, 0.035), (29370, 0.044), (323290, 0.053), (float("inf"), 0.0765)],
                   "brackets_mfj": [(19580, 0.035), (39150, 0.044), (431060, 0.053), (float("inf"), 0.0765)],
                   "deduction": 13230, "deduction_mfj": 24440},
    "Wyoming": {"brackets": [], "deduction": 0},
    "District of Columbia": {"brackets": [(10000, 0.04), (40000, 0.06), (60000, 0.065), (250000, 0.085), (500000, 0.0925), (1000000, 0.0975), (float("inf"), 0.1075)], "deduction": 14600},
}

FICA_SS_RATE = 0.062
FICA_SS_CAP = 184_500  # 2026 Social Security wage base (SSA official)
FICA_MEDICARE_RATE = 0.0145
FICA_MEDICARE_SURTAX = 0.009
FICA_MEDICARE_SURTAX_THRESHOLDS = {
    "Single": 200_000, "Head of Household": 200_000,
    "Married Filing Jointly": 250_000, "Married Filing Separately": 125_000,
}
SALT_CAP_BASE = 40_400       # 2026 OBBBA base cap
SALT_CAP_FLOOR = 10_000      # Cap can never go below this
SALT_PHASEOUT_THRESHOLD = {   # MAGI where phase-out begins
    "Single": 505_000, "Head of Household": 505_000,
    "Married Filing Jointly": 505_000, "Married Filing Separately": 252_500,
}
SALT_PHASEOUT_RATE = 0.30     # 30% of MAGI above threshold


def calc_salt_cap(magi, filing="Single"):
    """Calculate effective SALT cap after OBBBA phase-out."""
    threshold = SALT_PHASEOUT_THRESHOLD.get(filing, 505_000)
    mfs_cap = SALT_CAP_BASE // 2 if filing == "Married Filing Separately" else SALT_CAP_BASE
    if magi <= threshold:
        return mfs_cap
    reduction = SALT_PHASEOUT_RATE * (magi - threshold)
    return max(SALT_CAP_FLOOR, mfs_cap - reduction)


# Cost of living index by metro area (US avg = 100)
# Source: AdvisorSmith / BEA Regional Price Parities, 2024-2025 data
COL_INDEX = {
    "National Average": 100.0,
    "New York, NY": 187.2, "San Francisco, CA": 179.6, "Los Angeles, CA": 166.2,
    "Washington, DC": 152.1, "Boston, MA": 148.4, "San Diego, CA": 146.5,
    "Seattle, WA": 143.3, "Miami, FL": 133.8, "Denver, CO": 128.9,
    "Chicago, IL": 117.3, "Portland, OR": 120.4, "Austin, TX": 103.4,
    "Philadelphia, PA": 114.8, "Minneapolis, MN": 108.2, "Nashville, TN": 103.1,
    "Atlanta, GA": 105.7, "Dallas, TX": 104.8, "Houston, TX": 96.5,
    "Charlotte, NC": 98.4, "Phoenix, AZ": 100.7, "Las Vegas, NV": 102.3,
    "Tampa, FL": 99.5, "Raleigh, NC": 102.9, "Columbus, OH": 93.8,
    "Salt Lake City, UT": 104.2, "Detroit, MI": 89.4, "St. Louis, MO": 87.1,
    "Kansas City, MO": 91.2, "Indianapolis, IN": 90.3, "Cincinnati, OH": 90.9,
    "Pittsburgh, PA": 92.4, "Cleveland, OH": 88.7, "San Antonio, TX": 89.9,
    "Jacksonville, FL": 96.1, "Oklahoma City, OK": 87.3, "Louisville, KY": 91.8,
    "Memphis, TN": 84.2, "Birmingham, AL": 88.1, "Buffalo, NY": 93.5,
    "Richmond, VA": 101.3, "Honolulu, HI": 192.9, "Anchorage, AK": 127.4,
    "Fayetteville, AR": 84.5,
}


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


def calc_social_security(annual_salary, claiming_age=67):
    """Estimate monthly SS benefit using 2026 bend points. Simplified: assumes salary = career avg."""
    # 2026 bend points (for workers turning 62 in 2026)
    aime = min(annual_salary, FICA_SS_CAP) / 12  # Average Indexed Monthly Earnings
    # PIA = 90% of first $1,286 + 32% of $1,286-$7,749 + 15% above $7,749
    if aime <= 1286:
        pia = aime * 0.90
    elif aime <= 7749:
        pia = 1286 * 0.90 + (aime - 1286) * 0.32
    else:
        pia = 1286 * 0.90 + (7749 - 1286) * 0.32 + (aime - 7749) * 0.15
    # Adjust for claiming age (FRA = 67 for anyone born 1960+)
    fra = 67
    if claiming_age < fra:
        months_early = (fra - claiming_age) * 12
        if months_early <= 36:
            reduction = months_early * (5/9/100)  # 5/9% per month for first 36
        else:
            reduction = 36 * (5/9/100) + (months_early - 36) * (5/12/100)
        pia *= (1 - reduction)
    elif claiming_age > fra:
        months_late = min((claiming_age - fra) * 12, 36)  # max age 70
        pia *= (1 + months_late * (8/12/100))  # 8% per year delayed
    return max(0, pia)


def calc_student_loan_deduction(interest_paid, magi, filing="Single"):
    """Calculate above-the-line student loan interest deduction (max $2,500)."""
    if filing == "Married Filing Separately":
        return 0  # MFS cannot claim
    max_ded = 2_500
    if filing == "Married Filing Jointly":
        lower, upper = 175_000, 205_000
    else:  # Single, HoH
        lower, upper = 85_000, 100_000
    if magi <= lower:
        return min(interest_paid, max_ded)
    if magi >= upper:
        return 0
    reduction = (magi - lower) / (upper - lower)
    return min(interest_paid, max_ded) * (1 - reduction)


def calc_federal_tax(gross, deductions_401k=0, other_pretax=0, filing="Single",
                     student_loan_interest=0, charitable_cash=0):
    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])
    standard = STANDARD_DEDUCTION_2026.get(filing, 15_700)
    agi = gross - deductions_401k - other_pretax
    # Above-the-line deductions (reduce AGI)
    sl_deduction = calc_student_loan_deduction(student_loan_interest, agi, filing)
    agi -= sl_deduction
    # OBBBA 2026: non-itemizer charitable deduction (above-the-line, standard deduction filers)
    non_itemizer_limit = 2000 if filing == "Married Filing Jointly" else 1000
    charitable_atl = min(charitable_cash, non_itemizer_limit)
    agi -= charitable_atl
    taxable = max(0, agi - standard)
    tax = calc_bracket_tax(taxable, brackets)
    return tax, agi, taxable, standard


def _get_state_brackets_for_filing(sdata, filing):
    """Get the appropriate brackets and deduction for a filing status."""
    is_joint = filing == "Married Filing Jointly"
    if not is_joint:
        return sdata["brackets"], sdata["deduction"]
    # Check for explicit MFJ brackets first
    if "brackets_mfj" in sdata:
        return sdata["brackets_mfj"], sdata.get("deduction_mfj", sdata["deduction"] * 2)
    # Auto-double the bracket ceilings for MFJ (standard for most states)
    mfj_brackets = []
    for ceiling, rate in sdata["brackets"]:
        mfj_ceiling = ceiling * 2 if ceiling != float("inf") else float("inf")
        mfj_brackets.append((mfj_ceiling, rate))
    mfj_deduction = sdata.get("deduction_mfj", sdata["deduction"] * 2)
    return mfj_brackets, mfj_deduction


def calc_state_tax(gross, state, deductions_401k=0, other_pretax=0, filing="Single"):
    sdata = STATE_TAX_DATA.get(state)
    if not sdata or not sdata["brackets"]:
        return 0.0
    agi = gross - deductions_401k - other_pretax
    brackets, deduction = _get_state_brackets_for_filing(sdata, filing)
    taxable = max(0, agi - deduction)
    return calc_bracket_tax(taxable, brackets)


def calc_fica(gross, filing="Single"):
    ss = min(gross, FICA_SS_CAP) * FICA_SS_RATE
    medicare = gross * FICA_MEDICARE_RATE
    surtax_threshold = FICA_MEDICARE_SURTAX_THRESHOLDS.get(filing, 200_000)
    if gross > surtax_threshold:
        medicare += (gross - surtax_threshold) * FICA_MEDICARE_SURTAX
    return ss + medicare


def get_marginal_rate(taxable, brackets):
    prev = 0
    for ceiling, rate in brackets:
        if taxable <= ceiling:
            return rate * 100
        prev = ceiling
    return brackets[-1][1] * 100


def project_investment(start, monthly, rate, years, contribution_growth=0):
    values = [start]
    contributions = [start]
    r = rate / 100 / 12
    g = contribution_growth / 100 / 12  # monthly growth rate
    current_monthly = monthly
    for m in range(1, years * 12 + 1):
        if m > 1 and m % 12 == 1:  # annual raise applied at start of each year
            current_monthly = monthly * (1 + contribution_growth / 100) ** ((m - 1) // 12)
        prev = values[-1]
        values.append(prev * (1 + r) + current_monthly)
        contributions.append(contributions[-1] + current_monthly)
    return values, contributions


def payoff_order(debts, strategy):
    """The order debts are attacked in, fixed for the whole simulation.

    Snowball is defined by the balance you STARTED with, and that order is held
    to the end. Re-deriving it from live balances every month lets the target
    change when some other debt's own large minimum drags it below the one being
    attacked — the method then walks away from a nearly-cleared debt, which is
    the opposite of what a snowball is.
    """
    if strategy == "avalanche":
        return [d["name"] for d in sorted(debts, key=lambda d: -float(d["rate"]))]
    return [d["name"] for d in sorted(debts, key=lambda d: float(d["balance"]))]


def simulate_payoff(debts, extra, strategy):
    balances = {d["name"]: float(d["balance"]) for d in debts}
    rates = {d["name"]: d["rate"] / 100 / 12 for d in debts}
    mins = {d["name"]: float(d["min_payment"]) for d in debts}
    order_all = payoff_order(debts, strategy)
    total_interest = 0
    months = 0
    schedule = []
    payoff_months = {}  # Track when each debt hits $0
    max_months = 600

    # Check if payments can make progress
    total_min = sum(mins.values()) + extra
    total_monthly_interest = sum(b * r for b, r in zip(balances.values(), rates.values()) if b > 0)
    if total_min <= 0:
        return -1, 0, [], {}
    if total_min <= total_monthly_interest and total_monthly_interest > 0:
        return -1, 0, [], {}

    while any(b > 0.01 for b in balances.values()) and months < max_months:
        months += 1
        month_interest = 0
        for name in balances:
            if balances[name] > 0:
                interest = balances[name] * rates[name]
                balances[name] += interest
                month_interest += interest
                total_interest += interest

        # The whole payment capacity is available every month — the user's extra
        # PLUS every minimum, including the minimums of debts already cleared.
        #
        # This is the fix for the bug this function shipped with. It used to
        # start from `extra` alone and skip a cleared debt's minimum entirely, so
        # that money simply stopped being spent. Rolling a freed minimum onto the
        # next target IS the snowball, and avalanche works the same way. On a
        # card/car/student-loan profile the old behaviour reported payoff 23
        # months late and interest 19% high, and it penalised snowball hardest,
        # because momentum is the whole of snowball's case — so the page's
        # headline comparison reported an avalanche advantage that wasn't there.
        budget = extra + sum(mins.values())

        for name in balances:
            if balances[name] > 0:
                payment = min(mins[name], balances[name], budget)
                balances[name] -= payment
                budget -= payment

        for name in order_all:
            if budget <= 0:
                break
            if balances[name] > 0:
                payment = min(budget, balances[name])
                balances[name] -= payment
                budget -= payment

        # Check if any debt just got paid off
        for name in balances:
            if balances[name] <= 0.01 and name not in payoff_months:
                payoff_months[name] = months

        schedule.append({
            "month": months,
            "total_balance": sum(max(0, b) for b in balances.values()),
            "interest": month_interest,
        })

    return months, total_interest, schedule, payoff_months
