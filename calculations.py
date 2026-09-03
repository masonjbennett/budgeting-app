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

import random as _random

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
# Where the 37% bracket begins, by filing status — used to warn about the OBBBA
# 2/37 limitation on itemized deductions, which this app states rather than models.
TOP_BRACKET_START = {
    "Single": 640_600,
    "Married Filing Jointly": 768_700,
    "Married Filing Separately": 384_350,
    "Head of Household": 640_600,
}

# Annual contribution limits. These were literals in seven places across
# budget_app.py — six copies of 24_500 and one of 4_400 — which made the January
# refresh a hunt rather than an edit. Named here so there is one number to change.
K401_LIMIT = 24_500            # 2026 elective deferral limit (IRS Notice 2025-67)
HSA_INDIVIDUAL_LIMIT = 4_400   # 2026 self-only HSA limit (Rev. Proc. 2025-19)

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



def calc_itemized_total(itemized, agi, filing="Single"):
    """Deductible itemized total and its parts, under the 2026 OBBBA rules.

    Extracted from the Tax page, which had the only implementation. Take-home
    needed the same number, and a second copy of four floor-and-cap rules is how
    the two pages would have started disagreeing about the same taxpayer.

    Floors are read off AGI *before* the non-itemizer charitable deduction. That
    deduction is only available to someone taking the standard deduction, so on
    the itemizing branch it does not exist; the simplification is worth at most a
    few dollars of floor and keeps the two branches from depending on each other.
    """
    it = itemized or {}
    agi = max(0.0, float(agi or 0))
    salt = min(float(it.get("salt", 0) or 0), calc_salt_cap(agi, filing))
    mortgage = float(it.get("mortgage_interest", 0) or 0)
    # OBBBA 2026: an itemizer deducts only charity ABOVE 0.5% of AGI.
    charitable = max(0.0, float(it.get("charitable", 0) or 0) - agi * 0.005)
    # Medical above 7.5% of AGI.
    medical = max(0.0, float(it.get("medical", 0) or 0) - agi * 0.075) if agi > 0 else 0.0
    return {
        "salt": salt, "mortgage_interest": mortgage,
        "charitable": charitable, "medical": medical,
        "total": salt + mortgage + charitable + medical,
        # The floors are returned so the page can explain why a figure was
        # reduced without re-deriving the rule and drifting from it.
        "charitable_floor": agi * 0.005,
        "medical_floor": agi * 0.075,
        "salt_cap": calc_salt_cap(agi, filing),
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
                     student_loan_interest=0, charitable_cash=0, itemized_total=0):
    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])
    standard = STANDARD_DEDUCTION_2026.get(filing, 15_700)
    agi = gross - deductions_401k - other_pretax
    # Above-the-line deductions (reduce AGI)
    sl_deduction = calc_student_loan_deduction(student_loan_interest, agi, filing)
    agi -= sl_deduction

    # A taxpayer takes whichever deduction is larger. This used to force the
    # standard deduction unconditionally, so the Tax page could tell someone
    # itemizing saved them money while take-home, savings rate, dashboard cash
    # flow and the FIRE timeline all quietly assumed they had not.
    itemizing = float(itemized_total or 0) > standard

    # OBBBA 2026: the above-the-line charitable deduction is for NON-itemizers.
    # An itemizer already deducts charity inside their itemized total, so
    # granting both would deduct the same donation twice.
    if not itemizing:
        non_itemizer_limit = 2000 if filing == "Married Filing Jointly" else 1000
        agi -= min(charitable_cash, non_itemizer_limit)

    deduction = max(standard, float(itemized_total or 0))
    taxable = max(0, agi - deduction)
    tax = calc_bracket_tax(taxable, brackets)
    # The fourth value is the deduction ACTUALLY taken, which equals `standard`
    # whenever itemized_total is 0 — so every existing caller is unaffected.
    return tax, agi, taxable, deduction


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


