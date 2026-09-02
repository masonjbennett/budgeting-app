"use client";

import { useState } from "react";

import { FanChart, PathsChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import StatusCard from "@/components/StatusCard";
import { api, ApiError, type MonteCarlo } from "@/lib/api";
import { fmt, pct, sum, useFinance } from "@/context/FinanceContext";

const SWR = 0.04; // Trinity Study safe withdrawal rate — a stated assumption.

export default function FirePage() {
  const { profile, dashboard } = useFinance();

  const [currentAge, setCurrentAge] = useState(30);
  const [retireAge, setRetireAge] = useState(55);
  const [endAge, setEndAge] = useState(95);
  const [stockPct, setStockPct] = useState(80);
  const [inflation, setInflation] = useState(3.0);
  const [nSims, setNSims] = useState(1000);

  const [result, setResult] = useState<MonteCarlo | null>(null);
  const [ss, setSs] = useState<{ monthly: number; annual: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!profile || !dashboard) return <div className="skeleton h-96 rounded-xl" />;

  const th = dashboard.take_home;

  // These come from the profile rather than being typed again, so the FIRE page
  // models the person the rest of the app knows about. The abandoned scaffold's
  // version held its own useState and ignored your income and assets entirely.
  const annualExpenses =
    (sum(profile.budget.needs) + sum(profile.budget.wants)) * 12;
  const annualSavings = Math.max(0, th.annual_take_home - annualExpenses);
  const portfolio = sum(profile.assets);
  const fireNumber = annualExpenses / SWR;
  const savingsRate =
    th.annual_take_home > 0 ? (annualSavings / th.annual_take_home) * 100 : null;

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const [mc, social] = await Promise.all([
        api.monteCarlo({
          current_age: currentAge,
          retire_age: retireAge,
          end_age: endAge,
          portfolio,
          annual_savings: annualSavings,
          annual_expenses: annualExpenses,
          stock_pct: stockPct,
          inflation,
          n_sims: nSims,
        }),
        api.socialSecurity(th.annual_gross, 67),
      ]);
      setResult(mc);
      setSs(social);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Simulation failed");
    }
    setBusy(false);
  };

  const ordered = retireAge > currentAge && endAge > retireAge;

  return (
    <div>
      <PageHeader
        title="FIRE Calculator"
        description="How long your portfolio lasts, tested across thousands of randomised market paths rather than one assumed return."
      />

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="card">
            <h3 className="mb-4 text-[0.85rem] font-semibold text-primary">
              From your profile
            </h3>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Annual take-home", fmt(th.annual_take_home)],
                ["Annual expenses", fmt(annualExpenses)],
                ["Annual savings", fmt(annualSavings)],
                ["Portfolio today", fmt(portfolio)],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="text-[0.68rem] text-muted">{label}</p>
                  <p className="mt-0.5 font-num text-[1.05rem] text-primary">{value}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[0.68rem] leading-snug text-muted">
              Expenses are your budgeted needs and wants; savings is what your
              take-home leaves after them. Change them on Budget Builder and Net Worth.
            </p>
          </div>

          <div className="card">
            <h3 className="mb-4 text-[0.85rem] font-semibold text-primary">
              Simulation settings
            </h3>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Current age">
                <NumberInput
                  value={currentAge}
                  onChange={(v) => setCurrentAge(Math.round(v))}
                  min={18}
                  max={90}
                />
              </Field>
              <Field label="Retirement age">
                <NumberInput
                  value={retireAge}
                  onChange={(v) => setRetireAge(Math.round(v))}
                  min={19}
                  max={95}
                />
              </Field>
              <Field label="Plan through age">
                <NumberInput
                  value={endAge}
                  onChange={(v) => setEndAge(Math.round(v))}
                  min={20}
                  max={110}
                />
              </Field>
              <Field label="Assumed inflation">
                <NumberInput
                  value={inflation}
                  onChange={setInflation}
                  step={0.1}
                  min={0}
                  max={15}
                  suffix="%"
                />
              </Field>
              <Field
                label={`Stock allocation — ${stockPct}%`}
                help={`${100 - stockPct}% bonds`}
              >
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={stockPct}
                  onChange={(e) => setStockPct(Number(e.target.value))}
                />
              </Field>
              <Field label="Simulations">
                <select value={nSims} onChange={(e) => setNSims(Number(e.target.value))}>
                  {[500, 1000, 2000, 5000].map((n) => (
                    <option key={n} value={n}>
                      {n.toLocaleString()}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            {!ordered && (
              <p className="mt-3 text-[0.75rem] text-yellow">
                Retirement age must be after your current age, and the plan must run
                past retirement.
              </p>
            )}
          </div>
        </div>

        <div className="stagger space-y-3">
          <div className="card border-accent/20 bg-gradient-to-br from-accent/10 to-transparent">
            <p className="text-[0.68rem] font-semibold uppercase tracking-[0.08em] text-accent">
              FIRE number
            </p>
            <p className="mt-1 font-num text-[1.9rem] font-bold leading-tight text-primary">
              {fmt(fireNumber)}
            </p>
            <p className="mt-1 text-[0.72rem] text-muted">
              {fmt(annualExpenses)}/yr at a {(SWR * 100).toFixed(0)}% withdrawal rate
            </p>
          </div>
          {savingsRate === null ? (
            <StatusCard
              label="Savings rate"
              value="—"
              status="Needs income"
              color="blue"
              description="Enter a salary on Income Setup."
            />
          ) : (
            <StatusCard
              label="Savings rate (budgeted)"
              value={pct(savingsRate, 0)}
              status={savingsRate >= 50 ? "Excellent" : savingsRate >= 25 ? "Good" : "Low"}
              color={savingsRate >= 50 ? "green" : savingsRate >= 25 ? "yellow" : "red"}
              description="Take-home less your BUDGETED needs and wants. The dashboard's figure uses what you actually spent this month, so the two differ."
            />
          )}
          <div className="card">
            <p className="text-[0.68rem] text-muted">Portfolio as % of FIRE number</p>
            <p className="mt-1 font-num text-[1.4rem] font-bold text-primary">
              {fireNumber > 0 ? pct((portfolio / fireNumber) * 100, 1) : "—"}
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={run}
        disabled={busy || !ordered}
        className="btn-primary mb-10 flex w-full items-center justify-center gap-2 py-3.5 text-[0.9rem] disabled:opacity-40"
      >
        {busy ? `Running ${nSims.toLocaleString()} simulations…` : "Run Monte Carlo simulation"}
      </button>

      {error && (
        <div className="card mb-8 border-red/25 bg-red/[0.03] text-[0.82rem] text-red">
          {error}
        </div>
      )}

      {result && (
        <div className="animate-fade-in">
          <Section title={`Results · ${result.n_sims.toLocaleString()} scenarios`}>
            <div className="stagger grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatusCard
                label="Success rate"
                value={pct(result.success_rate, 0)}
                status={
                  result.success_rate >= 85
                    ? "Strong"
                    : result.success_rate >= 70
                      ? "Moderate"
                      : "At risk"
                }
                color={
                  result.success_rate >= 85
                    ? "green"
                    : result.success_rate >= 70
                      ? "yellow"
                      : "red"
                }
                description={`Money left at age ${endAge} in ${result.success_count.toLocaleString()} of ${result.n_sims.toLocaleString()} paths.`}
              />
              <div className="card">
                <p className="text-[0.6875rem] uppercase tracking-[0.06em] text-muted">
                  Median ending
                </p>
                <p className="mt-1 font-num text-[1.6rem] font-bold text-primary">
                  {fmt(result.median_ending)}
                </p>
              </div>
              <div className="card">
                <p className="text-[0.6875rem] uppercase tracking-[0.06em] text-muted">
                  Worst 10%
                </p>
                <p className="mt-1 font-num text-[1.6rem] font-bold text-primary">
                  {fmt(Math.max(0, result.p10_ending))}
                </p>
                <p className="mt-1 text-[0.65rem] text-muted">
                  9 in 10 paths end better than this
                </p>
              </div>
              <div className="card">
                <p className="text-[0.6875rem] uppercase tracking-[0.06em] text-muted">
                  Best 10%
                </p>
                <p className="mt-1 font-num text-[1.6rem] font-bold text-primary">
                  {fmt(result.p90_ending)}
                </p>
              </div>
            </div>
          </Section>

          <div className="mb-8">
            <FanChart
              title="Portfolio value by age"
              ages={result.ages}
              median={result.percentiles.p50}
              retireAge={result.retire_age}
              bands={[
                {
                  lower: result.percentiles.p10,
                  upper: result.percentiles.p90,
                  opacity: 0.1,
                  name: "10th–90th",
                },
                {
                  lower: result.percentiles.p25,
                  upper: result.percentiles.p75,
                  opacity: 0.2,
                  name: "25th–75th",
                },
              ]}
              height={400}
            />
          </div>

          <div className="mb-8">
            <PathsChart
              title={`${result.sample_paths.length} individual paths`}
              ages={result.ages}
              paths={result.sample_paths}
              median={result.percentiles.p50}
              height={320}
              // Same ceiling as the fan chart above, so the two are read on one
              // scale. Uncapped, a single lucky path sets the axis and flattens
              // everything else onto zero.
              yMax={Math.max(...result.percentiles.p90)}
              note="Drawn on the same axis as the chart above."
            />
          </div>

          {ss && (
            <Section title="Social Security estimate">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  ["Monthly benefit", fmt(ss.monthly), "At 67, full retirement age"],
                  ["Annual", fmt(ss.annual), ""],
                  [
                    "Reduces FIRE number by",
                    fmt(ss.annual / SWR),
                    "Less the portfolio has to cover",
                  ],
                ].map(([label, value, note]) => (
                  <div key={label} className="card">
                    <p className="text-[0.68rem] text-muted">{label}</p>
                    <p className="mt-1 font-num text-[1.4rem] font-bold text-primary">
                      {value}
                    </p>
                    {note && <p className="mt-1 text-[0.65rem] text-muted">{note}</p>}
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[0.72rem] leading-relaxed text-muted">
                A simplified estimate from the 2026 bend points on your current salary.
                Real benefits depend on your full 35-year earnings record.
              </p>
            </Section>
          )}

          <div className="card bg-white/[0.02]">
            <h3 className="mb-2 text-[0.82rem] font-semibold text-primary">Method</h3>
            <p className="text-[0.78rem] leading-relaxed text-muted">
              {result.n_sims.toLocaleString()} paths with correlated stock and bond
              returns drawn each year (Cholesky factorisation of a 0.05 correlation).
              Stocks 10% mean / 18% standard deviation, bonds 5% / 6%, at{" "}
              {result.stock_pct}% stocks. Inflation is drawn too, at {inflation}% mean
              and 1.5% deviation, and retirement spending compounds at the inflation
              actually realised — the sequence you get is the risk this exists to
              measure. Contributions grow at expected inflation until age{" "}
              {result.retire_age}, then withdrawals begin. A path that reaches zero
              stays there. Sources: Trinity Study (1998), Shiller/Ibbotson series.
            </p>
          </div>
        </div>
      )}

      <Footer />
    </div>
  );
}
