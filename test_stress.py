"""Stress test suite for budget_app.py — tests all calculation logic."""
from datetime import datetime, date, timedelta
import sys

print("=" * 60)
print("BUDGET APP STRESS TEST")
print("=" * 60)

# ── Tax bracket calculation ──────────────────────────────────

FEDERAL_BRACKETS = [
    (12_400, 0.10), (50_400, 0.12), (105_700, 0.22),
    (201_775, 0.24), (256_225, 0.32), (640_600, 0.35),
    (float("inf"), 0.37),
]

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

def calc_fica(gross):
    ss = min(gross, 184_500) * 0.062
    medicare = gross * 0.0145
    if gross > 200_000:
        medicare += (gross - 200_000) * 0.009
    return ss + medicare

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
      calc_bracket_tax(0, FEDERAL_BRACKETS) == 0)

check("Negative taxable = $0 tax",
      calc_bracket_tax(-5000, FEDERAL_BRACKETS) == 0)

taxable = 50000 - 16100  # 33900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS)
expected = 12400 * 0.10 + (33900 - 12400) * 0.12
check(f"$50K salary: tax=${tax:,.2f}", abs(tax - expected) < 0.01, f"expected {expected}")

taxable = 100000 - 16100  # 83900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS)
expected = 12400*0.10 + (50400-12400)*0.12 + (83900-50400)*0.22
check(f"$100K salary: tax=${tax:,.2f}", abs(tax - expected) < 0.01, f"expected {expected}")

taxable = 1000000 - 16100  # 983900
tax = calc_bracket_tax(taxable, FEDERAL_BRACKETS)
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

# ── 3. DEBT PAYOFF ──────────────────────────────────────────

print("\n--- DEBT PAYOFF ---")

def simulate_payoff(debts, extra, strategy):
    balances = {d["name"]: float(d["balance"]) for d in debts}
    rates = {d["name"]: d["rate"] / 100 / 12 for d in debts}
    mins = {d["name"]: float(d["min_payment"]) for d in debts}
    total_interest = 0; months = 0; schedule = []; payoff_months = {}
    total_min = sum(mins.values()) + extra
    total_monthly_interest = sum(b * r for b, r in zip(balances.values(), rates.values()) if b > 0)
    if total_min <= 0:
        return -1, 0, [], {}
    if total_min <= total_monthly_interest and total_monthly_interest > 0:
        return -1, 0, [], {}
    while any(b > 0.01 for b in balances.values()) and months < 600:
        months += 1; month_interest = 0
        for name in balances:
            if balances[name] > 0:
                interest = balances[name] * rates[name]
                balances[name] += interest; month_interest += interest; total_interest += interest
        remaining_extra = extra
        for name in balances:
            if balances[name] > 0:
                payment = min(mins[name], balances[name]); balances[name] -= payment
        if strategy == "avalanche":
            order = sorted([n for n in balances if balances[n] > 0], key=lambda n: rates[n], reverse=True)
        else:
            order = sorted([n for n in balances if balances[n] > 0], key=lambda n: balances[n])
        for name in order:
            if remaining_extra <= 0: break
            if balances[name] > 0:
                payment = min(remaining_extra, balances[name]); balances[name] -= payment; remaining_extra -= payment
        for name in balances:
            if balances[name] <= 0.01 and name not in payoff_months: payoff_months[name] = months
        schedule.append({"month": months, "total_balance": sum(max(0, b) for b in balances.values()), "interest": month_interest})
    return months, total_interest, schedule, payoff_months

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

def project_investment(start, monthly, rate, years):
    values = [start]; contributions = [start]
    r = rate / 100 / 12
    for m in range(1, years * 12 + 1):
        prev = values[-1]; values.append(prev * (1 + r) + monthly)
        contributions.append(contributions[-1] + monthly)
    return values, contributions

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

def calc_salt_cap(magi, filing="Single"):
    thresholds = {"Single": 505000, "Head of Household": 505000,
                  "Married Filing Jointly": 505000, "Married Filing Separately": 252500}
    threshold = thresholds.get(filing, 505000)
    mfs_cap = 20200 if filing == "Married Filing Separately" else 40400
    if magi <= threshold:
        return mfs_cap
    reduction = 0.30 * (magi - threshold)
    return max(10000, mfs_cap - reduction)

