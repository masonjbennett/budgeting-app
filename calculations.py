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

import math as _math
import random as _random
from datetime import date as _date

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


# ═══════════════════════════════════════════════════════════════════════
# SCENARIOS — the same person, in a different situation
# ═══════════════════════════════════════════════════════════════════════

def compare_scenarios(scenarios):
    """Several situations priced against each other, the first as the baseline.

    This is the screen no competitor has, and the reason is not effort — it is
    that comparing two jobs honestly needs a real tax engine for fifty states
    and four filing statuses, plus a cost-of-living index, and a tracker built
    on a bank connection has neither. Everything here is `compute_take_home`
    run once per scenario; nothing new is modelled.

    THE FIGURE THAT MATTERS IS `real_take_home` — annual take-home restated in
    national-average dollars, so a salary in one city can be set beside a
    salary in another. Take-home alone ranks the dearest city first, which is
    the wrong answer to the question people are actually asking. It is a
    deflation by the cost-of-living index and nothing more; it is labelled
    everywhere it appears, because a number that quietly rebases itself is
    worse than one that is merely wrong.

    Each scenario: {"name", "income", "itemized" (optional), "city" (optional)}.
    Returns rows in the order given, so the caller's baseline stays first.
    """
    if not scenarios:
        return {"rows": [], "baseline": None, "best": None}

    rows = []
    for s in scenarios:
        th = compute_take_home(s["income"], s.get("itemized") or {})
        city = s.get("city") or "National Average"
        index = COL_INDEX.get(city)
        real = th["annual_take_home"] * 100.0 / index if index else None
        rows.append({
            "name": s.get("name") or "Scenario",
            "city": city,
            # None where the city is not in the index — never a silent default.
            "col_index": index,
            "state": s["income"].get("state"),
            "filing": th["filing"],
            "gross": th["annual_gross"],
            "total_tax": th["total_tax"],
            "effective_rate": th["effective_rate"],
            "marginal_fed": th["marginal_fed"],
            "marginal_state": th["marginal_state"],
            "pretax": th["pretax"],
            "annual_take_home": th["annual_take_home"],
            "monthly_take_home": th["monthly_take_home"],
            "real_take_home": real,
        })

    base = rows[0]
    for r in rows:
        r["vs_baseline"] = r["annual_take_home"] - base["annual_take_home"]
        r["vs_baseline_real"] = (
            r["real_take_home"] - base["real_take_home"]
            if r["real_take_home"] is not None and base["real_take_home"] is not None
            else None
        )

    # Best on the cost-of-living-adjusted figure, and only where EVERY scenario
    # has one — ranking a set where some rows could not be adjusted would be
    # comparing two different measures and calling one of them the winner.
    comparable = [i for i, r in enumerate(rows) if r["real_take_home"] is not None]
    usable = len(comparable) == len(rows) and len(rows) > 1
    best_i = (max(comparable, key=lambda i: rows[i]["real_take_home"])
              if usable else None)

    # The winner on RAW take-home as well, so the page can say whether the
    # cost-of-living adjustment actually changed the answer. Without it the
    # copy has to guess, and it guessed wrong: it claimed take-home "would rank
    # these differently" on a pair where the same city won both ways.
    best_th_i = (max(range(len(rows)), key=lambda i: rows[i]["annual_take_home"])
                 if len(rows) > 1 else None)

    # THE INDEX IS THE IDENTITY; THE NAME IS ONLY THE LABEL. Names are typed by
    # the reader and are not unique — the page generates "Scenario N" from the
    # count, so removing one and adding another produces two columns called the
    # same thing without anybody typing a duplicate. Returning only a name made
    # `best` match EVERY column carrying it, and the page painted the winner's
    # colour on all of them: measured, a $49,438 column and a $133,988 column
    # were both marked best in the same table. The names are kept because the
    # verdict sentence reads them aloud.
    return {
        "rows": rows,
        "baseline": base["name"],
        "best": rows[best_i]["name"] if best_i is not None else None,
        "best_index": best_i,
        "best_take_home": rows[best_th_i]["name"] if best_th_i is not None else None,
        "best_take_home_index": best_th_i,
        # True only where the adjustment moves the winner, not merely the gap.
        # Compared by INDEX, or a set where the leader on both measures happens
        # to share a name with another column reads as though nothing moved.
        "col_changes_answer": bool(usable and best_i != best_th_i),
        "all_comparable": len(comparable) == len(rows),
    }


