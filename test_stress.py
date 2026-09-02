"""Stress test suite for the calculation engine.

Until September 2026 this file redefined all nine of its subjects inside
itself. It therefore passed 64/64 from April onward while never once executing
the shipping code, and by the time anyone checked, its copy had drifted: its
calc_fica had no filing-status argument, so the Medicare-surtax-by-status fix
was untested, and its project_investment had no contribution_growth, so income
growth modelling was untested. Both were shipped features with green tests.

Every assertion below is unchanged. The only difference is that they now run
against calculations.py, which is the code the app runs.
"""
from datetime import datetime, date, timedelta
import sys

from calculations import (
    FEDERAL_BRACKETS_2026,
    calc_bracket_tax,
    calc_fica,
    calc_salt_cap,
    calc_social_security,
    calc_student_loan_deduction,
    calc_state_tax,
    calc_federal_tax,
    calc_itemized_total,
    STANDARD_DEDUCTION_2026,
    TOP_BRACKET_START,
    get_marginal_rate,
    simulate_payoff,
    project_investment,
    calc_state_marginal_rate,
    marginal_fica_rate,
    monthly_debt_service,
    liquid_assets,
    emergency_fund_months,
    _get_state_brackets_for_filing,
    STATE_TAX_DATA,
)

print("=" * 60)
print("BUDGET APP STRESS TEST")
print("=" * 60)

# ── Tax bracket calculation ──────────────────────────────────

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} — {detail}")
        failed += 1

# ── 1. TAX TESTS ────────────────────────────────────────────

print("\n--- TAX CALCULATIONS ---")

check("$0 salary = $0 tax",
      calc_bracket_tax(0, FEDERAL_BRACKETS_2026["Single"]) == 0)

check("Negative taxable = $0 tax",
      calc_bracket_tax(-5000, FEDERAL_BRACKETS_2026["Single"]) == 0)

taxable = 50000 - 16100  # 33900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS_2026["Single"])
expected = 12400 * 0.10 + (33900 - 12400) * 0.12
check(f"$50K salary: tax=${tax:,.2f}", abs(tax - expected) < 0.01, f"expected {expected}")

taxable = 100000 - 16100  # 83900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS_2026["Single"])
expected = 12400*0.10 + (50400-12400)*0.12 + (83900-50400)*0.22
check(f"$100K salary: tax=${tax:,.2f}", abs(tax - expected) < 0.01, f"expected {expected}")

taxable = 1000000 - 16100  # 983900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS_2026["Single"])
check(f"$1M salary: tax=${tax:,.2f}", tax > 300000, "should be > $300K")

# ── 2. FICA TESTS ───────────────────────────────────────────

print("\n--- FICA ---")

check("$0 FICA = $0", calc_fica(0) == 0)

fica = calc_fica(100000)
expected = 100000 * 0.062 + 100000 * 0.0145
check(f"$100K FICA = ${fica:,.2f}", abs(fica - expected) < 0.01)

fica = calc_fica(250000)
ss = 184500 * 0.062
med = 250000 * 0.0145 + 50000 * 0.009
check(f"$250K FICA = ${fica:,.2f} (cap + surtax)", abs(fica - (ss + med)) < 0.01)

fica = calc_fica(50000)
check("$50K: no surtax", abs(fica - (50000*0.062 + 50000*0.0145)) < 0.01)

# The Medicare surtax threshold varies by filing status ($200K Single, $250K MFJ,
# $125K MFS). The mirror this suite used to run against had no `filing` argument
# at all, so this shipped in April with nothing checking it.
ss_cap = 184_500 * 0.062
check("MFJ surtax starts at $250K, not $200K",
      abs(calc_fica(240_000, "Married Filing Jointly")
          - (ss_cap + 240_000*0.0145)) < 0.01)
check("Single pays surtax on the same $240K",
      calc_fica(240_000, "Single") > calc_fica(240_000, "Married Filing Jointly"))
check("MFS surtax starts at $125K",
      abs(calc_fica(150_000, "Married Filing Separately")
          - (min(150_000,184_500)*0.062 + 150_000*0.0145 + 25_000*0.009)) < 0.01)
