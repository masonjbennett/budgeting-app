"""The budget app's calculation API — one Vercel Function, many routes.

EVERY NUMBER THIS RETURNS COMES FROM calculations.py, which is the repo root's
copy, brought in verbatim at build time by scripts/sync-calculations.mjs. There
is deliberately no arithmetic in this file beyond assembling arguments. The
previous attempt at this rebuild kept its own fork of that module and shipped a
debt engine that reported 79 months and $10,194 of interest where the real one
says 56 and $8,458; the whole point of the shape below is that the same class of
drift has nowhere to live.

If `calculations` fails to import, the sync did not run and the deploy must
fail rather than serve a stale copy — see the header in the sync script.

AUTH IS NOT HERE, ON PURPOSE. The browser talks to Supabase directly and
row-level security enforces isolation, so this function never sees a credential
or holds a JWT. That is only safe while every route below stays a PURE
CALCULATOR over numbers the caller supplies. Nothing here may read or write
user_data. If something ever needs to, it needs authentication first.
"""

import os
import sys
from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

# THIS DIRECTORY HAS TO BE ON sys.path AND ONLY PRODUCTION SAYS SO.
#
# `calculations` and `app_data` are siblings of this file, written here by
# scripts/sync-calculations.mjs. Every local way of running the API already put
# this directory on the path without being asked: uvicorn is started with
# `--app-dir api`, and test_api.py inserts it itself. Vercel is the one context
# that does neither — it imports `api/index.py` with /var/task as the root, so
# `import app_data` has nowhere to resolve from.
#
# The first deploy therefore built a function that crashed on import, every
# /api route 404d or 500d, and NOTHING in the build log was red: the sync had
# printed its verified byte-for-byte line, the bundle contained both files, and
# the failure only existed at invocation time. It took the runtime log to see
# it. Four local suites, 106 API assertions and a green production build all
# passed over it, because all of them had already made the path right.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app_data import _generate_demo_data, get_default_state  # noqa: E402
from calculations import (  # noqa: E402
    COL_INDEX,
    MONTHS_PER_YEAR,
    SWR_DEFAULT,
    cash_flow,
    col_compare,
    compare_scenarios,
    cost_of_waiting,
    FEDERAL_BRACKETS_2026,
    FILING_STATUSES,
    HSA_INDIVIDUAL_LIMIT,
    K401_LIMIT,
    STANDARD_DEDUCTION_2026,
    STATE_TAX_DATA,
    calc_salt_cap,
    calc_social_security,
    capital_equivalent,
    compute_take_home,
    emergency_fund_months,
    health_report,
    fire_projection,
    histogram,
    import_preview,
    liquid_assets,
    monthly_debt_service,
    project_investment_with_match,
    raise_impact,
    roth_vs_traditional,
    run_monte_carlo,
    simulate_payoff,
    top_bracket_limitation,
    year_to_date,
)

app = FastAPI(title="Budget Tracker API", version="5.0")


# ── Request models ───────────────────────────────────────────────────

class Income(BaseModel):
    gross_salary: float = 0
    state: str = "Texas"
    filing_status: str = "Single"
    contribution_401k: float = 0
    health_insurance: float = 0
    hsa: float = 0
    bonus_amount: float = 0
    bonus_type: str = "None"
    student_loan_interest: float = 0


class TakeHomeRequest(BaseModel):
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)


class Debt(BaseModel):
    name: str
    balance: float
    rate: float
    min_payment: float


class PayoffRequest(BaseModel):
    debts: List[Debt] = Field(default_factory=list)
    extra: float = 0


class ExpenseIn(BaseModel):
    """One logged expense, as the profile stores it.

    Permissive on purpose: this crosses from a store the user controls, and a
    row with a missing note or an unparseable date must reach the engine to be
    REPORTED as unreadable rather than 422 the whole request. The engine's
    date parsing already returns None rather than raising for exactly that.
    """
    id: str = ""
    date: str = ""
    amount: float = 0
    category: str = ""
    note: str = ""