def histogram(values, bins=24, isolate=None):
    """Bin a list of numbers for a distribution chart.

    The fan chart shows the RANGE of a Monte Carlo; the shape is a different
    question and the answer is often more useful — a run can have a comfortable
    median and a long tail of failures, and a band chart hides that. The ending
    balances were already in the payload and nothing drew them.

    `isolate` GIVES ONE OUTCOME ITS OWN BIN, first, and it exists because
    without it the failures are invisible in the very case they matter. A path
    that runs out stays at zero, so every failure ends at EXACTLY the same
    value; ordinary binning drops them into a bucket spanning $0 to several
    million alongside the paths that merely did badly, and a bar that is part
    catastrophe and part success cannot honestly be coloured either way.
    Measured before this existed: at every retirement age tried, the failing
    bars were either all of the chart or none of it, and never the mixture the
    colour was for.

    Returns [] for no values rather than a single degenerate bin, and puts
    everything in one bin where every value is identical, which is a real
    outcome (a plan that cannot fail) and not an error.
    """
    values = [v for v in values if v is not None]
    if not values:
        return []

    isolated = []
    if isolate is not None:
        isolated = [v for v in values if v <= isolate]
        values = [v for v in values if v > isolate]
        if not values:
            return [{"start": isolate, "end": isolate, "count": len(isolated)}]

    lead = ([{"start": isolate, "end": isolate, "count": len(isolated)}]
            if isolated else [])

    lo, hi = min(values), max(values)
    if hi <= lo:
        return lead + [{"start": lo, "end": lo, "count": len(values)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        i = int((v - lo) / width)
        counts[min(i, bins - 1)] += 1     # the maximum lands in the last bin
    return lead + [{"start": lo + i * width, "end": lo + (i + 1) * width, "count": c}
                   for i, c in enumerate(counts)]


def cost_of_waiting(start, monthly, rate, years, delay_years=1):
    """What a year of not starting costs, at the end.

    The most persuasive single number an investing page can show, and it is
    persuasive precisely because it is not a rate: a year's delay does not cost
    a year's contributions, it costs a year of COMPOUNDING on everything, which
    is a much larger and much less intuitive figure.

    Both runs end at the same date. The delayed one contributes for fewer
    years, so the difference is the delayed contributions AND the growth they
    would have had — the split is returned, because the second part is the
    whole point and a single number hides it.
    """
    if years <= 0 or delay_years <= 0 or delay_years >= years:
        return None
    now_values, now_contrib = project_investment(start, monthly, rate, years)
    # Waiting means the starting balance still grows, untouched, in the gap.
    idle_values, _ = project_investment(start, 0, rate, delay_years)
    later_values, later_contrib = project_investment(
        idle_values[-1], monthly, rate, years - delay_years)
    lost = now_values[-1] - later_values[-1]
    # Each run's contributions NET of the balance it began with. The delayed run
    # starts from a balance that has already grown for `delay_years`, and
    # project_investment counts that opening balance as contributed — so
    # subtracting the original `start` from the difference leaves the idle
    # growth mixed in, and a year of $500/mo came out as $853 missed instead of
    # $6,000. Caught by reading the number, not by an assertion.
    contributed_now = now_contrib[-1] - start
    contributed_later = later_contrib[-1] - idle_values[-1]
    contributions_missed = contributed_now - contributed_later
    return {
        "delay_years": delay_years,
        "start_now": now_values[-1],
        "start_later": later_values[-1],
        "cost": lost,
        "contributions_missed": contributions_missed,
        # The part that is not simply the money you did not put in.
        "growth_missed": lost - contributions_missed,
    }


# ═══════════════════════════════════════════════════════════════════════
# SAVINGS RATE AND THE TIME TO FINANCIAL INDEPENDENCE
#
# The one chart that makes the case for saving more better than a paragraph
# can, and the reason is that the relationship is not the one people expect.
# Doubling a savings rate does not halve the time: the rate sets BOTH how fast
# the portfolio fills AND how large it has to be, because the money not saved
# is the money that has to be replaced forever. That second half is what makes
# the curve steep at the low end and nearly flat at the high one, and it is
# invisible in any single "years to retirement" figure.
# ═══════════════════════════════════════════════════════════════════════

SWR_DEFAULT = 4.0          # Trinity Study (1998) safe withdrawal rate, percent.

# The savings rates the curve is drawn at. It stops short of both ends on
# purpose: at 0% the answer is "never" and at 100% the person spends nothing,
# so the FIRE number is zero and the answer is "already". Neither is a point on
# a curve — they are the asymptotes it runs between, and plotting them would
# squeeze the whole readable range into the middle third of the axis.
FIRE_RATE_MIN = 5.0
FIRE_RATE_MAX = 90.0
FIRE_RATE_STEP = 2.5


def expected_real_return(stock_pct, inflation):
    """The Monte Carlo's own mean return, net of inflation, as a percentage.

    Derived from MC_STOCK_MEAN and MC_BOND_MEAN rather than being a second
    assumption typed somewhere else, so that the deterministic curve and the
    stochastic simulation on the same page describe ONE world. Moving the stock
    slider moves both, which is the honest behaviour — with separate return
    assumptions the page would be quietly arguing with itself.

    Real, not nominal, and by the exact Fisher relation rather than by
    subtracting inflation: at these magnitudes the difference is a couple of
    tenths of a percent, which is a couple of YEARS at the low end of the curve.
    """
    stock_alloc = stock_pct / 100.0
    nominal = stock_alloc * MC_STOCK_MEAN + (1.0 - stock_alloc) * MC_BOND_MEAN
    return ((1.0 + nominal) / (1.0 + inflation / 100.0) - 1.0) * 100.0


def years_to_target(portfolio, annual_savings, target, real_return):
    """Years for a portfolio to reach a target, saving a constant real amount.

    Closed form rather than a loop, because the curve evaluates this ~35 times
    per request and the answer is wanted as a real number: a curve quantised to
    whole years has visible steps in it, and those steps are an artefact of the
    method rather than anything about the money.

        P(1+r)^n + S((1+r)^n - 1)/r = T
        n = ln((T + S/r) / (P + S/r)) / ln(1+r)

    Contributions arrive at the END of each year — an ordinary annuity, which
    is the conservative reading of "saves X a year".

    Returns None where the target is never reached. That is a real answer and
    not an error, and None is never rendered as a number.
    """
    portfolio = float(portfolio)
    target = float(target)
    annual_savings = float(annual_savings)
    r = real_return / 100.0

    if target <= portfolio:
        return 0.0                      # already there
    if r <= 0:
        # No growth to help; only the saving closes the gap, if there is any.
        return None if annual_savings <= 0 else (target - portfolio) / annual_savings

    base = portfolio + annual_savings / r
    # A balance grows only while r*P + S > 0, which is exactly base > 0. At or
    # below it the portfolio is flat or shrinking and no amount of time reaches
    # the target. The log would be of a negative number, so this guard is what
    # stops a drawdown returning a plausible-looking figure.
    if base <= 0:
        return None
    return _math.log((target + annual_savings / r) / base) / _math.log(1.0 + r)


def capital_equivalent(annual_income, swr=SWR_DEFAULT):
    """The portfolio an income stream saves you from having to build.

    A Social Security benefit of $30,000 a year at a 4% withdrawal rate is
    $750,000 the portfolio does not have to cover, and that is the figure worth
    printing beside a FIRE number — the monthly benefit on its own is not
    comparable to anything else on the page.

    It is one division, and it is here rather than in the front end for the
    same reason the rest of this section is: the divisor is the safe withdrawal
    rate, and a threshold with a copy in the display layer is a threshold that
    changes in one place.
    """
    if swr <= 0:
        return None
    return annual_income / (swr / 100.0)


def fire_curve_points(annual_take_home, portfolio, real_return, swr=SWR_DEFAULT,
                      rates=None):
    """Years to independence at each of a range of savings rates.

    At a savings rate of s the person saves s of take-home and lives on the
    rest, so BOTH sides of the problem move: annual savings is s x take-home
    and the target is (1 - s) x take-home / swr. That coupling is the entire
    shape of the curve, and it is why the answer is not proportional to s.
    """
    if annual_take_home <= 0 or swr <= 0:
        return []
    if rates is None:
        rates = []
        rate = FIRE_RATE_MIN
        while rate <= FIRE_RATE_MAX + 1e-9:
            rates.append(round(rate, 4))
            rate += FIRE_RATE_STEP

    points = []
    for s in rates:
        frac = s / 100.0
        savings = annual_take_home * frac
        spending = annual_take_home * (1.0 - frac)
        target = spending / (swr / 100.0)
        points.append({
            "savings_rate": s,
            "annual_savings": savings,
            "annual_expenses": spending,
            "fire_number": target,
            "years": years_to_target(portfolio, savings, target, real_return),
        })
    return points


def fire_projection(income, itemized=None, budget=None, assets=None,
                    stock_pct=80.0, inflation=3.0, swr=SWR_DEFAULT):
    """Everything the FIRE page states, from the profile it already holds.

    One function rather than five figures worked out in the front end, because
    every one of them is a rule: a ratio (the savings rate), a threshold
    divided into (the safe withdrawal rate), a target, a progress percentage
    and a solved-for duration. The page had all five in TypeScript, including a
    `const SWR = 0.04` that no test could see and that would have drifted from
    the Streamlit app the first time either of them changed.

    ANNUAL EXPENSES ARE BUDGETED NEEDS AND WANTS — not the savings bucket, and
    not what was actually spent. Money budgeted to savings is not an expense
    the portfolio has to replace, so counting it would inflate the FIRE number
    by exactly the amount being saved: the more you saved, the further away the
    page would say you are. What was actually SPENT is a different and noisier
    question, and the dashboard answers that one for the month; this is the
    plan, and the page says which it is.
    """
    th = compute_take_home(income, itemized)
    b = budget or {}
    take_home = th["annual_take_home"]

    annual_expenses = (sum((b.get("needs") or {}).values())
                       + sum((b.get("wants") or {}).values())) * MONTHS_PER_YEAR
    portfolio = sum((assets or {}).values())
    real_return = expected_real_return(stock_pct, inflation)
    fire_number = annual_expenses / (swr / 100.0) if swr > 0 else None

    # Savings is clamped at zero and `overspending` is what carries the fact
    # that it was. A negative savings rate is a different statement from a zero
    # one, and plotting -14% on an axis that starts at 5% would put the marker
    # off the chart with nothing on the page saying why.
    raw_savings = take_home - annual_expenses
    annual_savings = max(0.0, raw_savings)
    savings_rate = (annual_savings / take_home * 100.0) if take_home > 0 else None

    # The TIME uses the raw figure, not the clamped one, and the difference is
    # the whole answer for someone whose budget does not balance. Clamped, a
    # person spending $60,000/yr more than they earn has "zero savings" and a
    # portfolio left quietly compounding, so the engine reported 85 years — a
    # plan funded from nowhere. Passed the real number, years_to_target's
    # existing drawdown guard returns None, which is the truth: at this budget
    # the portfolio is being consumed and the target is never reached.
    years = None
    if fire_number is not None and take_home > 0:
        years = years_to_target(portfolio, raw_savings, fire_number, real_return)

    curve = fire_curve_points(take_home, portfolio, real_return, swr)

    # What one more point of savings rate is worth, in years — the single most
    # actionable number on the page. Only meaningful where both ends are
    # reachable: at a savings rate that never arrives, "a year sooner" has no
    # referent, so this is None rather than a difference against infinity.
    next_point = None
    if savings_rate is not None and years is not None and savings_rate + 1 <= 100:
        nxt = fire_curve_points(take_home, portfolio, real_return, swr,
                                rates=[savings_rate + 1])
        if nxt and nxt[0]["years"] is not None:
            next_point = {
                "savings_rate": nxt[0]["savings_rate"],
                "years": nxt[0]["years"],
                "years_saved": years - nxt[0]["years"],
            }

    return {
        "annual_take_home": take_home,
        "monthly_take_home": th["monthly_take_home"],
        "annual_expenses": annual_expenses,
        "annual_savings": annual_savings,
        "savings_rate": savings_rate,
        # True where the budget spends more than the take-home covers, which is
        # why the savings rate reads 0.0 rather than a negative number.
        "overspending": raw_savings < 0,
        "shortfall": max(0.0, -raw_savings),
        "portfolio": portfolio,
        "fire_number": fire_number,
        "still_to_accumulate": (max(0.0, fire_number - portfolio)
                                if fire_number is not None else None),
        "progress_pct": ((portfolio / fire_number * 100.0)
                         if fire_number else None),
        "years_at_current": years,
        "swr": swr,
        "real_return": real_return,
        "stock_pct": stock_pct,
        "inflation": inflation,
        "curve": curve,
        "next_point": next_point,
    }


# ═══════════════════════════════════════════════════════════════════════
# THE YEAR SO FAR
#
# The dashboard is entirely month-scoped, which flatters a good month and
# hides a bad run. This is the same money over the calendar year.
#
# TWO THINGS MAKE IT HARDER THAN A SUM, and both of them fail in the
# flattering direction, which is the dangerous one.
#
# 1. AN EXPENSE LOG IS NOT A BANK STATEMENT. It has holes, and a hole looks
#    exactly like a frugal month. Eight months of budget against two months of
#    records reads as "$33,242 under budget" — the most encouraging possible
#    way to be wrong. So the variance is measured only over months that HAVE
#    records, and `complete_record` says whether that is the whole year so far.
#
# 2. A MONTH IN PROGRESS IS NOT A SHORT MONTH. Rent is paid on the 1st, so on
#    the 2nd the month holds a full month of rent and two days of everything
#    else. Pro-rating the budget by day to match reported the demo's rent as
#    $3,800 against $2,030 "allowed" — 30x over on a bill that was paid on
#    time. Counting it as a whole month instead just moves the lie: everything
#    reads under budget until about the 28th. So the current month is not in
#    the variance at all. It is reported on its own, and the dashboard beside
#    this already owns it.
# ═══════════════════════════════════════════════════════════════════════

MONTH_ABBR = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def _parse_iso(value):
    """An ISO date, or None. Never raises — an expense log can hold anything."""
    try:
        return _date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def year_to_date(expenses, budget=None, monthly_take_home=0.0, today=None):
    """Spending, saving and budget adherence over the calendar year so far.

    `today` is the CLIENT's date, not the server's. The year and month
    boundaries belong to the person reading the page: a server in UTC has
    already rolled into January while someone in Chicago is still finishing New
    Year's Eve, and the dashboard beside this reads the browser's clock. Falls
    back to the server's date when it is not given.

    Three totals, and they are deliberately different numbers:
      `spent`             everything logged this year, the current month
                          included — what "spent this year" means to a reader.
      `spent_documented`  the same, restricted to COMPLETE months that hold at
                          least one record. The only one a budget is compared
                          against, because it is the only one with a matching
                          number of months of plan behind it.
      `current_month`     the month in progress, on its own.
    """
    ref = _parse_iso(today) or _date.today()
    year = ref.year
    b = budget or {}
    buckets = (("needs", "Needs"), ("wants", "Wants"), ("savings", "Savings"))
    cat_budget = {}
    cat_bucket = {}
    for key, label in buckets:
        for name, amount in (b.get(key) or {}).items():
            cat_budget[name] = float(amount)
            cat_bucket[name] = label
    budget_monthly = sum(cat_budget.values())

    # ── What is on record ──
    spent_by_month = {}
    by_month_cat = {}
    count = 0
    future = 0
    for e in expenses or []:
        d = _parse_iso(e.get("date"))
        if d is None or d.year != year:
            continue
        amount = float(e.get("amount") or 0)
        cat = e.get("category") or "Uncategorised"
        spent_by_month[d.month] = spent_by_month.get(d.month, 0.0) + amount
        by_month_cat.setdefault(d.month, {})
        by_month_cat[d.month][cat] = by_month_cat[d.month].get(cat, 0.0) + amount
        count += 1
        if d > ref:
            future += 1

    spent = sum(spent_by_month.values())

    # ── The comparable basis: complete months that hold records ──
    complete = [m for m in range(1, ref.month)]
    documented = [m for m in complete if m in spent_by_month]
    undocumented = [f"{year}-{m:02d}" for m in complete if m not in spent_by_month]
    months_complete = len(complete)
    documented_months = len(documented)
    complete_record = months_complete > 0 and not undocumented

    spent_documented = sum(spent_by_month[m] for m in documented)
    spent_by_cat = {}
    for m in documented:
        for cat, amount in by_month_cat[m].items():
            spent_by_cat[cat] = spent_by_cat.get(cat, 0.0) + amount

    budget_documented = budget_monthly * documented_months
    budget_to_date = budget_monthly * months_complete
    variance = (budget_documented - spent_documented) if documented_months else None

    # ── Pace and projection ──
    # Only from complete documented months. One month is a number rather than a
    # rate, but it is still the only rate available and extrapolating it is
    # what a reader would do anyway — so it is returned WITH the count it came
    # from, and the page says how thin the evidence is.
    pace = spent_documented / documented_months if documented_months else None
    projected = pace * MONTHS_PER_YEAR if pace is not None else None

    # ── Earning and saving, on the same basis as the spending ──
    # Take-home over the whole elapsed year is a fact and is returned as one,
    # but it must not be the denominator: subtracting two months of spending
    # from eight months of pay is not a savings rate, it is a missing record.
    take_home_documented = monthly_take_home * documented_months
    take_home_to_date = monthly_take_home * months_complete
    saved = (take_home_documented - spent_documented) if documented_months else None
    savings_rate = (saved / take_home_documented * 100.0
                    if saved is not None and take_home_documented > 0 else None)

    by_month = []
    for m in range(1, ref.month + 1):
        by_month.append({
            "month": f"{year}-{m:02d}",
            "label": MONTH_ABBR[m - 1],
            "spent": spent_by_month.get(m, 0.0),
            "budget": budget_monthly,
            # The month in progress. Its bar is not short because spending was
            # low; it is short because the month is.
            "in_progress": m == ref.month,
            # False means NOTHING WAS LOGGED, which is not the same as a month
            # in which nothing was spent. The zero is not evidence.
            "has_data": m in spent_by_month,
        })

    by_bucket = []
    for _, label in buckets:
        names = [n for n, lbl in cat_bucket.items() if lbl == label]
        plan = sum(cat_budget[n] for n in names)
        used = sum(spent_by_cat.get(n, 0.0) for n in names)
        by_bucket.append({
            "bucket": label,
            "budget_monthly": plan,
            "budget_to_date": plan * documented_months,
            "spent": used,
            "variance": plan * documented_months - used,
        })
    # Spending logged against a category the budget does not have. Its own row
    # rather than folded into a total, because it is the part of the variance
    # that no plan accounts for — and a category deleted from the budget after
    # it was spent against lands here rather than vanishing.
    unbudgeted = sum(v for k, v in spent_by_cat.items() if k not in cat_budget)
    if unbudgeted > 0:
        by_bucket.append({
            "bucket": "Unbudgeted",
            "budget_monthly": 0.0,
            "budget_to_date": 0.0,
            "spent": unbudgeted,
            "variance": -unbudgeted,
        })

    by_category = []
    for name in sorted(set(cat_budget) | set(spent_by_cat)):
        plan = cat_budget.get(name, 0.0)
        used = spent_by_cat.get(name, 0.0)
        allowed = plan * documented_months
        by_category.append({
            "category": name,
            "bucket": cat_bucket.get(name),
            "budget_monthly": plan,
            "budget_to_date": allowed,
            "spent": used,
            "variance": allowed - used,
            # Only where there is a plan to be over. A category with no budget
            # is not over its budget; it has none, which the bucket row says.
            "over": bool(plan > 0 and used > allowed),
            "pct_of_budget": (used / allowed * 100.0) if allowed > 0 else None,
        })
    by_category.sort(key=lambda r: -r["spent"])

    return {
        "year": year,
        "today": ref.isoformat(),
        "months_complete": months_complete,
        "documented_months": documented_months,
        "undocumented_months": undocumented,
        "complete_record": complete_record,
        "transactions": count,
        # Logged with a date still to come. Counted in `spent` because they
        # were entered deliberately, but named so the page can say so.
        "future_dated": future,
        "spent": spent,
        "spent_documented": spent_documented,
        "current_month": {
            "month": f"{year}-{ref.month:02d}",
            "label": MONTH_ABBR[ref.month - 1],
            "spent": spent_by_month.get(ref.month, 0.0),
            "has_data": ref.month in spent_by_month,
        },
        "budget_monthly": budget_monthly,
        "budget_year": budget_monthly * MONTHS_PER_YEAR,
        # `budget_documented` matches spent_documented month for month;
        # `budget_to_date` covers every complete month whether or not it holds
        # records. They are equal exactly when complete_record is true.
        "budget_documented": budget_documented,
        "budget_to_date": budget_to_date,
        # None where no complete month holds a record — there is nothing to
        # compare, which is not the same as being exactly on budget.
        "variance": variance,
        "pace": pace,
        "projected_year_end": projected,
        "projected_vs_budget": (budget_monthly * MONTHS_PER_YEAR - projected
                                if projected is not None else None),
        "take_home_monthly": monthly_take_home,
        "take_home_documented": take_home_documented,
        "take_home_to_date": take_home_to_date,
        "saved": saved,
        "savings_rate": savings_rate,
        "by_month": by_month,
        "by_bucket": by_bucket,
        "by_category": by_category,
    }


# ═══════════════════════════════════════════════════════════════════════
# READING A BANK'S CSV
#
# The cheap answer to having no bank connection, and the last thing keeping
# this a hand-typed tool. Splitting a file into cells is text handling and the
# front end does it. Everything below is a DECISION, and every one of them can
# be wrong quietly:
#
#   * 03/04/2026 is the 3rd of April or the 4th of March, and the file rarely
#     says which. Guessing wrong moves a whole year of spending by a month.
#   * Chase writes a purchase as -52.30 and American Express writes the same
#     purchase as 52.30. Guessing wrong imports a year of refunds and drops
#     every actual expense.
#   * 1.234,56 read as US notation is 1.23456 — a $1,234 charge that lands as
#     a rounding error, with nothing on screen looking wrong.
#   * Importing the same file twice doubles a year of spending.
#
# None of those raise. Each of them produces a number that looks like a
# number, which is why they are here with the rest of the rules and not in the
# display layer. Nothing is ever imported without being previewed first.
# ═══════════════════════════════════════════════════════════════════════

# Header names a bank might use, best first. Matched as substrings of the
# lowercased header, so "Transaction Date" is found by "transaction date".
IMPORT_HEADERS = {
    "date": ("transaction date", "trans date", "trade date", "posting date",
             "posted date", "post date", "date"),
    "amount": ("transaction amount", "amount", "value"),
    "debit": ("debit", "withdrawal", "money out", "paid out"),
    "credit": ("credit", "deposit", "money in", "paid in"),
    "description": ("original description", "description", "merchant name",
                    "merchant", "payee", "name", "details", "particulars",
                    "narrative", "memo", "reference"),
    "category": ("category", "type"),
}

# Merchant words that identify a KIND of spending. Matched as WHOLE WORDS --
# see `_word_at` -- which is why several appear in more than one form. Under
# a plain substring test "gym" claimed GYMBOREE, "rent" claimed PARENTS
# MAGAZINE, "metro" claimed the METROPOLITAN MUSEUM and "toll" claimed a
# TOLLHOUSE BAKERY: the same false-positive class the category-name half was
# already guarding against, on the half that had no guard. The value is a
# canonical
# category name, and it is used only when the person actually has a category
# of that name — this never invents a budget line, and a profile with no
# "Dining Out" simply gets no suggestion rather than a new category appearing
# in their budget because a coffee shop was in the file.
IMPORT_KEYWORDS = {
    "grocer": "Groceries", "grocery": "Groceries", "groceries": "Groceries",
    "supermarket": "Groceries", "trader joe": "Groceries", "trader joes": "Groceries",
    "whole foods": "Groceries", "safeway": "Groceries", "kroger": "Groceries",
    "aldi": "Groceries", "publix": "Groceries", "wegmans": "Groceries",
    "costco": "Groceries", "sam's club": "Groceries", "food lion": "Groceries",
    "sprouts": "Groceries", "heb": "Groceries", "meijer": "Groceries",

    "restaurant": "Dining Out", "restaurants": "Dining Out",
    "starbucks": "Dining Out", "mcdonald": "Dining Out", "mcdonalds": "Dining Out",
    "chipotle": "Dining Out", "doordash": "Dining Out", "uber eats": "Dining Out",
    "grubhub": "Dining Out", "seamless": "Dining Out", "postmates": "Dining Out",
    "cafe": "Dining Out", "coffee": "Dining Out", "pizza": "Dining Out",
    "panera": "Dining Out", "dunkin": "Dining Out", "chick-fil-a": "Dining Out",
    "taqueria": "Dining Out", "sushi": "Dining Out", "brewing": "Dining Out",
    "tavern": "Dining Out", "bistro": "Dining Out", "steakhouse": "Dining Out",

    "uber": "Transportation", "lyft": "Transportation", "shell oil": "Transportation",
    "chevron": "Transportation", "exxon": "Transportation", "bp": "Transportation",
    "parking": "Transportation", "transit": "Transportation", "metro": "Transportation",
    "mta": "Transportation", "toll": "Transportation", "gas station": "Transportation",
    "auto repair": "Transportation", "jiffy lube": "Transportation",

    "netflix": "Subscriptions", "spotify": "Subscriptions", "hulu": "Subscriptions",
    "disney+": "Subscriptions", "icloud": "Subscriptions", "prime video": "Subscriptions",
    "audible": "Subscriptions", "patreon": "Subscriptions", "substack": "Subscriptions",
    "adobe": "Subscriptions", "dropbox": "Subscriptions", "youtube premium": "Subscriptions",

    "amazon": "Shopping", "target": "Shopping", "walmart": "Shopping",
    "best buy": "Shopping", "etsy": "Shopping", "ebay": "Shopping",
    "nordstrom": "Shopping", "macy": "Shopping", "macys": "Shopping", "ikea": "Shopping",
    "home depot": "Shopping", "lowe's": "Shopping", "nike": "Shopping",

    "electric": "Utilities", "electricity": "Utilities", "utility": "Utilities",
    "utilities": "Utilities", "water dept": "Utilities",
    "comcast": "Utilities", "xfinity": "Utilities", "spectrum": "Utilities",
    "con edison": "Utilities", "national grid": "Utilities", "internet": "Utilities",

    "verizon": "Phone", "at&t": "Phone", "t-mobile": "Phone", "mint mobile": "Phone",

    "insurance": "Insurance", "geico": "Insurance", "state farm": "Insurance",
    "progressive insurance": "Insurance", "allstate": "Insurance",

    "rent": "Rent", "landlord": "Rent", "property mgmt": "Rent",
    "apartment": "Rent", "apartments": "Rent", "leasing": "Rent",

    "gym": "Gym", "fitness": "Gym", "planet fitness": "Gym", "equinox": "Gym",
    "crossfit": "Gym", "peloton": "Gym", "yoga": "Gym",

    "airlines": "Travel", "airbnb": "Travel", "hotel": "Travel", "hotels": "Travel",
    "marriott": "Travel", "hilton": "Travel", "expedia": "Travel",
    "delta air": "Travel", "united air": "Travel", "southwest air": "Travel",

    "cinema": "Entertainment", "amc": "Entertainment", "regal": "Entertainment",
    "ticketmaster": "Entertainment", "steam games": "Entertainment",
    "playstation": "Entertainment", "xbox": "Entertainment",
    "theatre": "Entertainment", "theater": "Entertainment",
}

_MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _digits_groups(text):
    """The runs of digits in a string, in order. [] where there are none."""
    groups = []
    run = ""
    for ch in str(text):
        if ch.isdigit():
            run += ch
        elif run:
            groups.append(run)
            run = ""
    if run:
        groups.append(run)
    return groups


def parse_amount(text):
    """A money string as a float, or None.

    Handles $, thousands separators, a trailing or leading minus, and
    accounting parentheses. THE DECIMAL SEPARATOR IS DECIDED, not assumed:
    where both a dot and a comma appear the LATER one is the decimal mark, and
    a lone comma followed by exactly two digits at the end is a decimal mark
    too. Without that, a European export's 1.234,56 parses as 1.23456 — a
    $1,234 charge arriving as a rounding error, which no total on the page
    would look wrong for.
    """
    s = str(text).strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    if negative:
        s = s[1:-1]
    s = s.replace("−", "-").replace(" ", " ")   # unicode minus, nbsp
    # Strip everything that is not a digit, separator or sign.
    kept = "".join(ch for ch in s if ch.isdigit() or ch in ".,-+")
    if kept.endswith("-"):                      # trailing-minus notation
        negative = True
        kept = kept[:-1]
    if kept.startswith("-"):
        negative = True
    kept = kept.lstrip("+-")
    if not any(ch.isdigit() for ch in kept):
        return None

    last_dot = kept.rfind(".")
    last_comma = kept.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        # Both present: the later one is the decimal mark.
        if last_comma > last_dot:
            kept = kept.replace(".", "").replace(",", ".")
        else:
            kept = kept.replace(",", "")
    elif last_comma >= 0:
        tail = kept[last_comma + 1:]
        if len(tail) == 2 and kept.count(",") == 1:
            kept = kept.replace(",", ".")       # 1234,56
        else:
            kept = kept.replace(",", "")        # 1,234
    elif last_dot >= 0 and kept.count(".") > 1:
        kept = kept.replace(".", "")            # 1.234.567

    try:
        value = float(kept)
    except ValueError:
        return None
    return -value if negative else value


def looks_like_amount(text):
    """Whether a cell is SHAPED like money, rather than merely containing digits.

    `parse_amount` is deliberately permissive, because a cell the caller has
    already identified as the amount may read "$1,234.56 CR" or "USD 52.30" and
    all of that should still come back as a number. As a test of WHETHER a
    column holds amounts it is useless: it strips non-digits, so
    "STARBUCKS STORE 4" parses as 4.0 and every merchant string carrying a
    store number scores as money.

    That is not hypothetical. Sniffing a headerless Amex export by content, the
    description column scored two out of two against the real amount column's
    two out of two, won the tie by being further left, and the file imported
    STARBUCKS STORE 4 as a $4.00 charge — a plausible-looking coffee, from a
    column of shop names.

    So detection uses this instead: after the currency furniture comes off,
    what is left must be only digits and separators.
    """
    s = str(text).strip()
    if not s:
        return False
    for junk in ("$", "£", "€", "¥", "(", ")", " ", " ",
                 "+", "-", "−"):
        s = s.replace(junk, "")
    # A trailing DR/CR marker is bookkeeping, not text.
    for marker in ("DR", "CR", "dr", "cr"):
        if s.endswith(marker):
            s = s[:-2]
    s = s.strip()
    return bool(s) and all(ch.isdigit() or ch in ".," for ch in s)


def detect_date_order(values):
    """Whether a column of dates is month-first, day-first or year-first.

    THE FILE USUALLY DOES NOT SAY, and getting it wrong does not fail — it
    moves spending between months for every date whose day is 12 or less,
    which is most of them. So the answer comes with its evidence, and the
    front end shows it: a column containing 13/04/2026 has proved itself
    day-first, and a column of nothing but 03/04/2026 has proved nothing.

    US bank exports are overwhelmingly month-first, so that is the fallback —
    but `ambiguous` is what says the fallback was used.
    """
    first_over_12 = second_over_12 = 0
    year_first = 0
    seen = 0
    for value in values:
        groups = _digits_groups(value)
        if len(groups) < 3:
            continue
        seen += 1
        if len(groups[0]) == 4:
            year_first += 1
            continue
        a, b = int(groups[0]), int(groups[1])
        if a > 12:
            first_over_12 += 1
        if b > 12:
            second_over_12 += 1

    if seen == 0:
        return {"order": "MDY", "ambiguous": True, "proved": False,
                "reason": "no parseable dates in the column",
                "day_first_evidence": 0, "month_first_evidence": 0}
    if year_first > seen / 2:
        return {"order": "YMD", "ambiguous": False, "proved": True,
                "reason": "dates begin with a four-digit year",
                "day_first_evidence": 0, "month_first_evidence": 0}
    if first_over_12 and not second_over_12:
        return {"order": "DMY", "ambiguous": False, "proved": True,
                "reason": f"{first_over_12} date(s) have a first number above 12",
                "day_first_evidence": first_over_12, "month_first_evidence": 0}
    if second_over_12 and not first_over_12:
        return {"order": "MDY", "ambiguous": False, "proved": True,
                "reason": f"{second_over_12} date(s) have a second number above 12",
                "day_first_evidence": 0, "month_first_evidence": second_over_12}
    if first_over_12 and second_over_12:
        # Both, which no consistent file can be. Something is wrong with the
        # column; say so rather than picking the larger count.
        return {"order": "MDY", "ambiguous": True, "proved": False,
                "reason": "the column contains both day-first and month-first dates",
                "day_first_evidence": first_over_12,
                "month_first_evidence": second_over_12}
    return {"order": "MDY", "ambiguous": True, "proved": False,
            "reason": "every day of the month is 12 or less, so the file does not say",
            "day_first_evidence": 0, "month_first_evidence": 0}


def parse_date(text, order="MDY"):
    """A date string as an ISO date, or None. `order` settles the ambiguity."""
    s = str(text).strip()
    if not s:
        return None

    # A month NAME removes the ambiguity by itself, whatever `order` says.
    lowered = s.lower()
    for name, month in _MONTH_NAMES.items():
        if name in lowered:
            nums = [int(g) for g in _digits_groups(s)]
            year = next((n for n in nums if n >= 1000), None)
            day = next((n for n in nums if 1 <= n <= 31 and n != year), None)
            if year and day:
                try:
                    return _date(year, month, day).isoformat()
                except ValueError:
                    return None
            return None

    groups = _digits_groups(s)
    if len(groups) < 3:
        return None
    a, b, c = groups[0], groups[1], groups[2]
    if len(a) == 4:
        year, month, day = int(a), int(b), int(c)
    else:
        year = int(c)
        if len(c) == 2:
            # A two-digit year. 70 is the pivot Python's own %y uses.
            year += 2000 if year < 70 else 1900
        if order == "DMY":
            day, month = int(a), int(b)
        else:
            month, day = int(a), int(b)
    try:
        return _date(year, month, day).isoformat()
    except ValueError:
        return None


def detect_sign(values):
    """Whether spending in this file is written negative or positive.

    Chase writes a $52.30 purchase as -52.30; American Express writes the same
    purchase as 52.30. Read the wrong way round, a year of card statements
    imports as a handful of refunds and drops every actual expense — and the
    import looks like it worked, because rows did arrive.

    Decided by the majority, because a card statement is mostly spending
    whichever way it signs it. The counts come back so the front end can show
    the split and let it be overridden; `ambiguous` marks a file balanced
    enough that the majority is not much of an argument (a current account
    with a salary in it, say).
    """
    negatives = positives = 0
    for value in values:
        amount = parse_amount(value)
        if amount is None or amount == 0:
            continue
        if amount < 0:
            negatives += 1
        else:
            positives += 1
    total = negatives + positives
    if total == 0:
        return {"convention": "negative", "negatives": 0, "positives": 0,
                "ambiguous": True, "reason": "no amounts could be read"}
    convention = "negative" if negatives > positives else "positive"
    minority = min(negatives, positives) / total
    return {
        "convention": convention,
        "negatives": negatives,
        "positives": positives,
        "ambiguous": minority > 0.4,
        "reason": (f"{negatives} negative and {positives} positive amounts"),
    }


def detect_header(grid):
    """Whether the first row NAMES the columns or holds a transaction.

    Getting this wrong loses exactly one row — the oldest transaction in the
    file, silently, at the bottom of a preview nobody scrolls to — or adds a
    row of column names as a $0 expense. So it is decided here rather than by
    the front end, and by the one test that is hard to fool: a header contains
    no date, and the rows under a header do.

    A file with no readable dates anywhere reaches this as False, which is the
    safe way round: nothing is dropped, and the preview reports every row as
    having an unreadable date, which is what is actually wrong with it.
    """
    if len(grid) < 2:
        return False
    first = grid[0]
    rest = grid[1:6]
    first_has_date = any(parse_date(c) for c in first)
    rest_has_date = any(parse_date(c) for row in rest for c in row)
    return rest_has_date and not first_has_date


def _header_column(headers, kind):
    """The best column for a role, by header name. None where none matches."""
    lowered = [str(h or "").strip().lower() for h in headers]
    for needle in IMPORT_HEADERS[kind]:
        for i, h in enumerate(lowered):
            if needle in h:
                return i
    return None


def sniff_columns(grid, has_header=True):
    """Which column is the date, the amount and the description.

    By header name where there is a header, and by CONTENT where there is not
    — the column whose cells parse as dates is the date column, whichever
    bank wrote it. A wrong guess is not dangerous here because the preview
    shows what the guess produced before anything is committed; it is only
    worth getting right so that the common files need no clicking.
    """
    if not grid:
        return {"date": None, "amount": None, "debit": None, "credit": None,
                "description": None, "category": None}

    headers = grid[0] if has_header else []
    body = grid[1:] if has_header else grid
    width = max(len(r) for r in grid)

    found = {}
    for kind in ("date", "amount", "debit", "credit", "description", "category"):
        found[kind] = _header_column(headers, kind) if has_header else None

    # "Amount" and "Debit" can both match the same header ("Debit Amount");
    # a debit/credit pair is only real when the two are different columns.
    if found["debit"] is not None and found["debit"] == found["amount"]:
        found["debit"] = None
    if found["credit"] is not None and found["credit"] == found["amount"]:
        found["credit"] = None
    if found["debit"] is None or found["credit"] is None:
        # One half of a pair is not a pair — Chase has a "Type" column reading
        # "DEBIT" per row, which is not an amount.
        if found["amount"] is not None:
            found["debit"] = found["credit"] = None

    sample = body[:40]

    if found["date"] is None:
        best, best_score = None, 0
        for col in range(width):
            score = sum(1 for r in sample
                        if col < len(r) and parse_date(r[col]) is not None)
            if score > best_score:
                best, best_score = col, score
        if best_score >= max(1, len(sample) // 2):
            found["date"] = best

    if found["amount"] is None and found["debit"] is None:
        # `looks_like_amount`, not `parse_amount` — see its docstring. Where two
        # genuinely money-shaped columns tie (a statement with both Amount and
        # Balance) the leftmost wins, which is arbitrary; that only arises in a
        # headerless file, and the preview shows which column was taken.
        best, best_score = None, 0
        for col in range(width):
            if col == found["date"]:
                continue
            score = sum(1 for r in sample
                        if col < len(r) and looks_like_amount(r[col]))
            if score > best_score:
                best, best_score = col, score
        if best_score >= max(1, len(sample) // 2):
            found["amount"] = best

    if found["description"] is None:
        # The wordiest column that is not the date or the amount. Length rather
        # than "is not a number", because a reference column of digits is not a
        # description either and this ranks it below the real one.
        best, best_score = None, 0.0
        taken = {found["date"], found["amount"], found["debit"], found["credit"]}
        for col in range(width):
            if col in taken:
                continue
            cells = [str(r[col]) for r in sample if col < len(r)]
            letters = [len([c for c in cell if c.isalpha()]) for cell in cells]
            score = sum(letters) / len(letters) if letters else 0.0
            if score > best_score:
                best, best_score = col, score
        if best_score > 0:
            found["description"] = best

    return found


def _word_at(text, needle):
    """Whether `needle` appears in `text` as a WHOLE word.

    The one place the boundary rule lives, because both halves of category
    matching need it and a second copy is how the two come to disagree.
    Without it, "Travel" claims TRAVELERS INSURANCE, "gym" claims GYMBOREE,
    "rent" claims PARENTS MAGAZINE and "metro" claims the METROPOLITAN MUSEUM
    -- every one a confident wrong category on a real merchant string.

    A boundary is any non-alphanumeric character, so an apostrophe or a hash
    still ends a word: "macy" matches MACY'S and "bp" matches BP#4471.
    """
    if not needle:
        return False
    i = text.find(needle)
    while i != -1:
        before = text[i - 1] if i else " "
        j = i + len(needle)
        after = text[j] if j < len(text) else " "
        if not before.isalnum() and not after.isalnum():
            return True
        i = text.find(needle, i + 1)
    return False


def suggest_category(description, bank_category, categories):
    """Which of the person's own budget categories a transaction belongs to.

    ONE RULE: the longest piece of the description that names a category wins.
    The obvious alternative is an ordered list of tests, and it needs hand
    tuning forever -- "uber eats" has to beat "uber", and "subway" the sandwich
    has to lose to "subway" the train exactly where the person has one category
    and not the other. Scoring by the length of what matched settles both
    without a special case: "uber eats" is nine characters and "uber" is four.

    Both sources of a match -- the person's own category names and the merchant
    table -- are scored on ONE list with ONE comparison. They used to have a
    comparison each, and a mutation reversing the ordering rule therefore broke
    only one of them while every assertion stayed green.

    A bank's own category column is the FALLBACK, not the winner, and that was
    measured rather than assumed. A bank's taxonomy is someone else's
    vocabulary that happens to collide with this budget's: Chase files an Uber
    ride under "Travel" and Netflix under "Entertainment", and against a
    profile holding both "Travel" and "Transportation", both "Entertainment"
    and "Subscriptions", letting the column win put both in the wrong one. It
    earns its place on the rows where the description is a payment-processor
    string -- "SQ *A1B2C3" names nothing at all, and there the bank's guess is
    the only one there is. It is accepted only when it names a category the
    person actually has; "Merchandise" and "Services" are what those columns
    usually say and neither is a budget line.

    Returns (category, source), with category None where nothing is known. None
    is the honest answer; a default would put a year of spending in one bucket
    and look like it had been classified.
    """
    by_lower = {}
    for name in categories or []:
        by_lower.setdefault(str(name).strip().lower(), name)

    fallback = (None, None)
    if bank_category:
        exact = by_lower.get(str(bank_category).strip().lower())
        if exact:
            fallback = (exact, "bank category")

    text = " " + str(description or "").lower() + " "
    if not text.strip():
        return fallback

    # (length of the match, prefer the person's own vocabulary, name, source)
    candidates = []
    for lower, name in by_lower.items():
        if _word_at(text, lower):
            candidates.append((len(lower), 1, name, "category name"))
    for keyword, canonical in IMPORT_KEYWORDS.items():
        own = by_lower.get(canonical.lower())
        if own is not None and _word_at(text, keyword):
            candidates.append((len(keyword), 0, own, "merchant"))

    if not candidates:
        return fallback
    # Longest first; a tie goes to the person's own category name; anything
    # still tied is settled by name, so the answer is the same on every run.
    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3]))
    return candidates[0][2], candidates[0][3]


def import_preview(grid, existing=None, categories=None, has_header=None,
                   mapping=None, date_order=None, sign=None):
    """Turn a split CSV into rows that can be reviewed, then committed.

    NOTHING IS IMPORTED HERE. This returns what each row would become, what
    was decided about it and why, and the front end shows every one of them
    before a single expense is created.

    DUPLICATES ARE COUNTED, NOT MATCHED. A date and an amount is the only key
    two records from different sources share, and two real coffees on one day
    are indistinguishable from one coffee imported twice. So for each key the
    rule is: if the profile already holds N expenses on that date for that
    amount, the first N rows in the file carrying it are duplicates and the
    rest are new. Importing a file twice flags everything; importing a file
    that genuinely contains a repeated charge flags only what is already held.

    A flagged row is never dropped and never overwrites anything — it comes
    back marked, unticked in the preview, and the person decides.
    """
    grid = grid or []
    # None means "work it out" — a caller that has not asked the question yet.
    # An explicit True or False is the person's own answer and is obeyed.
    if has_header is None:
        has_header = detect_header(grid)
    body = grid[1:] if has_header else grid
    headers = ([str(h) for h in grid[0]] if has_header and grid else [])

    cols = dict(mapping) if mapping else sniff_columns(grid, has_header)
    for key in ("date", "amount", "debit", "credit", "description", "category"):
        cols.setdefault(key, None)
    suggested = mapping is None

    def cell(row, col):
        if col is None or col >= len(row):
            return ""
        return str(row[col] or "").strip()

    date_values = [cell(r, cols["date"]) for r in body] if cols["date"] is not None else []
    date_info = detect_date_order(date_values)
    if date_order:
        date_info = dict(date_info, order=date_order, overridden=True)
    order = date_info["order"]

    using_pair = cols["debit"] is not None or cols["credit"] is not None
    if using_pair:
        # A debit column IS the spending column. There is no sign to work out.
        sign_info = {"convention": "debit column", "negatives": 0, "positives": 0,
                     "ambiguous": False,
                     "reason": "the file has separate debit and credit columns"}
    else:
        amount_values = ([cell(r, cols["amount"]) for r in body]
                         if cols["amount"] is not None else [])
        sign_info = detect_sign(amount_values)
        if sign:
            sign_info = dict(sign_info, convention=sign, overridden=True)
    spend_is_negative = sign_info["convention"] == "negative"

    # Existing expenses, counted by (date, amount).
    held = {}
    for e in existing or []:
        try:
            key = (str(e.get("date"))[:10], round(float(e.get("amount") or 0), 2))
        except (TypeError, ValueError):
            continue
        held.setdefault(key, []).append(e.get("id"))

    seen = {}
    rows = []
    for i, raw in enumerate(body):
        line = i + (2 if has_header else 1)          # 1-based, as a file reads
        description = cell(raw, cols["description"])
        bank_cat = cell(raw, cols["category"])
        iso = parse_date(cell(raw, cols["date"]), order) if cols["date"] is not None else None

        amount = None
        if using_pair:
            debit = parse_amount(cell(raw, cols["debit"])) if cols["debit"] is not None else None
            amount = abs(debit) if debit else None
        else:
            value = parse_amount(cell(raw, cols["amount"])) if cols["amount"] is not None else None
            if value is not None and value != 0:
                is_spend = (value < 0) if spend_is_negative else (value > 0)
                amount = abs(value) if is_spend else None

        skip = None
        if not any(cell(raw, c) for c in range(len(raw))):
            skip = "blank line"
        elif cols["date"] is None:
            skip = "no date column chosen"
        elif iso is None:
            skip = "the date could not be read"
        elif cols["amount"] is None and not using_pair:
            skip = "no amount column chosen"
        elif amount is None:
            # Three different reasons, and they need different words: a row
            # this app should not import is not the same as a row it could
            # not read. "0 imported" with no explanation is how a sign
            # convention read backwards looks from the outside.
            source_cell = cell(raw, cols["debit"] if using_pair else cols["amount"])
            parsed = parse_amount(source_cell)
            if using_pair and parsed is None and cols["credit"] is not None                     and parse_amount(cell(raw, cols["credit"])) is not None:
                # An empty debit cell beside a filled credit cell is a payment
                # or a refund, not an unreadable row. Reporting it as
                # unreadable would send someone looking for a fault in a file
                # that is fine.
                skip = "money in, not out"
            elif parsed is None:
                skip = "the amount could not be read"
            elif parsed == 0:
                skip = "the amount is zero"
            else:
                skip = "money in, not out"

        category, source = (suggest_category(description, bank_cat, categories)
                            if skip is None else (None, None))

        duplicate_of = None
        if skip is None:
            key = (iso, round(amount, 2))
            index = seen.get(key, 0)
            seen[key] = index + 1
            already = held.get(key, [])
            if index < len(already):
                duplicate_of = already[index]

        rows.append({
            "line": line,
            "date": iso,
            "amount": amount,
            "description": description,
            "category": category,
            "category_source": source,
            "duplicate_of": duplicate_of,
            "skip": skip,
            "raw": [str(c) for c in raw],
        })

    importable = [r for r in rows if r["skip"] is None]
    return {
        "columns": headers,
        "has_header": has_header,
        "mapping": cols,
        "mapping_suggested": suggested,
        "date_order": date_info,
        "sign": sign_info,
        "rows": rows,
        "summary": {
            "total": len(rows),
            "importable": len(importable),
            "duplicates": sum(1 for r in importable if r["duplicate_of"]),
            "skipped": len(rows) - len(importable),
            "uncategorised": sum(1 for r in importable if not r["category"]),
            "amount": sum(r["amount"] for r in importable
                          if not r["duplicate_of"]),
        },
    }
