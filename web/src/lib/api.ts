/**
 * The calculation API.
 *
 * Every number this app displays comes from here, and the routes are thin
 * wrappers over calculations.py at the repo root. That indirection is the whole
 * design: the maths had drifted into three implementations that disagreed, and
 * one of them was a Next.js frontend exactly like this one, doing its own
 * arithmetic in TypeScript. So there is deliberately NO tax, debt, projection
 * or ratio maths in this codebase — if a number needs working out, it needs a
 * route, not a helper.
 *
 * Same-origin: the Python function is served from /api by this same deployment,
 * so there is no base URL to configure and no CORS.
 */

import type { Token } from "@/lib/tokens";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // A dead network and a 500 are different problems and the UI says so —
    // telling someone their figures are wrong when the connection dropped is
    // the same class of mistake as telling them their password was wrong when
    // the auth service had been deleted.
    throw new ApiError("Could not reach the calculation service.", 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      if (typeof j?.detail === "string") detail = j.detail;
    } catch {
      /* a non-JSON error body is still an error */
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status);
  }
  return res.json() as Promise<T>;
}

// ── Shapes returned by the engine ────────────────────────────────────

export interface TakeHome {
  annual_gross: number;
  contrib_401k: number;
  health: number;
  hsa: number;
  pretax: number;
  fed_tax: number;
  state_tax: number;
  fica: number;
  total_tax: number;
  annual_take_home: number;
  monthly_take_home: number;
  agi: number;
  taxable: number;
  std_ded: number;
  /** The deduction ACTUALLY taken — the itemized total when that is larger. */
  deduction_taken: number;
  itemized_total: number;
  itemizing: boolean;
  effective_rate: number;
  marginal_fed: number;
  /** The user's own state rate, not the state's top bracket. */
  marginal_state: number;
  filing: string;
}

export interface Dashboard {
  take_home: TakeHome;
  monthly_debt_service: number;
  /** "debts" when read from entered debts, "budget" when from the category. */
  debt_service_source: string;
  /** null when income is zero — not 0, which would read as "no debt". */
  dti_pct: number | null;
  monthly_needs: number;
  /** The OBBBA 2/37 limitation the engine does NOT model, disclosed. */
  top_bracket: { applies: boolean; threshold: number; filing: string };
  /** null means COULD NOT BE MEASURED. It is not the same as 0.0. */
  emergency_fund_months: number | null;
  emergency_fund_counted: string[];
  liquid_assets: number;
}

export interface PayoffResult {
  months: number;
  never_pays_off: boolean;
  total_interest: number;
  schedule: { month: number; total_balance: number; interest: number }[];
  payoff_months: Record<string, number>;
}

export interface CashFlow {
  /** `tone` is a palette token name. The engine emits these as strings, so
   *  test_api.py checks every one it can produce against the map in
   *  tokens.ts — TypeScript cannot see across the HTTP boundary. */
  nodes: { id: string; label: string; column: number; value: number; tone: Token }[];
  links: { source: string; target: string; value: number }[];
  gross: number;
  take_home: number;
  allocated: number;
  unallocated: number;
  /** Positive only when the plan allocates more than take-home covers. */
  deficit: number;
  /** Figures that are genuinely zero this month, named rather than drawn. */
  omitted: string[];
  residual: number;
  /** False means the stages do not sum — the diagram must not be drawn. */
  balanced: boolean;
}

export interface EmployerMatch {
  annual_match: number;
  monthly_match: number;
  annual_missed: number;
  contribution_pct: number;
  match_limit: number;
  match_pct: number;
  /** True only when raising the contribution would collect more match. */
  leaving_money: boolean;
}

export interface Investment {
  values: number[];
  contributions: number[];
  months: number;
  final_value: number;
  total_contributed: number;
  growth: number;
  employer_match: EmployerMatch;
}

export interface RaiseImpact {
  base_salary: number;
  new_salary: number;
  increase: number;
  gross_increase: number;
  tax_increase: number;
  /** Not a loss — a percentage-based 401(k) rises with the salary. */
  pretax_increase: number;
  take_home_increase: number;
  monthly_take_home_increase: number;
  marginal_fed: number;
  marginal_state: number;
  /** From marginal_fica_rate, not the average — above the wage base they differ by 5x. */
  marginal_fica_pct: number;
  tax_share_pct: number | null;
  kept_share_pct: number | null;
}

