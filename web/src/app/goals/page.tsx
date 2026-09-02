"use client";

import { useState } from "react";

import { Empty, Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, useFinance, type Goal } from "@/context/FinanceContext";

function monthsUntil(deadline: string): number | null {
  if (!deadline) return null;
  const end = new Date(`${deadline}T00:00:00`);
  if (Number.isNaN(end.getTime())) return null;
  const now = new Date();
  const m =
    (end.getFullYear() - now.getFullYear()) * 12 +
    (end.getMonth() - now.getMonth()) +
    (end.getDate() >= now.getDate() ? 0 : -1);
  return m;
}

export default function GoalsPage() {
  const { profile, update } = useFinance();
  const [draft, setDraft] = useState<Goal>({
    name: "",
    target: 0,
    current: 0,
    deadline: "",
  });

  if (!profile) return <div className="skeleton h-96 rounded-xl" />;

  const goals = profile.savings_goals;
  const setGoals = (g: Goal[]) => update({ savings_goals: g });
  const patch = (i: number, p: Partial<Goal>) =>
    setGoals(goals.map((g, j) => (j === i ? { ...g, ...p } : g)));

  const add = () => {
    if (!draft.name.trim() || draft.target <= 0) return;
    setGoals([...goals, { ...draft, name: draft.name.trim() }]);
    setDraft({ name: "", target: 0, current: 0, deadline: "" });
  };

  const totalTarget = goals.reduce((s, g) => s + g.target, 0);
  const totalSaved = goals.reduce((s, g) => s + g.current, 0);

  return (
    <div>
      <PageHeader
        title="Savings Goals"
        description="What you're saving towards, how far along you are, and what it takes each month to land on time."
      />

      {goals.length > 0 && (
        <div className="stagger mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            ["Goals", String(goals.length)],
            ["Saved so far", fmt(totalSaved)],
            ["Total target", fmt(totalTarget)],
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
      )}

      <Section title="Goals">
        {goals.length === 0 ? (
          <Empty>No goals yet. Add one below.</Empty>
        ) : (
          <div className="space-y-3">
            {goals.map((g, i) => {
              const share = g.target > 0 ? Math.min((g.current / g.target) * 100, 100) : 0;
              const remaining = Math.max(0, g.target - g.current);
              const m = monthsUntil(g.deadline);
              const done = remaining === 0;
              return (
                <div key={`${g.name}-${i}`} className="card">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div>
                      <p className="text-[0.9rem] font-semibold text-primary">{g.name}</p>
                      <p className="mt-0.5 text-[0.72rem] text-muted">
                        {fmt(g.current)} of {fmt(g.target)} · {share.toFixed(0)}%
                      </p>
                    </div>
                    <div className="text-right">
                      {done ? (
                        <span className="badge badge-green">Funded</span>
                      ) : m === null ? (
                        <p className="text-[0.72rem] text-muted">
                          {fmt(remaining)} to go · no deadline set
                        </p>
                      ) : m <= 0 ? (
                        <p className="text-[0.72rem] text-red">
                          {fmt(remaining)} short, deadline passed
                        </p>
                      ) : (
                        <p className="text-[0.72rem] text-dim">
                          <strong className="font-num text-primary">
                            {fmt(remaining / m)}
                          </strong>
                          /mo for {m} month{m === 1 ? "" : "s"}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="progress-track mt-3">
                    <div
                      className={`progress-fill ${
                        done ? "bg-green" : share >= 50 ? "bg-accent" : "bg-yellow"
                      }`}
                      style={{ width: `${share}%` }}
                    />
                  </div>

                  <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-4">
                    <Field label="Name">
                      <input
                        type="text"
                        value={g.name}
                        onChange={(e) => patch(i, { name: e.target.value })}
                      />
                    </Field>
                    <Field label="Saved">
                      <NumberInput
                        value={g.current}
                        onChange={(v) => patch(i, { current: v })}
                        step={100}
                        min={0}
                        prefix="$"
                      />
                    </Field>
                    <Field label="Target">
                      <NumberInput
                        value={g.target}
                        onChange={(v) => patch(i, { target: v })}
                        step={500}
                        min={0}
                        prefix="$"
                      />
                    </Field>
                    <div className="flex items-end gap-2">
                      <div className="flex-1">
                        <Field label="Deadline">
                          <input
                            type="date"
                            value={g.deadline}
                            onChange={(e) => patch(i, { deadline: e.target.value })}
                          />
                        </Field>
                      </div>
                      <button
                        onClick={() => setGoals(goals.filter((_, j) => j !== i))}
                        aria-label={`Remove ${g.name}`}
                        className="mb-[1px] rounded-lg border border-white/[0.08] px-2.5 py-2 text-[0.75rem] text-muted transition-colors hover:border-red/40 hover:text-red"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Section>

      <Section title="Add a goal">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Name">
            <input
              type="text"
              placeholder="Down payment"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
          </Field>
          <Field label="Target">
            <NumberInput
              value={draft.target}
              onChange={(v) => setDraft({ ...draft, target: v })}
              step={500}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Saved so far">
            <NumberInput
              value={draft.current}
              onChange={(v) => setDraft({ ...draft, current: v })}
              step={100}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Deadline">
            <input
              type="date"
              value={draft.deadline}
              onChange={(e) => setDraft({ ...draft, deadline: e.target.value })}
            />
          </Field>
          <div className="flex items-end">
            <button
              onClick={add}
              disabled={!draft.name.trim() || draft.target <= 0}
              className="btn-primary w-full disabled:opacity-40"
            >
              Add goal
            </button>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