def calc_state_marginal_rate(gross, state, deductions_401k=0, other_pretax=0, filing="Single"):
    """The rate the NEXT dollar of state income tax is charged at, as a percent.

    The signature deliberately mirrors calc_state_tax. The marginal rate has to be
    read off the same taxable base as the tax itself, and sharing an argument list
    is what stops the two drifting onto different bases.

    Three call sites used to read `sdata["brackets"][-1][1]` — the state's TOP
    bracket — and label it the user's marginal rate. For anyone not already in the
    top band that overstates the value of a pre-tax dollar: at $110K in New York it
    read 10.9% against a real 6.0%, putting the advertised 401(k) tax saving on a
    $24,500 contribution at $8,060 against a true $6,860. It survived five months
    because the app's own author is in Arkansas, where $85K is already the top
    bracket and the error is exactly zero.
    """
    sdata = STATE_TAX_DATA.get(state)
    if not sdata or not sdata.get("brackets"):
        return 0.0
    brackets, deduction = _get_state_brackets_for_filing(sdata, filing)
    taxable = max(0, gross - deductions_401k - other_pretax - deduction)
    if taxable <= 0:
        return 0.0
    return get_marginal_rate(taxable, brackets)


def marginal_fica_rate(base, raised, filing="Single"):
    """The FICA rate on the INCREMENT between two salaries, as a fraction.

    Not the same as the average rate, and the gap is largest exactly where this
    is used. Above the Social Security wage base ($184,500) the marginal FICA on
    a raise falls from 7.65% to 1.45%, because the 6.2% has already stopped —
    so charging a raise the average rate can overstate the tax on it by a factor
    of five.
    """
    if raised <= base:
        return 0.0
    return (calc_fica(raised, filing) - calc_fica(base, filing)) / (raised - base)


def get_marginal_rate(taxable, brackets):
    prev = 0
    for ceiling, rate in brackets:
        if taxable <= ceiling:
            return rate * 100
        prev = ceiling
    return brackets[-1][1] * 100


def compute_take_home(income, itemized=None):
    """The whole pay stub for one income profile: taxes, deductions, take-home.

    Everything downstream runs through this — savings rate, dashboard cash flow,
    the budget page's income line, the FIRE timeline — so it is the single most
    load-bearing function in the app.

    It lived in budget_app.py until September 2026 and read a module-global
    `data` dict for the itemized deductions, which meant two things. Nothing
    could import it without importing Streamlit, so it was covered by zero of
    the 239 assertions; and its answer depended on state it was not passed. Both
    are fixed by taking `itemized` as an argument.

    `income` keys: gross_salary, state, filing_status, contribution_401k (a
    PERCENT of salary), health_insurance and hsa (both MONTHLY), and optionally
    bonus_amount, bonus_type, student_loan_interest.
    `itemized` is the itemized-deduction input dict, or None for none.
    """
    itemized_input = itemized or {}

    gross = income["gross_salary"]
    bonus = income.get("bonus_amount", 0)
    bonus_type = income.get("bonus_type", "None")
    filing = income.get("filing_status", "Single")
    annual_gross = gross + (bonus if bonus_type != "None" else 0)

    contrib_401k_annual = min(gross * income["contribution_401k"] / 100, K401_LIMIT)
    health_annual = income["health_insurance"] * 12
    hsa_annual = income["hsa"] * 12
    sl_interest = income.get("student_loan_interest", 0)
    pretax = contrib_401k_annual + health_annual + hsa_annual
    charitable = itemized_input.get("charitable", 0)

    # The itemized total depends on AGI, and AGI does not depend on it, so run the
    # federal calculation once to get AGI, work out the itemized total against it,
    # then run it again with that total. Two passes rather than one because the
    # 0.5% charitable and 7.5% medical floors are both percentages OF AGI.
    _, agi_only, _, _ = calc_federal_tax(
        annual_gross, contrib_401k_annual, health_annual + hsa_annual, filing,
        sl_interest, charitable)
    itemized_totals = calc_itemized_total(itemized_input, agi_only, filing)
    fed_tax, agi, taxable, deduction_taken = calc_federal_tax(
        annual_gross, contrib_401k_annual, health_annual + hsa_annual, filing,
        sl_interest, charitable, itemized_totals["total"])
    state_tax = calc_state_tax(
        annual_gross, income["state"], contrib_401k_annual, health_annual + hsa_annual, filing)
    fica = calc_fica(annual_gross, filing)

    total_tax = fed_tax + state_tax + fica
    annual_take_home = annual_gross - pretax - total_tax
    brackets = FEDERAL_BRACKETS_2026.get(filing, FEDERAL_BRACKETS_2026["Single"])
    std_ded = STANDARD_DEDUCTION_2026.get(filing, 15_700)

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
        "monthly_take_home": annual_take_home / 12,
        "agi": agi,
        "taxable": taxable,
        "std_ded": std_ded,
        "deduction_taken": deduction_taken,
        "itemized_total": itemized_totals["total"],
        "itemizing": deduction_taken > std_ded,
        "effective_rate": (total_tax / annual_gross * 100) if annual_gross else 0,
        "marginal_fed": get_marginal_rate(taxable, brackets),
        # Read off the same base as state_tax above, not the state's top bracket.
        "marginal_state": calc_state_marginal_rate(
            annual_gross, income["state"], contrib_401k_annual,
            health_annual + hsa_annual, filing),
        "filing": filing,
    }