class DashboardRequest(BaseModel):
    """Everything the health ratios need, in one round trip.

    These ratios are the reason this endpoint exists rather than the numbers
    being worked out in TypeScript. Both of them were wrong in the Streamlit app
    until September 2026 and wrong again in the abandoned Next.js scaffold, in
    the same two ways each time: debt-to-income read a single budget CATEGORY
    NAME so someone with $35,000 of student loans and a zero in that row saw
    "0.0% — Debt-Free", and emergency-fund coverage looked up the literal asset
    key "Savings" so renaming that row to "High-Yield Savings" read 0.0 months
    as though it had been measured. A second implementation in another language
    is how that happens a third time.
    """
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    debts: List[Debt] = Field(default_factory=list)
    budget_needs: Dict[str, float] = Field(default_factory=dict)
    assets: Dict[str, float] = Field(default_factory=dict)
    # The month's spending and the whole budget, because the savings rate and
    # budget adherence are measured over them — and both were computed and
    # GRADED in page.tsx until September 2026 for the simple reason that this
    # route was never given the data. See `health_report`.
    expenses: List[ExpenseIn] = Field(default_factory=list, max_length=50_000)
    budget: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    # The CLIENT's date. Omitted, the server's is used — right for a test and
    # wrong for a reader in a timezone behind this function, for whom the
    # server has already rolled into a month they are not in yet.
    today: Optional[str] = None


class CashFlowRequest(BaseModel):
    """Everything one month's flow needs: the pay stub and the plan."""
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    budget: Dict[str, Dict[str, float]] = Field(default_factory=dict)


class InvestmentRequest(BaseModel):
    start: float = 0
    monthly: float = 0
    rate: float = 7.0
    years: int = 30
    contribution_growth: float = 0
    # A year's delay is the default question; the page lets it be changed.
    delay_years: float = 1
    # Optional: with a salary the employer's match is projected too. Left at
    # zero this is the plain projection, which is what it always was.
    salary: float = 0
    contribution_pct: float = 0
    match_pct: float = 0
    match_limit: float = 0


class Scenario(BaseModel):
    name: str = "Scenario"
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    city: str = "National Average"


class CompareRequest(BaseModel):
    """Several situations, the FIRST of which is the baseline."""
    scenarios: List[Scenario] = Field(default_factory=list)


class RaiseRequest(BaseModel):
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    increase: float = 0


class ColRequest(BaseModel):
    salary: float = 0
    from_city: str = "National Average"
    to_city: str = "National Average"


class MonteCarloRequest(BaseModel):
    current_age: int = 30
    retire_age: int = 60
    end_age: int = 95
    portfolio: float = 0
    annual_savings: float = 0
    annual_expenses: float = 0
    stock_pct: float = 80
    inflation: float = 3.0
    n_sims: int = 1000
    seed: Optional[int] = None


class SocialSecurityRequest(BaseModel):
    annual_salary: float = 0
    claiming_age: int = 67
    # So the benefit can be stated as capital the portfolio need not build.
    swr: float = SWR_DEFAULT


class RothRequest(BaseModel):
    contribution: float = 0
    current_rate: float = 0.0     # a FRACTION, federal + state combined
    future_rate: float = 0.0      # a FRACTION
    annual_return: float = 7.0
    years: int = 30


class SaltRequest(BaseModel):
    magi: float = 0
    filing: str = "Single"


class FireRequest(BaseModel):
    """The profile the FIRE page already holds, plus its two assumptions.

    `stock_pct` and `inflation` are the SAME two controls the Monte Carlo on
    that page uses. They are here so the curve's expected return is derived
    from them rather than being a third assumption typed into a third place.
    """
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    budget: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    assets: Dict[str, float] = Field(default_factory=dict)
    stock_pct: float = 80.0
    inflation: float = 3.0
    swr: float = SWR_DEFAULT


class YearToDateRequest(BaseModel):
    income: Income
    itemized: Dict[str, float] = Field(default_factory=dict)
    expenses: List[ExpenseIn] = Field(default_factory=list, max_length=50_000)
    budget: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    # The CLIENT's date. Omitted, the server's is used — which is right for a
    # test and wrong for a reader in a timezone behind this function.
    today: Optional[str] = None


