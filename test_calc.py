"""Tests for the calculation engine.

Imports calculations.py directly — that module is stdlib-only, so the engine
needs no stubs. budget_app.py is still exec'd with streamlit stubbed, but only
for _generate_demo_data, which is app data rather than maths.

The assertions here are PROPERTIES, not a second implementation. Re-deriving the
expected answer with a reference copy of the algorithm would be the mirror
problem again — a bug reasoned into both copies passes. So instead: money in
equals money out, no month leaves payment capacity idle, and each strategy
clears debts in the order its name promises.

Run:  .venv/Scripts/python.exe test_calc.py
"""
import sys
import types

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# ── Load the shipping source ─────────────────────────────────────────

class _Any(types.ModuleType):
    def __init__(self, name):
        super().__init__(name)

    def __getattr__(self, _):
        return lambda *a, **k: None


class _SessionState(dict):
    """Streamlit's session_state takes both st.session_state["k"] and .k — the
    app uses both, so a plain dict fails at import on `st.session_state.data`."""

    def __getattr__(self, k):
        try:
            return self[k]
        except KeyError:
            raise AttributeError(k)

    def __setattr__(self, k, v):
        self[k] = v


class _StreamlitStub(_Any):
    def __init__(self):
        super().__init__("streamlit")
        self.__dict__["session_state"] = _SessionState()
        self.__dict__["secrets"] = {}
        self.__dict__["sidebar"] = _Any("sidebar")

    def cache_resource(self, fn=None, **kw):
        return fn if fn else (lambda f: f)

    cache_data = cache_resource


sys.modules["streamlit"] = _StreamlitStub()
sys.modules["supabase"] = types.SimpleNamespace(create_client=lambda *a, **k: None)
for m in ("plotly", "plotly.graph_objects", "plotly.express", "pandas", "numpy"):
    sys.modules.setdefault(m, _Any(m))

# The engine comes straight from calculations.py — that module is stdlib-only,
# so it needs no stubs at all. budget_app.py is still exec'd below, but only for
# _generate_demo_data, which is app data rather than maths.
import calculations as calc
import app_data

SRC = open("budget_app.py", encoding="utf-8").read()
_APP_SRC = SRC
CUT = SRC.index("# SIDEBAR NAVIGATION")   # everything below needs a live runtime
app = types.ModuleType("app_calc")
exec(compile(SRC[:CUT], "budget_app.py", "exec"), app.__dict__)

simulate_payoff = calc.simulate_payoff

print("=" * 66)
print("CALCULATION SUITE — driving the shipping engine in calculations.py")
print("=" * 66)


def payments_from(schedule, debts, extra):
    """Recover each month's cash outflow from the schedule the app returns.

    balance[m] = balance[m-1] + interest[m] - payment[m], so
    payment[m] = balance[m-1] - balance[m] + interest[m].
    """
    out = []
    prev = sum(float(d["balance"]) for d in debts)
    for row in schedule:
        out.append(prev - row["total_balance"] + row["interest"])
        prev = row["total_balance"]
    return out


# Minimums are small relative to balances, so no debt self-liquidates out of
# order and the ordering properties below are about the STRATEGY, not about a
# large minimum payment happening to clear a small debt first.
MIXED = [
    {"name": "Card",    "balance": 6_000,  "rate": 22.0, "min_payment": 120},
    {"name": "Car",     "balance": 18_000, "rate": 6.5,  "min_payment": 300},
    {"name": "Student", "balance": 32_000, "rate": 5.5,  "min_payment": 320},
]
# Rate order and balance order deliberately OPPOSED, so the two strategies
# cannot agree by accident.
OPPOSED = [
    {"name": "Small low-rate", "balance": 2_000,  "rate": 4.0,  "min_payment": 40},
    {"name": "Big high-rate",  "balance": 25_000, "rate": 21.0, "min_payment": 400},
]

# ── 1. The whole bug: a paid-off debt's minimum must keep working ────
print("\n--- every month spends the full payment capacity ---")
for label, debts, extra in [("mixed", MIXED, 300), ("opposed", OPPOSED, 400)]:
    for strategy in ("avalanche", "snowball"):
        months, interest, schedule, _ = simulate_payoff(debts, extra, strategy)
        capacity = extra + sum(float(d["min_payment"]) for d in debts)
        pays = payments_from(schedule, debts, extra)
        # Every month but the last should spend the whole budget. The last is
        # a stub payment that just clears the remainder.
        slack = [(i + 1, round(capacity - p, 2)) for i, p in enumerate(pays[:-1])
                 if capacity - p > 0.01]
        check(f"{label}/{strategy}: no month leaves payment capacity idle",
              not slack,
              f"{len(slack)} of {len(pays)-1} months underspend, first {slack[:2]}")

print("\n--- money in equals money out ---")
for strategy in ("avalanche", "snowball"):
    months, interest, schedule, _ = simulate_payoff(MIXED, 300, strategy)
    paid = sum(payments_from(schedule, MIXED, 300))
    owed = sum(float(d["balance"]) for d in MIXED) + interest
    check(f"{strategy}: total paid == principal + interest",
          abs(paid - owed) < 0.02, f"paid {paid:,.2f} vs owed {owed:,.2f}")

# ── 2. Each strategy must do what its name says ──────────────────────
print("\n--- the strategies order their targets correctly ---")
_, _, _, order_av = simulate_payoff(MIXED, 300, "avalanche")
by_rate = [d["name"] for d in sorted(MIXED, key=lambda d: -d["rate"])]
check("avalanche clears debts in descending rate order",
      sorted(order_av, key=lambda n: order_av[n]) == by_rate, str(order_av))

_, _, _, order_sn = simulate_payoff(MIXED, 300, "snowball")
by_balance = [d["name"] for d in sorted(MIXED, key=lambda d: d["balance"])]
check("snowball clears debts in ascending ORIGINAL-balance order",
      sorted(order_sn, key=lambda n: order_sn[n]) == by_balance, str(order_sn))

# The targeting rule is tested directly rather than through completion order,
# because completion order cannot detect it: a debt with a large enough minimum
# clears first under EITHER strategy, purely on its own payments. Below, "Fast"
# retires in 6 months whichever debt is being attacked, so payoff_months says
# nothing about which one the extra went to. Making the rule a named function is
# what makes it observable.
SWITCHER = [
    {"name": "Target", "balance": 5_000, "rate": 0.0, "min_payment": 50},
    {"name": "Fast",   "balance": 5_400, "rate": 0.0, "min_payment": 900},
]
check("snowball targets the smaller ORIGINAL balance first",
      calc.payoff_order(SWITCHER, "snowball") == ["Target", "Fast"],
      str(calc.payoff_order(SWITCHER, "snowball")))
check("avalanche targets the higher rate first regardless of size",
      calc.payoff_order(MIXED, "avalanche")[0] == "Card")
check("the order is a fixed list, not re-derived from live balances",
      calc.payoff_order(MIXED, "snowball") == ["Card", "Car", "Student"])

# Testing payoff_order in isolation is not enough: it says the rule is right, not
# that the engine obeys it. Re-sorting inside the loop leaves payoff_order intact
# and passes every assertion above — a rule nothing reads is a rule nothing
# enforces. So drive the engine with the order reversed and require the answer to
# move; if simulate_payoff computed its own order, it would not.
_real_order = calc.payoff_order
calc.payoff_order = lambda debts, strategy: list(reversed(_real_order(debts, strategy)))
_, i_reversed, _, _ = simulate_payoff(MIXED, 300, "avalanche")
calc.payoff_order = _real_order
_, i_normal, _, _ = simulate_payoff(MIXED, 300, "avalanche")
check("simulate_payoff actually consults payoff_order",
      abs(i_reversed - i_normal) > 1.0,
      f"reversing the order changed interest by only ${abs(i_reversed - i_normal):.2f}")
check("and the real order is the cheaper one", i_normal < i_reversed,
      f"normal {i_normal:,.2f} vs reversed {i_reversed:,.2f}")

print("\n--- avalanche is the cheaper strategy, by definition ---")
for label, debts in [("mixed", MIXED), ("opposed", OPPOSED)]:
    _, ia, _, _ = simulate_payoff(debts, 300, "avalanche")
    _, isn, _, _ = simulate_payoff(debts, 300, "snowball")
    check(f"{label}: avalanche interest <= snowball interest",
          ia <= isn + 0.01, f"avalanche {ia:,.2f} vs snowball {isn:,.2f}")

_, ia, _, _ = simulate_payoff(OPPOSED, 400, "avalanche")
_, isn, _, _ = simulate_payoff(OPPOSED, 400, "snowball")
check("on opposed debts the two strategies genuinely differ", abs(ia - isn) > 1.0,
      f"avalanche {ia:,.2f} vs snowball {isn:,.2f}")