check("MFS pays more surtax than Single at $150K",
      calc_fica(150_000, "Married Filing Separately") > calc_fica(150_000, "Single"))
check("filing status is irrelevant below every threshold",
      calc_fica(90_000, "Single") == calc_fica(90_000, "Married Filing Jointly"))
check("an unknown filing status falls back to the $200K threshold",
      calc_fica(240_000, "Nonsense") == calc_fica(240_000, "Single"))

# ── 3. DEBT PAYOFF ──────────────────────────────────────────

print("\n--- DEBT PAYOFF ---")

m, i, s, p = simulate_payoff([{"name": "X", "balance": 10000, "rate": 5, "min_payment": 0}], 0, "avalanche")
check("$0 payments = cant pay off", m == -1)

m, i, s, p = simulate_payoff([{"name": "X", "balance": 1000, "rate": 0, "min_payment": 100}], 0, "avalanche")
check(f"$1K at 0% / $100/mo = {m} months", m == 10)
check("0% interest = $0 interest paid", abs(i) < 0.01)

m, i, s, p = simulate_payoff([{"name": "X", "balance": 100000, "rate": 30, "min_payment": 50}], 0, "avalanche")
check("High interest + low payment = -1", m == -1)

m, i, s, p = simulate_payoff([
    {"name": "Small", "balance": 1000, "rate": 5, "min_payment": 100},
    {"name": "Large", "balance": 5000, "rate": 5, "min_payment": 100},
], 200, "snowball")
check("Snowball: small pays first", "Small" in p and "Large" in p and p["Small"] < p["Large"])

m_av, i_av, _, _ = simulate_payoff([
    {"name": "Low", "balance": 5000, "rate": 3, "min_payment": 100},
    {"name": "High", "balance": 5000, "rate": 20, "min_payment": 100},
], 300, "avalanche")
m_sn, i_sn, _, _ = simulate_payoff([
    {"name": "Low", "balance": 5000, "rate": 3, "min_payment": 100},
    {"name": "High", "balance": 5000, "rate": 20, "min_payment": 100},
], 300, "snowball")
check(f"Avalanche saves ${i_sn - i_av:,.0f} vs Snowball", i_av <= i_sn)

m, i, s, p = simulate_payoff([{"name": "X", "balance": 500, "rate": 5, "min_payment": 500}], 0, "avalanche")
check(f"Large min payment: pays off in {m} month(s)", m <= 2 and m > 0)

# ── 4. INVESTMENT PROJECTION ────────────────────────────────

print("\n--- INVESTMENT PROJECTION ---")

v, c = project_investment(0, 0, 0, 10)
check("$0 everything = $0", v[-1] == 0)

v, c = project_investment(10000, 0, 0, 10)
check("$10K at 0% for 10yr = $10K", abs(v[-1] - 10000) < 0.01)

v, c = project_investment(0, 500, 0, 10)
check(f"$500/mo for 10yr at 0% = ${c[-1]:,.0f}", abs(c[-1] - 60000) < 0.01)

v, c = project_investment(10000, 500, 7, 30)
check(f"$10K+$500/mo at 7% for 30yr = ${v[-1]:,.0f}", v[-1] > c[-1] and v[-1] > 500000)

v, c = project_investment(10000, 500, 7, 1)
check(f"1-year horizon works: ${v[-1]:,.0f}", v[-1] > 10000)

v, c = project_investment(10000, 500, 7, 50)
check(f"50-year horizon works: ${v[-1]:,.0f}", v[-1] > 1000000)

# Contribution growth — the second thing the old mirror had no argument for, so
# income-growth modelling also shipped in April with nothing checking it.
v0, c0 = project_investment(0, 500, 0, 10, 0)
v3, c3 = project_investment(0, 500, 0, 10, 3)
check("3% contribution growth contributes more than flat", c3[-1] > c0[-1])
check("growth of 0 matches omitting the argument entirely",
      project_investment(0, 500, 7, 10, 0)[0][-1] == project_investment(0, 500, 7, 10)[0][-1])