def roth_vs_traditional(contribution, current_rate, future_rate, annual_return, years):
    """Compare a pre-tax and a post-tax contribution of the same headline size.

    Traditional contributes the full amount, grows it, and is taxed on the way
    out. Roth pays tax first — so it invests LESS — and is not taxed again. Both
    grow as an annuity due: the contribution is made at the start of each year.

    `current_rate` and `future_rate` are FRACTIONS, not percents, and the
    current one is the combined federal + state marginal rate. Getting that
    wrong is not academic: budget-app-v2's fork of this used the federal rate
    alone, which understates the tax paid now and so overstates Roth's balance
    by the whole state component.
    """
    r = annual_return / 100.0

    # Grouped exactly as the Streamlit page grouped it, so the amounts are
    # bit-identical to what that page has always shown.
    if r > 0:
        trad_future = contribution * ((1 + r) ** years - 1) / r * (1 + r)
        roth_invested = contribution * (1 - current_rate)
        roth_future = roth_invested * ((1 + r) ** years - 1) / r * (1 + r)
    else:
        trad_future = contribution * years
        roth_invested = contribution * (1 - current_rate)
        roth_future = roth_invested * years
    trad_after_tax = trad_future * (1 - future_rate)

    # The verdict is decided on the RATES, not by comparing the two balances.
    # trad = C*g*(1-future) beats roth = C*(1-current)*g exactly when
    # current > future — whatever the contribution, the return or the horizon.
    # Comparing the balances instead makes the answer depend on float noise: at
    # equal rates the two are mathematically identical, and over a 1,600-case
    # grid the old inline version called 26 such ties both ways, sometimes on a
    # gap of 9e-10 and sometimes on a gap of exactly zero. It could also
    # contradict the page's own recommendation box one card away, which was
    # already keyed to the rates.
    if current_rate > future_rate:
        better = "Traditional"
    elif future_rate > current_rate:
        better = "Roth"
    else:
        better = "Equivalent"

    return {
        "contribution": contribution,
        "traditional_future": trad_future,
        "traditional_after_tax": trad_after_tax,
        "roth_invested": roth_invested,
        "roth_future": roth_future,
        "better": better,
        "difference": abs(trad_after_tax - roth_future),
        "current_rate": current_rate,
        "future_rate": future_rate,
    }


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


# ── Dashboard ratios ─────────────────────────────────────────────────