class ImportMapping(BaseModel):
    """Which column holds what. Every field optional — a file need not have
    one, and `null` here means "work it out", not "column zero"."""
    date: Optional[int] = None
    amount: Optional[int] = None
    debit: Optional[int] = None
    credit: Optional[int] = None
    description: Optional[int] = None
    category: Optional[int] = None


class ImportRequest(BaseModel):
    """A CSV already split into cells, and the profile to compare it against.

    The grid is capped rather than streamed. 20,000 rows is about fifteen
    years of one card's statements, and a file larger than that is a mistake
    worth failing loudly on — a truncated import is the same defect as a
    duplicated one, silently missing money instead of silently doubling it.
    """
    grid: List[List[str]] = Field(default_factory=list, max_length=20_000)
    # None asks the engine to work it out; True or False is the person's own
    # answer, made in the preview, and is obeyed.
    has_header: Optional[bool] = None
    mapping: Optional[ImportMapping] = None
    # "MDY" | "DMY" | "YMD", and None to let the file's own evidence decide.
    date_order: Optional[str] = None
    # "negative" | "positive", and None to decide by majority.
    sign: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    existing: List[ExpenseIn] = Field(default_factory=list, max_length=50_000)


# ── Routes ───────────────────────────────────────────────────────────

@app.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "version": app.version}


@app.get("/api/state")
def starting_state(demo: bool = True) -> Dict[str, Any]:
    """The profile a new visitor starts on.

    Served rather than retyped in TypeScript because the two front ends must
    agree on it, and because the demo has a tested property: it ships THREE
    debts whose rate order and balance order conflict. With one debt — which is
    what the abandoned scaffold's hand-written copy had — avalanche and snowball
    are identical by definition and the debt page's whole comparison is dead.
    """
    return _generate_demo_data() if demo else get_default_state()


@app.get("/api/reference")
def reference() -> Dict[str, Any]:
    """Tax tables and limits, so the client never hardcodes a number.

    float("inf") is not JSON, so the open-ended top bracket is sent as null and
    the client reads a null ceiling as "and everything above".
    """
    def brackets(rows):
        return [[None if c == float("inf") else c, r] for c, r in rows]

    return {
        "federal_brackets": {k: brackets(v) for k, v in FEDERAL_BRACKETS_2026.items()},
        "standard_deductions": STANDARD_DEDUCTION_2026,
        "filing_statuses": FILING_STATUSES,
        "states": sorted(STATE_TAX_DATA.keys()),
        "col_index": COL_INDEX,
        "k401_limit": K401_LIMIT,
        "hsa_individual_limit": HSA_INDIVIDUAL_LIMIT,
    }


@app.post("/api/take-home")
def api_take_home(req: TakeHomeRequest) -> Dict[str, Any]:
    return compute_take_home(req.income.model_dump(), req.itemized)


@app.post("/api/dashboard")
def api_dashboard(req: DashboardRequest) -> Dict[str, Any]:
    th = compute_take_home(req.income.model_dump(), req.itemized)
    debts = [d.model_dump() for d in req.debts]

    service, service_source = monthly_debt_service(debts, req.budget_needs)
    monthly_needs = sum(req.budget_needs.values())
    ef_months, ef_counted = emergency_fund_months(req.assets, monthly_needs)
    liquid_total, _ = liquid_assets(req.assets)

    # Lender debt-to-income bands (20% / 36%) are defined on GROSS income, so
    # the denominator is gross. Dividing by take-home instead — which both
    # earlier versions did — shrinks it by about a quarter and grades people a
    # whole category harsher than a lender would.
    gross_monthly = th["annual_gross"] / 12
    dti = (service / gross_monthly * 100) if gross_monthly else None
    return {
        "take_home": th,
        # Every band on the page, and the month they are measured over. The
        # figures are for the month SO FAR; the verdict is withheld until the
        # month is complete, because a month in progress grades flatteringly
        # and both of these cards were doing it.
        "health": health_report(
            th["monthly_take_home"],
            [e.model_dump() for e in req.expenses],
            req.budget,
            dti_pct=dti,
            emergency_fund=ef_months,
            today=req.today,
        ),
        "monthly_debt_service": service,
        "debt_service_source": service_source,
        "dti_pct": dti,
        "monthly_needs": monthly_needs,
        # None is not 0.0: it means coverage could not be measured, not that it
        # is zero. The client must render the two differently.
        "emergency_fund_months": ef_months,
        "emergency_fund_counted": ef_counted,
        "liquid_assets": liquid_total,
        # Not a calculation the app performs — a disclosure that it does NOT.
        # In the top bracket, itemized deductions are worth 2/37 less than the
        # marginal rate implies, and this engine does not model that. Saying so
        # is the only honest option; the alternative is being quietly wrong for
        # the people it affects.
        "top_bracket": top_bracket_limitation(th["taxable"], th["filing"]),
    }