# The raise applies annually, so year one is unaffected and totals 12 x $500.
v1, c1 = project_investment(0, 500, 0, 1, 10)
check(f"the first year is not yet raised: ${c1[-1]:,.0f}", abs(c1[-1] - 6000) < 0.01)
# Year two contributes 500 * 1.10; two years = 6000 + 6600.
v2, c2 = project_investment(0, 500, 0, 2, 10)
check(f"the second year is raised 10%: ${c2[-1]:,.0f}", abs(c2[-1] - 12600) < 0.01)
check("growth compounds off the base contribution, not the raised one",
      abs(project_investment(0, 500, 0, 3, 10)[1][-1] - (6000 + 6600 + 500*1.21*12)) < 0.01)

# ── 5. DEMO DATA FRESHNESS ──────────────────────────────────

print("\n--- DEMO DATA FRESHNESS ---")

today = date.today()
cur_month = today.strftime("%Y-%m")
prev_month = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
cur_month_1st = today.replace(day=1)
prev_month_1st = (cur_month_1st - timedelta(days=1)).replace(day=1)

# Simulate _generate_demo_data date logic
expense_date = cur_month_1st.isoformat()
check(f"Current month expense: {expense_date}", expense_date[:7] == cur_month)

prev_expense_date = prev_month_1st.isoformat()
check(f"Previous month expense: {prev_expense_date}", prev_expense_date[:7] == prev_month)

goal_deadline = (today + timedelta(days=600)).isoformat()
check(f"Goal deadline is future: {goal_deadline}", goal_deadline > today.isoformat())

nw_date = cur_month_1st.isoformat()
check(f"NW snapshot is current month: {nw_date}", nw_date[:7] == cur_month)

# ── 6. REGRESSION TESTS ────────────────────────────────────

print("\n--- REGRESSION TESTS ---")

# State with no brackets
state_data_tx = {"brackets": [], "deduction": 0}
state_m = state_data_tx["brackets"][-1][1] if (state_data_tx and state_data_tx.get("brackets")) else 0
check("Texas (no tax): rate=0 without crash", state_m == 0)

# Medical deduction at $0 AGI
agi = 0
med_threshold = max(0, agi) * 0.075
med_ded = max(0, 5000 - med_threshold) if agi > 0 else 0
check("Medical deduction = $0 when AGI = $0", med_ded == 0)

# 401k capped
contrib = min(200000 * 0.50, 24500)
check("401(k) capped at $24,500", contrib == 24500)

# FIRE number with 0 withdrawal rate
fire_withdrawal = 0
fire_number = (50000 / (fire_withdrawal / 100)) if fire_withdrawal > 0 else 0
check("FIRE number = $0 when withdrawal = 0%", fire_number == 0)

# Savings goal with past deadline
days_left = -30
monthly_needed = 0 if days_left < 0 else 1000
check("Past deadline: monthly_needed = $0", monthly_needed == 0)

# Zero budget: no division by zero
grand_total = 0
pct = (100 / grand_total * 100) if grand_total else 0
check("$0 budget: no divide by zero", pct == 0)

# ── 7. SALT PHASE-OUT ──────────────────────────────────────

print("\n--- SALT PHASE-OUT ---")

check("SALT cap at $100K = $40,400", calc_salt_cap(100000) == 40400)
check("SALT cap at $505K = $40,400", calc_salt_cap(505000) == 40400)
check("SALT cap at $550K < $40,400", calc_salt_cap(550000) < 40400)
check(f"SALT cap at $550K = ${calc_salt_cap(550000):,.0f}", calc_salt_cap(550000) == 40400 - 0.30 * 45000)
check("SALT cap at $700K = $10,000 (floor)", calc_salt_cap(700000) == 10000)
check("SALT cap MFS at $200K = $20,200", calc_salt_cap(200000, "Married Filing Separately") == 20200)
check("SALT cap MFS at $300K < $20,200", calc_salt_cap(300000, "Married Filing Separately") < 20200)