def monthly_debt_service(debts, budget_needs=None):
    """Total minimum monthly debt payments, and where the figure came from.

    Debts entered on the Debt Payoff page are authoritative when present. The
    dashboard used to read ONLY the budget category "Min. Debt Payments", so a
    user carrying three real debts who left that line at zero saw a
    debt-to-income ratio of 0.0%, labelled "Healthy" — which the demo data itself
    did, against $35,000 of student loans.

    Returns (amount, source) so the page can say which it used.
    """
    total = sum(float(d.get("min_payment") or 0) for d in (debts or []))
    if total > 0:
        return total, "debts"
    return float((budget_needs or {}).get("Min. Debt Payments", 0) or 0), "budget"


# Emergency-fund coverage has to decide which assets could actually be spent in
# an emergency, and the app stores no liquidity flag — users type their own asset
# labels — so the decision falls back to the name. That is unavoidable and
# imprecise; what matters is that it cannot fail SILENTLY, which is exactly what
# the old `assets["Savings"]` lookup did. Rename that row to "High-Yield Savings"
# and coverage read 0.0 months as though it had been measured.
LIQUID_HINTS = ("cash", "checking", "chequing", "saving", "money market",
                "emergency", "hysa", "high yield", "high-yield")
ILLIQUID_HINTS = ("401", "403", "457", "ira", "roth", "pension", "hsa", "annuity",
                  "property", "home", "house", "real estate", "land",
                  "car", "vehicle", "crypto", "brokerage", "taxable")


def liquid_assets(assets):
    """Assets spendable in an emergency: (total, names counted).

    The names come back so the page can print what it counted. A coverage figure
    that quietly excludes the account holding the money is worse than none.
    Illiquid hints are checked first, so "Roth IRA Savings" is excluded rather
    than counted on the strength of the word "savings".
    """
    counted, total = [], 0.0
    for name, value in (assets or {}).items():
        low = str(name).lower()
        if any(h in low for h in ILLIQUID_HINTS):
            continue
        if any(h in low for h in LIQUID_HINTS):
            counted.append(name)
            total += float(value or 0)
    return total, counted


def emergency_fund_months(assets, monthly_needs):
    """Months of essential spending covered: (months, names counted).

    months is None when it cannot be measured — no liquid asset matched, or no
    essential spending is budgeted. None and 0.0 are different answers and the
    page must not print them the same way.
    """
    total, counted = liquid_assets(assets)
    if not counted or not monthly_needs:
        return None, counted
    return total / monthly_needs, counted


# ──────────────────────────────────────────────
# MONTE CARLO RETIREMENT SIMULATION
# ──────────────────────────────────────────────
#
# This lived inline inside the FIRE page until September 2026 — not a function
# at all, just a block in the middle of a Streamlit callback — which is why it
# was the one calculation on the site with no assertions behind it, and why
# numpy was a dependency of the whole app.
#
# It does not need numpy. numpy supplied four things: normal draws, a 2x2
# Cholesky of a CONSTANT matrix, percentiles, and array storage. The Cholesky
# is worked out below by hand once; the rest is stdlib. Measured on the largest
# setting the UI offers (5,000 sims x 71 years): 0.91s.
#
# The randomness is deliberately kept OUT of the recurrence. `simulate_path`
# takes the return and inflation sequences as arguments, so the actual money
# arithmetic — the part that can be wrong — is exactly testable, and only the
# drawing of the numbers is stochastic.

MC_STOCK_MEAN = 0.10       # S&P 500 historical
MC_STOCK_STDEV = 0.18
MC_BOND_MEAN = 0.05
MC_BOND_STDEV = 0.06
MC_STOCK_BOND_CORR = 0.05
MC_INFLATION_STDEV = 0.015
MC_MAX_SAMPLE_PATHS = 50   # how many individual paths the fan chart draws

# Cholesky factor of [[1, r], [r, 1]] is [[1, 0], [r, sqrt(1 - r**2)]].
_MC_CHOL_21 = MC_STOCK_BOND_CORR
_MC_CHOL_22 = (1.0 - MC_STOCK_BOND_CORR ** 2) ** 0.5