# ── 3. Guards and edges, unchanged behaviour ─────────────────────────
print("\n--- guards ---")
m, i, s, p = simulate_payoff(
    [{"name": "A", "balance": 1_000, "rate": 0.0, "min_payment": 0}], 0, "avalanche")
check("no payment at all returns the -1 sentinel", m == -1)

m, i, s, p = simulate_payoff(
    [{"name": "A", "balance": 10_000, "rate": 30.0, "min_payment": 10}], 0, "avalanche")
check("payments below the interest accrual return -1", m == -1, f"got {m}")

m, i, s, p = simulate_payoff(
    [{"name": "Only", "balance": 1_200, "rate": 0.0, "min_payment": 100}], 0, "avalanche")
check("one debt, no interest, exact minimum: 12 months", m == 12, f"got {m}")
check("no interest accrues at 0%", abs(i) < 0.01)
check("payoff_months records the single debt", p == {"Only": 12}, str(p))

m, i, s, p = simulate_payoff(MIXED, 0, "avalanche")
check("zero extra still pays everything off", m > 0 and all(n in p for n in
      ("Card", "Car", "Student")), f"months {m}, payoff {p}")

m, i, s, p = simulate_payoff(MIXED, 100_000, "avalanche")
check("an extra payment larger than the debt clears it in one month", m == 1, f"got {m}")

check("simulate_payoff still returns four values",
      len(simulate_payoff(MIXED, 300, "avalanche")) == 4)

# ── 4. Demo data should demonstrate the feature ──────────────────────
print("\n--- the demo has to show the comparison it is there to show ---")
demo = app._generate_demo_data()
debts = demo["debts"]
check("demo ships more than one debt", len(debts) > 1, f"{len(debts)} debt(s)")
if len(debts) > 1:
    rate_order = [d["name"] for d in sorted(debts, key=lambda d: -d["rate"])]
    bal_order = [d["name"] for d in sorted(debts, key=lambda d: d["balance"])]
    check("demo debts put rate order and balance order in conflict",
          rate_order != bal_order,
          "the two strategies would target debts identically")
    _, dia, _, _ = simulate_payoff(debts, 200, "avalanche")
    _, dis, _, _ = simulate_payoff(debts, 200, "snowball")
    check("the demo's two strategies produce visibly different interest",
          abs(dia - dis) > 1.0, f"avalanche {dia:,.2f} vs snowball {dis:,.2f}")
    check("every demo debt has a positive minimum payment",
          all(d["min_payment"] > 0 for d in debts))
    check("demo minimums are affordable against demo take-home",
          sum(d["min_payment"] for d in debts) < demo["income"]["gross_salary"] / 12 * 0.4,
          "the demo would look like someone in distress")

# -- 5. compute_take_home: the function nothing could reach ------------
#
# Until September 2026 this lived in budget_app.py and read a module-global
# `data` dict, so it could not be imported without Streamlit and was covered by
# zero of the 239 assertions -- despite every page's take-home, savings rate,
# cash flow and FIRE timeline running through it.
print("\n--- take-home: the pay stub has to balance ---")

BASE = {"gross_salary": 95_000, "state": "New York", "filing_status": "Single",
        "contribution_401k": 6, "health_insurance": 180, "hsa": 100,
        "bonus_amount": 10_000, "bonus_type": "Annual (spread monthly)",
        "student_loan_interest": 0}


def income(**over):
    d = dict(BASE)
    d.update(over)
    return d


PROFILES = [income(), income(gross_salary=0), income(gross_salary=610_000),
            income(state="Texas"), income(state="Arkansas", gross_salary=85_000),
            income(filing_status="Married Filing Jointly"),
            income(contribution_401k=40), income(bonus_type="None")]

worst = 0.0
for prof in PROFILES:
    th = calc.compute_take_home(prof)
    worst = max(worst, abs(th["annual_gross"] - th["pretax"] - th["total_tax"]
                           - th["annual_take_home"]))
check("gross - pretax - tax == take-home on %d profiles (worst residual %.2e)"
      % (len(PROFILES), worst), worst < 1e-9, str(worst))
check("monthly is annual / 12",
      all(abs(calc.compute_take_home(p)["monthly_take_home"] * 12
              - calc.compute_take_home(p)["annual_take_home"]) < 1e-9 for p in PROFILES))
check("total_tax is the three taxes",
      all(abs(sum(calc.compute_take_home(p)[k] for k in ("fed_tax", "state_tax", "fica"))
              - calc.compute_take_home(p)["total_tax"]) < 1e-9 for p in PROFILES))
check("bonus_type 'None' keeps the bonus out of gross",
      calc.compute_take_home(income(bonus_type="None"))["annual_gross"] == 95_000)
check("a zero income does not divide by zero",
      calc.compute_take_home(income(gross_salary=0, bonus_type="None"))["effective_rate"] == 0)

# The bug this function's extraction was meant to make testable.
ny = calc.compute_take_home(income(gross_salary=110_000, state="New York"))
brackets, _ = calc._get_state_brackets_for_filing(calc.STATE_TAX_DATA["New York"], "Single")
check("marginal_state is the user's rate (%.1f%%), not the state's top bracket (%.1f%%)"
      % (ny["marginal_state"], brackets[-1][1] * 100),
      abs(ny["marginal_state"] - 6.0) < 1e-9 and ny["marginal_state"] < brackets[-1][1] * 100,
      str(ny["marginal_state"]))

# Assert the ENGINE READS the rule, not just that the rule is right. A version
# that inlined the top bracket would pass every assertion above about
# calc_state_marginal_rate itself.
_real_marg = calc.calc_state_marginal_rate
calc.calc_state_marginal_rate = lambda *a, **k: 99.0
try:
    hijacked = calc.compute_take_home(income(gross_salary=110_000))["marginal_state"]
finally:
    calc.calc_state_marginal_rate = _real_marg
check("compute_take_home reads calc_state_marginal_rate (monkeypatched answer moves)",
      hijacked == 99.0, "got %r" % (hijacked,))

_real_limit = calc.K401_LIMIT
calc.K401_LIMIT = 1_000
try:
    capped = calc.compute_take_home(income(gross_salary=610_000, contribution_401k=20))
finally:
    calc.K401_LIMIT = _real_limit
check("compute_take_home reads K401_LIMIT (monkeypatched cap moves the answer)",
      capped["contrib_401k"] == 1_000, "got %r" % (capped["contrib_401k"],))

print("\n--- take-home: itemizing ---")
plain = calc.compute_take_home(income())
check("with no itemized input the standard deduction is taken",
      plain["deduction_taken"] == plain["std_ded"] and not plain["itemizing"])
big = calc.compute_take_home(income(), {"mortgage_interest": 30_000, "salt": 25_000,
                                        "charitable": 5_000})
check("a large itemized total is taken instead, and says so",
      big["deduction_taken"] == big["itemized_total"] and big["itemizing"]
      and big["itemized_total"] > big["std_ded"],
      "taken %.0f vs std %.0f" % (big["deduction_taken"], big["std_ded"]))
check("itemizing lowers the tax bill", big["fed_tax"] < plain["fed_tax"])

# The wrapper still in budget_app.py must DELEGATE, not hold a second copy.
app.data = {"income": income(gross_salary=123_456), "itemized": {}}
_real_engine = app.calc_take_home
app.calc_take_home = lambda inc, item: {"sentinel": inc["gross_salary"], "itemized_seen": item}
try:
    relayed = app.compute_take_home()
    app.data["itemized"] = {"charitable": 777}
    relayed2 = app.compute_take_home()
finally:
    app.calc_take_home = _real_engine
check("budget_app's compute_take_home delegates to the engine, holding no copy",
      relayed["sentinel"] == 123_456, "got %r" % (relayed,))
check("the wrapper passes the session's itemized dict through",
      relayed2["itemized_seen"] == {"charitable": 777}, "got %r" % (relayed2,))


# -- 6. Monte Carlo ---------------------------------------------------
print("\n--- percentile: the numbers on a shipping page must not move ---")
check("percentile of a single value is that value", calc.percentile([42.0], 50) == 42.0)
check("percentile of an empty series is 0.0, not an error", calc.percentile([], 50) == 0.0)
check("p50 of 1..5 is 3 (linear interpolation)", calc.percentile([1, 2, 3, 4, 5], 50) == 3.0)
check("p25 of 1..5 is 2", calc.percentile([1, 2, 3, 4, 5], 25) == 2.0)
check("p10 of 1..5 interpolates to 1.4", abs(calc.percentile([1, 2, 3, 4, 5], 10) - 1.4) < 1e-12)
_SERIES = [3, 1, 4, 1, 5, 9, 2, 6]
check("percentile is monotone in q",
      all(calc.percentile(_SERIES, q) <= calc.percentile(_SERIES, q + 5)
          for q in range(0, 100, 5)))
