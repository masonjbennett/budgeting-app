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

SRC = open("budget_app.py", encoding="utf-8").read()
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


print("\n" + "=" * 66)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 66)
sys.exit(1 if failed else 0)
