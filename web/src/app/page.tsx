"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";

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

/**
 * A figure with the subtraction that produced it, over a rule.
 *
 * Every number here is one the engine already returned; the component adds a
 * relationship, not a calculation. The total is NOT summed from the rows —
 * it is passed in — because a client-side sum that happened to disagree with
 * the engine would be a second implementation of the thing this app spent a
 * whole rebuild removing. `check` asserts they agree instead.
 */
function LedgerCard({
  label,
  period,
  rows,
  total,
  totalLabel,
  tone = "default",
  note,
}: {
  label: string;
  period?: string;
  rows: { label: string; value: string }[];
  total: string;
  totalLabel: string;
  tone?: "default" | "positive" | "critical";
  note?: React.ReactNode;
}) {
  const toneClass =
    tone === "positive" ? "text-positive" : tone === "critical" ? "text-critical" : "text-ink";
  return (
    <div className="card flex flex-col">
      <p className="label">{label}</p>
      {period && <p className="t-micro mt-1 text-muted">{period}</p>}
      <div className="mt-2.5 space-y-1">
        {rows.map((r) => (
          <div key={r.label} className="flex items-baseline justify-between gap-3">
            <span className="t-micro text-muted">{r.label}</span>
            <span className="font-num t-small whitespace-nowrap text-body">{r.value}</span>
          </div>
        ))}
      </div>
      {/* The rule is the point: it says these figures are being added up, which
          is what a row of separate cards cannot say. */}
      <div className="mt-1.5 border-t border-hair pt-1.5">
        <div className="flex items-baseline justify-between gap-3">
          <span className="t-micro text-muted">{totalLabel}</span>
          <span className={`font-num t-lead whitespace-nowrap font-medium ${toneClass}`}>
            {total}
          </span>
        </div>
      </div>
      {note && <p className="t-micro mt-2 text-muted">{note}</p>}
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
  period,
}: {
  label: string;
  value: string;
  /** The unabbreviated figure, where `value` is short. */
  exact?: string;
  note?: React.ReactNode;
  tone?: "default" | "positive" | "critical";
  spark?: number[];
  /** THE SPAN THIS FIGURE COVERS. Four cards sat in one row at one type size
   *  under a single "This month" header while covering three different
   *  things: take-home is a monthly RATE, spent is however many days of
   *  records exist so far, and budgeted is a plan for a month that has not
   *  happened. Naming each is Actual Budget's pattern — every widget on their
   *  reports dashboard carries its range as a subtitle. */
  period?: string;
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
      {period && <p className="t-micro mt-1 text-muted">{period}</p>}
      <p className={`font-num t-h3 mt-1.5 leading-none font-medium ${toneClass}`} title={exact}>
        {value}
      </p>
      {note && <p className="t-micro mt-2 text-muted">{note}</p>}
    </div>
  );
}

/**
 * The months this profile can be shown, as a row.
 *
 * Actual Budget's pattern. Ours was pinned to `new Date()`, so there was no way
 * to look at August — which matters here more than it does for them, because
 * the verdict this dashboard withholds for a month in progress is exactly the
 * one a COMPLETE month can carry. Pinned to today, that grade would appear on
 * the last day of a month and never again.
 *
 * The engine decides which months exist. The row renders them and nothing else;
 * a month with no records in it is offered deliberately and answers for itself.
 */
