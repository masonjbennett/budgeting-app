"use client";

import Link from "next/link";

import { BarsChart, DonutChart, TrendChart } from "@/components/Chart";
import Footer from "@/components/Footer";
import RingChart from "@/components/RingChart";
import StatusCard from "@/components/StatusCard";
import { fmt, pct, sum, useFinance } from "@/context/FinanceContext";

function Skeleton() {
  return (
    <div className="space-y-8">
      <div>
        <div className="skeleton mb-2 h-7 w-52" />
        <div className="skeleton h-4 w-80" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="skeleton h-28 rounded-xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton h-40 rounded-xl" />
        ))}
      </div>
    </div>
  );
}

/** A metric with no invented history behind it. */
function Metric({
  label,
  value,
  note,
  tone = "default",
}: {
  label: string;
  value: string;
  note?: React.ReactNode;
  tone?: "default" | "green" | "red";
}) {
  const toneClass =
    tone === "green" ? "text-green" : tone === "red" ? "text-red" : "text-primary";
  return (
    <div className="card">
      <p className="text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-muted">
        {label}
      </p>
      <p className={`mt-1 font-num text-[1.9rem] font-bold leading-none tracking-tight ${toneClass}`}>
        {value}
      </p>
      {note && <p className="mt-1.5 text-[0.6875rem] leading-snug text-muted">{note}</p>}
    </div>
  );
}

const MONTH_NAMES = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