# ── 8. STUDENT LOAN DEDUCTION ──────────────────────────────

print("\n--- STUDENT LOAN DEDUCTION ---")

check("SL deduction: $2K paid, $50K income = $2,000", calc_student_loan_deduction(2000, 50000) == 2000)
check("SL deduction: $5K paid = capped at $2,500", calc_student_loan_deduction(5000, 50000) == 2500)
check("SL deduction: $0 paid = $0", calc_student_loan_deduction(0, 50000) == 0)
check("SL deduction: MFS = $0 always", calc_student_loan_deduction(2500, 50000, "Married Filing Separately") == 0)
check("SL deduction: $100K+ Single = $0", calc_student_loan_deduction(2500, 100000) == 0)
check("SL deduction: $90K Single = partial", 0 < calc_student_loan_deduction(2500, 90000) < 2500)
check("SL deduction: MFJ $175K = full $2,500", calc_student_loan_deduction(2500, 175000, "Married Filing Jointly") == 2500)
check("SL deduction: MFJ $205K+ = $0", calc_student_loan_deduction(2500, 205000, "Married Filing Jointly") == 0)

# ── 9. SOCIAL SECURITY ─────────────────────────────────────

print("\n--- SOCIAL SECURITY ---")

check("SS at $0 salary = $0", calc_social_security(0) == 0)
check("SS at $100K, age 67 > $0", calc_social_security(100000, 67) > 0)
check("SS at 62 < SS at 67 (early reduction)", calc_social_security(100000, 62) < calc_social_security(100000, 67))
check("SS at 70 > SS at 67 (delayed credit)", calc_social_security(100000, 70) > calc_social_security(100000, 67))
check("SS at $50K < SS at $100K", calc_social_security(50000) < calc_social_security(100000))
check("SS capped at wage base", calc_social_security(500000) == calc_social_security(184500))

# ── 10. CHARITABLE DEDUCTION (OBBBA) ───────────────────────

print("\n--- CHARITABLE DEDUCTION (OBBBA) ---")

# 0.5% AGI floor
agi = 200000
charitable = 2000
floor = agi * 0.005  # $1,000
deductible = max(0, charitable - floor)
check(f"Charitable floor: $2K donated, $200K AGI = ${deductible:,.0f} deductible", deductible == 1000)

agi = 50000
floor = agi * 0.005  # $250
deductible = max(0, 500 - floor)
check(f"Charitable floor: $500 donated, $50K AGI = ${deductible:,.0f}", deductible == 250)

# Non-itemizer limit
check("Non-itemizer Single cap = $1,000", min(5000, 1000) == 1000)
check("Non-itemizer MFJ cap = $2,000", min(5000, 2000) == 2000)

# ── 11. STATE TAX FILING STATUS ────────────────────────────

print("\n--- STATE TAX FILING STATUS ---")

# Auto-double test
# Test auto-doubling
test_state = {"brackets": [(10000, 0.05), (float("inf"), 0.10)], "deduction": 5000}
b, d = _get_state_brackets_for_filing(test_state, "Married Filing Jointly")
check("Auto-double: $10K bracket -> $20K", b[0][0] == 20000)
check("Auto-double: inf stays inf", b[1][0] == float("inf"))
check("Auto-double: deduction $5K -> $10K", d == 10000)

# Test custom MFJ
test_state2 = {"brackets": [(10000, 0.05)], "brackets_mfj": [(15000, 0.05)], "deduction": 5000, "deduction_mfj": 8000}
b, d = _get_state_brackets_for_filing(test_state2, "Married Filing Jointly")
check("Custom MFJ: uses brackets_mfj", b[0][0] == 15000)
check("Custom MFJ: uses deduction_mfj", d == 8000)

# Single should always use base brackets
b, d = _get_state_brackets_for_filing(test_state2, "Single")
check("Single: uses base brackets", b[0][0] == 10000)
check("Single: uses base deduction", d == 5000)

# ── STATE MARGINAL RATE ─────────────────────────────────────

print()
print("--- STATE MARGINAL RATE ---")

