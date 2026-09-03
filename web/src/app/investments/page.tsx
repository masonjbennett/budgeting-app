"use client";

import { useEffect, useState } from "react";

import { TrendChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { api, ApiError, type Investment } from "@/lib/api";
import { fmt, useFinance } from "@/context/FinanceContext";
import { cssVar, type Token } from "@/lib/tokens";

const SCENARIOS: { name: string; rate: number; tone: Token }[] = [
  { name: "Conservative", rate: 5, tone: "caution" },
  { name: "Moderate", rate: 7, tone: "accent" },
  { name: "Aggressive", rate: 9, tone: "s2" },
];

export default function InvestmentsPage() {
  const { profile, update } = useFinance();
  const [runs, setRuns] = useState<Investment[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const inv = profile?.investment;
  const income = profile?.income;
  const key = JSON.stringify([inv, income?.gross_salary, income?.contribution_401k]);

  useEffect(() => {
    if (!inv || !income) return;
    let live = true;
    Promise.all(
      SCENARIOS.map((s) =>
        api.investment({
          start: inv.starting_amount,
          monthly: inv.monthly_contribution,
          rate: s.rate,
          years: inv.time_horizon,
          // The match inputs rendered on this page and the projection ignored
          // them, which understates a matched 401(k) by the most reliable
          // return in the model.
          salary: income?.gross_salary ?? 0,
          contribution_pct: income?.contribution_401k ?? 0,
          match_pct: inv.employer_match_pct,
          match_limit: inv.employer_match_limit,
        }),
      ),
    )
      .then((r) => live && (setRuns(r), setError(null)))
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Projection failed"));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!profile || !inv || !income) return <div className="skeleton h-96" />;

  const set = (p: Partial<typeof inv>) => update({ investment: { ...inv, ...p } });

  // Yearly points only — a 30-year run is 361 monthly points, which draws a
  // heavier chart than it reads.
  const chartData = runs
    ? Array.from({ length: inv.time_horizon + 1 }, (_, y) => {
        const i = y * 12;
        const row: Record<string, number> = { year: y };
        SCENARIOS.forEach((s, si) => (row[s.name] = runs[si].values[i] ?? 0));
        row["Contributed"] = runs[1].contributions[i] ?? 0;
        return row;
      })
    : [];

  return (
    <div>
      <PageHeader
        title="Investments"
        description="Compound growth on a starting balance plus monthly contributions, across three return assumptions."
      />

      <Section title="Assumptions">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Starting amount">
            <NumberInput
              value={inv.starting_amount}
              onChange={(v) => set({ starting_amount: v })}
              step={500}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Monthly contribution">
            <NumberInput
              value={inv.monthly_contribution}
              onChange={(v) => set({ monthly_contribution: v })}
              step={50}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Time horizon">
            <NumberInput
              value={inv.time_horizon}
              onChange={(v) => set({ time_horizon: Math.round(v) })}
              step={1}
              min={1}
              max={60}
              suffix="yr"
            />
          </Field>
          <Field
            label="Employer match"
            help={`${inv.employer_match_pct}% of the first ${inv.employer_match_limit}% of salary.`}
          >
            <NumberInput
              value={inv.employer_match_pct}
              onChange={(v) => set({ employer_match_pct: v })}
              step={5}
              min={0}
              max={200}
              suffix="%"
            />
          </Field>
        </div>
      </Section>

      {error && (
        <div className="card mark-critical t-small mb-8 text-critical">{error}</div>
      )}

      {runs && (
        <>
          <Section title="Employer match">
            {(() => {
              const m = runs[0].employer_match;
              return (
                <div className={`card ${m.leaving_money ? "mark-caution" : "mark-accent"}`}>
                  <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
                    <div>
                      <p className="label">Employer adds</p>
                      <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                        {fmt(m.annual_match)}/yr
                      </p>
                    </div>
                    <p className="t-small max-w-[46ch] text-body">
                      {m.leaving_money ? (
                        <>
                          You contribute {m.contribution_pct}% of salary and the match runs
                          to {m.match_limit}%, so{" "}
                          <strong className="font-num text-caution">
                            {fmt(m.annual_missed)} a year
                          </strong>{" "}
                          is left on the table. That is an immediate {m.match_pct}% return
                          on the difference, which no market assumption is needed to
                          justify.
                        </>
                      ) : (
                        <>
                          You contribute enough to collect the whole match —{" "}
                          {m.match_pct}% of the first {m.match_limit}% of salary. The
                          projections below include it.
                        </>
                      )}
                    </p>
                  </div>
                </div>
              );
            })()}
          </Section>

          <Section title={`After ${inv.time_horizon} years`}>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {SCENARIOS.map((s, i) => (
                <div key={s.name} className="card">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="label">{s.name}</p>
                    <span
                      className="font-num t-micro"
                      style={{ color: cssVar(s.tone) }}
                    >
                      {s.rate}%/yr
                    </span>
                  </div>
                  <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                    {fmt(runs[i].final_value)}
                  </p>
                  <p className="t-micro mt-1.5 text-muted">
                    {fmt(runs[i].total_contributed)} contributed ·{" "}
                    <span className="text-positive">{fmt(runs[i].growth)} growth</span>
                    {runs[i].employer_match.annual_match > 0 && (
                      <>
                        {" "}
                        · includes {fmt(runs[i].employer_match.monthly_match)}/mo of match
                      </>
                    )}
                  </p>
                </div>
              ))}
            </div>
          </Section>

          <Section title="Projected balance">
            <TrendChart
              data={chartData}
              xKey="year"
              series={[
                ...SCENARIOS.map((s) => ({
                  key: s.name,
                  name: `${s.name} (${s.rate}%)`,
                  tone: s.tone,
                  area: false as const,
                })),
                { key: "Contributed", name: "Contributed", tone: "muted" as const, dashed: true, area: false },
              ]}
              height={360}
              xFormatter={(v) => `${v}y`}
            />
            <p className="t-micro mt-3 leading-relaxed text-muted">
              Returns are assumed constant, which no market is — the three lines are
              there to show the spread, not to predict one. The FIRE page runs the
              same money through randomised, correlated returns instead.
            </p>
          </Section>
        </>
      )}

      <Footer />
    </div>
  );
}
