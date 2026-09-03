"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import AnimatedNumber from "@/components/AnimatedNumber";
import { FanChart, HistogramChart, PathsChart, SavingsCurveChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import StatusCard from "@/components/StatusCard";
import {
  api,
  ApiError,
  type FireProjection,
  type MonteCarlo,
  type SocialSecurity,
} from "@/lib/api";
import { abbr, fmt, pct, useFinance } from "@/context/FinanceContext";

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

/**
 * A span of time, said the way a person says it.
 *
 * Formatting, not a rule: it decides nothing and changes no answer, which is
 * the standing `fmt` and `abbr` already have. One function rather than two
 * because "1.4 years" and "7 months" were being chosen in two places, and the
 * second copy had no zero case.
 */
function duration(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  if (v < 1) return `${Math.round(v * 12)} months`;
  return `${v.toFixed(1)} years`;
}

export default function FirePage() {
  const { profile } = useFinance();

  const [currentAge, setCurrentAge] = useState(30);
  const [retireAge, setRetireAge] = useState(55);
  const [endAge, setEndAge] = useState(95);
  const [stockPct, setStockPct] = useState(80);
  const [inflation, setInflation] = useState(3.0);
  const [nSims, setNSims] = useState(1000);

  // Every figure on this page is now the engine's. It used to hold five of its
  // own — the savings rate, the FIRE number, annual savings, the progress
  // percentage and a `const SWR = 0.04` — which is exactly the arithmetic that
  // has drifted between this app's front ends twice before.
  const [fire, setFire] = useState<FireProjection | null>(null);
  const [fireError, setFireError] = useState<string | null>(null);

  const [result, setResult] = useState<MonteCarlo | null>(null);
  const [ss, setSs] = useState<SocialSecurity | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The stock slider fires on every 5% step, so the projection is debounced.
  // A sequence number rather than a cancel: a slow earlier response landing
  // after a faster later one would replace the curve with the one for a
  // setting that is no longer on screen — the same race the dashboard's
  // recompute carries, and just as invisible when it happens.
  const seq = useRef(0);
  const load = useCallback(async () => {
    if (!profile) return;
    const mine = ++seq.current;
    try {
      const f = await api.fire({
        income: profile.income,
        itemized: profile.itemized,
        budget: profile.budget,
        assets: profile.assets,
        stock_pct: stockPct,
        inflation,
      });
      if (mine === seq.current) {
        setFire(f);
        setFireError(null);
      }
    } catch (e) {
      if (mine === seq.current) {
        setFire(null);
        setFireError(e instanceof ApiError ? e.message : "Could not build the projection.");
      }
    }
  }, [profile, stockPct, inflation]);

  useEffect(() => {
    const t = setTimeout(load, 220);
    return () => clearTimeout(t);
  }, [load]);

  if (!profile) return <div className="skeleton h-96" />;

  const run = async () => {
    if (!fire) return;
    setBusy(true);
    setError(null);
    try {
      const [mc, social] = await Promise.all([
        api.monteCarlo({
          current_age: currentAge,
          retire_age: retireAge,
          end_age: endAge,
          portfolio: fire.portfolio,
          annual_savings: fire.annual_savings,
          annual_expenses: fire.annual_expenses,
          stock_pct: stockPct,
          inflation,
          n_sims: nSims,
        }),
        api.socialSecurity(fire.annual_take_home, 67, fire.swr),
      ]);
      setResult(mc);
      setSs(social);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Simulation failed");
    }
    setBusy(false);
  };

  const ordered = retireAge > currentAge && endAge > retireAge;
  // A budget with nothing in it gives a FIRE number of zero, which is
  // arithmetically right and useless as a headline. The page says so instead.
  const noBudget = !!fire && fire.annual_expenses <= 0;
  const rate = fire?.savings_rate ?? null;

  return (
    <div>
      <PageHeader
        title="FIRE"
        description="What independence costs, how long it takes at your savings rate, and how the plan holds up across thousands of randomised market paths."
      />

      {fireError && (
        <div className="card mark-critical t-small mb-8 text-critical">{fireError}</div>
      )}

      {/* The one hero on this page: the number the whole model is about. */}
      {!fire ? (
        <div className="skeleton mb-9 h-[9.5rem] w-full" />
      ) : (
        <div className="animate-fade-in mb-9 border-b border-hair pb-6">
          <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
            <div>
              <p className="label">FIRE number</p>
              {noBudget ? (
                <>
                  <p className="figure-hero mt-1.5 text-muted">—</p>
                  <p className="t-small mt-2 text-muted">
                    Budget some needs and wants first — the target is what your
                    spending costs, so with no spending there is nothing to fund.
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-1.5">
                    <AnimatedNumber
                      value={fire.fire_number ?? 0}
                      className="figure-hero"
                      title={fmt(fire.fire_number)}
                    />
                  </p>
                  <p className="t-small mt-2 text-muted">
                    <span className="font-num text-body">{fmt(fire.annual_expenses)}</span>/yr
                    of budgeted spending at a {fire.swr.toFixed(0)}% withdrawal rate
                  </p>
                </>
              )}
            </div>
            <div className="text-right">
              <p className="label">Portfolio today</p>
              <p className="font-num t-h3 mt-1 leading-none font-medium text-ink">
                {fmt(fire.portfolio)}
              </p>
              <p className="t-micro mt-1.5 text-muted">
                {fire.progress_pct === null
                  ? "—"
                  : `${pct(fire.progress_pct, 1)} of the way`}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="mb-8 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <div className="card">
            <h3 className="label mb-4">From your profile</h3>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[
                ["Annual take-home", fmt(fire?.annual_take_home)],
                ["Annual expenses", fmt(fire?.annual_expenses)],
                ["Annual savings", fmt(fire?.annual_savings)],
                ["Portfolio today", fmt(fire?.portfolio)],
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
            {fire?.overspending && (
              <p className="t-micro mt-2 text-critical">
                Your budget spends {fmt(fire.shortfall)}/yr more than your take-home
                covers, so annual savings reads zero rather than a negative number.
              </p>
            )}
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
          {rate === null ? (
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
              value={pct(rate, 0)}
              status={rate >= 50 ? "Excellent" : rate >= 25 ? "Good" : "Low"}
              tone={rate >= 50 ? "positive" : rate >= 25 ? "caution" : "critical"}
              description="Take-home less your BUDGETED needs and wants. The dashboard's figure uses what you actually spent this month, so the two differ."
            />
          )}
          <div className="card">
            <p className="label">At this rate</p>
            <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
              {fire && fire.years_at_current === null && !noBudget
                ? "Never"
                : fire && fire.years_at_current !== null && fire.years_at_current <= 0
                  ? "Already there"
                  : duration(fire?.years_at_current)}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              {fire && fire.years_at_current === null && !noBudget
                ? fire.overspending
                  ? `The budget spends ${fmt(
                      fire.shortfall,
                    )}/yr more than take-home covers, so the portfolio is being drawn down rather than built.`
                  : "Nothing is being saved, so the portfolio never reaches the target."
                : `Saving ${fmt(fire?.annual_savings)}/yr at a ${
                    fire ? fire.real_return.toFixed(1) : "—"
                  }% real return.`}
            </p>
          </div>
          <div className="card">
            <p className="label">Still to accumulate</p>
            <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
              {fmt(fire?.still_to_accumulate)}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              Before any market return.
            </p>
          </div>
        </div>
      </div>

      {/* ── The curve ──────────────────────────────────────────────────
             The most persuasive thing on the page and the cheapest: it is
             deterministic, so it is on screen before the simulation below has
             been asked for. It moves with the two settings above because its
             return comes from the same constants the Monte Carlo draws. ──── */}
      {fire && !noBudget && fire.curve.length > 0 && (
        <Section
          title="Savings rate against years to independence"
          action={
            fire.next_point &&
            fire.next_point.years_saved > 0 && (
              <p className="t-micro text-muted">
                one more point ·{" "}
                <span className="font-num text-accent">
                  {duration(fire.next_point.years_saved)} sooner
                </span>
              </p>
            )
          }
        >
          <SavingsCurveChart
            points={fire.curve}
            current={
              rate !== null && fire.years_at_current !== null
                ? { savings_rate: rate, years: fire.years_at_current }
                : null
            }
            height={330}
            note={
              <>
                Both sides of the problem move with the rate, which is why the
                curve is steep at the left and nearly flat at the right: saving
                more fills the portfolio faster AND lowers the target, because
                the money you do not spend is money the portfolio never has to
                replace. Drawn at a{" "}
                <span className="font-num">{fire.real_return.toFixed(1)}%</span> real
                return — the same {stockPct}/{100 - stockPct} stock and bond means
                the simulation below uses, less {inflation}% inflation — and a{" "}
                <span className="font-num">{fire.swr.toFixed(0)}%</span> withdrawal
                rate. This is the AVERAGE path and it has no spread in it; the
                Monte Carlo below is where the range lives.
                {fire.curve.some((c) => c.years === null) && (
                  <> The line stops where a rate never reaches the target at all.</>
                )}
              </>
            }
          />
        </Section>
      )}

      <button
        onClick={run}
        disabled={busy || !ordered || !fire}
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

          {result.ending_histogram.length > 0 && (
            <div className="mb-8">
              <HistogramChart
                title="Where the paths end up"
                bins={result.ending_histogram}
                height={280}
                formatBin={(v) => abbr(v)}
                note={
                  <>
                    The two charts above show the RANGE; this shows the shape. Bars in
                    claret are paths that ran out of money before age {endAge} —{" "}
                    {(result.n_sims - result.success_count).toLocaleString()} of{" "}
                    {result.n_sims.toLocaleString()}. A run can have a comfortable median
                    and a long tail of failures, and a band chart hides that.
                  </>
                }
              />
            </div>
          )}

          {ss && (
            <Section title="Social Security estimate">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                {[
                  ["Monthly benefit", fmt(ss.monthly), "At 67, full retirement age"],
                  ["Annual", fmt(ss.annual), ""],
                  [
                    "Reduces FIRE number by",
                    fmt(ss.reduces_target_by),
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