# numpy as an oracle, which needs care in THIS file: it installs a stub numpy
# in sys.modules so budget_app.py can be exec'd without one. A stub returns None
# from every call, so an oracle read through it compares against nothing and the
# check becomes decoration. The real module is loaded past the stub, and the
# block refuses to run unless it is demonstrably the real one.
_np = None
try:
    import importlib
    import random as _rnd
    _stub = sys.modules.pop("numpy", None)
    try:
        _np = importlib.import_module("numpy")
        if _np.percentile([1.0, 2.0, 3.0], 50) != 2.0:
            _np = None                      # a stub, or something else entirely
    finally:
        if _stub is not None and "numpy" not in sys.modules:
            sys.modules["numpy"] = _stub
except Exception:
    _np = None

if _np is None:
    print("  [skip] no real numpy available to check percentile against")
else:
    _r = _rnd.Random(11)
    _worst = 0.0
    for _ in range(200):
        _v = [_r.uniform(-1e6, 1e7) for _ in range(_r.randint(1, 60))]
        for _q in (0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100):
            _worst = max(_worst, abs(calc.percentile(_v, _q)
                                     - float(_np.percentile(_np.array(_v), _q))))
    check("matches numpy.percentile, the function it replaced "
          "(2,200 comparisons, worst %.1e)" % _worst, _worst < 1e-6, str(_worst))

print("\n--- simulate_path: the recurrence, with the randomness taken out ---")
YEARS = 10
flat = [0.0] * YEARS
bal, fail = calc.simulate_path(30, 40, 40, 1_000.0, 100.0, 0.0, 0.0, flat, flat)
check("no return, no inflation, accumulation only: start + savings * years",
      abs(bal[-1] - (1_000 + 100 * YEARS)) < 1e-9 and fail is None, str(bal[-1]))
check("one balance per year, inclusive of both ends", len(bal) == YEARS + 1)
bal, fail = calc.simulate_path(30, 30, 40, 1_000.0, 0.0, 100.0, 0.0, flat, flat)
check("retired throughout: start - expenses * years",
      abs(bal[-1] - (1_000 - 100 * YEARS)) < 1e-9, str(bal[-1]))
bal, fail = calc.simulate_path(30, 30, 40, 500.0, 0.0, 100.0, 0.0, flat, flat)
check("a path that runs out reports the age it happened", fail == 35, str(fail))
check("and stays at zero afterwards", all(b == 0.0 for b in bal[6:]), str(bal))
bal, _ = calc.simulate_path(30, 40, 41, 1_000.0, 0.0, 0.0, 0.0, [0.10] * 11, [0.0] * 11)
check("a 10% return compounds", abs(bal[-1] - 1_000 * 1.10 ** 11) < 1e-6, str(bal[-1]))

# Retirement spending compounds over the years spent RETIRED, not over calendar
# years since the start. The two are the same number whenever retire_age equals
# current_age, which is what every case above did -- so a mutation swapping one
# for the other survived them all. Retire at 35 of a run from 30 to 40 and they
# differ: five withdrawals growing 1.10**1..1.10**5, not 1.10**6..1.10**10.
_expected = 100_000.0 - sum(1_000 * 1.10 ** k for k in range(1, 6))
bal, _ = calc.simulate_path(30, 35, 40, 100_000.0, 0.0, 1_000.0, 0.0,
                            [0.0] * 10, [0.10] * 10)
check("retirement spending compounds over years retired, not calendar years",
      abs(bal[-1] - _expected) < 1e-6,
      "got %.2f, expected %.2f" % (bal[-1], _expected))
check("nothing is withdrawn before the retirement age",
      all(b == 100_000.0 for b in bal[:6]), str(bal[:6]))

print("\n--- run_monte_carlo ---")
mc = calc.run_monte_carlo(24, 45, 95, 25_000, 30_000, 50_000, 80, 3.0, 300, seed=3)
mc2 = calc.run_monte_carlo(24, 45, 95, 25_000, 30_000, 50_000, 80, 3.0, 300, seed=3)
check("a seeded run is reproducible", mc["ending"] == mc2["ending"])
check("success_rate is success_count over n_sims",
      abs(mc["success_rate"] - mc["success_count"] / mc["n_sims"] * 100) < 1e-9)
check("one age per column of the bands",
      all(len(mc["percentiles"][k]) == len(mc["ages"]) for k in mc["percentiles"]))
ordered = all(mc["percentiles"][a][i] <= mc["percentiles"][b][i] + 1e-9
              for a, b in zip(("p5", "p10", "p25", "p50", "p75", "p90"),
                              ("p10", "p25", "p50", "p75", "p90", "p95"))
              for i in range(len(mc["ages"])))
check("the percentile bands never cross", ordered)
check("sample paths are capped at %d and are full length" % calc.MC_MAX_SAMPLE_PATHS,
      len(mc["sample_paths"]) == calc.MC_MAX_SAMPLE_PATHS
      and all(len(p) == len(mc["ages"]) for p in mc["sample_paths"]))
check("one ending balance per simulation", len(mc["ending"]) == 300)
check("median_ending is the median of ending",
      abs(mc["median_ending"] - calc.percentile(mc["ending"], 50)) < 1e-9)
rich = calc.run_monte_carlo(60, 61, 70, 50_000_000, 0, 10_000, 0, 3.0, 60, seed=5)
check("a plan that cannot fail succeeds 100% of the time",
      rich["success_rate"] == 100.0, str(rich["success_rate"]))
broke = calc.run_monte_carlo(60, 60, 90, 1_000, 0, 500_000, 0, 3.0, 60, seed=5)
check("a plan that cannot survive succeeds 0% of the time",
      broke["success_rate"] == 0.0, str(broke["success_rate"]))

# Again: assert the engine READS the recurrence rather than inlining it.
_real_path = calc.simulate_path
calc.simulate_path = lambda *a, **k: ([1.0] * (a[2] - a[0] + 1), None)
try:
    hijacked_mc = calc.run_monte_carlo(24, 45, 95, 25_000, 30_000, 50_000, 80, 3.0, 20, seed=3)
finally:
    calc.simulate_path = _real_path
check("run_monte_carlo reads simulate_path (monkeypatched paths reach the output)",
      set(hijacked_mc["ending"]) == {1.0}, str(set(hijacked_mc["ending"])))


# -- 7. Roth vs Traditional --------------------------------------------
#
# Inline in the tax page until September 2026, and reimplemented a fourth time
# in budget-app-v2's endpoint body -- where it used the FEDERAL marginal rate
# alone, dropping the state half of the tax a pre-tax dollar actually saves.
print("\n--- roth vs traditional ---")

_rt = calc.roth_vs_traditional(24_500, 0.34, 0.15, 7.0, 30)
check("traditional invests the full contribution",
      abs(_rt["traditional_future"] - 24_500 * ((1.07 ** 30 - 1) / 0.07) * 1.07) < 1e-6,
      str(_rt["traditional_future"]))
check("roth invests the contribution net of tax paid now",
      abs(_rt["roth_invested"] - 24_500 * (1 - 0.34)) < 1e-9, str(_rt["roth_invested"]))
check("difference is the gap between the two after-tax balances",
      abs(_rt["difference"] - abs(_rt["traditional_after_tax"] - _rt["roth_future"])) < 1e-9)

# The verdict depends ONLY on the two rates. Comparing the balances instead is
# what made the old inline version answer ties on float noise.
check("a higher rate now than later favours Traditional",
      calc.roth_vs_traditional(10_000, 0.37, 0.15, 7.0, 30)["better"] == "Traditional")
check("a lower rate now than later favours Roth",
      calc.roth_vs_traditional(10_000, 0.12, 0.30, 7.0, 30)["better"] == "Roth")
check("equal rates are Equivalent, not a coin flip",
      calc.roth_vs_traditional(10_000, 0.22, 0.22, 7.0, 30)["better"] == "Equivalent")
check("and Equivalent really means the two balances match",
      abs(calc.roth_vs_traditional(10_000, 0.22, 0.22, 7.0, 30)["difference"]) < 1e-6)
_verdicts = {calc.roth_vs_traditional(c, 0.37, 0.15, r, y)["better"]
             for c in (1, 500, 24_500) for r in (0.0, 0.5, 7.0, 20.0) for y in (1, 5, 50)}
