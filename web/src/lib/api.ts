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

import type { Expense } from "@/context/FinanceContext";
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

/** A verdict the ENGINE reached. `tone` names a meaning, not a colour, and
 *  null means no verdict — never "neutral is fine". */
export type Tone = "positive" | "caution" | "critical" | "info";

/**
 * The dashboard's four verdicts and the month they are measured over.
 *
 * Every band here was a ternary in `page.tsx`, and the savings rate and
 * adherence percentage were computed there too. Worse, both month-dependent
 * cards graded a month that was not over, flatteringly: the ring read 70%
 * green on the 4th with one rent charge logged, and adherence read 15/15 "On
 * track" because a category with nothing against it counts as within budget.
 * The figures are the month SO FAR; a tone of null means the engine declined
 * to grade it and `verdict_withheld` says why.
 */
export interface Health {
  month: string;
  day: number;
  days_in_month: number;
  month_complete: boolean;
  transactions: number;
  spent: number;
  net_savings: number;
  /** null when no salary has been entered. */
  savings_rate: number | null;
  savings_tone: Tone | null;
  savings_status: string | null;
  /** The reason there is no verdict, in words. null means there IS one. */
  verdict_withheld: string | null;
  budgeted_categories: number;
  on_track: number;
  /** Budgeted categories with nothing logged against them. They count as on
   *  track, which is true of the month so far and says nothing about it. */
  unlogged_categories: number;
  adherence_pct: number | null;
  adherence_tone: Tone | null;
  adherence_status: string | null;
  dti_tone: Tone | null;
  dti_status: string;
  emergency_fund_tone: Tone | null;
  emergency_fund_status: string;
}

export interface Dashboard {
  take_home: TakeHome;
  health: Health;
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
  /** null where a delay cannot be modelled — never a zero, which would read
   *  as "waiting costs nothing". */
  cost_of_waiting: {
    delay_years: number;
    start_now: number;
    start_later: number;
    cost: number;
    contributions_missed: number;
    /** The part that is not simply the money you did not put in. */
    growth_missed: number;
  } | null;
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

export interface ScenarioInput {
  name: string;
  income: Income;
  itemized?: Record<string, number>;
  city: string;
}

export interface ScenarioRow {
  name: string;
  city: string;
  /** null where the city is not in the index — never a silent default. */
  col_index: number | null;
  state: string;
  filing: string;
  gross: number;
  total_tax: number;
  effective_rate: number;
  marginal_fed: number;
  marginal_state: number;
  pretax: number;
  annual_take_home: number;
  monthly_take_home: number;
  /** Take-home restated in national-average dollars. The figure that matters. */
  real_take_home: number | null;
  vs_baseline: number;
  vs_baseline_real: number | null;
}

export interface Comparison {
  rows: ScenarioRow[];
  baseline: string | null;
  /** null unless EVERY row could be cost-of-living adjusted. */
  best: string | null;
  /** Which ROW won. Names are typed by the reader and are not unique, so the
   *  paint has to follow the index — a name matched every column carrying it. */
  best_index: number | null;
  /** The winner on RAW take-home, so the page can say whether adjusting moved it. */
  best_take_home: string | null;
  best_take_home_index: number | null;
  /** True only where the adjustment changes the winner, not merely the gap. */
  col_changes_answer: boolean;
  all_comparable: boolean;
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
  ending_histogram: { start: number; end: number; count: number }[];
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

export interface FireCurvePoint {
  savings_rate: number;
  annual_savings: number;
  annual_expenses: number;
  fire_number: number;
  /** null where that savings rate never reaches the target. Not a large number. */
  years: number | null;
}

export interface FireProjection {
  annual_take_home: number;
  monthly_take_home: number;
  /** Budgeted needs and wants — not the savings bucket, and not what was spent. */
  annual_expenses: number;
  annual_savings: number;
  /** null with no income. Clamped at zero; `overspending` carries the rest. */
  savings_rate: number | null;
  overspending: boolean;
  shortfall: number;
  portfolio: number;
  fire_number: number | null;
  still_to_accumulate: number | null;
  progress_pct: number | null;
  /** null where the current rate never gets there. */
  years_at_current: number | null;
  swr: number;
  /** Derived from the Monte Carlo's own means, so one page holds one world. */
  real_return: number;
  stock_pct: number;
  inflation: number;
  curve: FireCurvePoint[];
  /** What one more point of savings rate buys. null where either end is null. */
  next_point: { savings_rate: number; years: number; years_saved: number } | null;
}

export interface YearMonth {
  month: string;
  label: string;
  spent: number;
  budget: number;
  in_progress: boolean;
  /** False means NOTHING WAS LOGGED — not a month in which nothing was spent. */
  has_data: boolean;
}

export interface YearBucket {
  bucket: string;
  budget_monthly: number;
  budget_to_date: number;
  spent: number;
  variance: number;
}

export interface YearCategory {
  category: string;
  bucket: string | null;
  budget_monthly: number;
  budget_to_date: number;
  spent: number;
  variance: number;
  over: boolean;
  pct_of_budget: number | null;
}

export interface YearToDate {
  year: number;
  today: string;
  months_complete: number;
  /** Complete months holding at least one record — the comparable basis. */
  documented_months: number;
  undocumented_months: string[];
  complete_record: boolean;
  transactions: number;
  future_dated: number;
  /** Everything logged this year, the month in progress included. */
  spent: number;
  /** The same, over documented complete months. What the budget is compared to. */
  spent_documented: number;
  current_month: { month: string; label: string; spent: number; has_data: boolean };
  budget_monthly: number;
  budget_year: number;
  budget_documented: number;
  budget_to_date: number;
  /** null where no complete month holds a record — not "exactly on budget". */
  variance: number | null;
  pace: number | null;
  projected_year_end: number | null;
  projected_vs_budget: number | null;
  take_home_monthly: number;
  take_home_documented: number;
  take_home_to_date: number;
  saved: number | null;
  savings_rate: number | null;
  by_month: YearMonth[];
  by_bucket: YearBucket[];
  by_category: YearCategory[];
}

/** Which column holds what. null means "work it out", never "column zero". */
export interface ImportMapping {
  date: number | null;
  amount: number | null;
  debit: number | null;
  credit: number | null;
  description: number | null;
  category: number | null;
}

export interface ImportRow {
  /** 1-based line in the file, as an editor would number it. */
  line: number;
  date: string | null;
  amount: number | null;
  description: string;
  category: string | null;
  /** "merchant" | "category name" | "bank category", or null for no guess. */
  category_source: string | null;
  /** The id of an expense already held that this row matches. */
  duplicate_of: string | null;
  /** Non-null means the row cannot be imported, and says why in words. */
  skip: string | null;
  raw: string[];
}

export interface ImportPreview {
  columns: string[];
  /** What was used — the engine's own reading where none was supplied. */
  has_header: boolean;
  mapping: ImportMapping;
  mapping_suggested: boolean;
  date_order: {
    order: "MDY" | "DMY" | "YMD";
    /** True where the file's own dates do not settle it and a default was used. */
    ambiguous: boolean;
    proved: boolean;
    reason: string;
    day_first_evidence: number;
    month_first_evidence: number;
  };
  sign: {
    convention: string;
    negatives: number;
    positives: number;
    ambiguous: boolean;
    reason: string;
  };
  rows: ImportRow[];
  summary: {
    total: number;
    importable: number;
    duplicates: number;
    skipped: number;
    uncategorised: number;
    amount: number;
  };
}

export interface SocialSecurity {
  monthly: number;
  annual: number;
  /** The benefit as capital — the only form comparable to a FIRE number.
   *  null where the withdrawal rate is not positive. */
  reduces_target_by: number | null;
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
    expenses?: Expense[];
    budget?: Record<string, Record<string, number>>;
    today?: string;
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

