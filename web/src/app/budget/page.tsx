"use client";

import { useState } from "react";

import { DonutChart } from "@/components/Chart";
import { NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, pct, sum, useFinance } from "@/context/FinanceContext";

type Bucket = "needs" | "wants" | "savings";

// The 50/30/20 rule is a guideline the page STATES, not a calculation. It has
// no inputs and no edge cases, so it does not belong behind an HTTP call.
const BUCKETS: { key: Bucket; label: string; share: number; blurb: string }[] = [
  { key: "needs", label: "Needs", share: 0.5, blurb: "Rent, utilities, groceries, minimum debt payments." },
  { key: "wants", label: "Wants", share: 0.3, blurb: "Dining, entertainment, shopping, travel." },
  { key: "savings", label: "Savings", share: 0.2, blurb: "Emergency fund, investing, extra debt payments." },
];

export default function BudgetPage() {
  const { profile, dashboard, update } = useFinance();
  const [tab, setTab] = useState<Bucket>("needs");
  const [newName, setNewName] = useState("");

  if (!profile || !dashboard) return <div className="skeleton h-96" />;

  const budget = profile.budget;
  const monthly = dashboard.take_home.monthly_take_home;
  const allocated = sum(budget.needs) + sum(budget.wants) + sum(budget.savings);
  const left = monthly - allocated;

  const setLine = (bucket: Bucket, name: string, value: number) =>
    update({ budget: { ...budget, [bucket]: { ...budget[bucket], [name]: value } } });

  const removeLine = (bucket: Bucket, name: string) => {
    const next = { ...budget[bucket] };
    delete next[name];
    update({ budget: { ...budget, [bucket]: next } });
  };

  const addLine = () => {
    const name = newName.trim();
    if (!name || name in budget[tab]) return;
    setLine(tab, name, 0);
    setNewName("");
  };

  return (
    <div>
      <PageHeader
        title="Budget"
        description="Allocate your monthly take-home across needs, wants and savings. Changes save automatically."
      />

      <div className={`card mb-6 ${left >= 0 ? "mark-accent" : "mark-critical"}`}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="t-small text-body">
            Monthly take-home <strong className="font-num text-ink">{fmt(monthly)}</strong> ·
            allocated <strong className="font-num text-ink">{fmt(allocated)}</strong>
          </span>
          <span
            className={`font-num t-small font-medium ${
              left >= 0 ? "text-positive" : "text-critical"
            }`}
          >
            {left >= 0 ? `${fmt(left)} unallocated` : `${fmt(Math.abs(left))} over budget`}
          </span>
        </div>
      </div>

      <div className="tab-list mb-6 flex-wrap">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            onClick={() => setTab(b.key)}
            className={`tab ${tab === b.key ? "tab-active" : ""}`}
          >
            {b.label} · {fmt(sum(budget[b.key]))}
          </button>
        ))}
      </div>

      <Section title={`${BUCKETS.find((b) => b.key === tab)!.label} lines`}>
        <p className="t-small mb-4 text-muted">{BUCKETS.find((b) => b.key === tab)!.blurb}</p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {Object.entries(budget[tab]).map(([name, amount]) => (
            <div key={name} className="flex items-end gap-2">
              <div className="flex-1">
                <label className="t-small mb-1.5 block font-medium text-body">{name}</label>
                <NumberInput
                  value={amount}
                  onChange={(v) => setLine(tab, name, v)}
                  step={10}
                  min={0}
                  prefix="$"
                />
              </div>
              <button
                onClick={() => removeLine(tab, name)}
                aria-label={`Remove ${name}`}
                className="btn-remove"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        <div className="mt-4 flex gap-2">
          <input
            type="text"
            placeholder="Add a category…"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addLine()}
            className="max-w-xs"
          />
          <button onClick={addLine} disabled={!newName.trim()} className="btn-secondary">
            Add
          </button>
        </div>
      </Section>

      <Section title="Against the 50/30/20 guideline">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
          {BUCKETS.map((b) => {
            const total = sum(budget[b.key]);
            const target = monthly * b.share;
            const shareOfPlan = allocated > 0 ? (total / allocated) * 100 : 0;
            const over = target > 0 && total > target;
            return (
              <div key={b.key} className="card">
                <div className="flex items-baseline justify-between">
                  <p className="label">
                    {b.label} · {Math.round(b.share * 100)}%
                  </p>
                  <p className="font-num t-micro text-muted">{pct(shareOfPlan, 0)} of plan</p>
                </div>
                <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                  {fmt(total)}
                </p>
                <p className="t-micro mt-1.5 text-muted">
                  Guideline {fmt(target)}
                  {target > 0 && (
                    <span className={over ? "text-critical" : "text-positive"}>
                      {" "}
                      · {over ? "over by " : "under by "}
                      {fmt(Math.abs(total - target))}
                    </span>
                  )}
                </p>
                <div className="progress-track mt-3">
                  <div
                    className={`progress-fill ${over ? "bg-critical" : "bg-accent"}`}
                    style={{
                      width: `${target > 0 ? Math.min((total / target) * 100, 100) : 0}%`,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {allocated > 0 && (
        <Section title="Plan by category">
          <DonutChart
            data={BUCKETS.flatMap((b) =>
              Object.entries(budget[b.key])
                .filter(([, v]) => v > 0)
                .map(([name, value]) => ({ name, value })),
            )}
            height={320}
          />
        </Section>
      )}

      <Footer />
    </div>
  );
}