check("the verdict does not depend on contribution, return or horizon",
      _verdicts == {"Traditional"}, str(_verdicts))
check("a zero contribution still answers on the rates, not 0 > 0",
      calc.roth_vs_traditional(0, 0.37, 0.15, 7.0, 30)["better"] == "Traditional")
check("a zero return still grows by the number of years",
      calc.roth_vs_traditional(1_000, 0.0, 0.0, 0.0, 10)["traditional_future"] == 10_000)

# The page must read the shared function, not keep its own arithmetic.
_real_rt = app.roth_vs_traditional
app.roth_vs_traditional = lambda *a, **k: {
    "contribution": -1, "traditional_future": -2, "traditional_after_tax": -3,
    "roth_invested": -4, "roth_future": -5, "better": "Roth", "difference": -6,
    "current_rate": 0, "future_rate": 0}
try:
    _sentinel_reached = app.roth_vs_traditional(1, 0, 0, 0, 1)["traditional_future"] == -2
finally:
    app.roth_vs_traditional = _real_rt
check("the tax page's Roth block resolves roth_vs_traditional from the engine",
      _sentinel_reached and "roth_vs_traditional" in _APP_SRC
      and "trad_future = _rt[" in _APP_SRC,
      "the page still holds its own copy of the arithmetic")
check("and the page no longer computes the verdict by comparing two floats",
      'better = "Traditional" if trad_after_tax > roth_future else "Roth"' not in _APP_SRC)


# ── 8. Card HTML must not emit a blank line ──────────────────────────
#
# Streamlit renders these cards through markdown, and markdown ENDS an HTML
# block at the first blank line. A conditional inside an f-string card that
# falls back to "" leaves a whitespace-only line, the block ends there, and the
# 8-space-indented </div> after it becomes an indented CODE BLOCK — a literal
# "</div>" printed on whichever card LOST. It was live on the public app on both
# deduction cards and both Roth cards, and no assertion could see it because
# every one of them was about the numbers.
print("\n--- card HTML: no conditional may collapse to a blank line ---")
import re as _re

_blank = _re.findall(r'^[ \t]*\{[^\n]*else ""\}[ \t]*$', _APP_SRC, _re.M)
check("no card conditional falls back to an empty string",
      not _blank,
      "%d site(s), e.g. %s" % (len(_blank), [b.strip()[-58:] for b in _blank[:2]]))
check("the four known sites fall back to an HTML comment instead",
      _APP_SRC.count('else "<!-- -->"}') == 4,
      "found %d" % _APP_SRC.count('else "<!-- -->"}'))


# ═══════════════════════════════════════════════════════════════════════
# 9. THE SAVINGS-RATE CURVE
# ═══════════════════════════════════════════════════════════════════════
print("\n--- years to a target: closed form against a year-by-year loop ---")

# The loop is the DEFINITION — add a year's saving, apply a year's return,
# stop when the target is passed. It is a genuinely different method from the
# logarithm the engine uses, which is what makes it an oracle rather than a
# mirror: an algebra slip cannot be present in both.


def _loop_years(P, S, T, r, cap=4000):
    r = r / 100.0
    n = 0
    while P < T and n < cap:
        P = P * (1 + r) + S
        n += 1
    return None if n >= cap else n


_cases = [
    (0, 20_000, 1_000_000, 5.0), (50_000, 30_000, 900_000, 6.0),
    (1_000_000, 0, 2_000_000, 4.0), (5_000, 12_000, 400_000, 7.0),
    (250_000, 45_000, 1_800_000, 5.8), (0, 1, 1_000_000, 3.0),
    (100_000, -3_000, 200_000, 5.0), (12_345, 6_789, 250_000, 6.25),
]
_agree = 0
for P, S, T, r in _cases:
    closed = calc.years_to_target(P, S, T, r)
    loop = _loop_years(P, S, T, r)
    # The loop can only answer in whole years, so the closed form must land in
    # the year the loop stopped in: ceil(closed) == loop.
    ok = (closed is None and loop is None) or (
        closed is not None and loop is not None and -1e-9 < loop - closed <= 1.0)
    if ok:
        _agree += 1
    else:
        check(f"years_to_target agrees with the loop for P={P} S={S} T={T} r={r}",
              False, f"closed={closed} loop={loop}")
check(f"the closed form lands in the loop's year, all {len(_cases)} cases",
      _agree == len(_cases), f"{_agree}/{len(_cases)}")

check("a target already reached is zero years, not a negative number",
      calc.years_to_target(500_000, 10_000, 400_000, 5.0) == 0.0)
check("nothing saved and nothing held never arrives, and says None",
      calc.years_to_target(0, 0, 100_000, 5.0) is None)
# A withdrawal larger than the growth shrinks the balance forever. The closed
# form's logarithm would be of a negative number here, so the guard is what
# stops a drawdown returning a confident-looking figure.
check("a portfolio being drawn down faster than it grows never arrives",
      calc.years_to_target(100_000, -20_000, 200_000, 5.0) is None)
check("a portfolio drawn down but still growing does arrive",
      calc.years_to_target(100_000, -3_000, 200_000, 5.0) is not None)
check("with no return at all it is simply the gap over the saving",
      abs(calc.years_to_target(0, 10_000, 50_000, 0.0) - 5.0) < 1e-9)
check("with no return and no saving it never arrives",
      calc.years_to_target(0, 0, 50_000, 0.0) is None)

print("\n--- the expected return is the simulation's, not a second assumption ---")
_r80 = calc.expected_real_return(80, 3.0)
check("an all-bond portfolio returns the bond mean, less inflation",
      abs(calc.expected_real_return(0, 0.0) - calc.MC_BOND_MEAN * 100) < 1e-9)
check("an all-stock portfolio returns the stock mean, less inflation",
      abs(calc.expected_real_return(100, 0.0) - calc.MC_STOCK_MEAN * 100) < 1e-9)
check("a blend sits between the two",
      calc.MC_BOND_MEAN * 100 < _r80 < calc.MC_STOCK_MEAN * 100)
check("inflation reduces it",
      calc.expected_real_return(80, 5.0) < calc.expected_real_return(80, 2.0))
# Testing the value alone would pass on a function that had copied the numbers.
# Moving the constant and requiring the answer to follow is what proves it is
# READ — the lesson from payoff_order, applied to a constant.
_saved_mean = calc.MC_STOCK_MEAN
try:
    calc.MC_STOCK_MEAN = 0.20
    _moved = calc.expected_real_return(100, 0.0)
finally:
    calc.MC_STOCK_MEAN = _saved_mean
check("it reads MC_STOCK_MEAN rather than holding its own copy of it",
      abs(_moved - 20.0) < 1e-9, f"got {_moved}")

print("\n--- the curve's shape is the point of it ---")
_curve = calc.fire_curve_points(70_000, 25_000, 5.8)
check("the curve is drawn at every rate between the two bounds",
      len(_curve) > 10 and _curve[0]["savings_rate"] == calc.FIRE_RATE_MIN
      and _curve[-1]["savings_rate"] == calc.FIRE_RATE_MAX)
_years = [p["years"] for p in _curve if p["years"] is not None]
check("saving more never takes longer",
      all(a >= b - 1e-9 for a, b in zip(_years, _years[1:])),
      "the curve is not monotonic")
check("saving more lowers the target AND raises the saving — both sides move",
      _curve[0]["fire_number"] > _curve[-1]["fire_number"]
      and _curve[0]["annual_savings"] < _curve[-1]["annual_savings"])
check("each point's savings and spending add back to take-home",
      all(abs(p["annual_savings"] + p["annual_expenses"] - 70_000) < 1e-6
          for p in _curve))
check("no take-home means no curve, rather than a curve of zeroes",
      calc.fire_curve_points(0, 25_000, 5.8) == [])

print("\n--- the projection, and the marker that must sit on its line ---")
_demo = app_data._generate_demo_data()
_proj = calc.fire_projection(_demo["income"], _demo["itemized"],
                             _demo["budget"], _demo["assets"])
_th = calc.compute_take_home(_demo["income"], _demo["itemized"])
_needs_wants = (sum(_demo["budget"]["needs"].values())
                + sum(_demo["budget"]["wants"].values())) * 12
check("expenses are budgeted needs and wants — the savings bucket is not spending",
      abs(_proj["annual_expenses"] - _needs_wants) < 1e-9)
check("the FIRE number is that spending at the withdrawal rate",
      abs(_proj["fire_number"] - _needs_wants / (calc.SWR_DEFAULT / 100)) < 1e-6)
check("savings is what take-home leaves after it",
      abs(_proj["annual_savings"]
          - (_th["annual_take_home"] - _needs_wants)) < 1e-9)