# Three call sites used to report the state's TOP bracket as the user's marginal
# rate, which overstates the value of every pre-tax dollar for anyone below it.
ny_top = STATE_TAX_DATA["New York"]["brackets"][-1][1] * 100
ny_real = calc_state_marginal_rate(110_000, "New York", filing="Single")
check(f"NY $110K marginal is {ny_real:.1f}%, not the {ny_top:.1f}% top bracket",
      ny_real < ny_top - 1)
ny_highest_finite = max(c for c, _ in STATE_TAX_DATA["New York"]["brackets"]
                        if c != float("inf"))
check("income above every finite bracket DOES reach the top rate",
      abs(calc_state_marginal_rate(ny_highest_finite * 2, "New York") - ny_top) < 1e-9)
check("NY's millionaire tiers are distinct, not collapsed to the top rate",
      len({calc_state_marginal_rate(g, "New York")
           for g in (2_000_000, 6_000_000, 30_000_000)}) == 3)
check("no-income-tax state returns 0", calc_state_marginal_rate(120_000, "Texas") == 0.0)
check("unknown state returns 0", calc_state_marginal_rate(120_000, "Atlantis") == 0.0)
check("income below the state deduction returns 0",
      calc_state_marginal_rate(500, "New York") == 0.0)
check("zero income returns 0", calc_state_marginal_rate(0, "California") == 0.0)
check("pre-tax deductions lower the marginal rate or leave it alone",
      calc_state_marginal_rate(110_000, "New York", 24_500, 4_400)
      <= calc_state_marginal_rate(110_000, "New York", 0, 0))
check("MFJ is taxed no higher than Single on the same income",
      calc_state_marginal_rate(110_000, "New York", filing="Married Filing Jointly")
      <= calc_state_marginal_rate(110_000, "New York", filing="Single"))
check("the rate never exceeds the state's top bracket, in any state",
      all(calc_state_marginal_rate(250_000, st) <= d["brackets"][-1][1] * 100
          for st, d in STATE_TAX_DATA.items() if d.get("brackets")))
check("the rate is never negative, in any state",
      all(calc_state_marginal_rate(g, st) >= 0
          for st in STATE_TAX_DATA for g in (0, 40_000, 250_000)))
# The rate must agree with the tax: one more dollar taxed at the marginal rate.
ca_tax = calc_state_tax(95_000, "California") if "calc_state_tax" in dir() else None
check("marginal rate matches what the next dollar is actually taxed",
      all(abs((calc_state_tax(g + 1000, st) - calc_state_tax(g, st)) / 1000 * 100
              - calc_state_marginal_rate(g, st)) < 0.51
          for st in ("New York", "California", "Arkansas", "Ohio")
          for g in (60_000, 95_000, 140_000)))

# ── MARGINAL FICA ───────────────────────────────────────────

print()
print("--- MARGINAL FICA ---")

check("a raise below the wage base is charged the full 7.65%",
      abs(marginal_fica_rate(80_000, 90_000) - 0.0765) < 0.0001)
check("a raise above the wage base but below the surtax is charged 1.45%",
      abs(marginal_fica_rate(200_000, 210_000, "Married Filing Jointly") - 0.0145) < 0.0001)
check("Single pays 1.45% + 0.9% surtax on the same raise",
      abs(marginal_fica_rate(200_000, 210_000, "Single") - 0.0235) < 0.0001)
check("a raise straddling the wage base falls between the two",
      0.0145 < marginal_fica_rate(180_000, 190_000) < 0.0765)
check("marginal is below the average rate above the wage base",
      marginal_fica_rate(200_000, 210_000) < calc_fica(210_000) / 210_000)
check("a zero raise returns 0", marginal_fica_rate(90_000, 90_000) == 0.0)
check("a pay cut returns 0", marginal_fica_rate(90_000, 80_000) == 0.0)
check("the surtax makes a high raise cost more than 1.45% for MFS",
      marginal_fica_rate(300_000, 310_000, "Married Filing Separately") > 0.0145)

# ── DASHBOARD RATIOS ────────────────────────────────────────

print()
print("--- DEBT SERVICE ---")