def percentile(values, q):
    """The q-th percentile with linear interpolation.

    Matches numpy.percentile's default method exactly, which matters because
    this replaced np.percentile in a shipping page and the numbers on it must
    not move. test_calc.py asserts that against numpy over random data — numpy
    is an oracle for the test, never an import of this module.
    """
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    pos = (len(s) - 1) * (q / 100.0)
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return float(s[lo] + (s[hi] - s[lo]) * (pos - lo))


def portfolio_return(stock_z, bond_z, stock_pct):
    """One year's blended portfolio return from two CORRELATED standard normals."""
    stock_alloc = stock_pct / 100.0
    stock_ret = MC_STOCK_MEAN + MC_STOCK_STDEV * stock_z
    bond_ret = MC_BOND_MEAN + MC_BOND_STDEV * bond_z
    return stock_alloc * stock_ret + (1.0 - stock_alloc) * bond_ret


def simulate_path(current_age, retire_age, end_age, portfolio, annual_savings,
                  annual_expenses, inflation, returns, inflations):
    """One portfolio path, year by year. Deterministic given its sequences.

    Two phases. Before retirement the portfolio earns its return and receives
    savings grown at the EXPECTED inflation rate — a raise you can plan for.
    After retirement it earns its return and pays expenses grown at that year's
    REALISED inflation, compounded over the years already retired: the sequence
    of inflation you actually get is a risk, and modelling it as the average
    would remove the thing the simulation exists to measure.

    Once a path hits zero it stays at zero — a portfolio does not recover from
    having been spent. Returns (balances, failure_age); failure_age is None if
    the path survived. len(balances) == end_age - current_age + 1.
    """
    infl_mean = inflation / 100.0
    years = end_age - current_age
    balances = [float(portfolio)]
    balance = float(portfolio)
    failure_age = None

    for year in range(1, years + 1):
        if failure_age is not None:
            balances.append(0.0)
            continue
        age = current_age + year
        balance *= (1.0 + returns[year - 1])
        if age <= retire_age:
            balance += annual_savings * ((1.0 + infl_mean) ** year)
        else:
            realised = inflations[year - 1]
            balance -= annual_expenses * ((1.0 + realised) ** (age - retire_age))
        if balance <= 0:
            balance = 0.0
            failure_age = age
        balances.append(balance)

    return balances, failure_age


def run_monte_carlo(current_age, retire_age, end_age, portfolio, annual_savings,
                    annual_expenses, stock_pct=80, inflation=3.0, n_sims=1000,
                    seed=None):
    """Run n_sims correlated-return paths and summarise them.

    `sample_paths` is drawn HERE rather than at render time. The page used to
    pick 50 paths with np.random.choice while drawing the chart, so the sample
    changed on every Streamlit rerun — every widget touch redrew a different
    fifty. It is also the reason the full matrix is not returned: at 5,000 sims
    it is 355,000 numbers, of which the chart shows 50 paths' worth, and over
    HTTP that is several megabytes to throw away.
    """
    rng = _random.Random(seed)
    years = end_age - current_age
    ages = list(range(current_age, end_age + 1))
    infl_mean = inflation / 100.0

    if years <= 0 or n_sims <= 0:
        return {
            "ages": ages, "n_sims": 0, "success_count": 0, "success_rate": 0.0,
            "percentiles": {k: [] for k in ("p5", "p10", "p25", "p50", "p75", "p90", "p95")},
            "ending": [], "sample_paths": [], "failure_ages": [],
            "median_ending": 0.0, "p10_ending": 0.0, "p90_ending": 0.0,
            "retire_age": retire_age, "stock_pct": stock_pct,
        }

    columns = [[] for _ in range(years + 1)]
    ending = []
    failure_ages = []
    sample_paths = []

    for sim in range(n_sims):
        returns = []
        inflations = []
        for _ in range(years):
            z1 = rng.gauss(0.0, 1.0)
            z2 = rng.gauss(0.0, 1.0)
            returns.append(portfolio_return(z1, _MC_CHOL_21 * z1 + _MC_CHOL_22 * z2, stock_pct))
            inflations.append(max(0.0, rng.gauss(infl_mean, MC_INFLATION_STDEV)))

        balances, failure_age = simulate_path(
            current_age, retire_age, end_age, portfolio, annual_savings,
            annual_expenses, inflation, returns, inflations)

        for i, b in enumerate(balances):
            columns[i].append(b)
        ending.append(balances[-1])
        if failure_age is not None:
            failure_ages.append(failure_age)
        if sim < MC_MAX_SAMPLE_PATHS:
            sample_paths.append(balances)

    success_count = sum(1 for e in ending if e > 0)
    return {
        "ages": ages,
        "n_sims": n_sims,
        "success_count": success_count,
        "success_rate": success_count / n_sims * 100.0,
        "percentiles": {f"p{q}": [percentile(col, q) for col in columns]
                        for q in (5, 10, 25, 50, 75, 90, 95)},
        "ending": ending,
        "sample_paths": sample_paths,
        "failure_ages": failure_ages,
        "median_ending": percentile(ending, 50),
        "p10_ending": percentile(ending, 10),
        "p90_ending": percentile(ending, 90),
        "retire_age": retire_age,
        "stock_pct": stock_pct,
    }