# The marker is drawn at the reported savings rate. If the page's rate and the
# curve's rate were computed differently the dot would float off the line, and
# nothing on a chart says which of the two is wrong.
_at_rate = calc.fire_curve_points(_proj["annual_take_home"], _proj["portfolio"],
                                  _proj["real_return"], _proj["swr"],
                                  rates=[_proj["savings_rate"]])
check("the reader's own point lies ON the curve, not beside it",
      abs(_at_rate[0]["years"] - _proj["years_at_current"]) < 1e-6,
      f"marker {_proj['years_at_current']} vs curve {_at_rate[0]['years']}")
check("and the target under the marker matches the headline FIRE number",
      abs(_at_rate[0]["fire_number"] - _proj["fire_number"]) < 1e-6)
check("one more point of savings rate arrives sooner, by a stated amount",
      _proj["next_point"] is not None
      and _proj["next_point"]["years_saved"] > 0
      and abs(_proj["next_point"]["years_saved"]
              - (_proj["years_at_current"] - _proj["next_point"]["years"])) < 1e-9)

# A budget that spends more than the take-home covers. The savings rate is
# clamped to zero so it can be plotted, and `overspending` is what carries the
# fact that it was clamped — 0% and -14% are different statements.
_over = dict(_demo["budget"])
_over["needs"] = dict(_demo["budget"]["needs"], Rent=9_000)
_p2 = calc.fire_projection(_demo["income"], _demo["itemized"], _over, _demo["assets"])
check("overspending clamps the savings rate at zero and SAYS it did",
      _p2["savings_rate"] == 0.0 and _p2["overspending"] is True
      and _p2["shortfall"] > 0)
check("and nothing saved never reaches the target — None, not a large number",
      _p2["years_at_current"] is None)

# The projection must READ years_to_target rather than growing its own copy.
# Testing the function alone would not notice a second implementation inside
# fire_projection that happened to agree today.
_saved_fn = calc.years_to_target
try:
    calc.years_to_target = lambda *a, **k: 123.0
    _p3 = calc.fire_projection(_demo["income"], _demo["itemized"],
                               _demo["budget"], _demo["assets"])
finally:
    calc.years_to_target = _saved_fn
check("fire_projection reads years_to_target rather than re-deriving it",
      _p3["years_at_current"] == 123.0 and _p3["curve"][0]["years"] == 123.0)

check("an income stream is stated as the capital it replaces",
      abs(calc.capital_equivalent(40_000, 4.0) - 1_000_000) < 1e-6)
check("and a withdrawal rate of zero has no capital equivalent",
      calc.capital_equivalent(40_000, 0) is None)


# ═══════════════════════════════════════════════════════════════════════
# 10. THE YEAR SO FAR
# ═══════════════════════════════════════════════════════════════════════
print("\n--- the year to date, and the hole an expense log always has ---")

_BUD = {"needs": {"Rent": 1_000, "Groceries": 400},
        "wants": {"Dining Out": 200},
        "savings": {"Investing": 300}}
_EXP = [
    {"date": "2026-01-05", "amount": 1_000, "category": "Rent"},
    {"date": "2026-01-20", "amount": 500, "category": "Groceries"},
    {"date": "2026-01-22", "amount": 60, "category": "Not In The Budget"},
    {"date": "2026-02-05", "amount": 1_000, "category": "Rent"},
    {"date": "2026-02-11", "amount": 150, "category": "Dining Out"},
    # March and April deliberately empty.
    {"date": "2026-05-05", "amount": 1_000, "category": "Rent"},
    {"date": "2026-06-02", "amount": 90, "category": "Not In The Budget"},
    {"date": "2025-12-31", "amount": 9_999, "category": "Rent"},   # last year
]
_y = calc.year_to_date(_EXP, _BUD, 4_000, "2026-06-15")

check("last year's spending is not in this year's total",
      _y["spent"] == 1_000 + 500 + 60 + 1_000 + 150 + 1_000 + 90,
      str(_y["spent"]))
check("five complete months have passed",
      _y["months_complete"] == 5)
check("three of them hold records — March and April have none",
      _y["documented_months"] == 3)
check("and the two that do not are named",
      _y["undocumented_months"] == ["2026-03", "2026-04"])
check("so the record is not complete, and says so",
      _y["complete_record"] is False)
# The whole design of this function. Comparing five months of plan against four
# months of spending reports someone under budget by a month's budget.
check("the budget compared against is the DOCUMENTED months, not the calendar",
      abs(_y["budget_documented"] - 1_900 * 3) < 1e-9
      and abs(_y["budget_to_date"] - 1_900 * 5) < 1e-9)
check("and the variance uses that basis, exactly",
      abs(_y["variance"] - (_y["budget_documented"] - _y["spent_documented"])) < 1e-9)
check("the calendar basis would have flattered it by two months of budget",
      abs((_y["budget_to_date"] - _y["spent_documented"])
          - _y["variance"] - 1_900 * 2) < 1e-9)

# The month in progress is excluded from every comparison. Rent is paid on the
# 1st, so on the 2nd a pro-rated month holds a full month of rent against two
# days of budget — measured at 30x over on a bill that was paid on time.
_y_big = calc.year_to_date(
    _EXP + [{"date": "2026-06-14", "amount": 50_000, "category": "Rent"}],
    _BUD, 4_000, "2026-06-15")
check("a huge charge in the month IN PROGRESS does not move the variance",
      _y_big["variance"] == _y["variance"])
check("but it is in the year's total, and in the current month's own figure",
      _y_big["spent"] == _y["spent"] + 50_000
      and _y_big["current_month"]["spent"] == 50_000 + 90)
check("the current month is reported separately, by name",
      _y["current_month"]["month"] == "2026-06" and _y["current_month"]["label"] == "Jun")

check("the pace is spent over the months that have records",
      abs(_y["pace"] - _y["spent_documented"] / 3) < 1e-9)
check("and the projection is that pace across twelve months",
      abs(_y["projected_year_end"] - _y["pace"] * 12) < 1e-9)
check("saving is measured over the same months as the spending",
      abs(_y["saved"] - (4_000 * 3 - _y["spent_documented"])) < 1e-9)
check("take-home for the whole elapsed year is reported but NOT the denominator",
      abs(_y["take_home_to_date"] - 4_000 * 5) < 1e-9
      and abs(_y["savings_rate"] - _y["saved"] / (4_000 * 3) * 100) < 1e-9)

_jan = calc.year_to_date(_EXP, _BUD, 4_000, "2026-01-20")
check("in the first month of the year there is nothing to compare, and it is None",
      _jan["variance"] is None and _jan["pace"] is None
      and _jan["saved"] is None and _jan["projected_year_end"] is None,
      "a zero here would read as 'exactly on budget'")
# Every 2026 expense is in the year's total on 20 January, including the ones
# dated later in the year: they were entered deliberately, so they are counted
# and the count of them is reported rather than being quietly dropped.
check("and the year's spending so far is still reported",
      _jan["spent"] == _y["spent"] and _jan["future_dated"] == 5,
      f'{_jan["spent"]} / {_jan["future_dated"]} future-dated')

check("a month with no records is marked, not shown as a month of no spending",
      [m["has_data"] for m in _y["by_month"]] == [True, True, False, False, True, True])
check("every month of the year that has begun gets a row",
      len(_y["by_month"]) == 6 and _y["by_month"][-1]["in_progress"] is True)

_buckets = {b["bucket"]: b for b in _y["by_bucket"]}
check("spending against a category the budget does not have gets its own row",
      "Unbudgeted" in _buckets and _buckets["Unbudgeted"]["spent"] == 60)
check("and a charge in the month IN PROGRESS does not create that row",
      calc.year_to_date([e for e in _EXP if e["date"] != "2026-01-22"],
                        _BUD, 4_000, "2026-06-15")["by_bucket"][-1]["bucket"] != "Unbudgeted",
      "the June unbudgeted charge is not on the documented basis")
check("the buckets' spending adds back to the documented total",
      abs(sum(b["spent"] for b in _y["by_bucket"]) - _y["spent_documented"]) < 1e-9)
check("and their variances add back to the total variance",
      abs(sum(b["variance"] for b in _y["by_bucket"]) - _y["variance"]) < 1e-9)
check("a savings bucket nobody logs against reads as fully unspent, by design",
      _buckets["Savings"]["spent"] == 0
      and abs(_buckets["Savings"]["budget_to_date"] - 300 * 3) < 1e-9)

_cats = {c["category"]: c for c in _y["by_category"]}
check("a category's allowance is its monthly amount over the documented months",
      abs(_cats["Rent"]["budget_to_date"] - 1_000 * 3) < 1e-9)