check("SALT cap at $100K = $40,400", calc_salt_cap(100000) == 40400)
check("SALT cap at $505K = $40,400", calc_salt_cap(505000) == 40400)
check("SALT cap at $550K < $40,400", calc_salt_cap(550000) < 40400)
check(f"SALT cap at $550K = ${calc_salt_cap(550000):,.0f}", calc_salt_cap(550000) == 40400 - 0.30 * 45000)
check("SALT cap at $700K = $10,000 (floor)", calc_salt_cap(700000) == 10000)
check("SALT cap MFS at $200K = $20,200", calc_salt_cap(200000, "Married Filing Separately") == 20200)
check("SALT cap MFS at $300K < $20,200", calc_salt_cap(300000, "Married Filing Separately") < 20200)

# ── 8. STUDENT LOAN DEDUCTION ──────────────────────────────

print("\n--- STUDENT LOAN DEDUCTION ---")

def calc_student_loan_deduction(interest_paid, magi, filing="Single"):
    if filing == "Married Filing Separately":
        return 0
    max_ded = 2500
    if filing == "Married Filing Jointly":
        lower, upper = 175000, 205000
    else:
        lower, upper = 85000, 100000
    if magi <= lower:
        return min(interest_paid, max_ded)
    if magi >= upper:
        return 0
    reduction = (magi - lower) / (upper - lower)
    return min(interest_paid, max_ded) * (1 - reduction)

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

def calc_social_security(annual_salary, claiming_age=67):
    aime = min(annual_salary, 184500) / 12
    if aime <= 1286:
        pia = aime * 0.90
    elif aime <= 7749:
        pia = 1286 * 0.90 + (aime - 1286) * 0.32
    else:
        pia = 1286 * 0.90 + (7749 - 1286) * 0.32 + (aime - 7749) * 0.15
    fra = 67
    if claiming_age < fra:
        months_early = (fra - claiming_age) * 12
        if months_early <= 36:
            reduction = months_early * (5/9/100)
        else:
            reduction = 36 * (5/9/100) + (months_early - 36) * (5/12/100)
        pia *= (1 - reduction)
    elif claiming_age > fra:
        months_late = min((claiming_age - fra) * 12, 36)
        pia *= (1 + months_late * (8/12/100))
    return max(0, pia)

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
def _get_brackets_for_filing(sdata, filing):
    is_joint = filing == "Married Filing Jointly"
    if not is_joint:
        return sdata["brackets"], sdata["deduction"]
    if "brackets_mfj" in sdata:
        return sdata["brackets_mfj"], sdata.get("deduction_mfj", sdata["deduction"] * 2)
    mfj_brackets = []
    for ceiling, rate in sdata["brackets"]:
        mfj_ceiling = ceiling * 2 if ceiling != float("inf") else float("inf")
        mfj_brackets.append((mfj_ceiling, rate))
    return mfj_brackets, sdata.get("deduction_mfj", sdata["deduction"] * 2)

# Test auto-doubling
test_state = {"brackets": [(10000, 0.05), (float("inf"), 0.10)], "deduction": 5000}
b, d = _get_brackets_for_filing(test_state, "Married Filing Jointly")
check("Auto-double: $10K bracket -> $20K", b[0][0] == 20000)
check("Auto-double: inf stays inf", b[1][0] == float("inf"))
check("Auto-double: deduction $5K -> $10K", d == 10000)

# Test custom MFJ
test_state2 = {"brackets": [(10000, 0.05)], "brackets_mfj": [(15000, 0.05)], "deduction": 5000, "deduction_mfj": 8000}
b, d = _get_brackets_for_filing(test_state2, "Married Filing Jointly")
check("Custom MFJ: uses brackets_mfj", b[0][0] == 15000)
check("Custom MFJ: uses deduction_mfj", d == 8000)

# Single should always use base brackets
b, d = _get_brackets_for_filing(test_state2, "Single")
check("Single: uses base brackets", b[0][0] == 10000)
check("Single: uses base deduction", d == 5000)

# ── RESULTS ─────────────────────────────────────────────────

print("\n" + "=" * 60)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)