@app.post("/api/cash-flow")
def api_cash_flow(req: CashFlowRequest) -> Dict[str, Any]:
    """The Sankey's nodes and links.

    A route rather than a component because the flow is DERIVED — annualised
    tax figures reduced to the month the budget is kept in, bucket totals, and
    the remainder that is left unallocated. The client draws the geometry and
    works out nothing.
    """
    return cash_flow(req.income.model_dump(), req.itemized, req.budget)


@app.post("/api/debt-payoff")
def api_debt_payoff(req: PayoffRequest) -> Dict[str, Any]:
    debts = [d.model_dump() for d in req.debts]
    out = {}
    for strategy in ("avalanche", "snowball"):
        months, interest, schedule, payoff_months = simulate_payoff(
            debts, req.extra, strategy)
        out[strategy] = {
            # -1 is the engine's sentinel for "these payments never clear this
            # debt". It is not a duration and must not be rendered as one.
            "months": months,
            "never_pays_off": months == -1,
            "total_interest": interest,
            "schedule": schedule,
            "payoff_months": payoff_months,
        }
    return out


@app.post("/api/investment")
def api_investment(req: InvestmentRequest) -> Dict[str, Any]:
    # project_investment returns a (values, contributions) TUPLE — the two
    # series are only told apart by position. Naming them is the whole job of
    # this route; a client that got the tuple would be one index slip away from
    # plotting contributions as the portfolio value.
    values, contributions, match = project_investment_with_match(
        req.start, req.monthly, req.rate, req.years, req.salary,
        req.contribution_pct, req.match_pct, req.match_limit,
        req.contribution_growth)
    return {
        "values": values,
        "contributions": contributions,
        "months": len(values) - 1,
        "final_value": values[-1],
        "total_contributed": contributions[-1],
        "growth": values[-1] - contributions[-1],
        "employer_match": match,
        # None where a delay cannot be modelled (no horizon, or a delay as long
        # as the horizon) — never a zero, which would read as "costs nothing".
        "cost_of_waiting": cost_of_waiting(
            req.start, req.monthly, req.rate, req.years, req.delay_years),
    }


@app.post("/api/raise")
def api_raise(req: RaiseRequest) -> Dict[str, Any]:
    """What a raise is worth after tax, pre-tax deductions and marginal FICA."""
    return raise_impact(req.income.model_dump(), req.increase, req.itemized)


@app.post("/api/compare")
def api_compare(req: CompareRequest) -> Dict[str, Any]:
    """The same person in several situations, priced against each other."""
    return compare_scenarios([s.model_dump() for s in req.scenarios])


@app.post("/api/cost-of-living")
def api_cost_of_living(req: ColRequest) -> Dict[str, Any]:
    """Buying power between two metros. Null where either is unknown."""
    return {"comparison": col_compare(req.salary, req.from_city, req.to_city)}