# ═══════════════════════════════════════════════════════════════════════
# CASH FLOW — the month as a flow, for the Sankey
# ═══════════════════════════════════════════════════════════════════════

MONTHS_PER_YEAR = 12


def cash_flow(income, itemized=None, budget=None):
    """One month's money as a flow: gross in, and everything it becomes.

    Returns nodes and links for a Sankey. It lives here rather than in a route
    or a component for the usual reason — two front ends will want it, and a
    second copy is how this app's maths came to disagree with itself three
    times. What the caller gets is values; where they go on screen is geometry
    and belongs to the renderer.

    THE DIAGRAM BALANCES BY CONSTRUCTION, which is the whole reason it is worth
    drawing. `compute_take_home` defines annual_take_home as the REMAINDER
    after pre-tax and the three taxes, so stage one sums to gross exactly, to
    the cent, for every input. A Sankey whose stages did not sum would be a
    picture of a flow rather than a flow, and the reader has no way to tell
    those apart by looking. `balanced` and `residual` are returned so the
    renderer can refuse to draw one that does not.

    Two shapes have to be reported rather than drawn:
      - a figure that is genuinely ZERO (no state tax in Texas, no HSA) gets no
        node, because a zero-height ribbon with a label beside it reads as a
        rendering fault. They come back in `omitted` so the page can say which,
        rather than leaving the reader to notice an absence.
      - a plan that allocates MORE than take-home has no "unallocated" node and
        cannot be drawn as a flow at all — the outflow exceeds the inflow. That
        is `deficit`, and it is the budget page's over-allocated state showing
        up structurally.

    `budget` is the profile's budget dict: {"needs": {...}, "wants": {...},
    "savings": {...}}. Every figure returned is MONTHLY, because that is the
    unit the budget is kept in; the tax figures are annual and divided here so
    that no front end has to know which is which.
    """
    th = compute_take_home(income, itemized)
    b = budget or {}

    def monthly(annual):
        return annual / MONTHS_PER_YEAR

    gross = monthly(th["annual_gross"])
    take_home = monthly(th["annual_take_home"])

    nodes = []
    links = []
    omitted = []

    def add(node_id, label, column, value, tone, parent=None):
        """A node, unless it is worth nothing — then a note instead."""
        if value <= 0:
            omitted.append(label)
            return False
        nodes.append({"id": node_id, "label": label, "column": column,
                      "value": value, "tone": tone})
        if parent is not None:
            links.append({"source": parent, "target": node_id, "value": value})
        return True

    nodes.append({"id": "gross", "label": "Gross pay", "column": 0,
                  "value": gross, "tone": "ink"})

    # ── Stage one: what the gross becomes. Sums to gross exactly. ──
    stage_one = [
        ("pretax", "Pre-tax", monthly(th["pretax"]), "s4"),
        ("federal", "Federal tax", monthly(th["fed_tax"]), "critical"),
        ("state", "State tax", monthly(th["state_tax"]), "s5"),
        ("fica", "FICA", monthly(th["fica"]), "caution"),
        ("takehome", "Take-home", take_home, "accent"),
    ]
    for node_id, label, value, tone in stage_one:
        add(node_id, label, 1, value, tone, parent="gross")

    # ── Pre-tax, broken out. Terminal: this money leaves the picture. ──
    for node_id, label, value in (
        ("k401", "401(k)", monthly(th["contrib_401k"])),
        ("health", "Health premium", monthly(th["health"])),
        ("hsa", "HSA", monthly(th["hsa"])),
    ):
        add(node_id, label, 2, value, "s4", parent="pretax")

    # ── Stage two: what the take-home is planned to do. ──
    buckets = (
        ("needs", "Needs", b.get("needs") or {}, "s1"),
        ("wants", "Wants", b.get("wants") or {}, "s2"),
        ("savings", "Savings", b.get("savings") or {}, "s6"),
    )
    allocated = 0.0
    for key, label, lines, tone in buckets:
        total = sum(lines.values())
        allocated += total
        if not add(key, label, 2, total, tone, parent="takehome"):
            continue
        for name, amount in sorted(lines.items(), key=lambda kv: -kv[1]):
            if amount <= 0:
                continue
            nodes.append({"id": key + ":" + name, "label": name, "column": 3,
                          "value": amount, "tone": tone})
            links.append({"source": key, "target": key + ":" + name,
                          "value": amount})

    unallocated = take_home - allocated
    if unallocated > 0:
        nodes.append({"id": "unallocated", "label": "Unallocated", "column": 2,
                      "value": unallocated, "tone": "muted"})
        links.append({"source": "takehome", "target": "unallocated",
                      "value": unallocated})

    stage_one_total = sum(value for _, _, value, _ in stage_one)
    residual = gross - stage_one_total

    return {
        "nodes": nodes,
        "links": links,
        "gross": gross,
        "take_home": take_home,
        "allocated": allocated,
        "unallocated": max(0.0, unallocated),
        # Positive only when the plan spends more than the take-home covers.
        "deficit": max(0.0, -unallocated),
        "omitted": omitted,
        "residual": residual,
        "balanced": abs(residual) < 0.01,
    }