function MonthStrip({
  months,
  current,
  selected,
  onSelect,
}: {
  months: string[];
  /** The reader's own month — the one "Today" returns to. */
  current: string;
  selected: string;
  onSelect: (m: string | null) => void;
}) {
  const row = useRef<HTMLDivElement | null>(null);

  /* Put the selection on screen. The row scrolls rather than wraps — two years
     of months wrapped over three lines reads as a paragraph — and the first
     version used `justify-end` to keep the newest in view, which is a trap:
     content overflowing a flex container justified to the end overflows at the
     START, where Chrome will not scroll to it. Scrolling the selection into
     view keeps the newest visible at rest AND makes a chosen past month
     reachable when the strip is long. */
  useEffect(() => {
    const el = row.current;
    const sel = el?.querySelector<HTMLElement>('[aria-current="true"]');
    if (!el || !sel) return;
    // scrollLeft, not scrollIntoView: the latter scrolls the PAGE as well and
    // would jump the reader away from the figures they just changed.
    el.scrollLeft = Math.max(0, sel.offsetLeft - (el.clientWidth - sel.clientWidth) / 2);
  }, [selected, months.length]);

  if (months.length < 2) return null;
  return (
    <div className="mb-8 flex items-center gap-3 border-b border-hair pb-2">
      <div ref={row} className="flex flex-1 gap-0.5 overflow-x-auto">
        {months.map((m) => {
          const [y, mm] = [m.slice(0, 4), Number(m.slice(5, 7))];
          const isSel = m === selected;
          return (
            <button
              key={m}
              onClick={() => onSelect(m === current ? null : m)}
              aria-current={isSel ? "true" : undefined}
              // The visible gap before the year is a margin, so the text reads
              // "Aug’26" to anything that listens rather than looks.
              aria-label={`${MONTH_NAMES[mm - 1]} ${y}`}
              title={`${MONTH_NAMES[mm - 1]} ${y}`}
              className={`t-micro shrink-0 border-b-2 px-2.5 py-1.5 font-mono tracking-wider uppercase transition-colors ${
                isSel
                  ? "border-accent text-ink"
                  : "border-transparent text-muted hover:text-body"
              }`}
            >
              {MONTH_NAMES[mm - 1]}
              {/* Where the strip starts, and wherever it turns over. With an
                  apostrophe, because "AUG 26" reads as the 26th of August —
                  a year that looks like a day is worse than no year at all. */}
              {mm === 1 || m === months[0] ? (
                <span className="ml-1 text-muted">{YEAR_MARK + y.slice(2)}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {selected !== current && (
        <button onClick={() => onSelect(null)} className="btn-ghost t-micro shrink-0">
          Today
        </button>
      )}
    </div>
  );
}

/** U+2019, so the year reads as a year: AUG ’26. */
const YEAR_MARK = "’";

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function Dashboard() {
  const { profile, dashboard, status, error, showingUntouchedDemo,
          dismissDemoNote, resetToEmpty, setMonth } = useFinance();

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

  /* THE MONTH ON SCREEN, not the clock. Everything below followed
     `new Date()`, so the donut, the transaction count and the month-over-month
     comparison would all have gone on describing September while the cards
     above them described August. */
  const curKey = h.month;
  const monthIndex = Number(curKey.slice(5, 7)) - 1;
  const now = new Date();
  const thisMonthKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;

  /* How much of the month the records cover, in words. The engine supplies the
     FACTS — which day of how many, and whether the month is over; turning them
     into a caption is formatting, the same class as `fmt` and `pct`. A
     complete month is named rather than spanned, because "Sep 1-30" invites
     the reader to check the arithmetic on a range that is just "September". */
  const monthName = MONTH_NAMES[monthIndex];
  const soFar = h.month_complete ? monthName : `${monthName} 1\u2013${h.day}`;

  // Adding up what the user typed, which is the one thing this layer may do.
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
  const prev = new Date(Number(curKey.slice(0, 4)), monthIndex - 1, 1);
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
            <p className="label">Net worth · as of today</p>
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
              {MONTH_NAMES[monthIndex]} {curKey.slice(0, 4)}
              <br />
              Calculated server-side
            </p>
          </div>
        </div>
      </header>

      <MonthStrip
        months={h.months_available}
        current={thisMonthKey}
        selected={curKey}
        onSelect={setMonth}
      />

      {/* ── The month on screen ────────────────────────────────────── */}
      <p className="label mb-3">
        {curKey === thisMonthKey ? "This month" : `${monthName} ${curKey.slice(0, 4)}`}
      </p>
      <div className="stagger mb-11 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Take-home"
          period="a month, after tax"
          value={fmt(monthly)}
          note={
            <>
              {abbr(th.annual_take_home)}/yr · {pct(th.effective_rate)} effective tax
            </>
          }
        />
        <Metric
          // The period line carries the month, so the label need not: "Spent in
          // Sep" above "Sep 1-4" says it twice and reads as a stutter.
          label="Spent"
          period={soFar}
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
        {/* The one figure on this row that is a RESULT rather than a reading,
            so it shows its working. The other three are read straight off the
            profile or the pay calculation. */}
        <LedgerCard
          label="Net savings"
          period={soFar}
          rows={[
            { label: "Take-home", value: fmt(monthly) },
            { label: "less spent", value: `\u2212${fmt(spent)}` },
          ]}
          total={fmt(netSavings)}
          totalLabel="left over"
          tone={netSavings >= 0 ? "positive" : "critical"}
          note={savingsRate === null ? "no income entered" : `${pct(savingsRate, 0)} of take-home`}
        />
        <Metric
          label="Budgeted"
          period="a month, planned"
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
                  : `Saved in ${MONTH_NAMES[monthIndex]}`
              }
            />
          )}
        </div>

        {dti === null ? (
          <StatusCard
            label="Debt-to-income"
            period="as of today"
            value="—"
            status="Needs income"
            tone="info"
            description="Enter your salary on Income Setup to measure this."
          />
        ) : (
          <StatusCard
            label="Debt-to-income"
            period="as of today"
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
            period="as of today"
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
            period="as of today"
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
            period={soFar}
            value="—"
            status="No budget set"
            tone="info"
            description="Set some category amounts on Budget Builder."
          />
        ) : (
          <StatusCard
            label="Budget adherence"
            period={soFar}
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
      <p className="label mb-3">Spending · {soFar}</p>
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