export interface ColComparison {
  from_city: string;
  to_city: string;
  from_index: number;
  to_index: number;
  salary: number;
  equivalent_salary: number;
  difference: number;
  pct_difference: number;
}

export interface MonteCarlo {
  ages: number[];
  n_sims: number;
  success_count: number;
  success_rate: number;
  percentiles: Record<"p5" | "p10" | "p25" | "p50" | "p75" | "p90" | "p95", number[]>;
  ending: number[];
  sample_paths: number[][];
  failure_ages: number[];
  median_ending: number;
  p10_ending: number;
  p90_ending: number;
  retire_age: number;
  stock_pct: number;
}

export interface RothComparison {
  contribution: number;
  traditional_future: number;
  traditional_after_tax: number;
  roth_invested: number;
  roth_future: number;
  /** "Equivalent" when the two rates are equal — the maths says so exactly. */
  better: "Traditional" | "Roth" | "Equivalent";
  difference: number;
  current_rate: number;
  future_rate: number;
}

export interface Reference {
  /** A null ceiling means "and everything above" — inf is not JSON. */
  federal_brackets: Record<string, [number | null, number][]>;
  standard_deductions: Record<string, number>;
  filing_statuses: string[];
  states: string[];
  col_index: Record<string, number>;
  k401_limit: number;
  hsa_individual_limit: number;
}

export interface Income {
  gross_salary: number;
  state: string;
  filing_status: string;
  contribution_401k: number;
  health_insurance: number;
  hsa: number;
  bonus_amount: number;
  bonus_type: string;
  student_loan_interest: number;
}

export interface Debt {
  name: string;
  balance: number;
  rate: number;
  min_payment: number;
}

// ── Routes ───────────────────────────────────────────────────────────

export const api = {
  reference: () => request<Reference>("/reference"),

  takeHome: (income: Income, itemized: Record<string, number> = {}) =>
    request<TakeHome>("/take-home", { income, itemized }),

  dashboard: (input: {
    income: Income;
    itemized?: Record<string, number>;
    debts: Debt[];
    budget_needs: Record<string, number>;
    assets: Record<string, number>;
  }) => request<Dashboard>("/dashboard", input),

  cashFlow: (input: {
    income: Income;
    itemized?: Record<string, number>;
    budget: Record<string, Record<string, number>>;
  }) => request<CashFlow>("/cash-flow", input),

  debtPayoff: (debts: Debt[], extra: number) =>
    request<{ avalanche: PayoffResult; snowball: PayoffResult }>("/debt-payoff", {
      debts,
      extra,
    }),

  investment: (input: {
    start: number;
    monthly: number;
    rate: number;
    years: number;
    contribution_growth?: number;
    /** With a salary, the employer's match is projected too. */
    salary?: number;
    contribution_pct?: number;
    match_pct?: number;
    match_limit?: number;
  }) => request<Investment>("/investment", input),

  raiseImpact: (input: {
    income: Income;
    itemized?: Record<string, number>;
    increase: number;
  }) => request<RaiseImpact>("/raise", input),

  costOfLiving: (input: { salary: number; from_city: string; to_city: string }) =>
    request<{ comparison: ColComparison | null }>("/cost-of-living", input),

  monteCarlo: (input: {
    current_age: number;
    retire_age: number;
    end_age: number;
    portfolio: number;
    annual_savings: number;
    annual_expenses: number;
    stock_pct: number;
    inflation: number;
    n_sims: number;
  }) => request<MonteCarlo>("/monte-carlo", input),

  socialSecurity: (annual_salary: number, claiming_age = 67) =>
    request<{ monthly: number; annual: number }>("/social-security", {
      annual_salary,
      claiming_age,
    }),

  rothVsTraditional: (input: {
    contribution: number;
    current_rate: number;
    future_rate: number;
    annual_return: number;
    years: number;
  }) => request<RothComparison>("/roth-vs-traditional", input),

  saltCap: (magi: number, filing: string) =>
    request<{ effective_cap: number }>("/salt-cap", { magi, filing }),
};
