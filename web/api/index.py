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

from typing import Any, Dict, List, Optional

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app_data import _generate_demo_data, get_default_state
from calculations import (
    COL_INDEX,
    cash_flow,
    FEDERAL_BRACKETS_2026,
    FILING_STATUSES,
    HSA_INDIVIDUAL_LIMIT,
    K401_LIMIT,
    STANDARD_DEDUCTION_2026,
    STATE_TAX_DATA,
    calc_salt_cap,
    calc_social_security,
    compute_take_home,
    emergency_fund_months,
    liquid_assets,
    monthly_debt_service,
    project_investment,
    roth_vs_traditional,
    run_monte_carlo,
    simulate_payoff,
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


class RothRequest(BaseModel):
    contribution: float = 0
    current_rate: float = 0.0     # a FRACTION, federal + state combined
    future_rate: float = 0.0      # a FRACTION
    annual_return: float = 7.0
    years: int = 30


class SaltRequest(BaseModel):
    magi: float = 0
    filing: str = "Single"


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
    return {
        "take_home": th,
        "monthly_debt_service": service,
        "debt_service_source": service_source,
        "dti_pct": (service / gross_monthly * 100) if gross_monthly else None,
        "monthly_needs": monthly_needs,
        # None is not 0.0: it means coverage could not be measured, not that it
        # is zero. The client must render the two differently.
        "emergency_fund_months": ef_months,
        "emergency_fund_counted": ef_counted,
        "liquid_assets": liquid_total,
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
    values, contributions = project_investment(
        req.start, req.monthly, req.rate, req.years, req.contribution_growth)
    return {
        "values": values,
        "contributions": contributions,
        "months": len(values) - 1,
        "final_value": values[-1],
        "total_contributed": contributions[-1],
        "growth": values[-1] - contributions[-1],
    }


@app.post("/api/monte-carlo")
def api_monte_carlo(req: MonteCarloRequest) -> Dict[str, Any]:
    return run_monte_carlo(
        req.current_age, req.retire_age, req.end_age, req.portfolio,
        req.annual_savings, req.annual_expenses, req.stock_pct,
        req.inflation, req.n_sims, req.seed)


@app.post("/api/social-security")
def api_social_security(req: SocialSecurityRequest) -> Dict[str, Any]:
    monthly = calc_social_security(req.annual_salary, req.claiming_age)
    return {"monthly": monthly, "annual": monthly * 12}


@app.post("/api/roth-vs-traditional")
def api_roth(req: RothRequest) -> Dict[str, Any]:
    return roth_vs_traditional(req.contribution, req.current_rate,
                               req.future_rate, req.annual_return, req.years)


@app.post("/api/salt-cap")
def api_salt_cap(req: SaltRequest) -> Dict[str, Any]:
    return {"effective_cap": calc_salt_cap(req.magi, req.filing)}