export default function Dashboard() {
  const { profile, dashboard, status, error } = useFinance();

  if (status === "error") {
    return (
      <div className="card border-red/20 bg-red/[0.03]">
        <h1 className="text-[1.1rem] font-semibold text-primary">Something went wrong</h1>
        <p className="mt-1 text-[0.85rem] text-dim">{error}</p>
      </div>
    );
  }
  if (!profile || !dashboard) return <Skeleton />;

  const th = dashboard.take_home;
  const monthly = th.monthly_take_home;

  // Adding up what the user typed. Every RULE — thresholds, denominators,
  // classifications — is in Python; nothing below decides anything.
  const now = new Date();
  const curKey = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const monthExpenses = profile.expenses.filter((e) => e.date.startsWith(curKey));
  const spent = monthExpenses.reduce((s, e) => s + e.amount, 0);
  const netSavings = monthly - spent;
  const savingsRate = monthly > 0 ? (netSavings / monthly) * 100 : null;

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

  // Net-worth trend comes only from snapshots the user has actually logged.
  const snapshots = [...profile.net_worth_snapshots].sort((a, b) =>
    a.date.localeCompare(b.date),
  );

  const budgetTotal =
    sum(profile.budget.needs) + sum(profile.budget.wants) + sum(profile.budget.savings);
  const allCats = { ...profile.budget.needs, ...profile.budget.wants, ...profile.budget.savings };
  const budgeted = Object.entries(allCats).filter(([, v]) => v > 0);
  const onTrack = budgeted.filter(([c, v]) => (byCategory[c] ?? 0) <= v).length;
  const adherence = budgeted.length ? Math.round((onTrack / budgeted.length) * 100) : null;

  const ef = dashboard.emergency_fund_months;
  const dti = dashboard.dti_pct;

  return (
    <div>
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-[1.5rem] font-semibold tracking-tight text-primary">Dashboard</h1>
          <p className="mt-0.5 text-[0.8125rem] text-muted">
            {MONTH_NAMES[now.getMonth()]} {now.getFullYear()} · every figure here is
            calculated server-side from your inputs.
          </p>
        </div>
        <kbd className="hidden rounded border border-white/[0.06] bg-surface px-2 py-1 text-[0.625rem] text-muted sm:block">
          ⌘K
        </kbd>
      </div>

      {/* Headline figures */}
      <div className="stagger mb-12 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Take-home"
          value={fmt(monthly)}
          note={
            <>
              {fmt(th.annual_take_home)}/yr · {pct(th.effective_rate)} effective tax
            </>
          }
        />
        <Metric
          label={`Spent in ${MONTH_NAMES[now.getMonth()]}`}
          value={fmt(spent)}
          note={
            spendDelta === null ? (
              <>
                {monthExpenses.length} transaction{monthExpenses.length === 1 ? "" : "s"} · no
                prior month to compare
              </>
            ) : (
              <>
                {monthExpenses.length} transaction{monthExpenses.length === 1 ? "" : "s"} ·{" "}
                <span className={spendDelta > 0 ? "text-red" : "text-green"}>
                  {spendDelta > 0 ? "+" : "−"}
                  {fmt(Math.abs(spendDelta))}
                </span>{" "}
                vs {MONTH_NAMES[prev.getMonth()]}
              </>
            )
          }
        />
        <Metric
          label="Net worth"
          value={fmt(netWorth)}
          note={
            <>
              {fmt(totalAssets)} assets − {fmt(totalLiabilities)} liabilities
            </>
          }
        />
        <Metric
          label="Net savings"
          value={fmt(netSavings)}
          tone={netSavings >= 0 ? "green" : "red"}
          note={
            savingsRate === null ? "no income entered" : `${pct(savingsRate, 0)} of take-home`
          }
        />
      </div>

      {/* Health */}
      <p className="mb-3 text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted">
        Financial health
      </p>
      <div className="mb-12 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
        <div className="card flex flex-col items-center justify-center py-6">
          {savingsRate === null ? (
            <p className="text-[0.8rem] text-muted">No income entered</p>
          ) : (
            <RingChart
              value={Math.max(0, Math.min(savingsRate, 100))}
              size={104}
              strokeWidth={7}
              color={savingsRate >= 20 ? "#4ade80" : savingsRate >= 10 ? "#fbbf24" : "#f87171"}
              label={`${savingsRate.toFixed(0)}%`}
              sublabel={`Saved in ${MONTH_NAMES[now.getMonth()]}`}
            />
          )}
        </div>

        {dti === null ? (
          <StatusCard
            label="Debt-to-income"
            value="—"
            status="Needs income"
            color="blue"
            description="Enter your salary on Income Setup to measure this."
          />
        ) : (
          <StatusCard
            label="Debt-to-income"
            value={pct(dti)}
            status={dti === 0 ? "No debt" : dti <= 20 ? "Healthy" : dti <= 36 ? "Manageable" : "High"}
            color={dti <= 20 ? "green" : dti <= 36 ? "yellow" : "red"}
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
            color="blue"
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
            status={ef >= 6 ? "Strong" : ef >= 3 ? "Building" : "Priority"}
            color={ef >= 6 ? "green" : ef >= 3 ? "yellow" : "red"}
            description={`${fmt(dashboard.liquid_assets)} counted from ${dashboard.emergency_fund_counted.join(
              ", ",
            )}, against ${fmt(dashboard.monthly_needs)}/mo of needs.`}
          />
        )}

        {adherence === null ? (
          <StatusCard
            label="Budget adherence"
            value="—"
            status="No budget set"
            color="blue"
            description="Set some category amounts on Budget Builder."
          />
        ) : (
          <StatusCard
            label="Budget adherence"
            value={`${onTrack}/${budgeted.length}`}
            status={adherence >= 80 ? "On track" : "Watch"}
            color={adherence >= 80 ? "blue" : "yellow"}
            description={`Categories within budget this month. Total budgeted ${fmt(
              budgetTotal,
            )}/mo.`}
          />
        )}
      </div>

      {/* Spending */}
      <p className="mb-3 text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted">
        Spending · {MONTH_NAMES[now.getMonth()]}
      </p>
      {categories.length === 0 ? (
        <div className="card mb-12 py-10 text-center">
          <p className="text-[0.85rem] text-dim">Nothing logged this month yet.</p>
          <Link
            href="/expenses"
            className="mt-2 inline-block text-[0.8rem] font-medium text-accent hover:underline"
          >
            Add an expense →
          </Link>
        </div>
      ) : (
        <div className="mb-12 grid grid-cols-1 gap-3 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <DonutChart
              data={categories.map(([name, value]) => ({ name, value }))}
              height={280}
            />
          </div>
          <div className="card overflow-hidden p-0 lg:col-span-3">
            <div className="divide-y divide-white/[0.04]">
              {categories.map(([cat, amount], i) => {
                const budget = allCats[cat];
                const share = spent > 0 ? (amount / spent) * 100 : 0;
                const over = budget > 0 && amount > budget;
                return (
                  <div
                    key={cat}
                    className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-white/[0.02]"
                  >
                    <span
                      className="h-2 w-2 shrink-0 rounded-full"
                      style={{
                        background: ["#5b8def", "#4ade80", "#818cf8", "#fbbf24", "#f472b6",
                          "#22d3ee", "#c084fc", "#fb923c", "#2dd4bf", "#e879f9"][i % 10],
                      }}
                    />
                    <span className="flex-1 text-[0.8125rem] text-dim">{cat}</span>
                    {budget > 0 && (
                      <span
                        className={`font-num text-[0.7rem] ${over ? "text-red" : "text-muted"}`}
                      >
                        of {fmt(budget)}
                      </span>
                    )}
                    <div className="hidden w-16 sm:block">
                      <div className="h-1 overflow-hidden rounded-full bg-white/[0.05]">
                        <div
                          className="h-full rounded-full bg-accent"
                          style={{ width: `${Math.min(share, 100)}%` }}
                        />
                      </div>
                    </div>
                    <span className="w-20 text-right font-num text-[0.8125rem] text-primary">
                      {fmt(amount, 2)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Cash flow */}
      <p className="mb-3 text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted">
        Cash flow
      </p>
      <div className="mb-12">
        <BarsChart
          data={[
            { name: "Take-home", value: monthly },
            { name: "Spent", value: spent },
            { name: "Net", value: netSavings },
          ]}
          xKey="name"
          valueKey="value"
          colors={["#5b8def", "#f87171", netSavings >= 0 ? "#4ade80" : "#f87171"]}
          height={260}
        />
      </div>

      {/* Net worth trend — only from real snapshots */}
      <p className="mb-3 text-[0.6875rem] font-medium uppercase tracking-[0.1em] text-muted">
        Net worth over time
      </p>
      {snapshots.length < 2 ? (
        <div className="card mb-12 py-10 text-center">
          <p className="text-[0.85rem] text-dim">
            {snapshots.length === 0
              ? "No snapshots logged yet."
              : "One snapshot logged — two are needed to draw a trend."}
          </p>
          <Link
            href="/net-worth"
            className="mt-2 inline-block text-[0.8rem] font-medium text-accent hover:underline"
          >
            Log a snapshot →
          </Link>
        </div>
      ) : (
        <div className="mb-12">
          <TrendChart
            data={snapshots.map((s) => ({
              date: s.date,
              "Net worth": s.net_worth,
              Assets: s.assets,
            }))}
            xKey="date"
            series={[
              { key: "Net worth", name: "Net worth", color: "#5b8def" },
              { key: "Assets", name: "Assets", color: "#4ade80", area: false },
            ]}
            height={300}
          />
        </div>
      )}

      <Footer />
    </div>
  );
}
