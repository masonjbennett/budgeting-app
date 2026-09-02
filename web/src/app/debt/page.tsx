"use client";

import { useEffect, useState } from "react";

import { TrendChart } from "@/components/Chart";
import { Empty, Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { api, ApiError, type Debt, type PayoffResult } from "@/lib/api";
import { fmt, useFinance } from "@/context/FinanceContext";

function months(n: number) {
  const y = Math.floor(n / 12);
  const m = n % 12;
  if (!y) return `${m} mo`;
  return m ? `${y} yr ${m} mo` : `${y} yr`;
}

function StrategyCard({
  name,
  blurb,
  result,
  better,
}: {
  name: string;
  blurb: string;
  result: PayoffResult;
  better: boolean;
}) {
  // The engine returns -1 for "these payments never clear this debt". Rendering
  // it as a duration gives "-1 mo to debt-free", which reads as a number.
  if (result.never_pays_off) {
    return (
      <div className="card border-red/25 bg-red/[0.03]">
        <p className="text-[0.85rem] font-semibold text-primary">{name}</p>
        <p className="mt-2 text-[0.85rem] text-red">Never pays off</p>
        <p className="mt-1 text-[0.72rem] leading-snug text-muted">
          The monthly payments do not cover the interest accruing, so the balance
          grows. Raise the minimums or the extra payment.
        </p>
      </div>
    );
  }
  return (
    <div className={`card ${better ? "border-green/30 bg-green/[0.03]" : ""}`}>
      <div className="flex items-baseline justify-between">
        <p className="text-[0.85rem] font-semibold text-primary">{name}</p>
        {better && <span className="badge badge-green">Lower interest</span>}
      </div>
      <p className="mt-2 font-num text-[1.7rem] font-bold leading-none text-primary">
        {months(result.months)}
      </p>
      <p className="mt-1.5 text-[0.78rem] text-dim">
        {fmt(result.total_interest)} of interest
      </p>
      <p className="mt-2 text-[0.7rem] leading-snug text-muted">{blurb}</p>
    </div>
  );
}

export default function DebtPage() {
  const { profile, dashboard, update } = useFinance();
  const [extra, setExtra] = useState(200);
  const [result, setResult] = useState<{
    avalanche: PayoffResult;
    snowball: PayoffResult;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState({ name: "", balance: 0, rate: 5, min_payment: 0 });

  const debts = profile?.debts ?? [];
  const key = JSON.stringify([debts, extra]);

  useEffect(() => {
    // No synchronous setState for the empty case: `shown` below derives it, so
    // clearing a stale result costs no extra render.
    if (!debts.length) return;
    let live = true;
    api
      .debtPayoff(debts, extra)
      .then((r) => live && (setResult(r), setError(null)))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Calculation failed"));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!profile || !dashboard) return <div className="skeleton h-96 rounded-xl" />;

  const setDebts = (d: Debt[]) => update({ debts: d });
  const addDebt = () => {
    if (!draft.name.trim() || draft.balance <= 0) return;
    setDebts([...debts, { ...draft, name: draft.name.trim() }]);
    setDraft({ name: "", balance: 0, rate: 5, min_payment: 0 });
  };

  const totalBalance = debts.reduce((s, d) => s + d.balance, 0);
  const totalMin = debts.reduce((s, d) => s + d.min_payment, 0);

  // Derived, so a result left over from a previous set of debts can never be
  // shown against the current (empty) one.
  const shown = debts.length ? result : null;

  const better =
    shown && !shown.avalanche.never_pays_off && !shown.snowball.never_pays_off
      ? shown.avalanche.total_interest < shown.snowball.total_interest - 0.01
        ? "avalanche"
        : shown.snowball.total_interest < shown.avalanche.total_interest - 0.01
          ? "snowball"
          : "tie"
      : null;

  return (
    <div>
      <PageHeader
        title="Debt Payoff"
        description="Compare avalanche against snowball. Both roll a cleared debt's minimum onto the next target — that rolling is what makes either strategy work."
      />

      <div className="stagger mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {[
          ["Total balance", fmt(totalBalance)],
          ["Minimums", `${fmt(totalMin)}/mo`],
          ["With extra", `${fmt(totalMin + extra)}/mo`],
        ].map(([label, value]) => (
          <div key={label} className="card">
            <p className="text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-muted">
              {label}
            </p>
            <p className="mt-1 font-num text-[1.6rem] font-bold leading-none text-primary">
              {value}
            </p>
          </div>
        ))}
      </div>

      <Section title="Your debts">
        {debts.length === 0 ? (
          <Empty>No debts entered. Add one below to compare payoff strategies.</Empty>
        ) : (
          <div className="card overflow-x-auto p-0">
            <table>
              <thead>
                <tr>
                  <th>Debt</th>
                  <th className="text-right">Balance</th>
                  <th className="text-right">Rate</th>
                  <th className="text-right">Minimum</th>
                  <th className="text-right">Cleared</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {debts.map((d, i) => (
                  <tr key={`${d.name}-${i}`}>
                    <td className="text-primary">{d.name}</td>
                    <td className="text-right font-num">{fmt(d.balance)}</td>
                    <td className="text-right font-num">{d.rate.toFixed(2)}%</td>
                    <td className="text-right font-num">{fmt(d.min_payment)}</td>
                    <td className="text-right font-num text-muted">
                      {shown?.avalanche.payoff_months?.[d.name]
                        ? months(shown.avalanche.payoff_months[d.name])
                        : "—"}
                    </td>
                    <td className="w-8 text-right">
                      <button
                        onClick={() => setDebts(debts.filter((_, j) => j !== i))}
                        aria-label={`Remove ${d.name}`}
                        className="text-muted transition-colors hover:text-red"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Name">
            <input
              type="text"
              placeholder="Credit card"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </Field>
          <Field label="Balance">
            <NumberInput
              value={draft.balance}
              onChange={(v) => setDraft({ ...draft, balance: v })}
              step={100}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Rate">
            <NumberInput
              value={draft.rate}
              onChange={(v) => setDraft({ ...draft, rate: v })}
              step={0.1}
              min={0}
              suffix="%"
            />
          </Field>
          <Field label="Minimum payment">
            <NumberInput
              value={draft.min_payment}
              onChange={(v) => setDraft({ ...draft, min_payment: v })}
              step={10}
              min={0}
              prefix="$"
            />
          </Field>
          <div className="flex items-end">
            <button
              onClick={addDebt}
              disabled={!draft.name.trim() || draft.balance <= 0}
              className="btn-primary w-full disabled:opacity-40"
            >
              Add debt
            </button>
          </div>
        </div>
      </Section>

      {debts.length > 0 && (
        <Section title="Strategy comparison">
          <div className="mb-4 max-w-xs">
            <Field
              label={`Extra payment — ${fmt(extra)}/mo`}
              help="On top of every minimum, applied to whichever debt the strategy targets."
            >
              <input
                type="range"
                min={0}
                max={2000}
                step={25}
                value={extra}
                onChange={(e) => setExtra(Number(e.target.value))}
              />
            </Field>
          </div>

          {error && (
            <div className="card border-red/25 bg-red/[0.03] text-[0.82rem] text-red">
              {error}
            </div>
          )}

          {shown && (
            <>
              <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <StrategyCard
                  name="Avalanche"
                  blurb="Targets the highest interest rate first. Mathematically cheapest."
                  result={shown.avalanche}
                  better={better === "avalanche"}
                />
                <StrategyCard
                  name="Snowball"
                  blurb="Targets the smallest balance first. Clears individual debts sooner."
                  result={shown.snowball}
                  better={better === "snowball"}
                />
              </div>

              {better === "tie" && (
                <p className="mb-4 text-[0.78rem] text-muted">
                  Both strategies cost the same here — with these debts they attack in
                  the same order, so there is nothing to choose between them.
                </p>
              )}
              {better === "avalanche" && (
                <p className="mb-4 text-[0.78rem] text-dim">
                  Avalanche saves{" "}
                  <strong className="font-num text-green">
                    {fmt(
                      shown.snowball.total_interest - shown.avalanche.total_interest,
                    )}
                  </strong>{" "}
                  in interest. Snowball clears its first debt sooner, which some people
                  find easier to stick to.
                </p>
              )}

              {!shown.avalanche.never_pays_off && !shown.snowball.never_pays_off && (
                <TrendChart
                  title="Balance over time"
                  data={shown.avalanche.schedule.map((row, i) => ({
                    month: row.month,
                    Avalanche: row.total_balance,
                    Snowball: shown.snowball.schedule[i]?.total_balance ?? 0,
                  }))}
                  xKey="month"
                  series={[
                    { key: "Avalanche", name: "Avalanche", color: "#5b8def" },
                    { key: "Snowball", name: "Snowball", color: "#fbbf24", area: false },
                  ]}
                  height={300}
                  xFormatter={(v) => `${v}`}
                />
              )}
            </>
          )}
        </Section>
      )}

      <Footer />
    </div>
  );
}
