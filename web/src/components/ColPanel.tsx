"use client";

/**
 * What this salary is worth somewhere else.
 *
 * BUYING POWER ONLY, and the card says so. Two metros can differ by tens of
 * thousands on state tax alone, and this comparison knows nothing about that —
 * quietly implying otherwise would be the most misleading thing on the site,
 * because the whole claim of the app is that its numbers are real. An unknown
 * city comes back as null from the engine rather than falling back to the
 * national average, and the card renders that as "not measured".
 */

import { useEffect, useState } from "react";

import { Field } from "@/components/Field";
import { fmt, pct } from "@/context/FinanceContext";
import { api, ApiError, type ColComparison } from "@/lib/api";

export default function ColPanel({
  salary,
  cities,
}: {
  salary: number;
  cities: string[];
}) {
  const [from, setFrom] = useState("National Average");
  const [to, setTo] = useState("New York, NY");
  const [result, setResult] = useState<ColComparison | null>(null);
  const [missing, setMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!cities.length) return;
    let live = true;
    api
      .costOfLiving({ salary, from_city: from, to_city: to })
      .then((r) => {
        if (!live) return;
        setResult(r.comparison);
        setMissing(r.comparison === null);
        setError(null);
      })
      .catch((e) =>
        live && setError(e instanceof ApiError ? e.message : "Could not compare"),
      );
    return () => {
      live = false;
    };
  }, [salary, from, to, cities.length]);

  if (!cities.length) {
    return <div className="skeleton h-32" />;
  }

  const dearer = result ? result.pct_difference > 0 : false;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-3 lg:col-span-1">
        <Field label="Living in">
          <select value={from} onChange={(e) => setFrom(e.target.value)}>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Compared with">
          <select value={to} onChange={(e) => setTo(e.target.value)}>
            {cities.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </Field>
      </div>

      <div className="lg:col-span-2">
        {error ? (
          <div className="card mark-critical t-small text-critical">{error}</div>
        ) : missing || !result ? (
          <div className="card t-small text-muted">
            No cost-of-living index for one of those places, so this is not measured.
          </div>
        ) : (
          <div className="card">
            <p className="label">To live the same way in {result.to_city}</p>
            <p className="font-num t-h2 mt-1.5 leading-none font-medium text-ink">
              {fmt(result.equivalent_salary)}
            </p>
            <p className="t-small mt-2 text-body">
              against your {fmt(result.salary)} in {result.from_city} —{" "}
              <span className={dearer ? "text-critical" : "text-positive"}>
                {dearer ? "+" : "−"}
                {fmt(Math.abs(result.difference))} ({pct(Math.abs(result.pct_difference), 0)}{" "}
                {dearer ? "dearer" : "cheaper"})
              </span>
              .
            </p>
            <p className="t-micro mt-3 border-t border-hair-soft pt-2.5 text-muted">
              Buying power only. It does not include tax, and the two places can differ
              by thousands on state tax alone — change the state on this page to see
              what that does to your take-home.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