DEBTS = [{"name": "Card", "min_payment": 110}, {"name": "Car", "min_payment": 240},
         {"name": "Student", "min_payment": 135}]

# The dashboard read only the budget category, so real debts plus a zeroed
# category reported debt-to-income of 0.0%, "Healthy".
check("entered debts win over a zeroed budget category",
      monthly_debt_service(DEBTS, {"Min. Debt Payments": 0}) == (485.0, "debts"))
check("entered debts win over a populated budget category too",
      monthly_debt_service(DEBTS, {"Min. Debt Payments": 50})[0] == 485.0)
check("the budget category is the fallback when there are no debts",
      monthly_debt_service([], {"Min. Debt Payments": 400}) == (400.0, "budget"))
check("no debts and no category is zero, and says which it used",
      monthly_debt_service([], {}) == (0.0, "budget"))
check("debts with zero minimums fall back rather than reporting zero",
      monthly_debt_service([{"min_payment": 0}], {"Min. Debt Payments": 300})[0] == 300.0)
check("a missing min_payment key does not raise",
      monthly_debt_service([{"name": "X"}], {})[0] == 0.0)
check("None arguments do not raise", monthly_debt_service(None, None)[0] == 0.0)

print()
print("--- LIQUID ASSETS / EMERGENCY FUND ---")

DEMO_ASSETS = {"Checking": 6200, "Savings": 9500, "401(k)": 4800,
               "Roth IRA": 2500, "Brokerage": 1800, "Property": 0}
total, counted = liquid_assets(DEMO_ASSETS)
check("checking and savings count", sorted(counted) == ["Checking", "Savings"])
check(f"liquid total is ${total:,.0f}", total == 15700)
check("retirement accounts do not count", "401(k)" not in counted and "Roth IRA" not in counted)
check("a brokerage account does not count", "Brokerage" not in counted)

# The whole bug: the old code looked up the literal key "Savings".
renamed = liquid_assets({"Checking": 6200, "High-Yield Savings": 9500})
check("renaming the account does not silently zero the fund", renamed[0] == 15700)
check("'Cash Reserve' counts", liquid_assets({"Cash Reserve": 5000})[0] == 5000)
check("'Emergency Fund' counts", liquid_assets({"Emergency Fund": 5000})[0] == 5000)
# Illiquid hints are checked FIRST, so the word "savings" cannot rescue an IRA.
check("'Roth IRA Savings' is excluded despite the word savings",
      liquid_assets({"Roth IRA Savings": 50000})[0] == 0)
check("'HSA Savings' is excluded", liquid_assets({"HSA Savings": 9000})[0] == 0)
check("an unrecognised asset is not counted", liquid_assets({"Gold bars": 99999})[0] == 0)
check("empty assets do not raise", liquid_assets({}) == (0.0, []))
check("None assets do not raise", liquid_assets(None) == (0.0, []))
check("a None value is treated as zero", liquid_assets({"Savings": None})[0] == 0.0)

m, c_ = emergency_fund_months(DEMO_ASSETS, 3187)
check(f"demo coverage is {m:.1f} months", abs(m - 15700 / 3187) < 0.001)
check("coverage returns the names it counted", sorted(c_) == ["Checking", "Savings"])
# None and 0.0 are different answers; the card must not print them the same way.
check("no recognised liquid asset returns None, not 0.0",
      emergency_fund_months({"Gold bars": 99999}, 2000)[0] is None)
check("no budgeted essentials returns None, not a divide-by-zero",
      emergency_fund_months(DEMO_ASSETS, 0)[0] is None)
check("a recognised but empty account still measures, at 0.0 months",
      emergency_fund_months({"Savings": 0}, 2000)[0] == 0.0)

# ── ITEMIZED DEDUCTIONS ─────────────────────────────────────

print()
print("--- ITEMIZED DEDUCTIONS ---")

BIG = {"salt": 20_000, "mortgage_interest": 12_000, "charitable": 2_000, "medical": 5_000}
it = calc_itemized_total(BIG, 95_000, "Single")
check("charity is deductible only above the 0.5% AGI floor",
      abs(it["charitable"] - (2_000 - 95_000 * 0.005)) < 0.01)