@app.post("/api/monte-carlo")
def api_monte_carlo(req: MonteCarloRequest) -> Dict[str, Any]:
    out = run_monte_carlo(
        req.current_age, req.retire_age, req.end_age, req.portfolio,
        req.annual_savings, req.annual_expenses, req.stock_pct,
        req.inflation, req.n_sims, req.seed)
    # Binned here rather than inside run_monte_carlo, so that function's
    # contract — which test_calc compares against directly — does not move.
    # The fan chart shows the RANGE; the shape is a different question, and a
    # comfortable median with a long tail of failures looks fine on a band.
    # `isolate=0` gives the paths that RAN OUT a bar of their own. Without it
    # they share a bucket with the merely-poor survivors and the chart cannot
    # honestly colour it either way — measured, the claret was all of the chart
    # or none of it and never the mixture it exists for.
    out["ending_histogram"] = histogram(out["ending"], isolate=0)
    return out


@app.post("/api/social-security")
def api_social_security(req: SocialSecurityRequest) -> Dict[str, Any]:
    monthly = calc_social_security(req.annual_salary, req.claiming_age)
    annual = monthly * MONTHS_PER_YEAR
    return {
        "monthly": monthly,
        "annual": annual,
        # The benefit as capital, which is the only form comparable to a FIRE
        # number. The page used to divide by its own copy of the withdrawal
        # rate to get this.
        "reduces_target_by": capital_equivalent(annual, req.swr),
    }


@app.post("/api/roth-vs-traditional")
def api_roth(req: RothRequest) -> Dict[str, Any]:
    return roth_vs_traditional(req.contribution, req.current_rate,
                               req.future_rate, req.annual_return, req.years)


@app.post("/api/salt-cap")
def api_salt_cap(req: SaltRequest) -> Dict[str, Any]:
    return {"effective_cap": calc_salt_cap(req.magi, req.filing)}


@app.post("/api/fire")
def api_fire(req: FireRequest) -> Dict[str, Any]:
    """The FIRE number, the savings rate, and the curve between them.

    A route rather than five lines of TypeScript because all five figures on
    that page are rules — a ratio, a target, a progress percentage, a solved-
    for duration, and a `const SWR = 0.04` that used to live in the front end
    where no test could see it and where it would have drifted from the
    Streamlit app the first time either changed.

    The return assumption is DERIVED from the same constants the Monte Carlo
    below it draws from, so the deterministic curve and the simulation on one
    page describe one world rather than two.
    """
    return fire_projection(
        req.income.model_dump(), req.itemized, req.budget, req.assets,
        req.stock_pct, req.inflation, req.swr)


@app.post("/api/year-to-date")
def api_year_to_date(req: YearToDateRequest) -> Dict[str, Any]:
    """The calendar year so far — spent, saved, and against the plan.

    `today` comes from the CLIENT. The year boundary belongs to the person
    reading the page, not to the region this function happens to run in: a
    server in UTC is already into January while someone in Chicago is still
    finishing New Year's Eve, and the dashboard beside this reads the browser's
    clock for exactly the same reason.
    """
    th = compute_take_home(req.income.model_dump(), req.itemized)
    return year_to_date(
        [e.model_dump() for e in req.expenses],
        req.budget,
        th["monthly_take_home"],
        req.today,
    )


@app.post("/api/import-preview")
def api_import_preview(req: ImportRequest) -> Dict[str, Any]:
    """What a bank's CSV would become, before any of it is committed.

    NOTHING IS WRITTEN ANYWHERE BY THIS. It reads a grid of strings the client
    split out of a file and returns, per row, the date it parsed to, the
    amount, the category it suggests and whether the profile already holds a
    matching expense — plus what it decided about the file as a whole and the
    evidence for each decision.

    The decisions are here rather than in the front end because every one of
    them fails silently: a date order read backwards moves a year of spending
    by a month, a sign convention read backwards imports the refunds and drops
    the purchases, and importing the same file twice doubles the year. All
    three produce numbers that look like numbers.
    """
    return import_preview(
        req.grid,
        existing=[e.model_dump() for e in req.existing],
        categories=req.categories,
        has_header=req.has_header,
        mapping=req.mapping.model_dump() if req.mapping else None,
        date_order=req.date_order,
        sign=req.sign,
    )
