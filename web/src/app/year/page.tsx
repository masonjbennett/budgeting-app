"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import AnimatedNumber from "@/components/AnimatedNumber";
import { BarsChart } from "@/components/Chart";
import { Empty, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import StatusCard from "@/components/StatusCard";
import { api, ApiError, type YearToDate } from "@/lib/api";
import { fmt, pct, useFinance } from "@/context/FinanceContext";

/**
 * Today, in the BROWSER's timezone.
 *
 * `toISOString()` is UTC, and this is the one place in the app where that
 * difference changes an answer: for the seven hours after midnight in Chicago
 * on the 31st of December, UTC is already into the next year and this page
 * would report a year that has one day in it. The dashboard reads local time
 * for the same reason, and the two must agree about which month it is.
 */
function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
    d.getDate(),
  ).padStart(2, "0")}`;
}

function prettyMonth(key: string): string {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

/** A list of month names, said the way a person would. Formatting only. */
function nameMonths(keys: string[]): string {
  const names = keys.map((k) => prettyMonth(k).split(" ")[0]);
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} and ${names[1]}`;
  return `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`;
}

export default function YearPage() {
  const { profile } = useFinance();
  const [ytd, setYtd] = useState<YearToDate | null>(null);
  const [error, setError] = useState<string | null>(null);

  const payload = profile && {
    income: profile.income,
    itemized: profile.itemized,
    expenses: profile.expenses,
    budget: profile.budget,
  };
  const key = JSON.stringify(payload);

  useEffect(() => {
    if (!payload) return;
    // `today` is read HERE rather than during render: the server has no idea
    // what day it is where the reader is, and a date in the markup would be a
    // hydration mismatch as well as the wrong year for seven hours a night.
    let live = true;
    api
      .yearToDate({ ...payload, today: localToday() })
      .then((y) => live && (setYtd(y), setError(null)))
      .catch(
        (e) =>
          live &&
          (setYtd(null),
          setError(e instanceof ApiError ? e.message : "Could not measure the year.")),
      );
    return () => {
      live = false;
    };
    // The payload is compared by VALUE — object identity changes on every
    // render of the provider, and refetching the year on each keystroke
    // elsewhere in the app is a request per character.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (error) {
    return (
      <div className="card mark-critical">
        <h2 className="t-lead">Something went wrong</h2>
        <p className="t-small mt-1 text-body">{error}</p>
      </div>
    );
  }
  if (!profile || !ytd) {
    return (
      <div className="space-y-8">
        <div className="skeleton h-[9.5rem] w-full" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="skeleton h-28" />
          ))}
        </div>
        <div className="skeleton h-72 w-full" />
      </div>
    );
  }

  const measured = ytd.documented_months > 0;
  const variance = ytd.variance;
  const monthWord = (n: number) => `${n} month${n === 1 ? "" : "s"}`;

  // Consecutive months with no records, collapsed into runs so the chart can
  // shade each stretch once. Grouping a boolean the engine already returned is
  // presentation — it decides nothing and no figure depends on it.
  const undocumentedRuns: { from: string; to: string; label?: string }[] = [];
  for (const m of ytd.by_month) {
    if (m.has_data || m.in_progress) continue;
    const last = undocumentedRuns[undocumentedRuns.length - 1];
    const prevIdx = ytd.by_month.findIndex((x) => x.label === last?.to);
    const thisIdx = ytd.by_month.findIndex((x) => x.label === m.label);
    if (last && thisIdx === prevIdx + 1) last.to = m.label;
    else undocumentedRuns.push({ from: m.label, to: m.label });
  }
  for (const run of undocumentedRuns) run.label = "nothing logged";

  return (
    <div>
      <PageHeader
        title={`${ytd.year} so far`}
        description="The dashboard is one month wide. This is the same money over the calendar year — what has gone out, what has been kept, and how it sits against the plan."
      />

      {/* ── The hero: the one figure that needs no caveat ────────────── */}
      <header className="animate-fade-in mb-9 border-b border-hair pb-7">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-3">
          <div>
            <p className="label">Spent in {ytd.year}</p>
            <p className="mt-1.5">
              <AnimatedNumber value={ytd.spent} className="figure-hero" title={fmt(ytd.spent)} />
            </p>
            <p className="t-small mt-2 text-muted">
              <span className="font-num text-body">{ytd.transactions}</span> transaction
              {ytd.transactions === 1 ? "" : "s"} across{" "}
              <span className="font-num text-body">
                {ytd.by_month.filter((m) => m.has_data).length}
              </span>{" "}
              month{ytd.by_month.filter((m) => m.has_data).length === 1 ? "" : "s"}
              {ytd.future_dated > 0 && (
                <>
                  {" · "}
                  <span className="text-caution">
                    {ytd.future_dated} dated in the future
                  </span>
                </>
              )}
            </p>
          </div>
          <div className="text-right">
            <p className="label">{ytd.current_month.label} so far</p>
            <p className="font-num t-h3 mt-1 leading-none font-medium text-ink">
              {fmt(ytd.current_month.spent)}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              Still running ·{" "}
              <Link href="/" className="text-accent hover:underline">
                dashboard
              </Link>
            </p>
          </div>
        </div>
      </header>

      {/* ── The caveat comes BEFORE anything measured against it ───────
             A missing month looks exactly like a frugal one, and the error is
             always in the flattering direction: eight months of budget against
             one month of records reads as thousands under. Every figure below
             is on the documented basis for that reason, and this says which
             months that is. ─────────────────────────────────────────────── */}
      {!measured ? (
        <Empty>
          {ytd.months_complete === 0 ? (
            <>
              {ytd.year} is still in its first month, so there is no completed
              month to measure yet. The{" "}
              <Link href="/" className="text-accent hover:underline">
                dashboard
              </Link>{" "}
              has {ytd.current_month.label} as it stands.
            </>
          ) : (
            <>
              No completed month of {ytd.year} has any expenses logged, so there is
              nothing to compare against the plan.{" "}
              <Link href="/expenses" className="text-accent hover:underline">
                Log some expenses →
              </Link>
            </>
          )}
        </Empty>
      ) : (
        <>
          {!ytd.complete_record && (
            <div className="card mark-caution mb-8">
              <p className="t-small text-body">
                <span className="text-caution">
                  {nameMonths(ytd.undocumented_months)}{" "}
                  {ytd.undocumented_months.length === 1 ? "has" : "have"} nothing logged.
                </span>{" "}
                Every figure below is measured over the{" "}
                {monthWord(ytd.documented_months)} that {ytd.documented_months === 1 ? "does" : "do"}{" "}
                have records, against{" "}
                <span className="font-num">{fmt(ytd.budget_documented)}</span> of budget
                for the same {monthWord(ytd.documented_months)} — not against the whole
                year, which would compare {monthWord(ytd.months_complete)} of plan to{" "}
                {monthWord(ytd.documented_months)} of spending and report you{" "}
                <span className="font-num">
                  {fmt(ytd.budget_to_date - ytd.spent_documented)}
                </span>{" "}
                under.
              </p>
            </div>
          )}

          {/* ── Against the plan ───────────────────────────────────── */}
          <p className="label mb-3">
            Against the plan · {monthWord(ytd.documented_months)} on record
          </p>
          <div className="stagger mb-11 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatusCard
              label="Budget variance"
              value={fmt(Math.abs(variance ?? 0))}
              status={(variance ?? 0) >= 0 ? "Under" : "Over"}
              tone={(variance ?? 0) >= 0 ? "positive" : "critical"}
              description={`${fmt(ytd.spent_documented)} spent against ${fmt(
                ytd.budget_documented,
              )} budgeted over ${monthWord(ytd.documented_months)}.`}
            />
            <div className="card">
              <p className="label">Monthly pace</p>
              <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                {fmt(ytd.pace)}
              </p>
              <p className="t-micro mt-2 text-muted">
                Average across {monthWord(ytd.documented_months)} of records, against{" "}
                {fmt(ytd.budget_monthly)} budgeted.
              </p>
            </div>
            <div className="card">
              <p className="label">On this pace, the year</p>
              <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                {fmt(ytd.projected_year_end)}
              </p>
              <p className="t-micro mt-2 text-muted">
                {ytd.documented_months === 1 ? (
                  <span className="text-caution">
                    Extrapolated from a single month — one number is not yet a rate.
                  </span>
                ) : (
                  <>
                    Against {fmt(ytd.budget_year)} of plan ·{" "}
                    <span
                      className={
                        (ytd.projected_vs_budget ?? 0) >= 0 ? "text-positive" : "text-critical"
                      }
                    >
                      {fmt(Math.abs(ytd.projected_vs_budget ?? 0))}{" "}
                      {(ytd.projected_vs_budget ?? 0) >= 0 ? "under" : "over"}
                    </span>
                  </>
                )}
              </p>
            </div>
            {ytd.savings_rate === null ? (
              <StatusCard
                label="Kept"
                value="—"
                status="Needs income"
                tone="info"
                description="Enter a salary on Income to measure what the year has kept."
              />
            ) : (
              <StatusCard
                label="Kept"
                value={fmt(ytd.saved)}
                status={
                  ytd.savings_rate >= 20
                    ? "Strong"
                    : ytd.savings_rate >= 10
                      ? "Building"
                      : ytd.savings_rate >= 0
                        ? "Thin"
                        : "Negative"
                }
                tone={
                  ytd.savings_rate >= 20
                    ? "positive"
                    : ytd.savings_rate >= 10
                      ? "caution"
                      : "critical"
                }
                description={`${pct(ytd.savings_rate, 0)} of the ${fmt(
                  ytd.take_home_documented,
                )} taken home over the same ${monthWord(ytd.documented_months)}.`}
              />
            )}
          </div>

          {/* ── The three buckets ──────────────────────────────────── */}
          <Section title="By bucket">
            <div className="card card-flush overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    {/* "Per month" is hidden on a phone. Five columns are
                        414px against the 335px a 375px phone offers, so
                        Variance — the column this page exists for — sat off
                        screen. The monthly rate is the least load-bearing of
                        the five: "Budgeted" is the year-to-date figure that
                        Spent and Variance are actually measured against. */}
                    <th>Bucket</th>
                    <th className="hidden text-right sm:table-cell">Per month</th>
                    <th className="text-right">Budgeted</th>
                    <th className="text-right">Spent</th>
                    <th className="text-right">Variance</th>
                  </tr>
                </thead>
                <tbody>
                  {ytd.by_bucket.map((b) => (
                    <tr key={b.bucket}>
                      <td className="text-ink">{b.bucket}</td>
                      <td className="font-num hidden text-right sm:table-cell">
                        {b.budget_monthly > 0 ? fmt(b.budget_monthly) : "—"}
                      </td>
                      <td className="font-num text-right">
                        {b.budget_monthly > 0 ? fmt(b.budget_to_date) : "—"}
                      </td>
                      <td className="font-num text-right text-ink">{fmt(b.spent)}</td>
                      <td
                        className={`font-num text-right ${
                          b.variance >= 0 ? "text-positive" : "text-critical"
                        }`}
                      >
                        {b.variance >= 0 ? "+" : "−"}
                        {fmt(Math.abs(b.variance))}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="t-micro mt-2 leading-relaxed text-muted">
              Money budgeted to <span className="text-body">Savings</span> is usually
              not logged as an expense, so that row reads as under-spent by design —
              which is why the buckets are shown separately rather than rolled into
              one number. <span className="text-body">Unbudgeted</span>, where it
              appears, is spending against a category the budget does not have.
            </p>
          </Section>
        </>
      )}

      {/* ── Every month of the year that has begun ─────────────────── */}
      <Section title="Month by month">
        <BarsChart
          data={ytd.by_month.map((m) => ({ name: m.label, value: m.spent }))}
          xKey="name"
          valueKey="value"
          tones={ytd.by_month.map((m) => (m.in_progress ? "s2" : "accent"))}
          // A month with nothing logged is SHADED, not drawn faint. Faint was
          // the first version and it rendered nothing at all: a zero-value bar
          // is no element in Recharts, so seven undocumented months were
          // indistinguishable from the space between two bars — under a note
          // telling the reader to look for faint bars that did not exist.
          bands={undocumentedRuns}
          reference={
            ytd.budget_monthly > 0
              ? { value: ytd.budget_monthly, label: `${fmt(ytd.budget_monthly)} budgeted` }
              : undefined
          }
          height={260}
        />
        <p className="t-micro mt-2 leading-relaxed text-muted">
          {undocumentedRuns.length > 0 && (
            <>
              The shaded stretch is months with nothing logged — not months in
              which nothing was spent, which is why no bar is drawn there rather
              than a bar of zero.{" "}
            </>
          )}
          {ytd.current_month.label} is drawn in blue because it is still running,
          so its bar is short for a reason that has nothing to do with spending.
        </p>
      </Section>

      {/* ── Categories ────────────────────────────────────────────── */}
      {measured && ytd.by_category.some((c) => c.spent > 0 || c.budget_monthly > 0) && (
        <Section title="By category">
          <div className="card card-flush overflow-x-auto">
            <table>
              <thead>
                <tr>
                  {/* On a phone this is Category · Budgeted · Spent ·
                      Variance. Six columns are 539px against 335px, so
                      Spent, Of budget AND Variance were all off screen —
                      every number the table carries.

                      The two that go are the two that are recoverable from
                      what stays: "Of budget" is Spent over Budgeted, and
                      "Bucket" is a grouping rather than a measurement.
                      Budgeted stays because Variance is meaningless without
                      the figure it is measured against. */}
                  <th>Category</th>
                  <th className="hidden sm:table-cell">Bucket</th>
                  <th className="text-right">Budgeted</th>
                  <th className="text-right">Spent</th>
                  <th className="hidden text-right sm:table-cell">Of budget</th>
                  <th className="text-right">Variance</th>
                </tr>
              </thead>
              <tbody>
                {ytd.by_category
                  .filter((c) => c.spent > 0 || c.budget_monthly > 0)
                  .map((c) => (
                    <tr key={c.category}>
                      <td className="text-ink">{c.category}</td>
                      <td className="hidden text-muted sm:table-cell">{c.bucket ?? "—"}</td>
                      <td className="font-num text-right">
                        {c.budget_monthly > 0 ? fmt(c.budget_to_date) : "not budgeted"}
                      </td>
                      <td className="font-num text-right text-ink">{fmt(c.spent)}</td>
                      <td
                        className={`font-num hidden text-right sm:table-cell ${c.over ? "text-critical" : "text-muted"}`}
                      >
                        {c.pct_of_budget === null ? "—" : pct(c.pct_of_budget, 0)}
                      </td>
                      <td
                        className={`font-num text-right ${
                          c.budget_monthly <= 0
                            ? "text-muted"
                            : c.variance >= 0
                              ? "text-positive"
                              : "text-critical"
                        }`}
                      >
                        {c.budget_monthly <= 0 ? (
                          "—"
                        ) : (
                          <>
                            {c.variance >= 0 ? "+" : "−"}
                            {fmt(Math.abs(c.variance))}
                          </>
                        )}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
          <p className="t-micro mt-2 text-muted">
            Budgeted is {monthWord(ytd.documented_months)} of that category&apos;s
            monthly amount, matching the months the spending is drawn from.
          </p>
        </Section>
      )}

      <Footer />
    </div>
  );
}