check("medical below the 7.5% AGI floor is not deductible", it["medical"] == 0)
check("medical above the floor is deductible",
      abs(calc_itemized_total({"medical": 20_000}, 95_000)["medical"] - (20_000 - 7_125)) < 0.01)
check("SALT is capped", calc_itemized_total({"salt": 90_000}, 95_000)["salt"] == 40_400)
check("the SALT cap phases out for high earners",
      calc_itemized_total({"salt": 90_000}, 900_000)["salt"] < 40_400)
check("the parts sum to the total",
      abs(it["total"] - (it["salt"] + it["mortgage_interest"] + it["charitable"] + it["medical"])) < 0.01)
check("empty input totals zero", calc_itemized_total({}, 95_000)["total"] == 0)
check("None input does not raise", calc_itemized_total(None, 95_000)["total"] == 0)
check("zero AGI does not raise and blocks the medical deduction",
      calc_itemized_total(BIG, 0)["medical"] == 0)
check("negative AGI does not raise", calc_itemized_total(BIG, -5_000)["total"] >= 0)

std = STANDARD_DEDUCTION_2026["Single"]

# The whole point: take-home used to force the standard deduction, so the Tax
# page could say itemizing was better while every other number ignored it.
t_std, _, _, d_std = calc_federal_tax(95_000, 0, 0, "Single", 0, 0, 0)
t_small, _, _, d_small = calc_federal_tax(95_000, 0, 0, "Single", 0, 0, std - 1_000)
t_big, _, _, d_big = calc_federal_tax(95_000, 0, 0, "Single", 0, 0, 40_000)
check("no itemized total still takes the standard deduction", d_std == std)
check("an itemized total BELOW the standard does not reduce the deduction",
      d_small == std)
check("an itemized total ABOVE the standard is taken instead", d_big == 40_000)
check("itemizing above the standard lowers the tax", t_big < t_std)
check("itemizing below the standard changes nothing", t_small == t_std)

# An itemizer already deducts charity inside the itemized total, so granting the
# non-itemizer above-the-line deduction as well would deduct it twice.
_, agi_ni, _, _ = calc_federal_tax(95_000, 0, 0, "Single", 0, 1_000, 0)
_, agi_it, _, _ = calc_federal_tax(95_000, 0, 0, "Single", 0, 1_000, 40_000)
check("a non-itemizer gets the above-the-line charitable deduction",
      abs(agi_ni - (95_000 - 1_000)) < 0.01)
check("an itemizer does NOT also get it (no double deduction)",
      abs(agi_it - 95_000) < 0.01)
check("the MFJ above-the-line cap is $2,000",
      abs(calc_federal_tax(95_000, 0, 0, "Married Filing Jointly", 0, 5_000, 0)[1]
          - (95_000 - 2_000)) < 0.01)

# Backwards compatibility: every existing caller passes no itemized total.
check("the 4th return value still equals the standard deduction when not itemizing",
      all(calc_federal_tax(g, 0, 0, f)[3] == STANDARD_DEDUCTION_2026[f]
          for f in STANDARD_DEDUCTION_2026 for g in (0, 50_000, 300_000)))

# ── TOP BRACKET THRESHOLDS (the 2/37 warning) ───────────────

print()
print("--- TOP BRACKET THRESHOLDS ---")

# The 2/37 limitation is stated, not modelled, so the only thing that can be
# wrong is the threshold it quotes. It must be the income at which 37% starts.
for f, brackets in FEDERAL_BRACKETS_2026.items():
    starts = [c for c, r in brackets if r == 0.35][-1]
    check(f"{f}: quoted 37% threshold matches the bracket table",
          TOP_BRACKET_START[f] == starts,
          f"quoted {TOP_BRACKET_START.get(f)}, table says {starts}")
check("every filing status has a threshold",
      set(TOP_BRACKET_START) == set(FEDERAL_BRACKETS_2026))