# Groceries: $500 spent against $400 x 3 months of allowance. Rent: $3,000
# against $1,000 x 3, exactly on plan, which is NOT over.
check("a category over its allowance is marked, and one exactly on it is not",
      _cats["Groceries"]["over"] is False and _cats["Rent"]["over"] is False)
check("and a category genuinely over IS marked",
      {c["category"]: c for c in calc.year_to_date(
          _EXP, dict(_BUD, needs={"Rent": 1_000, "Groceries": 100}),
          4_000, "2026-06-15")["by_category"]}["Groceries"]["over"] is True)
check("a category with no budget is not 'over' its budget — it has none",
      _cats["Not In The Budget"]["over"] is False
      and _cats["Not In The Budget"]["pct_of_budget"] is None)

check("the caller's date is what decides the year, not the machine's",
      calc.year_to_date(_EXP, _BUD, 4_000, "2025-12-31")["year"] == 2025)
check("an unreadable date is skipped rather than raising",
      calc.year_to_date([{"date": "not a date", "amount": 5, "category": "Rent"},
                         {"date": None, "amount": 5, "category": "Rent"}],
                        _BUD, 0, "2026-06-15")["spent"] == 0)
check("an expense dated in the future is counted, and counted OUT LOUD",
      calc.year_to_date(_EXP + [{"date": "2026-12-25", "amount": 40,
                                 "category": "Rent"}],
                        _BUD, 4_000, "2026-06-15")["future_dated"] == 1)


# ═══════════════════════════════════════════════════════════════════════
# 11. READING A BANK'S CSV
# ═══════════════════════════════════════════════════════════════════════
print("\n--- money strings ---")
for text, want in [("$1,234.56", 1234.56), ("1234.56", 1234.56), ("(52.30)", -52.30),
                   ("-52.30", -52.30), ("52.30-", -52.30), ("$0.00", 0.0),
                   ("1,234", 1234.0), ("1.234.567", 1234567.0), ("+18.40", 18.40)]:
    check(f"{text!r} reads as {want}", calc.parse_amount(text) == want,
          str(calc.parse_amount(text)))
check("something that is not a number is None, not zero",
      calc.parse_amount("PENDING") is None and calc.parse_amount("") is None)
# The silent one. Read as US notation this is 1.23456, so a $1,234 charge lands
# as a rounding error and no total on the page looks wrong.
check("1.234,56 is twelve hundred, not one and a bit",
      calc.parse_amount("1.234,56") == 1234.56)
check("and 1234,56 with no thousands mark is too",
      calc.parse_amount("1234,56") == 1234.56)

print("\n--- date order, which the file usually does not state ---")
check("a first number above 12 proves day-first",
      calc.detect_date_order(["13/04/2026", "05/06/2026"])["order"] == "DMY")
check("a second number above 12 proves month-first",
      calc.detect_date_order(["04/13/2026", "06/05/2026"])["order"] == "MDY")
check("a four-digit year first is unambiguous",
      calc.detect_date_order(["2026-04-13"])["order"] == "YMD")
_amb = calc.detect_date_order(["03/04/2026", "05/06/2026"])
check("where every day is 12 or less the file proves nothing, and it says so",
      _amb["order"] == "MDY" and _amb["ambiguous"] is True and _amb["proved"] is False)
_both = calc.detect_date_order(["13/04/2026", "04/13/2026"])
check("a column that is both ways round is reported as such, not majority-voted",
      _both["ambiguous"] is True and _both["proved"] is False)
check("the same string reads as two different days under the two orders",
      calc.parse_date("03/04/2026", "MDY") == "2026-03-04"
      and calc.parse_date("03/04/2026", "DMY") == "2026-04-03")
check("a month NAME settles it whatever the order says",
      calc.parse_date("5 Jan 2026", "DMY") == "2026-01-05"
      and calc.parse_date("Jan 5, 2026", "MDY") == "2026-01-05")
check("a two-digit year pivots at 70, as strptime does",
      calc.parse_date("12/25/25") == "2025-12-25"
      and calc.parse_date("12/25/99") == "1999-12-25")
check("an impossible date is None rather than rolling over into the next month",
      calc.parse_date("02/30/2026") is None)

print("\n--- which way round the bank writes a purchase ---")
_neg = calc.detect_sign(["-52.30", "-28.14", "-15.99", "510.00"])
check("a card statement of mostly negatives is negative-for-spending",
      _neg["convention"] == "negative" and _neg["ambiguous"] is False)
_pos = calc.detect_sign(["52.30", "28.14", "15.99", "-510.00"])
check("and mostly positives is positive-for-spending",
      _pos["convention"] == "positive")
check("an even split is flagged, because the majority is not much of an argument",
      calc.detect_sign(["-1", "-2", "3", "4"])["ambiguous"] is True)
check("no readable amounts at all is flagged rather than guessed",
      calc.detect_sign(["", "n/a"])["ambiguous"] is True)

print("\n--- which row is the header, and which column is which ---")
_CHASE = [["Transaction Date", "Post Date", "Description", "Category", "Type", "Amount"],
          ["08/14/2026", "08/15/2026", "TRADER JOE'S #452", "Groceries", "Sale", "-52.30"],
          ["08/16/2026", "08/17/2026", "UBER EATS", "Food & Drink", "Sale", "-28.14"],
          ["08/18/2026", "08/19/2026", "PAYMENT THANK YOU", "Payment", "Payment", "510.00"]]
_AMEX = [["12/25/2025", "STARBUCKS STORE 4", "6.75"],
         ["12/26/2025", "CHEVRON 0091", "41.02"]]
_CAP1 = [["Transaction Date", "Posted Date", "Card No.", "Description", "Category",
          "Debit", "Credit"],
         ["2026-08-14", "2026-08-15", "1234", "TRADER JOES", "Grocery", "52.30", ""],
         ["2026-08-16", "2026-08-17", "1234", "PAYMENT", "Payment", "", "510.00"]]

check("a first row with no date in it is column names",
      calc.detect_header(_CHASE) is True)
check("a first row with a date in it is a transaction",
      calc.detect_header(_AMEX) is False)
_m = calc.sniff_columns(_CHASE)
check("the transaction date beats the post date",
      _m["date"] == 0 and _m["description"] == 2 and _m["amount"] == 5)
_m2 = calc.sniff_columns(_AMEX, has_header=False)
check("with no header the columns are found by what is IN them",
      _m2["date"] == 0 and _m2["amount"] == 2 and _m2["description"] == 1,
      str(_m2))
# The reason detection cannot use parse_amount: it strips non-digits, so every
# merchant string carrying a store number scores as money. This file imported
# STARBUCKS STORE 4 as a $4.00 charge until the test above was written.
check("a column of shop names is not money, however many digits are in it",
      calc.looks_like_amount("STARBUCKS STORE 4") is False
      and calc.parse_amount("STARBUCKS STORE 4") == 4.0)
check("but a designated amount cell stays permissive about its furniture",
      calc.looks_like_amount("52.30 CR") is True
      and calc.looks_like_amount("$1,234.56") is True
      and calc.looks_like_amount("(52.30)") is True)
_m3 = calc.sniff_columns(_CAP1)
check("a debit/credit pair is recognised as a pair",
      _m3["debit"] == 5 and _m3["credit"] == 6 and _m3["amount"] is None)

print("\n--- what each row would become ---")
_CATS = ["Rent", "Groceries", "Dining Out", "Transportation", "Subscriptions",
         "Insurance", "Travel", "Gym", "Entertainment", "Shopping"]
_pv = calc.import_preview(_CHASE, categories=_CATS)
check("every line in the file comes back, none silently dropped",
      len(_pv["rows"]) == len(_CHASE) - 1)
check("and they add up: importable plus skipped is the whole file",
      _pv["summary"]["importable"] + _pv["summary"]["skipped"] == _pv["summary"]["total"])
check("a payment INTO the account is not imported, and says why in words",
      _pv["rows"][2]["skip"] == "money in, not out")
check("every skipped row carries a reason, never a bare None amount",
      all(r["skip"] for r in _pv["rows"] if r["amount"] is None))
check("a purchase written as -52.30 arrives as a positive expense of 52.30",
      _pv["rows"][0]["amount"] == 52.30)

_pv1 = calc.import_preview(_CAP1, categories=_CATS)
check("a debit column needs no sign convention worked out",
      _pv1["sign"]["convention"] == "debit column" and _pv1["rows"][0]["amount"] == 52.30)
check("an empty debit beside a filled credit is money in, not an unreadable row",
      _pv1["rows"][1]["skip"] == "money in, not out")

