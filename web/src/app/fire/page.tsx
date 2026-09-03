"use client";

import { useState } from "react";

import AnimatedNumber from "@/components/AnimatedNumber";
import { FanChart, PathsChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import StatusCard from "@/components/StatusCard";
import { api, ApiError, type MonteCarlo } from "@/lib/api";
import { abbr, fmt, pct, sum, useFinance } from "@/context/FinanceContext";

const SWR = 0.04; // Trinity Study safe withdrawal rate — a stated assumption.

/**
 * A figure large enough that its digits stop being readable.
 *
 * This page used to render $36,033,288 beside $148,039,029 at the same size,
 * and at a glance those are the same number. The short form is the one the eye
 * takes; the exact one is printed underneath rather than hidden behind a hover,
 * because a hover is not available on the phone this link gets opened on.
 */
function BigFigure({ label, value, note }: { label: string; value: number; note?: string }) {
  const short = abbr(value);
  const full = fmt(value);
  return (
    <div className="card">
      <p className="label">{label}</p>
      <p className="font-num t-h2 mt-1.5 leading-none font-medium text-ink" title={full}>
        {short}
      </p>
      {short !== full && <p className="font-num t-micro mt-1.5 text-muted">{full}</p>}
      {note && <p className="t-micro mt-1.5 text-muted">{note}</p>}
    </div>
  );
}

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

  if (!profile || !dashboard) return <div className="skeleton h-96" />;

  const th = dashboard.take_home;

  // These come from the profile rather than being typed again, so the FIRE page
  // models the person the rest of the app knows about. The abandoned scaffold's
  // version held its own useState and ignored your income and assets entirely.
  const annualExpenses = (sum(profile.budget.needs) + sum(profile.budget.wants)) * 12;
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
        title="FIRE"
        description="How long your portfolio lasts, tested across thousands of randomised market paths rather than one assumed return."
      />

      {/* The one hero on this page: the number the whole model is about. */}
      <div className="animate-fade-in mb-9 border-b border-hair pb-6">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <div>
            <p className="label">FIRE number</p>
            <p className="mt-1.5">
              <AnimatedNumber value={fireNumber} className="figure-hero" title={fmt(fireNumber)} />
            </p>
            <p className="t-small mt-2 text-muted">
              <span className="font-num text-body">{fmt(annualExpenses)}</span>/yr of
              budgeted spending at a {(SWR * 100).toFixed(0)}% withdrawal rate
            </p>
          </div>
          <div className="text-right">
            <p className="label">Portfolio today</p>
            <p className="font-num t-h3 mt-1 leading-none font-medium text-ink">
              {fmt(portfolio)}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              {fireNumber > 0 ? `${pct((portfolio / fireNumber) * 100, 1)} of the way` : "—"}
            </p>
          </div>
        </div>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="card">
            <h3 className="label mb-4">From your profile</h3>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Annual take-home", fmt(th.annual_take_home)],
                ["Annual expenses", fmt(annualExpenses)],
                ["Annual savings", fmt(annualSavings)],
                ["Portfolio today", fmt(portfolio)],
              ].map(([label, value]) => (
                <div key={label}>
                  <p className="t-micro text-muted">{label}</p>
                  <p className="font-num t-lead mt-0.5 text-ink">{value}</p>
                </div>
              ))}
            </div>
            <p className="t-micro mt-3 text-muted">
              Expenses are your budgeted needs and wants; savings is what your
              take-home leaves after them. Change them on Budget and Net Worth.
            </p>
          </div>

          <div className="card">
            <h3 className="label mb-4">Simulation settings</h3>
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
              <p className="t-small mt-3 text-caution">
                Retirement age must be after your current age, and the plan must run
                past retirement.
              </p>
            )}
          </div>
        </div>

        <div className="stagger space-y-3">
          {savingsRate === null ? (
            <StatusCard
              label="Savings rate"
              value="—"
              status="Needs income"
              tone="info"
              description="Enter a salary on Income."
            />
          ) : (
            <StatusCard
              label="Savings rate (budgeted)"
              value={pct(savingsRate, 0)}
              status={savingsRate >= 50 ? "Excellent" : savingsRate >= 25 ? "Good" : "Low"}
              tone={savingsRate >= 50 ? "positive" : savingsRate >= 25 ? "caution" : "critical"}
              description="Take-home less your BUDGETED needs and wants. The dashboard's figure uses what you actually spent this month, so the two differ."
            />
          )}
          <div className="card">
            <p className="label">Still to accumulate</p>
            <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
              {fmt(Math.max(0, fireNumber - portfolio))}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              At {fmt(annualSavings)}/yr saved, before any market return.
            </p>
          </div>
        </div>
      </div>

      <button
        onClick={run}
        disabled={busy || !ordered}
        className="btn-primary mb-10 w-full py-3"
      >
        {busy ? `Running ${nSims.toLocaleString()} simulations…` : "Run Monte Carlo simulation"}
      </button>

      {error && (
        <div className="card mark-critical t-small mb-8 text-critical">{error}</div>
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
                tone={
                  result.success_rate >= 85
                    ? "positive"
                    : result.success_rate >= 70
                      ? "caution"
                      : "critical"
                }
                description={`Money left at age ${endAge} in ${result.success_count.toLocaleString()} of ${result.n_sims.toLocaleString()} paths.`}
              />
              <BigFigure label="Median ending" value={result.median_ending} />
              <BigFigure
                label="Worst 10%"
                value={Math.max(0, result.p10_ending)}
                note="9 in 10 paths end better than this"
              />
              <BigFigure label="Best 10%" value={result.p90_ending} />
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
                    <p className="label">{label}</p>
                    <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                      {value}
                    </p>
                    {note && <p className="t-micro mt-1.5 text-muted">{note}</p>}
                  </div>
                ))}
              </div>
              <p className="t-micro mt-3 leading-relaxed text-muted">
                A simplified estimate from the 2026 bend points on your current salary.
                Real benefits depend on your full 35-year earnings record.
              </p>
            </Section>
          )}

          <div className="panel p-5">
            <h3 className="label mb-2">Method</h3>
            <p className="t-small leading-relaxed text-body">
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
