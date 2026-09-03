"use client";

/**
 * Scenario comparison — the same person, in a different situation.
 *
 * This is the screen nothing else in the category has, and the reason is not
 * effort: comparing two jobs honestly needs a real tax engine for fifty states
 * and four filing statuses plus a cost-of-living index, and a tracker built on
 * a bank connection has neither. Every figure here is `compute_take_home` run
 * once per scenario, server-side, in one round trip.
 *
 * SCENARIOS LIVE IN THE PROFILE, under `scenarios`. That is not laziness — it
 * means they save to Supabase, ride along in the JSON export and come back on
 * import through machinery that already exists and is already tested, rather
 * than through a second storage mechanism with its own failure modes. A
 * scenario is the INCOME block plus a city, because that is where all five
 * things worth varying live.
 */

import { useEffect, useState } from "react";

import { Empty, Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, pct, useFinance, type Scenario } from "@/context/FinanceContext";
import {
  api,
  ApiError,
  type Comparison,
  type Reference,
  type ScenarioInput,
} from "@/lib/api";

const BASELINE_NAME = "As you are now";

export default function ComparePage() {
  const { profile, update } = useFinance();
  const [ref, setRef] = useState<Reference | null>(null);
  const [result, setResult] = useState<Comparison | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reference().then(setRef).catch(() => setRef(null));
  }, []);

  const scenarios = profile?.scenarios ?? [];
  const baselineCity = profile?.baseline_city ?? "National Average";

  // The baseline is the live profile, not a copy of it — so it follows the
  // Income page instead of going stale the moment anything changes there.
  const payload: ScenarioInput[] | null = profile
    ? [
        {
          name: BASELINE_NAME,
          income: profile.income,
          itemized: profile.itemized,
          city: baselineCity,
        },
        ...scenarios.map((s) => ({
          name: s.name,
          income: s.income,
          itemized: profile.itemized,
          city: s.city,
        })),
      ]
    : null;

  const key = JSON.stringify(payload);
  useEffect(() => {
    if (!payload) return;
    let live = true;
    api
      .compare(payload)
      .then((r) => live && (setResult(r), setError(null)))
      .catch((e) =>
        live && setError(e instanceof ApiError ? e.message : "Could not compare"),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (!profile) return <div className="skeleton h-96" />;

  const cities = ref ? Object.keys(ref.col_index) : [baselineCity];
  const setScenarios = (next: Scenario[]) => update({ scenarios: next });

  const addScenario = () =>
    setScenarios([
      ...scenarios,
      {
        // A copy of where you are now is the only sensible starting point:
        // the whole exercise is changing ONE thing and seeing what it does.
        name: `Scenario ${scenarios.length + 1}`,
        income: { ...profile.income },
        city: baselineCity,
      },
    ]);

  const patch = (i: number, p: Partial<Scenario>) =>
    setScenarios(scenarios.map((s, j) => (j === i ? { ...s, ...p } : s)));

  const patchIncome = (i: number, p: Partial<Scenario["income"]>) =>
    patch(i, { income: { ...scenarios[i].income, ...p } });

  const rows = result?.rows ?? [];

  return (
    <div>
      <PageHeader
        title="Compare"
        description="The same person in a different situation — another city, another state, another salary. Every figure is your real 2026 tax, worked out again from scratch for each one."
      />

      <Section
        title="Scenarios"
        action={
          <button onClick={addScenario} className="btn-secondary">
            Add a scenario
          </button>
        }
      >
        <div className="card mark-accent mb-3">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="label">{BASELINE_NAME}</p>
              <p className="t-small mt-1.5 text-body">
                <span className="font-num text-ink">{fmt(profile.income.gross_salary)}</span>{" "}
                in {profile.income.state} · {profile.income.filing_status} ·{" "}
                {profile.income.contribution_401k}% to a 401(k). Change any of it on the
                Income page.
              </p>
            </div>
            <div className="w-full max-w-[15rem]">
              <Field label="Cost of living where you are">
                <select
                  value={baselineCity}
                  onChange={(e) => update({ baseline_city: e.target.value })}
                >
                  {cities.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>
        </div>

        {scenarios.length === 0 ? (
          <Empty>
            No scenarios yet. Add one and change a single thing — the state, the salary,
            the city — to see what it actually does to your money.
          </Empty>
        ) : (
          <div className="space-y-3">
            {scenarios.map((s, i) => (
              <div key={i} className="card">
                <div className="mb-3 flex items-center gap-2">
                  <input
                    type="text"
                    value={s.name}
                    onChange={(e) => patch(i, { name: e.target.value })}
                    aria-label="Scenario name"
                    className="max-w-xs font-medium"
                  />
                  <div className="flex-1" />
                  <button
                    onClick={() => setScenarios(scenarios.filter((_, j) => j !== i))}
                    aria-label={`Remove ${s.name}`}
                    className="btn-remove"
                  >
                    ✕
                  </button>
                </div>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                  <Field label="Salary">
                    <NumberInput
                      value={s.income.gross_salary}
                      onChange={(v) => patchIncome(i, { gross_salary: v })}
                      step={1000}
                      min={0}
                      prefix="$"
                    />
                  </Field>
                  <Field label="State">
                    <select
                      value={s.income.state}
                      onChange={(e) => patchIncome(i, { state: e.target.value })}
                      disabled={!ref}
                    >
                      {(ref?.states ?? [s.income.state]).map((st) => (
                        <option key={st} value={st}>
                          {st}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Filing status">
                    <select
                      value={s.income.filing_status}
                      onChange={(e) => patchIncome(i, { filing_status: e.target.value })}
                      disabled={!ref}
                    >
                      {(ref?.filing_statuses ?? [s.income.filing_status]).map((f) => (
                        <option key={f} value={f}>
                          {f}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="401(k)">
                    <NumberInput
                      value={s.income.contribution_401k}
                      onChange={(v) => patchIncome(i, { contribution_401k: v })}
                      step={1}
                      min={0}
                      max={100}
                      suffix="%"
                    />
                  </Field>
                  <Field label="City">
                    <select
                      value={s.city}
                      onChange={(e) => patch(i, { city: e.target.value })}
                    >
                      {cities.map((c) => (
                        <option key={c} value={c}>
                          {c}
                        </option>
                      ))}
                    </select>
                  </Field>
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      {error && <div className="card mark-critical t-small text-critical">{error}</div>}

      {rows.length > 1 && !error && (
        <Section title="Side by side">
          <div className="card card-flush overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Measure</th>
                  {rows.map((r) => (
                    <th key={r.name} className="text-right">
                      {r.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ["Where", (r: (typeof rows)[number]) => `${r.city}`],
                    ["State tax rules", (r: (typeof rows)[number]) => r.state],
                    ["Gross salary", (r: (typeof rows)[number]) => fmt(r.gross)],
                    ["Total tax", (r: (typeof rows)[number]) => fmt(r.total_tax)],
                    ["Effective rate", (r: (typeof rows)[number]) => pct(r.effective_rate)],
                    [
                      "Marginal (fed + state)",
                      (r: (typeof rows)[number]) =>
                        `${pct(r.marginal_fed, 0)} + ${pct(r.marginal_state, 2)}`,
                    ],
                    ["Take-home", (r: (typeof rows)[number]) => fmt(r.annual_take_home)],
                    ["Per month", (r: (typeof rows)[number]) => fmt(r.monthly_take_home)],
                  ] as const
                ).map(([label, render]) => (
                  <tr key={label}>
                    <td className="text-ink">{label}</td>
                    {rows.map((r) => (
                      <td key={r.name} className="font-num text-right whitespace-nowrap">
                        {render(r)}
                      </td>
                    ))}
                  </tr>
                ))}

                {/* The row the page exists for. It is a deflation by the
                    cost-of-living index and nothing more, and it says so. */}
                <tr>
                  <td className="text-ink">
                    <strong>Worth, in national-average dollars</strong>
                    <span className="t-micro block text-muted">
                      take-home ÷ the local cost of living
                    </span>
                  </td>
                  {rows.map((r) => (
                    <td key={r.name} className="font-num text-right whitespace-nowrap">
                      {r.real_take_home === null ? (
                        <span className="text-muted">not indexed</span>
                      ) : (
                        <span
                          className={
                            result?.best === r.name ? "font-medium text-positive" : "text-ink"
                          }
                        >
                          {fmt(r.real_take_home)}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
                <tr>
                  <td className="text-muted">
                    Difference
                    <span className="t-micro block">against {result?.baseline}</span>
                  </td>
                  {rows.map((r) => (
                    <td key={r.name} className="font-num text-right whitespace-nowrap">
                      {r.vs_baseline_real === null ? (
                        "—"
                      ) : Math.abs(r.vs_baseline_real) < 0.5 ? (
                        <span className="text-muted">baseline</span>
                      ) : (
                        <span
                          className={
                            r.vs_baseline_real > 0 ? "text-positive" : "text-critical"
                          }
                        >
                          {r.vs_baseline_real > 0 ? "+" : "−"}
                          {fmt(Math.abs(r.vs_baseline_real))}
                        </span>
                      )}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>

          {/* The verdict is driven by what the engine actually found, not by
              what the sentence would like to be true. It first read "take-home
              alone would rank these differently" unconditionally, and on the
              very first pair tried — New York against Austin — the same city
              won both ways, so the page asserted something false about its own
              table. `col_changes_answer` is the engine answering that. */}
          <p className="t-small mt-3 leading-relaxed text-body">
            {!result?.best ? (
              <>
                One of these places is not in the cost-of-living index, so there is no
                like-for-like ranking. The tax figures above are still exact.
              </>
            ) : result.col_changes_answer ? (
              <>
                <strong className="text-ink">{result.best}</strong> leaves you the most
                once tax and the cost of living are both accounted for — but{" "}
                <strong className="text-ink">{result.best_take_home}</strong> pays more
                take-home. That is the whole reason to look at both: the dearest place
                usually pays the most, which is the wrong answer to the question you are
                asking.
              </>
            ) : (
              <>
                <strong className="text-ink">{result.best}</strong> leaves you the most
                on both measures, so cost of living does not change the answer here — it
                changes the size of it. Compare the take-home row with the one below it.
              </>
            )}
          </p>
          <p className="t-micro mt-2 leading-relaxed text-muted">
            Every figure is 2026 federal and state tax from Rev. Proc. 2025-32 as amended
            by the OBBBA, recalculated from scratch for each column — not the baseline
            scaled by a rate. Cost of living is an index of 44 metros; it covers rent,
            groceries and the rest of the basket, and it does not know what you
            personally spend. Scenarios are saved with the rest of your data.
          </p>
        </Section>
      )}

      <Footer />
    </div>
  );
}