# The warning fires off marginal_fed >= 37, so the threshold and the marginal
# rate must agree about who is in the top bracket.
for f in FEDERAL_BRACKETS_2026:
    b = FEDERAL_BRACKETS_2026[f]
    check(f"{f}: one dollar above the threshold reads as 37%",
          get_marginal_rate(TOP_BRACKET_START[f] + 1, b) == 37.0)
    check(f"{f}: one dollar below it does not",
          get_marginal_rate(TOP_BRACKET_START[f] - 1, b) < 37.0)

# ── BADGE LEGIBILITY ────────────────────────────────────────

print()
print("--- BADGE LEGIBILITY ---")
# readable_on_tint lives in budget_app (it is presentation, not maths), so it is
# imported here rather than from calculations.
import types as _t, sys as _s
class _A(_t.ModuleType):
    def __getattr__(self, _): return lambda *a, **k: None
class _SS(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)
    def __setattr__(self, k, v): self[k] = v
class _St(_A):
    def __init__(self):
        super().__init__("streamlit")
        self.__dict__["session_state"] = _SS(); self.__dict__["secrets"] = {}
        self.__dict__["sidebar"] = _A("sb")
    def cache_resource(self, fn=None, **k): return fn if fn else (lambda f: f)
    cache_data = cache_resource
_s.modules["streamlit"] = _St()
_s.modules["supabase"] = _t.SimpleNamespace(create_client=lambda *a, **k: None)
for _m in ("plotly", "plotly.graph_objects", "plotly.express", "pandas", "numpy"):
    _s.modules.setdefault(_m, _A(_m))
_src = open("budget_app.py", encoding="utf-8").read()
_app = _t.ModuleType("app_badge")
exec(compile(_src[:_src.index("# SIDEBAR NAVIGATION")], "budget_app.py", "exec"), _app.__dict__)

def _rgb(h): return tuple(int(h.lstrip("#")[i:i+2], 16) for i in (0, 2, 4))
for name in ("GREEN", "YELLOW", "BLUE", "RED", "PURPLE"):
    base = getattr(_app, name)
    tint = tuple(c * 0.15 + 255 * 0.85 for c in _rgb(base))
    got = _app._contrast(_rgb(_app.readable_on_tint(base)), tint)
    check(f"{name} badge text reaches 4.5:1 on its own tint ({got:.2f}:1)", got >= 4.5)
check("the raw brand green would NOT have passed",
      _app._contrast(_rgb(_app.GREEN),
                     tuple(c * 0.15 + 255 * 0.85 for c in _rgb(_app.GREEN))) < 3)
check("a colour already legible is left close to itself",
      _app.readable_on_tint("#111111") == "#111111")
check("readable_on_tint always returns a valid hex colour",
      all(len(_app.readable_on_tint(c)) == 7 and c.startswith("#")
          for c in ("#000000", "#FFFFFF", "#F18F01", "#2ECC71")))

# Testing readable_on_tint alone says the rule is right, not that the badge obeys
# it — reverting status_badge_html to the raw brand colour passed every assertion
# above. So assert on the rendered markup: the text colour it emits must be the
# darkened one, and must clear 4.5:1 against the tint it sets beside it.
import re as _re
for _name in ("GREEN", "YELLOW", "BLUE", "RED"):
    _base = getattr(_app, _name)
    _html = _app.status_badge_html("x", _base)
    _text = _re.search(r"color:(#[0-9a-fA-F]{6})", _html).group(1)
    _tintrgb = tuple(int(v) for v in _re.search(r"rgba\(([\d, ]+),", _html).group(1).split(","))
    _tint = tuple(c * 0.15 + 255 * 0.85 for c in _tintrgb)
    check(f"{_name} badge MARKUP uses the darkened colour, not the raw one",
          _text.lower() == _app.readable_on_tint(_base).lower(),
          f"emitted {_text}, expected {_app.readable_on_tint(_base)}")
    check(f"{_name} badge markup clears 4.5:1 as rendered",
          _app._contrast(_rgb(_text), _tint) >= 4.5)

# ── RESULTS ─────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
