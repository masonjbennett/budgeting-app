"use client";

import Link from "next/link";

import AnimatedNumber from "@/components/AnimatedNumber";
import { DonutChart, TrendChart } from "@/components/Chart";
import Footer from "@/components/Footer";
import RingChart from "@/components/RingChart";
import CashFlowPanel from "@/components/CashFlowPanel";
import Sparkline from "@/components/Sparkline";
import StatusCard from "@/components/StatusCard";
import { abbr, fmt, pct, sum, useFinance } from "@/context/FinanceContext";
import { cssVar, SERIES } from "@/lib/tokens";

function Skeleton() {
  return (
    <div className="space-y-8">
      <div className="skeleton h-[9.5rem] w-full" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton h-24" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton h-36" />
        ))}
      </div>
    </div>
  );
}

/** A supporting figure. Demoted on purpose — one hero per screen. */
function Metric({
  label,
  value,
  exact,
  note,
  tone = "default",
  spark,
}: {
  label: string;
  value: string;
  /** The unabbreviated figure, where `value` is short. */
  exact?: string;
  note?: React.ReactNode;
  tone?: "default" | "positive" | "critical";
  spark?: number[];
}) {
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "critical" ? "text-critical" : "text-ink";
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-2">
        <p className="label">{label}</p>
        {/* Deliberately NOT `tone="trend"`. A trend-coloured sparkline reads
            down as bad, and on the one metric that has a history — what you
            spent — down is good. It painted a falling month in claret, which
            is the alarm colour, next to a teal "−$38" saying the opposite. The
            shape is information; the verdict belongs to the note underneath,
            which knows what the number means. */}
        {spark && spark.length > 1 && (
          <Sparkline data={spark} tone="faint" className="mt-0.5 shrink-0" />
        )}
      </div>
      <p className={`font-num t-h3 mt-1.5 leading-none font-medium ${toneClass}`} title={exact}>
        {value}
      </p>
      {note && <p className="t-micro mt-2 text-muted">{note}</p>}
    </div>
  );
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function Dashboard() {
  const { profile, dashboard, status, error, showingUntouchedDemo,
          dismissDemoNote, resetToEmpty } = useFinance();

  if (status === "error") {
    return (
      <div className="card mark-critical">
        <h2 className="t-lead">Something went wrong</h2>
        <p className="t-small mt-1 text-body">{error}</p>
      </div>
    );
  }
  if (!profile || !dashboard) return <Skeleton />;

  const th = dashboard.take_home;
  const monthly = th.monthly_take_home;
  /* The month's figures and all four verdicts, from the engine.

     This comment used to say "every RULE — thresholds, denominators,
     classifications — is in Python" and the twenty lines under it computed a
     savings rate, an adherence percentage and four sets of bands. Worse, both
     month-dependent cards graded a month that was not over: the ring read 70%
     GREEN on the 4th with one rent charge logged, and adherence read 15/15 "On
     track" because a category with nothing against it counts as within budget.
     `health_report` reports the month so far and withholds the verdict until
     the month is complete. The comment is true now. */
  const h = dashboard.health;

  // Adding up what the user typed, which is the one thing this layer may do.
  const now = new Date();
  const curKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const monthExpenses = profile.expenses.filter((e) => e.date.startsWith(curKey));
  const spent = h.spent;
  const netSavings = h.net_savings;
  const savingsRate = h.savings_rate;

  const totalAssets = sum(profile.assets);
  const totalLiabilities = sum(profile.liabilities);
  const netWorth = totalAssets - totalLiabilities;

  const byCategory: Record<string, number> = {};
  for (const e of monthExpenses) byCategory[e.category] = (byCategory[e.category] ?? 0) + e.amount;
  const categories = Object.entries(byCategory).sort((a, b) => b[1] - a[1]);

  // Month-over-month, from the expenses actually recorded. Where there is no
  // previous month there is no comparison — the scaffold printed a hardcoded
  // "+$1,700 from last month" here, beside a real balance.
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  const prevKey = `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}`;
  const prevExpenses = profile.expenses.filter((e) => e.date.startsWith(prevKey));
  const prevSpent = prevExpenses.reduce((s, e) => s + e.amount, 0);
  const spendDelta = prevExpenses.length ? spent - prevSpent : null;

  // The spending sparkline is the months actually recorded, in order, and is
  // drawn only where there are at least two of them. The scaffold drew this
  // from a hardcoded array with the real total appended to the end of it.
  const byMonth: Record<string, number> = {};
  for (const e of profile.expenses) {
    const k = e.date.slice(0, 7);
    byMonth[k] = (byMonth[k] ?? 0) + e.amount;
  }
  const monthTotals = Object.keys(byMonth)
    .sort()
    .slice(-6)
    .map((k) => byMonth[k]);

  // Net-worth trend comes only from snapshots the user has actually logged.
  const snapshots = [...profile.net_worth_snapshots].sort((a, b) =>
    a.date.localeCompare(b.date),
  );
  const snapshotTrend = snapshots.slice(-6).map((s) => s.net_worth);

  const budgetTotal =
    sum(profile.budget.needs) + sum(profile.budget.wants) + sum(profile.budget.savings);
  const allCats = { ...profile.budget.needs, ...profile.budget.wants, ...profile.budget.savings };
  const budgeted = Object.entries(allCats).filter(([, v]) => v > 0);

  const ef = dashboard.emergency_fund_months;
  const dti = dashboard.dti_pct;

  return (
    <div>
      {/* ── Whose figures are these? ───────────────────────────────────
             The app ships a populated demo so that a first visit shows the
             Sankey, the fan chart, the year view and a debt comparison
             working rather than a shell of empty states — and the demo is
             load-bearing for one of them, since it carries three debts whose
             rate order and balance order conflict, which is the only reason
             avalanche and snowball differ at all.

             What it did NOT do was say so anywhere, so the figures read as
             somebody's real money, or as noise. This says it once, on the
             landing page, and retires itself on the first edit — the flag is
             set when the SERVED profile loads and cleared by `update`, rather
             than guessing by comparing values, which would be wrong the
             moment somebody edited a number back to what it was.

             Not a modal, and not on all thirteen pages: it is one line where
             the visit starts, and it can be dismissed. ────────────────── */}
      {showingUntouchedDemo && (
        <div className="card mark-accent animate-fade-in mb-8">
          <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
            <p className="t-small text-body">
              These are <span className="text-ink">example figures</span>, so every
              chart has something to show. Edit anything and they become yours.
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <button
                onClick={() => void resetToEmpty()}
                className="btn-secondary text-[12px]"
              >
                Start empty
              </button>
              <button onClick={dismissDemoNote} className="btn-ghost text-[12px]">
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── The hero. One figure at display size; everything else is demoted
             to it, because a 4-up grid of identically weighted numbers gives
             the eye nowhere to land. ─────────────────────────────────── */}
      <header className="animate-fade-in mb-10 border-b border-hair pb-7">
        {/* Every other page gets its <h1> from PageHeader. This one leads with
            the figure instead of a title, so the heading is present for the
            document outline and for a screen reader without adding a line of
            furniture above the hero. */}
        <h1 className="sr-only">Dashboard</h1>
        {/* items-end, not items-baseline: the right-hand block's first child is
            an <svg>, which contributes no baseline, so a baseline-aligned row
            hoists the whole block to the top of the header — the date ended up
            above the label it was meant to sit beside. */}
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div>
            <p className="label">Net worth</p>
            <p className="mt-1.5">
              <AnimatedNumber
                value={netWorth}
                className="figure-hero"
                title={fmt(netWorth)}
              />
            </p>
            <p className="t-small mt-2 text-muted">
              <span className="font-num text-body">{fmt(totalAssets)}</span> of assets less{" "}
              <span className="font-num text-body">{fmt(totalLiabilities)}</span> of
              liabilities
              {snapshotTrend.length > 1 && (
                <>
                  {" · "}
                  <Link href="/net-worth" className="text-accent hover:underline">
                    {snapshots.length} snapshots
                  </Link>
                </>
              )}
            </p>
          </div>
          <div className="flex items-end gap-5">
            {snapshotTrend.length > 1 && (
              <Sparkline data={snapshotTrend} width={104} height={34} tone="accent" />
            )}
            <p className="t-micro text-right text-muted">
              {MONTH_NAMES[now.getMonth()]} {now.getFullYear()}
              <br />
              Calculated server-side
            </p>
          </div>
        </div>
      </header>

      {/* ── This month ─────────────────────────────────────────────── */}
      <p className="label mb-3">This month</p>
      <div className="stagger mb-11 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Take-home"
          value={fmt(monthly)}
          note={
            <>
              {abbr(th.annual_take_home)}/yr · {pct(th.effective_rate)} effective tax
            </>
          }
        />
        <Metric
          label={`Spent in ${MONTH_NAMES[now.getMonth()]}`}
          value={fmt(spent)}
          spark={monthTotals}
          note={
            spendDelta === null ? (
              <>
                {monthExpenses.length} transaction{monthExpenses.length === 1 ? "" : "s"} · no
                prior month to compare
              </>
            ) : (
              <>
                {monthExpenses.length} transaction{monthExpenses.length === 1 ? "" : "s"} ·{" "}
                <span className={spendDelta > 0 ? "text-critical" : "text-positive"}>
                  {spendDelta > 0 ? "+" : "−"}
                  {fmt(Math.abs(spendDelta))}
                </span>{" "}
                vs {MONTH_NAMES[prev.getMonth()]}
              </>
            )
          }
        />
        <Metric
          label="Net savings"
          value={fmt(netSavings)}
          tone={netSavings >= 0 ? "positive" : "critical"}
          note={savingsRate === null ? "no income entered" : `${pct(savingsRate, 0)} of take-home`}
        />
        <Metric
          label="Budgeted"
          value={fmt(budgetTotal)}
          note={
            budgeted.length === 0 ? (
              <Link href="/budget" className="text-accent hover:underline">
                Set some category amounts →
              </Link>
            ) : (
              <>
                across {budgeted.length} categor{budgeted.length === 1 ? "y" : "ies"} ·{" "}
                {fmt(monthly - budgetTotal)} unallocated
              </>
            )
          }
        />
      </div>

      {/* ── Health ─────────────────────────────────────────────────── */}
      <p className="label mb-3">Financial health</p>
      <div className="mb-11 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="card flex flex-col items-center justify-center py-5">
          {savingsRate === null ? (
            <p className="t-small text-muted">No income entered</p>
          ) : (
            <RingChart
              value={Math.max(0, Math.min(savingsRate, 100))}
              size={102}
              strokeWidth={5}
              /* The engine's verdict, or its refusal to give one. A ring
                 painted "info" is not a grade — it is the figure with no
                 grade attached, which is the honest answer to a month that is
                 four days old. */
              tone={h.savings_tone ?? "info"}
              label={`${savingsRate.toFixed(0)}%`}
              sublabel={
                h.verdict_withheld
                  ? `Saved so far · ${h.verdict_withheld}`
                  : `Saved in ${MONTH_NAMES[now.getMonth()]}`
              }
            />
          )}
        </div>

        {dti === null ? (
          <StatusCard
            label="Debt-to-income"
            value="—"
            status="Needs income"
            tone="info"
            description="Enter your salary on Income Setup to measure this."
          />
        ) : (
          <StatusCard
            label="Debt-to-income"
            value={pct(dti)}
            status={h.dti_status}
            tone={h.dti_tone ?? "info"}
            description={`${fmt(dashboard.monthly_debt_service)}/mo of ${
              dashboard.debt_service_source === "debts"
                ? "minimums on the debts you entered"
                : 'your "Min. Debt Payments" budget line'
            }, against gross income.`}
          />
        )}

        {ef === null ? (
          <StatusCard
            label="Emergency fund"
            value="—"
            status="Not measurable"
            tone="info"
            description={
              dashboard.monthly_needs === 0
                ? "Budget some essential spending under Needs first."
                : "No liquid assets recognised — add a checking or savings row on Net Worth."
            }
          />
        ) : (
          <StatusCard
            label="Emergency fund"
            value={`${ef.toFixed(1)} mo`}
            status={h.emergency_fund_status}
            tone={h.emergency_fund_tone ?? "info"}
            description={`${fmt(dashboard.liquid_assets)} counted from ${dashboard.emergency_fund_counted.join(
              ", ",
            )}, against ${fmt(dashboard.monthly_needs)}/mo of needs.`}
          />
        )}

        {h.budgeted_categories === 0 ? (
          <StatusCard
            label="Budget adherence"
            value="—"
            status="No budget set"
            tone="info"
            description="Set some category amounts on Budget Builder."
          />
        ) : (
          <StatusCard
            label="Budget adherence"
            value={
              h.verdict_withheld
                ? `${h.on_track}/${h.budgeted_categories} so far`
                : `${h.on_track}/${h.budgeted_categories}`
            }
            status={h.adherence_status ?? "Partial month"}
            tone={h.adherence_tone ?? "info"}
            /* A category with nothing logged against it counts as within
               budget, which is true of the month so far and says nothing
               about the month. Naming them is what stops the score reading
               as a result — measured, a profile with one expense in it
               scored 15/15 "On track". */
            description={
              `Categories within budget${h.verdict_withheld ? " so far" : " this month"}. ` +
              (h.unlogged_categories > 0
                ? `${h.unlogged_categories} of them ` +
                  `${h.verdict_withheld ? "have nothing logged yet" : "had nothing logged against them"}. `
                : "") +
              `Total budgeted ${fmt(budgetTotal)}/mo.`
            }
          />
        )}
      </div>

      {/* ── Spending ───────────────────────────────────────────────── */}
      <p className="label mb-3">Spending · {MONTH_NAMES[now.getMonth()]}</p>
      {categories.length === 0 ? (
        <div className="card mb-11 py-9 text-center">
          <p className="t-small text-muted">Nothing logged this month yet.</p>
          <Link href="/expenses" className="t-small mt-1.5 inline-block text-accent hover:underline">
            Add an expense →
          </Link>
        </div>
      ) : (
        <div className="mb-11 grid grid-cols-1 gap-3 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <DonutChart
              data={categories.map(([name, value]) => ({ name, value }))}
              height={280}
            />
          </div>
          <div className="card card-flush overflow-hidden lg:col-span-3">
            <div className="divide-y divide-hair-soft">
              {categories.map(([cat, amount], i) => {
                const budget = allCats[cat];
                // Spend against budget, as a filled rule. Where there is no
                // budget for the category there is no bar — an empty track
                // would read as "nothing spent".
                const used = budget > 0 ? (amount / budget) * 100 : null;
                const over = budget > 0 && amount > budget;
                return (
                  <div key={cat} className="px-4 py-2.5 transition-colors hover:bg-raise">
                    <div className="flex items-center gap-2.5">
                      <span
                        className="h-2 w-[3px] shrink-0"
                        style={{ background: cssVar(SERIES[i % SERIES.length]) }}
                        aria-hidden="true"
                      />
                      <span className="t-small flex-1 truncate text-body">{cat}</span>
                      {budget > 0 && (
                        <span
                          className={`font-num t-micro ${over ? "text-critical" : "text-muted"}`}
                        >
                          {Math.round(used!)}% of {fmt(budget)}
                        </span>
                      )}
                      <span className="font-num t-small w-20 text-right text-ink">
                        {fmt(amount, 2)}
                      </span>
                    </div>
                    {used !== null && (
                      <div className="progress-track mt-1.5 ml-[13px]">
                        <div
                          className={`progress-fill ${over ? "bg-critical" : "bg-accent"}`}
                          style={{ width: `${Math.min(used, 100)}%` }}
                        />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* ── Cash flow ──────────────────────────────────────────────────
             The Sankey replaces a three-bar chart of take-home / spent / net.
             It is the same money and a great deal more of the story: the bars
             said nothing about the ~32% of gross pay that never reaches the
             account, which is the part this app can describe better than any
             competitor because it has a real tax engine behind it. ───────── */}
      <p className="label mb-3">Where the money goes · monthly</p>
      <div className="mb-11">
        <CashFlowPanel />
      </div>

      {/* ── Net worth trend — only from real snapshots ─────────────── */}
      <p className="label mb-3">Net worth over time</p>
      {snapshots.length < 2 ? (
        <div className="card mb-11 py-9 text-center">
          <p className="t-small text-muted">
            {snapshots.length === 0
              ? "No snapshots logged yet."
              : "One snapshot logged — two are needed to draw a trend."}
          </p>
          <Link href="/net-worth" className="t-small mt-1.5 inline-block text-accent hover:underline">
            Log a snapshot →
          </Link>
        </div>
      ) : (
        <div className="mb-11">
          <TrendChart
            data={snapshots.map((s) => ({
              date: s.date,
              "Net worth": s.net_worth,
              Assets: s.assets,
            }))}
            xKey="date"
            series={[
              { key: "Net worth", name: "Net worth", tone: "accent" },
              { key: "Assets", name: "Assets", tone: "s2", area: false },
            ]}
            height={300}
          />
        </div>
      )}

      <Footer />
    </div>
  );
}