print("\n--- which of the person's own categories a row belongs to ---")
check("the longest match wins, so 'uber eats' beats 'uber'",
      calc.suggest_category("UBER EATS", None, _CATS)[0] == "Dining Out"
      and calc.suggest_category("UBER TRIP 4RT2", None, _CATS)[0] == "Transportation")
check("a category the person does not have is never suggested",
      calc.suggest_category("NETFLIX.COM", None, ["Rent"])[0] is None,
      "the keyword table must not invent a budget line")
check("whole words only — TRAVELERS INSURANCE is not Travel",
      calc.suggest_category("TRAVELERS INSURANCE PMT", None, _CATS)[0] == "Insurance")
for _desc, _wrong in [("GYMBOREE PLAY AND MUSIC", "Gym"),
                      ("PARENTS MAGAZINE SUB", "Rent"),
                      ("METROPOLITAN MUSEUM", "Transportation"),
                      ("TOLLHOUSE BAKERY", "Transportation")]:
    check(f"{_desc.split()[0]} is not {_wrong} — the merchant table matches whole words too",
          calc.suggest_category(_desc, None, _CATS)[0] is None,
          str(calc.suggest_category(_desc, None, _CATS)))
check("and the words those nearly-matched still work when they are the word",
      calc.suggest_category("METRO TRANSIT AUTH", None, _CATS)[0] == "Transportation"
      and calc.suggest_category("TOLL ROAD AUTHORITY", None, _CATS)[0] == "Transportation"
      and calc.suggest_category("EQUINOX GYM", None, _CATS)[0] == "Gym")
check("a boundary is any non-letter, so an apostrophe or a hash still ends a word",
      calc.suggest_category("MACYS #12", None, _CATS)[0] == "Shopping"
      and calc.suggest_category("BP#4471 FUEL", None, _CATS)[0] == "Transportation")
# The longest-match rule on the OWN-CATEGORY half. Every other ordering case
# here is decided among merchant keywords, so a mutation reversing the rule
# used to break only that half and nothing noticed.
check("between two of the reader's own names, the longer match wins",
      calc.suggest_category("GAS AND ELECTRIC CO", None,
                            ["Gas", "Gas and Electric"])[0] == "Gas and Electric")
check("and a merchant keyword beats a SHORTER category name of the reader's own",
      calc.suggest_category("WHOLE FOODS MKT", None, ["Groceries", "Food"])[0]
      == "Groceries",
      "whole foods (11) beats food (4)")
check("the bank's own category is a fallback, not the winner",
      calc.suggest_category("NETFLIX.COM", "Entertainment", _CATS)[0] == "Subscriptions",
      "Chase files Netflix under Entertainment; this profile has Subscriptions")
check("but it is used where the description names nothing",
      calc.suggest_category("SQ *A1B2C3XYZ", "Groceries", _CATS) == ("Groceries", "bank category"))
check("and only when it names a category that exists",
      calc.suggest_category("SQ *A1B2C3XYZ", "Merchandise", _CATS)[0] is None)
check("no guess is None, never a default bucket",
      calc.suggest_category("WEIRD MERCHANT LLC", None, _CATS)[0] is None)

print("\n--- duplicates, counted rather than matched ---")
_HELD = [{"id": "e1", "date": "2026-08-14", "amount": 52.30},
         {"id": "e2", "date": "2026-08-20", "amount": 5.00}]
_TWICE = [["Date", "Description", "Amount"],
          ["08/14/2026", "TRADER JOES", "-52.30"],
          ["08/14/2026", "TRADER JOES AGAIN", "-52.30"],
          ["08/20/2026", "COFFEE", "-5.00"],
          ["08/20/2026", "COFFEE 2", "-5.00"],
          ["08/20/2026", "COFFEE 3", "-5.00"]]
_d = calc.import_preview(_TWICE, existing=_HELD, categories=_CATS)
check("one held expense flags exactly one of the file's matching rows",
      [r["duplicate_of"] for r in _d["rows"]] == ["e1", None, "e2", None, None],
      "two real coffees on one day must not both be called duplicates")
# The other half of the same rule: import the file a second time and every row
# is already held, so every row is flagged.
_again = [{"id": f"n{i}", "date": r["date"], "amount": r["amount"]}
          for i, r in enumerate(_d["rows"])]
_d2 = calc.import_preview(_TWICE, existing=_HELD + _again, categories=_CATS)
check("importing the same file twice flags every row of it",
      all(r["duplicate_of"] for r in _d2["rows"]),
      "this is the failure that doubles a year of spending")
check("a flagged row is still importable — it is marked, not removed",
      all(r["skip"] is None for r in _d2["rows"])
      and _d2["summary"]["importable"] == 5)

print("\n--- the file's own evidence comes back with the answer ---")
# 08/12 is valid read either way round, which is exactly the case the file
# cannot settle for itself and the reader has to.
_AMBIG = [["Date", "Description", "Amount"], ["08/12/2026", "TRADER JOES", "-52.30"]]
check("the file's own reading is month-first where nothing proves otherwise",
      calc.import_preview(_AMBIG, categories=_CATS)["rows"][0]["date"] == "2026-08-12")
check("and an overridden date order is used instead, on every row",
      calc.import_preview(_AMBIG, categories=_CATS,
                          date_order="DMY")["rows"][0]["date"] == "2026-12-08")
check("a date that is impossible under the chosen order is reported, not guessed",
      calc.import_preview(_TWICE, categories=_CATS, date_order="DMY")["rows"][0]["skip"]
      == "the date could not be read",
      "08/14 has no 14th month")
check("an overridden sign convention is used",
      calc.import_preview(_TWICE, categories=_CATS,
                          sign="positive")["summary"]["importable"] == 0,
      "every amount in this file is negative, so nothing is spending")
check("a supplied mapping is used instead of the sniffed one",
      calc.import_preview(_TWICE, categories=_CATS,
                          mapping={"date": 0, "amount": 2, "description": 1})
      ["mapping_suggested"] is False)
check("an empty file is an empty preview, not an error",
      calc.import_preview([], categories=_CATS)["rows"] == [])


# ── The dashboard's health verdicts ──────────────────────────────────
print("\n--- health_report: the month is not over ---")

_HEXP = [{"id": "1", "date": "2026-09-01", "amount": 1800.0, "category": "Rent"}]
_HBUD = {"needs": {"Rent": 1800, "Groceries": 600}, "wants": {"Dining": 300},
         "savings": {}}
_mid = calc.health_report(5932.0, _HEXP, _HBUD, dti_pct=0.0,
                          emergency_fund=4.9, today="2026-09-04")
_end = calc.health_report(5932.0, _HEXP, _HBUD, dti_pct=0.0,
                          emergency_fund=4.9, today="2026-09-30")

# THE DEFECT. `1 - spent_so_far / take_home` starts each month at 100% and
# falls through it, so on the 4th with one rent charge logged the ring read
# 70% and was painted GREEN. The figure is still reported; the GRADE is not.
check("a month in progress reports its figure",
      round(_mid["savings_rate"], 1) == 69.7, str(_mid["savings_rate"]))
check("but is not graded, and says why",
      _mid["savings_tone"] == "info" and _mid["savings_status"] is None
      and _mid["verdict_withheld"] == "4 of 30 days into the month",
      f'{_mid["savings_tone"]} / {_mid["verdict_withheld"]}')
check("the same month, once complete, IS graded",
      _end["verdict_withheld"] is None
      and _end["savings_tone"] == "positive" and _end["savings_status"] == "Strong")

# The second half of the same defect: a category with nothing logged against
# it is "within budget", so a month holding one expense scored 15/15.
check("adherence counts a category with nothing logged as on track",
      _mid["on_track"] == 3 and _mid["budgeted_categories"] == 3)
check("and REPORTS how many those are, so the score is not read as a result",
      _mid["unlogged_categories"] == 2)
check("adherence is not graded mid-month either",
      _mid["adherence_tone"] == "info" and _mid["adherence_status"] == "Partial month")
check("a budgeted category at zero is not a category",
      calc.health_report(1000.0, [], {"needs": {"Rent": 0}},
                         today="2026-09-30")["budgeted_categories"] == 0)

# A month with nothing in it cannot be graded either, however far through it
# is: an expense log has holes and a hole looks exactly like a frugal month.
_empty = calc.health_report(5932.0, [], _HBUD, today="2026-09-30")
check("a complete month with nothing logged is still not graded",
      _empty["verdict_withheld"] == "no records for this month"
      and _empty["savings_tone"] == "info")