  compare: (scenarios: ScenarioInput[]) =>
    request<Comparison>("/compare", { scenarios }),

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

  socialSecurity: (annual_salary: number, claiming_age = 67, swr?: number) =>
    request<SocialSecurity>("/social-security", { annual_salary, claiming_age, swr }),

  rothVsTraditional: (input: {
    contribution: number;
    current_rate: number;
    future_rate: number;
    annual_return: number;
    years: number;
  }) => request<RothComparison>("/roth-vs-traditional", input),

  saltCap: (magi: number, filing: string) =>
    request<{ effective_cap: number }>("/salt-cap", { magi, filing }),

  fire: (input: {
    income: Income;
    itemized?: Record<string, number>;
    budget: Record<string, Record<string, number>>;
    assets: Record<string, number>;
    /** The same two controls the Monte Carlo uses, so both describe one world. */
    stock_pct?: number;
    inflation?: number;
    swr?: number;
  }) => request<FireProjection>("/fire", input),

  yearToDate: (input: {
    income: Income;
    itemized?: Record<string, number>;
    expenses: Expense[];
    budget: Record<string, Record<string, number>>;
    /** The BROWSER's date. The year boundary belongs to the reader, not to
     *  the region the function runs in. */
    today: string;
  }) => request<YearToDate>("/year-to-date", input),

  importPreview: (input: {
    /** The file, split into cells. Splitting is text handling and happens in
     *  the browser; every DECISION about what the cells mean is in Python. */
    grid: string[][];
    /** null asks the engine to decide; a boolean is the reader's own answer. */
    has_header: boolean | null;
    mapping?: ImportMapping | null;
    date_order?: string | null;
    sign?: string | null;
    categories: string[];
    existing: Expense[];
  }) => request<ImportPreview>("/import-preview", input),
};