# ═══════════════════════════════════════════════════════════════════════
# THINGS THE ENGINE COULD ALREADY DO AND NO PAGE ASKED FOR
# ═══════════════════════════════════════════════════════════════════════

def employer_match(salary, contribution_pct, match_pct, match_limit):
    """What the employer adds to a 401(k), and what a low contribution forfeits.

    `contribution_pct` and `match_limit` are percentages OF SALARY;
    `match_pct` is what the employer pays per dollar you do (50 = fifty cents).

    The forfeited half is the point. It is the highest-value single sentence a
    budgeting app can say — an immediate, riskless return that no market
    assumption is needed to justify — and the web app rendered both inputs
    while the projection ignored them entirely.
    """
    matched_pct = min(max(contribution_pct, 0.0), max(match_limit, 0.0))
    per_dollar = max(match_pct, 0.0) / 100.0
    matched = salary * matched_pct / 100.0 * per_dollar
    shortfall_pct = max(0.0, match_limit - contribution_pct)
    missed = salary * shortfall_pct / 100.0 * per_dollar
    return {
        "annual_match": matched,
        "monthly_match": matched / MONTHS_PER_YEAR,
        "annual_missed": missed,
        "contribution_pct": contribution_pct,
        "match_limit": match_limit,
        "match_pct": match_pct,
        # True only when raising the contribution would collect more match.
        "leaving_money": missed > 0.005,
    }