# and the month still running says the opposite thing, because "yet" is a claim
# about a month that has time left in it
check("an EMPTY month in progress says 'yet' and a finished one does not",
      calc.health_report(5932.0, [], _HBUD, today="2026-09-04")["verdict_withheld"]
      == "nothing logged this month yet")
check("and its rate would have been a flattering 100%",
      _empty["savings_rate"] == 100.0)

# "Needs income" is not a verdict about the month, so it survives.
_broke = calc.health_report(0.0, [], _HBUD, today="2026-09-04")
check("with no salary the rate is None, not zero",
      _broke["savings_rate"] is None)
check("and the reason given is the missing salary, not the missing month",
      _broke["savings_status"] == "Needs income")

check("expenses from another month are not this month's",
      calc.health_report(1000.0, [{"date": "2026-08-31", "amount": 500.0}],
                         today="2026-09-04")["spent"] == 0)
check("the client's date decides which month 'this month' is",
      calc.health_report(1000.0, _HEXP, today="2026-10-04")["transactions"] == 0
      and calc.health_report(1000.0, _HEXP, today="2026-09-04")["transactions"] == 1)

print("\n--- the bands live in one place ---")
# They were a ternary on the dashboard and a DIFFERENT ternary on /year —
# three tiers against four — so one rate was graded two ways depending which
# page you were looking at.
check("the savings bands are Strong / Building / Thin / Negative",
      [calc.savings_rate_verdict(r)[1] for r in (25, 15, 5, -5)]
      == ["Strong", "Building", "Thin", "Negative"])
check("and /year reports its verdict from that same function",
      calc.year_to_date([{"date": "2026-01-15", "amount": 100.0, "category": "X"}],
                        monthly_take_home=1000.0, today="2026-03-04")["savings_status"]
      == calc.savings_rate_verdict(
          calc.year_to_date([{"date": "2026-01-15", "amount": 100.0, "category": "X"}],
                            monthly_take_home=1000.0, today="2026-03-04")["savings_rate"])[1])
check("lender DTI bands are graded on the boundaries, not near them",
      [calc.dti_verdict(v)[1] for v in (None, 0, 20, 20.1, 36, 36.1)]
      == ["Needs income", "No debt", "Healthy", "Manageable", "Manageable", "High"])
check("emergency-fund coverage of None is not coverage of zero",
      calc.emergency_fund_verdict(None)[1] == "Not measurable"
      and calc.emergency_fund_verdict(0)[1] == "Priority"
      and calc.emergency_fund_verdict(6)[1] == "Strong")
check("February knows about leap years",
      calc._days_in_month(2028, 2) == 29 and calc._days_in_month(2027, 2) == 28
      and calc._days_in_month(2026, 12) == 31)

print("\n--- health_report: looking at a month other than this one ---")
# The verdict withheld above is only ever REACHABLE through this: pinned to the
# current month, a grade could appear on the last day and never again.
_HPAST = [{"date": "2026-07-03", "amount": 900.0, "category": "Rent"}] + _HEXP
_jul = calc.health_report(5932.0, _HPAST, _HBUD, today="2026-09-04", month="2026-07")
_aug = calc.health_report(5932.0, _HPAST, _HBUD, today="2026-09-04", month="2026-08")

check("a past month is complete however early in today it is",
      _jul["month"] == "2026-07" and _jul["month_complete"] is True
      and _jul["day"] == 31)
check("and therefore carries the verdict the current one cannot",
      _jul["verdict_withheld"] is None and _jul["savings_status"] == "Strong")
check("a past month with no records says so, and does not say 'yet'",
      _aug["verdict_withheld"] == "no records for this month")
check("the current month is still measured against today",
      calc.health_report(5932.0, _HPAST, _HBUD, today="2026-09-04",
                         month="2026-09")["day"] == 4)
check("a malformed month falls back to the reader's own, rather than raising",
      [calc.health_report(1000.0, [], today="2026-09-04", month=m)["month"]
       for m in ("nonsense", "2026-13", "2026-00", "", None, "26-09")]
      == ["2026-09"] * 6)

# The strip is contiguous, so a month nobody logged is reachable and answers
# for itself; a gap in it would read as a gap in the app.
check("the strip runs from the earliest record to the reader's month",
      _jul["months_available"] == ["2026-07", "2026-08", "2026-09"])
check("including the month that holds no records at all",
      "2026-08" in _jul["months_available"])
check("with no records at all it is just this month",
      calc.health_report(1000.0, [], today="2026-09-04")["months_available"]
      == ["2026-09"])
check("a record dated in the future does not extend it",
      calc.health_report(1000.0, [{"date": "2027-03-02", "amount": 5.0}],
                         today="2026-09-04")["months_available"] == ["2026-09"])
check("and it is bounded, so a decade of history is not a decade of buttons",
      len(calc.health_report(1000.0, [{"date": "2001-01-05", "amount": 5.0}],
                             today="2026-09-04")["months_available"])
      == calc.MONTH_STRIP_MAX)
check("the bound keeps the RECENT end, which is the reachable one",
      calc.health_report(1000.0, [{"date": "2001-01-05", "amount": 5.0}],
                         today="2026-09-04")["months_available"][-1] == "2026-09")
check("a year boundary is crossed without skipping a month",
      calc.health_report(1000.0, [{"date": "2025-11-05", "amount": 5.0}],
                         today="2026-02-04")["months_available"]
      == ["2025-11", "2025-12", "2026-01", "2026-02"])

print("\n--- Start empty starts empty ---")
# It served `get_default_state()` until September 2026, which is a STARTER
# TEMPLATE: a $100,000 salary, 17 budget rows totalling $4,430 and $20,000 of
# assets. The dashboard read take-home $5,682 and net worth $20,000 to someone
# who had just asked for no figures at all.
_empty_p = app_data.empty_profile()
_default_p = app_data.get_default_state()


def _numbers(node, path=""):
    """Every numeric leaf in the profile, with the path that reaches it."""
    if isinstance(node, dict):
        out = []
        for k, v in node.items():
            out += _numbers(v, f"{path}.{k}" if path else k)
        return out
    if isinstance(node, list):
        return [(path, x) for x in node if isinstance(x, (int, float))]
    if isinstance(node, bool) or not isinstance(node, (int, float)):
        return []
    return [(path, node)]


_KEEP = {"investment.annual_return", "investment.time_horizon"}
_nonzero = [(k, v) for k, v in _numbers(_empty_p) if v != 0 and k not in _KEEP]

check("the empty profile has the same SHAPE as the default",
      set(_empty_p) == set(_default_p)
      and set(_empty_p["budget"]) == set(_default_p["budget"])
      and set(_empty_p["income"]) == set(_default_p["income"]))
check("and every figure in it is zero",
      _nonzero == [], f"{len(_nonzero)} left: {_nonzero[:4]}")
check("the row NAMES survive, because a blank page is not a fresh start",
      set(_empty_p["budget"]["needs"]) == set(_default_p["budget"]["needs"])
      and set(_empty_p["assets"]) == set(_default_p["assets"]))
check("every list is empty",
      _empty_p["expenses"] == [] and _empty_p["debts"] == []
      and _empty_p["savings_goals"] == [] and _empty_p["net_worth_snapshots"] == [])
# Zero is not "unset" for these two, and a 0% return over 0 years is a broken
# projection rather than a blank one.
check("the projection's assumptions are kept, because zero is not unset there",
      _empty_p["investment"]["annual_return"] == _default_p["investment"]["annual_return"]
      and _empty_p["investment"]["time_horizon"] == _default_p["investment"]["time_horizon"])
check("a selection is not a figure, so the state and filing status survive",
      _empty_p["income"]["state"] == _default_p["income"]["state"]
      and _empty_p["income"]["filing_status"] == _default_p["income"]["filing_status"])
# The starter template is what the report was about, so assert it is NOT this.
check("and the template it used to serve really did carry figures",
      any(v != 0 for k, v in _numbers(_default_p) if k not in _KEEP))

# The whole point: the dashboard reads nothing rather than somebody's money.
_eh = calc.health_report(0.0, _empty_p["expenses"], _empty_p["budget"],
                         dti_pct=None, emergency_fund=None, today="2026-09-04")
check("an empty profile measures no savings rate, rather than one of zero",
      _eh["savings_rate"] is None and _eh["savings_status"] == "Needs income")
check("no budget is 'no budget set', not 0 of 0 on track",
      _eh["budgeted_categories"] == 0 and _eh["adherence_pct"] is None
      and _eh["adherence_status"] == "No budget set")
check("and the strip offers only the month you are in",
      _eh["months_available"] == ["2026-09"])

print("\n" + "=" * 66)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 66)
sys.exit(1 if failed else 0)
