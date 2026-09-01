"""Tests for the calculation engine in budget_app.py.

Like test_cloud.py and unlike test_stress.py, this imports the SHIPPING code
rather than a copy of it: the source above the sidebar (tax data, calculations,
helpers, compute_take_home) is exec'd with streamlit and the plotting libraries
stubbed. test_stress.py redefines its nine subjects inside itself, which is why
it has been green since April over an April photocopy.

The assertions here are PROPERTIES, not a second implementation. Re-deriving the
expected answer with a reference copy of the algorithm would just be the mirror
problem again — a bug reasoned into both copies passes. So instead: money in
equals money out, a strategy pays debts off in the order its name promises, and
avalanche never costs more interest than snowball.

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

SRC = open("budget_app.py", encoding="utf-8").read()
CUT = SRC.index("# SIDEBAR NAVIGATION")   # everything below needs a live runtime
app = types.ModuleType("app_calc")
exec(compile(SRC[:CUT], "budget_app.py", "exec"), app.__dict__)

simulate_payoff = app.simulate_payoff

print("=" * 66)
print("CALCULATION SUITE — driving the shipping functions in budget_app.py")
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
      app.payoff_order(SWITCHER, "snowball") == ["Target", "Fast"],
      str(app.payoff_order(SWITCHER, "snowball")))
check("avalanche targets the higher rate first regardless of size",
      app.payoff_order(MIXED, "avalanche")[0] == "Card")
check("the order is a fixed list, not re-derived from live balances",
      app.payoff_order(MIXED, "snowball") == ["Card", "Car", "Student"])

# Testing payoff_order in isolation is not enough: it says the rule is right, not
# that the engine obeys it. Re-sorting inside the loop leaves payoff_order intact
# and passes every assertion above — a rule nothing reads is a rule nothing
# enforces. So drive the engine with the order reversed and require the answer to
# move; if simulate_payoff computed its own order, it would not.
_real_order = app.payoff_order
app.payoff_order = lambda debts, strategy: list(reversed(_real_order(debts, strategy)))
_, i_reversed, _, _ = simulate_payoff(MIXED, 300, "avalanche")
app.payoff_order = _real_order
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

print("\n" + "=" * 66)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 66)
sys.exit(1 if failed else 0)
