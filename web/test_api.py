"""Tests for the calculation API — drives the SHIPPING api/index.py.

Nothing here re-derives an expected number with a second copy of the algorithm;
that is the mirror problem that let 64 assertions stay green from April to
September while never executing the app. Instead every assertion is either a
property that must hold (money in equals money out), or a comparison against
calculations.py itself — proving the route is a pass-through and not a place
arithmetic has quietly grown.

Run:  .venv/Scripts/python.exe test_api.py     (from web/)
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api"))

from fastapi.testclient import TestClient          # noqa: E402

import calculations as calc                        # noqa: E402
import index                                       # noqa: E402

client = TestClient(index.app)

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


print("=" * 66)
print("API SUITE — driving the shipping api/index.py")
print("=" * 66)

INCOME = {
    "gross_salary": 95_000, "state": "New York", "filing_status": "Single",
    "contribution_401k": 6, "health_insurance": 180, "hsa": 100,
    "bonus_amount": 10_000, "bonus_type": "Annual (spread monthly)",
    "student_loan_interest": 0,
}
DEBTS = [
    {"name": "Card", "balance": 6_000, "rate": 22.0, "min_payment": 120},
    {"name": "Car", "balance": 18_000, "rate": 6.5, "min_payment": 300},
    {"name": "Student", "balance": 32_000, "rate": 5.5, "min_payment": 320},
]
NEEDS = {"Rent": 1_900, "Utilities": 130, "Groceries": 380,
         "Min. Debt Payments": 0, "Phone": 75}
ASSETS = {"Checking": 6_200, "Savings": 9_500, "401(k)": 4_800,
          "Roth IRA": 2_500, "Brokerage": 1_800}

# ── 1. The module under the routes is the repo's one copy ────────────
print("\n--- the API imports the shared engine, not a fork ---")
check("api/calculations.py is the repo root's file, byte for byte",
      open(os.path.join("api", "calculations.py"), "rb").read().endswith(
          open(os.path.join("..", "calculations.py"), "rb").read()),
      "the sync did not produce a verbatim copy")
check("and it is not committed — exactly one copy is in version control",
      "api/calculations.py" in open(".gitignore", encoding="utf-8").read())
_api_src = open(os.path.join("api", "index.py"), encoding="utf-8").read()
check("no route body does its own arithmetic on money",
      " * (1 +" not in _api_src and "** years" not in _api_src
      and "/ 12 * 100" not in _api_src,
      "an expression that belongs in calculations.py has appeared in a route")

# ── 2. Health and reference ──────────────────────────────────────────
print("\n--- health and reference ---")
r = client.get("/api/health")
check("health answers 200", r.status_code == 200, str(r.status_code))

ref = client.get("/api/reference").json()
check("reference lists every filing status the engine knows",
      ref["filing_statuses"] == calc.FILING_STATUSES)
check("reference lists every state the engine knows",
      ref["states"] == sorted(calc.STATE_TAX_DATA.keys()))
check("reference carries the contribution limits, so the client hardcodes none",
      ref["k401_limit"] == calc.K401_LIMIT
      and ref["hsa_individual_limit"] == calc.HSA_INDIVIDUAL_LIMIT)
# float("inf") is not JSON. If it leaked through as a string or a float it would
# reach the client as something that is not a number and not null.
_tops = [b[-1][0] for b in ref["federal_brackets"].values()]
check("the open-ended top bracket is sent as null, not Infinity",
      all(t is None for t in _tops), str(_tops))
check("every other ceiling is a real number",
      all(isinstance(c, (int, float)) for b in ref["federal_brackets"].values()
          for c, _ in b[:-1]))

# ── 2b. the starting profile is served, not retyped ──────────────────
print("\n--- starting state ---")
import app_data                                    # noqa: E402

demo = client.get("/api/state").json()
empty = client.get("/api/state?demo=false").json()
check("the demo profile is app_data's, key for key",
      set(demo) == set(app_data._generate_demo_data()))
check("the empty profile is app_data's, key for key",
      set(empty) == set(app_data.get_default_state()))
# The property test_calc.py asserts on the same profile: with ONE debt the two
# payoff strategies are identical by definition and the debt page's comparison
# is dead. The abandoned scaffold's hand-written TypeScript copy had one.
check("the demo ships more than one debt", len(demo["debts"]) > 1,
      f'{len(demo["debts"])} debt(s)')
_rate_order = [d["name"] for d in sorted(demo["debts"], key=lambda d: -d["rate"])]
_bal_order = [d["name"] for d in sorted(demo["debts"], key=lambda d: d["balance"])]
check("and its rate order conflicts with its balance order, so the two "
      "strategies cannot agree by accident", _rate_order != _bal_order)
check("the empty profile really is empty",
      empty["expenses"] == [] and empty["debts"] == []
      and empty["savings_goals"] == [])
# Relative dates, always: a demo pinned to fixed dates reads as abandoned
# within a month.
_this_month = __import__("datetime").date.today().strftime("%Y-%m")
check("demo expenses are dated relative to today, not hardcoded",
      any(e["date"].startswith(_this_month) for e in demo["expenses"]),
      "no expense falls in the current month")


# ── 3. take-home is a pass-through ───────────────────────────────────
print("\n--- take-home ---")
body = {"income": INCOME, "itemized": {}}
got = client.post("/api/take-home", json=body).json()
want = calc.compute_take_home(INCOME, {})
check("every field matches calculations.compute_take_home exactly",
      all(abs(got[k] - want[k]) < 1e-9 for k in want if isinstance(want[k], (int, float)))
      and got["filing"] == want["filing"],
      str({k: (got[k], want[k]) for k in want if got[k] != want[k]}))
check("the itemized dict reaches the engine",
      client.post("/api/take-home", json={
          "income": INCOME,
          "itemized": {"mortgage_interest": 30_000, "salt": 25_000},
      }).json()["itemizing"] is True)
check("a request with no itemized key still works",
      client.post("/api/take-home", json={"income": INCOME}).status_code == 200)

# ── 4. dashboard: the two ratios that were wrong twice ───────────────
print("\n--- dashboard ratios ---")
dash = client.post("/api/dashboard", json={
    "income": INCOME, "debts": DEBTS, "budget_needs": NEEDS, "assets": ASSETS,
}).json()

check("debt service comes from the entered debts, not the budget category",
      dash["monthly_debt_service"] == sum(d["min_payment"] for d in DEBTS)
      and dash["debt_service_source"] == "debts",
      f'{dash["monthly_debt_service"]} from {dash["debt_service_source"]}')
# The exact failure both earlier versions shipped: real debts, a zero in the
# "Min. Debt Payments" budget row, and a dashboard reading 0.0% "Debt-Free".
check("real debts with a zero in that budget row do NOT read as debt-free",
      dash["dti_pct"] > 0, f'dti {dash["dti_pct"]}')
_gross_monthly = dash["take_home"]["annual_gross"] / 12
check("DTI divides by GROSS, the base the 20%/36% lender bands are defined on",
      abs(dash["dti_pct"] - dash["monthly_debt_service"] / _gross_monthly * 100) < 1e-9,
      f'{dash["dti_pct"]}')
check("...and so is smaller than the take-home-based figure it replaced",
      dash["dti_pct"] < dash["monthly_debt_service"]
      / dash["take_home"]["monthly_take_home"] * 100)

_ef, _counted = calc.emergency_fund_months(ASSETS, sum(NEEDS.values()))
check("emergency fund counts every liquid asset, not the literal key 'Savings'",
      abs(dash["emergency_fund_months"] - _ef) < 1e-9
      and set(dash["emergency_fund_counted"]) == set(_counted)
      and len(_counted) > 1,
      str(dash["emergency_fund_counted"]))
check("renaming the savings row does not silently zero the coverage",
      client.post("/api/dashboard", json={
          "income": INCOME, "debts": DEBTS, "budget_needs": NEEDS,
          "assets": {"Checking": 6_200, "High-Yield Savings": 9_500},
      }).json()["emergency_fund_months"] > 0)
# None is not 0.0 — "could not be measured" against "measured, and it is zero".
_none = client.post("/api/dashboard", json={
    "income": INCOME, "debts": [], "budget_needs": NEEDS,
    "assets": {"401(k)": 50_000, "Roth IRA": 20_000},
}).json()
check("with no liquid assets, coverage is null rather than 0.0",
      _none["emergency_fund_months"] is None, str(_none["emergency_fund_months"]))
check("and with no essential spending budgeted, also null",
      client.post("/api/dashboard", json={
          "income": INCOME, "debts": [], "budget_needs": {}, "assets": ASSETS,
      }).json()["emergency_fund_months"] is None)
check("a zero income gives a null DTI rather than dividing by zero",
      client.post("/api/dashboard", json={
          "income": {**INCOME, "gross_salary": 0, "bonus_type": "None"},
          "debts": DEBTS, "budget_needs": NEEDS, "assets": ASSETS,
      }).json()["dti_pct"] is None)
check("with no debts entered it falls back to the budget category, and says so",
      client.post("/api/dashboard", json={
          "income": INCOME, "debts": [],
          "budget_needs": {**NEEDS, "Min. Debt Payments": 450}, "assets": ASSETS,
      }).json()["debt_service_source"] == "budget")

# ── 5. debt payoff ───────────────────────────────────────────────────
print("\n--- debt payoff ---")
pay = client.post("/api/debt-payoff", json={"debts": DEBTS, "extra": 300}).json()
for strategy in ("avalanche", "snowball"):
    m, i, sched, po = calc.simulate_payoff(DEBTS, 300, strategy)
    check(f"{strategy} matches the engine ({m} months, ${i:,.0f})",
          pay[strategy]["months"] == m
          and abs(pay[strategy]["total_interest"] - i) < 1e-9
          and pay[strategy]["payoff_months"] == po)
check("avalanche costs no more interest than snowball",
      pay["avalanche"]["total_interest"] <= pay["snowball"]["total_interest"])
# The bug the fork shipped: when a debt clears, its minimum stops being spent.
# A month count is not the test -- any threshold here would be a number invented
# to pass. The property is that every month but the last spends the FULL
# capacity, extra + every minimum, no matter how many debts remain.
_capacity = 300 + sum(d["min_payment"] for d in DEBTS)
for _strategy in ("avalanche", "snowball"):
    _sched = pay[_strategy]["schedule"]
    _prev = sum(d["balance"] for d in DEBTS)
    _spend = []
    for _row in _sched:
        _spend.append(_prev - _row["total_balance"] + _row["interest"])
        _prev = _row["total_balance"]
    _idle = [(i + 1, round(_capacity - v, 2)) for i, v in enumerate(_spend[:-1])
             if _capacity - v > 0.01]
    check(f"{_strategy}: a cleared debt's minimum keeps working "
          f"(no month underspends {_capacity:,.0f})",
          not _idle,
          f"{len(_idle)} of {len(_spend) - 1} months idle, first {_idle[:2]}")
# -1 is a sentinel, not a duration. A client that renders it as one shows
# "-1 months to debt-free".
_never = client.post("/api/debt-payoff", json={"debts": DEBTS, "extra": 0}).json()
_never = client.post("/api/debt-payoff", json={
    "debts": [{"name": "Card", "balance": 10_000, "rate": 25.0, "min_payment": 1}],
    "extra": 0}).json()["avalanche"]
check("payments that never clear the debt are flagged, not returned as -1 months",
      _never["months"] == -1 and _never["never_pays_off"] is True,
      str(_never["months"]))
check("no debts at all does not error",
      client.post("/api/debt-payoff", json={"debts": [], "extra": 0}).status_code == 200)

# ── 6. the rest ──────────────────────────────────────────────────────
print("\n--- projections ---")
inv = client.post("/api/investment", json={
    "start": 5_000, "monthly": 500, "rate": 7.0, "years": 30}).json()
_vals, _contribs = calc.project_investment(5_000, 500, 7.0, 30, 0)
check("investment matches the engine",
      inv["values"] == _vals and inv["contributions"] == _contribs)
# The engine returns an unnamed (values, contributions) tuple. Swapping them is
# a one-character mistake that plots contributions as the portfolio value, and
# both series start at the same number so the chart's left edge looks right.
check("values and contributions are not transposed",
      inv["final_value"] > inv["total_contributed"]
      and abs(inv["growth"] - (inv["final_value"] - inv["total_contributed"])) < 1e-9,
      f'final {inv["final_value"]:,.0f} vs contributed {inv["total_contributed"]:,.0f}')
check("one point per month, plus the starting balance",
      len(inv["values"]) == 30 * 12 + 1 and inv["months"] == 30 * 12)
check("a 0% return grows only by what was contributed",
      client.post("/api/investment", json={
          "start": 1_000, "monthly": 100, "rate": 0.0, "years": 1
      }).json()["growth"] == 0)

mc = client.post("/api/monte-carlo", json={
    "current_age": 24, "retire_age": 45, "end_age": 95, "portfolio": 25_000,
    "annual_savings": 30_000, "annual_expenses": 50_000, "stock_pct": 80,
    "inflation": 3.0, "n_sims": 200, "seed": 7}).json()
check("monte carlo is reproducible through the API when seeded",
      mc["ending"] == calc.run_monte_carlo(
          24, 45, 95, 25_000, 30_000, 50_000, 80, 3.0, 200, 7)["ending"])
check("the payload carries sample paths, not the whole matrix",
      len(mc["sample_paths"]) == calc.MC_MAX_SAMPLE_PATHS and mc["n_sims"] == 200)
check("percentile bands are one value per age",
      all(len(v) == len(mc["ages"]) for v in mc["percentiles"].values()))

ss = client.post("/api/social-security", json={
    "annual_salary": 95_000, "claiming_age": 67}).json()
check("social security matches the engine, and annual is 12x monthly",
      abs(ss["monthly"] - calc.calc_social_security(95_000, 67)) < 1e-9
      and abs(ss["annual"] - ss["monthly"] * 12) < 1e-9)

roth = client.post("/api/roth-vs-traditional", json={
    "contribution": 24_500, "current_rate": 0.34, "future_rate": 0.15,
    "annual_return": 7.0, "years": 30}).json()
check("roth comparison matches the engine",
      roth == calc.roth_vs_traditional(24_500, 0.34, 0.15, 7.0, 30))
check("equal rates come back as Equivalent, not a coin flip",
      client.post("/api/roth-vs-traditional", json={
          "contribution": 10_000, "current_rate": 0.22, "future_rate": 0.22,
          "annual_return": 7.0, "years": 30}).json()["better"] == "Equivalent")

salt = client.post("/api/salt-cap", json={"magi": 600_000, "filing": "Single"}).json()
check("salt cap matches the engine",
      abs(salt["effective_cap"] - calc.calc_salt_cap(600_000, "Single")) < 1e-9)

# ── 6b. Cash flow: the Sankey's numbers ──────────────────────────────
print("\n--- cash flow ---")
BUDGET = {"needs": NEEDS, "wants": {"Dining Out": 280, "Shopping": 120},
          "savings": {"Emergency Fund": 400, "Brokerage": 550}}
cf = client.post("/api/cash-flow", json={
    "income": INCOME, "itemized": {}, "budget": BUDGET}).json()

check("cash flow matches the engine", cf == calc.cash_flow(INCOME, {}, BUDGET))

# THE PROPERTY THE DIAGRAM EXISTS FOR. A Sankey whose stages do not sum is a
# picture of a flow rather than a flow, and no reader can tell the difference
# by looking — so the balance is asserted here rather than assumed, and the
# client refuses to draw one whose `balanced` is false.
_stage_one = sum(n["value"] for n in cf["nodes"] if n["column"] == 1)
check("stage one sums to gross, to the cent",
      abs(_stage_one - cf["gross"]) < 0.01 and cf["balanced"],
      f"{_stage_one} vs {cf['gross']}")
check("every link's value equals its target node's value",
      all(abs(l["value"]
              - next(n["value"] for n in cf["nodes"] if n["id"] == l["target"])) < 1e-9
          for l in cf["links"]))
check("every node but the root has exactly one parent",
      sorted(l["target"] for l in cf["links"])
      == sorted(n["id"] for n in cf["nodes"] if n["id"] != "gross"))
_out = {}
for _l in cf["links"]:
    _out[_l["source"]] = _out.get(_l["source"], 0) + _l["value"]
check("no node sends out more than it took in",
      all(v <= next(n["value"] for n in cf["nodes"] if n["id"] == src) + 0.01
          for src, v in _out.items()),
      "a parent's children exceed it, which cannot be drawn as a flow")
check("the figures are MONTHLY, not annual",
      abs(cf["gross"] * 12
          - calc.compute_take_home(INCOME, {})["annual_gross"]) < 1e-6)

# A zero figure gets NO node and is named instead: a zero-height ribbon with a
# label beside it reads as a rendering fault rather than as "there is none".
_TX = dict(INCOME, state="Texas")
cf_tx = client.post("/api/cash-flow", json={
    "income": _TX, "itemized": {}, "budget": BUDGET}).json()
check("a state with no income tax gets no State tax node, and says so",
      not any(n["id"] == "state" for n in cf_tx["nodes"])
      and "State tax" in cf_tx["omitted"],
      "a zero node was drawn, or an absent one went unexplained")

# Over-allocation is not drawable as a flow — the outflow exceeds the inflow —
# so it comes back as a number the page states in words.
cf_over = client.post("/api/cash-flow", json={
    "income": INCOME, "itemized": {},
    "budget": {"needs": {"Rent": 99_000}, "wants": {}, "savings": {}}}).json()
check("over-allocating reports a deficit and no unallocated node",
      cf_over["deficit"] > 0 and cf_over["unallocated"] == 0
      and not any(n["id"] == "unallocated" for n in cf_over["nodes"]))

# THE TONE NAMES CROSS AN HTTP BOUNDARY, WHERE TYPESCRIPT CANNOT SEE THEM.
# The engine emits "s1", "critical" and so on as plain strings and the client
# turns each into var(--x). A name the client does not know resolves to nothing
# and paints NOTHING — absent rather than wrong, so there is no literal for
# check-tokens.mjs to find. This reads the map out of the shipping tokens.ts.
import re as _re                                                # noqa: E402

_tokens_src = open(os.path.join("src", "lib", "tokens.ts"), encoding="utf-8").read()
_var_map = _re.search(r"const VAR: Record<Token, string> = \{(.*?)\n\};",
                      _tokens_src, _re.S)
_known = set(_re.findall(r"^\s*(\w+):", _var_map.group(1), _re.M)) if _var_map else set()
check("the token map in tokens.ts could be read at all",
      len(_known) > 10,
      "the pattern went stale, so the check below would prove nothing")
_emitted = {n["tone"] for n in cf["nodes"]} | {n["tone"] for n in cf_tx["nodes"]}
check("every tone the engine emits is a token the client knows",
      _emitted <= _known, f"unknown: {sorted(_emitted - _known)}")


# ── 6c. The capabilities the engine had and no page asked for ────────
print("\n--- raise, employer match, cost of living, top bracket ---")

rz = client.post("/api/raise", json={
    "income": INCOME, "itemized": {}, "increase": 10_000}).json()
check("a raise matches the engine", rz == calc.raise_impact(INCOME, 10_000, {}))
check("the raise splits tax from the pre-tax that rose with it",
      abs(rz["gross_increase"]
          - (rz["tax_increase"] + rz["pretax_increase"] + rz["take_home_increase"]))
      < 0.01,
      "the parts of the raise do not add back up to it")

# THE REASON marginal_fica_rate EXISTS. Above the Social Security wage base the
# 6.2% has already stopped, so the marginal rate on a raise collapses — and the
# AVERAGE rate, which is what a naive implementation reaches for, overstates the
# tax on that raise several times over.
_low = client.post("/api/raise", json={
    "income": dict(INCOME, gross_salary=60_000, bonus_type="None"),
    "itemized": {}, "increase": 10_000}).json()
_high = client.post("/api/raise", json={
    "income": dict(INCOME, gross_salary=300_000, bonus_type="None"),
    "itemized": {}, "increase": 10_000}).json()
check("marginal FICA collapses above the wage base",
      _low["marginal_fica_pct"] > 7.0 and _high["marginal_fica_pct"] < 3.0,
      f"{_low['marginal_fica_pct']:.2f}% at 60k vs {_high['marginal_fica_pct']:.2f}% at 300k")
check("a raise of nothing moves nothing",
      client.post("/api/raise", json={
          "income": INCOME, "itemized": {}, "increase": 0,
      }).json()["take_home_increase"] == 0)

inv_match = client.post("/api/investment", json={
    "start": 5_000, "monthly": 500, "rate": 7.0, "years": 30,
    "salary": 100_000, "contribution_pct": 3, "match_pct": 50,
    "match_limit": 6}).json()
check("employer match matches the engine",
      inv_match["employer_match"] == calc.employer_match(100_000, 3, 50, 6))
check("the match is actually INVESTED, not just reported",
      inv_match["final_value"]
      > client.post("/api/investment", json={
          "start": 5_000, "monthly": 500, "rate": 7.0, "years": 30}).json()["final_value"],
      "the projection ignored the match, which is the bug this closes")
check("contributing under the limit is flagged as money left behind",
      inv_match["employer_match"]["leaving_money"]
      and inv_match["employer_match"]["annual_missed"] > 0)
check("contributing up to the limit forfeits nothing",
      not client.post("/api/investment", json={
          "start": 0, "monthly": 0, "rate": 7.0, "years": 1, "salary": 100_000,
          "contribution_pct": 6, "match_pct": 50, "match_limit": 6,
      }).json()["employer_match"]["leaving_money"])
check("with no salary the projection is unchanged",
      client.post("/api/investment", json={
          "start": 5_000, "monthly": 500, "rate": 7.0, "years": 30,
      }).json()["values"] == calc.project_investment(5_000, 500, 7.0, 30, 0)[0])

col = client.post("/api/cost-of-living", json={
    "salary": 100_000, "from_city": "National Average",
    "to_city": "New York, NY"}).json()["comparison"]
check("cost of living matches the engine",
      col == calc.col_compare(100_000, "National Average", "New York, NY"))
check("a dearer city needs a bigger salary for the same life",
      col["equivalent_salary"] > 100_000 and col["pct_difference"] > 0)
# An unknown city returns null rather than quietly falling back to the national
# average, which would be a wrong answer wearing a right one's clothes.
check("an unknown city returns null, not a default",
      client.post("/api/cost-of-living", json={
          "salary": 100_000, "from_city": "Atlantis", "to_city": "New York, NY",
      }).json()["comparison"] is None)

_top = client.post("/api/dashboard", json={
    "income": dict(INCOME, gross_salary=900_000, bonus_type="None"),
    "itemized": {}, "debts": [], "budget_needs": NEEDS, "assets": ASSETS,
}).json()["top_bracket"]
check("the top-bracket limitation is disclosed where it applies",
      _top["applies"] and _top["threshold"] == calc.TOP_BRACKET_START["Single"])
check("and is not claimed where it does not",
      not client.post("/api/dashboard", json={
          "income": INCOME, "itemized": {}, "debts": DEBTS,
          "budget_needs": NEEDS, "assets": ASSETS,
      }).json()["top_bracket"]["applies"])


# ── 6d. Scenario comparison ──────────────────────────────────────────
print("\n--- scenarios ---")
_NYC = {"name": "NYC now", "income": dict(INCOME, gross_salary=95_000,
                                          state="New York", bonus_type="None"),
        "itemized": {}, "city": "New York, NY"}
_ATX = {"name": "Austin offer", "income": dict(INCOME, gross_salary=110_000,
                                               state="Texas", bonus_type="None"),
        "itemized": {}, "city": "Austin, TX"}
cmp_ = client.post("/api/compare", json={"scenarios": [_NYC, _ATX]}).json()

check("comparison matches the engine",
      cmp_ == calc.compare_scenarios([_NYC, _ATX]))
check("the first scenario is the baseline and rows keep their order",
      cmp_["baseline"] == "NYC now"
      and [r["name"] for r in cmp_["rows"]] == ["NYC now", "Austin offer"])
check("each row is the engine's own take-home, recalculated per scenario",
      all(abs(r["annual_take_home"]
              - calc.compute_take_home(s["income"], {})["annual_take_home"]) < 1e-9
          for r, s in zip(cmp_["rows"], [_NYC, _ATX])),
      "a column was scaled from the baseline instead of computed")

# THE POINT OF THE SCREEN. Take-home alone ranks the dearest city first, which
# is the wrong answer to the question people are actually asking; deflating by
# the cost-of-living index is what makes two cities comparable at all.
_nyc, _atx = cmp_["rows"]
check("no-income-tax Texas beats New York on take-home",
      _atx["annual_take_home"] > _nyc["annual_take_home"])
check("and beats it by MORE once cost of living is taken out",
      _atx["real_take_home"] - _nyc["real_take_home"]
      > _atx["annual_take_home"] - _nyc["annual_take_home"],
      "the adjustment did not change the size of the gap")
check("real take-home is the take-home deflated by the local index",
      abs(_nyc["real_take_home"]
          - _nyc["annual_take_home"] * 100.0 / calc.COL_INDEX["New York, NY"]) < 1e-9)
check("the baseline compares against itself as zero",
      _nyc["vs_baseline"] == 0 and _nyc["vs_baseline_real"] == 0)

# A set where one row cannot be adjusted has no like-for-like ranking, and
# naming a winner anyway would be comparing two different measures.
_odd = client.post("/api/compare", json={
    "scenarios": [_NYC, dict(_ATX, city="Atlantis")]}).json()
check("an unindexed city yields no ranking rather than a wrong one",
      _odd["best"] is None and _odd["all_comparable"] is False
      and _odd["rows"][1]["real_take_home"] is None)
check("its tax figures are still exact",
      _odd["rows"][1]["annual_take_home"] == cmp_["rows"][1]["annual_take_home"])

check("one scenario alone is not a comparison",
      client.post("/api/compare", json={"scenarios": [_NYC]}).json()["best"] is None)

# The page's verdict sentence is driven by this, and it has to be, because the
# first version asserted "take-home alone would rank these differently" on a
# pair where the same city won both ways. Here Austin wins on BOTH measures...
check("where the same scenario wins both ways, the answer is not 'changed'",
      cmp_["best"] == "Austin offer" and cmp_["best_take_home"] == "Austin offer"
      and cmp_["col_changes_answer"] is False)
# ...and here it does not: a bigger salary in a much dearer city pays more
# take-home and is worth less once the cost of living is taken out.
_flip = client.post("/api/compare", json={"scenarios": [
    {"name": "Cheap", "income": dict(INCOME, gross_salary=100_000, state="Texas",
                                     bonus_type="None"),
     "itemized": {}, "city": "Austin, TX"},
    {"name": "Dear", "income": dict(INCOME, gross_salary=125_000, state="New York",
                                    bonus_type="None"),
     "itemized": {}, "city": "New York, NY"},
]}).json()
check("where cost of living flips the winner, the answer says so",
      _flip["best_take_home"] == "Dear" and _flip["best"] == "Cheap"
      and _flip["col_changes_answer"] is True,
      f"best={_flip['best']} raw={_flip['best_take_home']}")
check("no scenarios is empty, not an error",
      client.post("/api/compare", json={"scenarios": []}).json()["rows"] == [])


# ── 7. Nothing here touches user data ────────────────────────────────
print("\n--- the API stays a pure calculator ---")
# Read the CODE, not the prose about the code. The first version of this check
# matched the module docstring's own sentence saying user_data must not appear,
# and failed on a file that was already correct -- a test that cannot pass is as
# useless as one that cannot fail.
import ast as _ast

_tree = _ast.parse(_api_src)
for _n in _ast.walk(_tree):                 # drop docstrings
    if isinstance(_n, (_ast.Module, _ast.ClassDef, _ast.FunctionDef,
                       _ast.AsyncFunctionDef)) and _ast.get_docstring(_n):
        _n.body = _n.body[1:]
_code = _ast.dump(_tree)                    # comments never reach the AST
check("no route reads or writes user_data",
      "user_data" not in _code and "supabase" not in _code.lower(),
      "the API has started touching stored user data — it needs auth first")
check("no route accepts a token or a password",
      not any(w in _code for w in ("access_token", "password", "Authorization")))
check("the purity check reads code, not the comments about it",
      "user_data" in _api_src and "user_data" not in _code,
      "stripping did not work, so the check proves nothing")

print("\n" + "=" * 66)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 66)
sys.exit(1 if failed else 0)
