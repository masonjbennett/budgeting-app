"use client";

import { useMemo, useState } from "react";

import { BarsChart } from "@/components/Chart";
import { Empty, Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, useFinance, type Expense } from "@/context/FinanceContext";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function monthKey(d: Date) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function prettyMonth(key: string) {
  const [y, m] = key.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
  });
}

export default function ExpensesPage() {
  const { profile, update } = useFinance();
  const [draft, setDraft] = useState({
    date: today(),
    amount: 0,
    category: "",
    note: "",
  });
  const [filterMonth, setFilterMonth] = useState<string>(monthKey(new Date()));
  const [filterCat, setFilterCat] = useState<string>("");

  const categories = useMemo(() => {
    if (!profile) return [];
    return [
      ...Object.keys(profile.budget.needs),
      ...Object.keys(profile.budget.wants),
      ...Object.keys(profile.budget.savings),
    ];
  }, [profile]);

  if (!profile) return <div className="skeleton h-96 rounded-xl" />;

  const expenses = [...profile.expenses].sort((a, b) => b.date.localeCompare(a.date));
  const months = Array.from(new Set(expenses.map((e) => e.date.slice(0, 7)))).sort().reverse();

  const visible = expenses.filter(
    (e) =>
      (!filterMonth || e.date.startsWith(filterMonth)) &&
      (!filterCat || e.category === filterCat),
  );
  const visibleTotal = visible.reduce((s, e) => s + e.amount, 0);

  const add = () => {
    const category = draft.category || categories[0];
    if (!category || draft.amount <= 0) return;
    const entry: Expense = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      date: draft.date,
      amount: draft.amount,
      category,
      note: draft.note.trim(),
    };
    update({ expenses: [entry, ...profile.expenses] });
    setDraft({ date: draft.date, amount: 0, category, note: "" });
  };

  const remove = (id: string) =>
    update({ expenses: profile.expenses.filter((e) => e.id !== id) });

  // Month-over-month, from what is recorded. No filler months.
  const byMonth: Record<string, number> = {};
  for (const e of expenses) {
    const k = e.date.slice(0, 7);
    byMonth[k] = (byMonth[k] ?? 0) + e.amount;
  }
  const monthSeries = Object.entries(byMonth)
    .sort((a, b) => a[0].localeCompare(b[0]))
    .slice(-12)
    .map(([k, v]) => ({ name: prettyMonth(k).split(" ")[0].slice(0, 3), value: v }));

  const budgetFor = (cat: string) =>
    profile.budget.needs[cat] ?? profile.budget.wants[cat] ?? profile.budget.savings[cat] ?? 0;

  return (
    <div>
      <PageHeader
        title="Expense Tracker"
        description="Log what you actually spend. The dashboard's spending panel and budget adherence both read from here."
      />

      <Section title="Add an expense">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Date">
            <input
              type="date"
              value={draft.date}
              onChange={(e) => setDraft({ ...draft, date: e.target.value })}
            />
          </Field>
          <Field label="Amount">
            <NumberInput
              value={draft.amount}
              onChange={(v) => setDraft({ ...draft, amount: v })}
              step={1}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="Category">
            <select
              value={draft.category || categories[0] || ""}
              onChange={(e) => setDraft({ ...draft, category: e.target.value })}
            >
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Note">
            <input
              type="text"
              placeholder="Optional"
              value={draft.note}
              onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && add()}
            />
          </Field>
          <div className="flex items-end">
            <button
              onClick={add}
              disabled={draft.amount <= 0 || categories.length === 0}
              className="btn-primary w-full disabled:opacity-40"
            >
              Add
            </button>
          </div>
        </div>
        {categories.length === 0 && (
          <p className="mt-2 text-[0.72rem] text-yellow">
            Add some budget categories first — an expense needs somewhere to go.
          </p>
        )}
      </Section>

      {monthSeries.length > 1 && (
        <Section title="Spending by month">
          <BarsChart
            data={monthSeries}
            xKey="name"
            valueKey="value"
            colors={monthSeries.map(() => "#5b8def")}
            height={240}
          />
        </Section>
      )}

      <Section
        title={`Transactions · ${fmt(visibleTotal)} across ${visible.length}`}
        action={
          <div className="flex gap-2">
            <select
              value={filterMonth}
              onChange={(e) => setFilterMonth(e.target.value)}
              className="w-auto py-1 text-[0.72rem]"
            >
              <option value="">All months</option>
              {months.map((m) => (
                <option key={m} value={m}>
                  {prettyMonth(m)}
                </option>
              ))}
            </select>
            <select
              value={filterCat}
              onChange={(e) => setFilterCat(e.target.value)}
              className="w-auto py-1 text-[0.72rem]"
            >
              <option value="">All categories</option>
              {Array.from(new Set(expenses.map((e) => e.category))).map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        }
      >
        {visible.length === 0 ? (
          <Empty>Nothing recorded for this filter.</Empty>
        ) : (
          <div className="card overflow-x-auto p-0">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Category</th>
                  <th>Note</th>
                  <th className="text-right">Amount</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((e) => {
                  const b = budgetFor(e.category);
                  return (
                    <tr key={e.id}>
                      <td className="whitespace-nowrap font-num">{e.date}</td>
                      <td className="text-dim">
                        {e.category}
                        {b > 0 && (
                          <span className="ml-1.5 text-[0.68rem] text-muted">
                            ({fmt(b)}/mo budgeted)
                          </span>
                        )}
                      </td>
                      <td className="text-muted">{e.note || "—"}</td>
                      <td className="whitespace-nowrap text-right font-num text-primary">
                        {fmt(e.amount, 2)}
                      </td>
                      <td className="w-8 text-right">
                        <button
                          onClick={() => remove(e.id)}
                          aria-label="Delete expense"
                          className="text-muted transition-colors hover:text-red"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Footer />
    </div>
  );
}