def raise_impact(income, increase, itemized=None):
    """What a raise is actually worth, after everything it moves.

    Runs the WHOLE pay stub twice rather than applying a marginal rate to the
    increment, because a raise moves more than tax: a 401(k) set as a PERCENT of
    salary rises with it, so take-home grows by less than the after-tax raise
    and the difference is saved rather than lost. Reporting one number without
    that split is how a tool tells someone their raise vanished.

    FICA on the increment comes from `marginal_fica_rate`, not the average.
    Above the Social Security wage base the marginal rate falls from 7.65% to
    1.45% — for exactly the earners who ask this question.
    """
    itemized = itemized or {}
    before = compute_take_home(income, itemized)
    after_income = dict(income)
    after_income["gross_salary"] = income.get("gross_salary", 0) + increase
    after = compute_take_home(after_income, itemized)

    gross_increase = after["annual_gross"] - before["annual_gross"]
    tax_increase = after["total_tax"] - before["total_tax"]
    pretax_increase = after["pretax"] - before["pretax"]
    take_home_increase = after["annual_take_home"] - before["annual_take_home"]

    return {
        "base_salary": income.get("gross_salary", 0),
        "new_salary": after_income["gross_salary"],
        "increase": increase,
        "gross_increase": gross_increase,
        "tax_increase": tax_increase,
        # Not a loss: a percentage-based 401(k) rises with the salary.
        "pretax_increase": pretax_increase,
        "take_home_increase": take_home_increase,
        "monthly_take_home_increase": take_home_increase / MONTHS_PER_YEAR,
        "marginal_fed": after["marginal_fed"],
        "marginal_state": after["marginal_state"],
        "marginal_fica_pct": marginal_fica_rate(
            before["annual_gross"], after["annual_gross"],
            income.get("filing_status", "Single")) * 100,
        # Share of the raise lost to tax, and the share that reaches the bank.
        "tax_share_pct": (tax_increase / gross_increase * 100) if gross_increase else None,
        "kept_share_pct": (take_home_increase / gross_increase * 100) if gross_increase else None,
    }


def col_compare(salary, from_city, to_city):
    """The salary that buys the same life somewhere else.

    Buying power ONLY. It says nothing about tax, and the two cities can differ
    by tens of thousands on that alone — which is the whole reason the scenario
    comparison exists. Returns None where either city is unknown rather than
    falling back to the national average, because a silent default here is a
    wrong answer that looks like a right one.
    """
    a = COL_INDEX.get(from_city)
    b = COL_INDEX.get(to_city)
    if a is None or b is None or a <= 0:
        return None
    equivalent = salary * b / a
    return {
        "from_city": from_city,
        "to_city": to_city,
        "from_index": a,
        "to_index": b,
        "salary": salary,
        "equivalent_salary": equivalent,
        "difference": equivalent - salary,
        "pct_difference": (b - a) / a * 100,
    }


def top_bracket_limitation(taxable, filing="Single"):
    """Whether the OBBBA 2/37 limitation on itemized deductions is in play.

    In the top bracket, itemized deductions are worth 2/37 less than the
    marginal rate suggests. This app does NOT model it, so the only honest
    thing to do is say when it applies rather than quietly be wrong. The
    threshold is a bracket boundary, which is why it is read from the same
    table the tax is, and not typed again.
    """
    threshold = TOP_BRACKET_START.get(filing, TOP_BRACKET_START["Single"])
    return {
        "applies": taxable > threshold,
        "threshold": threshold,
        "filing": filing,
    }


def project_investment_with_match(start, monthly, rate, years, salary=0,
                                  contribution_pct=0, match_pct=0,
                                  match_limit=0, contribution_growth=0):
    """A projection that spends the employer's money too.

    The web app rendered the match inputs and then projected as though they
    were zero, which understates a matched 401(k) by the most reliable return
    in the whole model. The addition lives here rather than in the route
    because the route is a pass-through by design; with no salary the match is
    zero and this is `project_investment` exactly.
    """
    match = employer_match(salary, contribution_pct, match_pct, match_limit)
    values, contributions = project_investment(
        start, monthly + match["monthly_match"], rate, years, contribution_growth)
    return values, contributions, match
