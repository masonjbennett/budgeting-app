"use client";

import { useMemo, useState } from "react";

import BillsCalendar from "@/components/BillsCalendar";
import ImportPanel from "@/components/ImportPanel";
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

/* "2026-09-03" -> "Sep 3", for the phone-width date column.
   Formatting, not arithmetic — the value is the string the profile stores.

   Built from the PARTS rather than `new Date(iso)`, which parses a bare
   date as UTC midnight and therefore renders as the day BEFORE for every
   reader west of Greenwich. An expense list is exactly where that would go
   unnoticed: every row is off by one, each one still looks like a date, and
   it only misleads at a month boundary. `prettyMonth` above avoids it the
   same way. */
function shortDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  if (!y || !m || !d) return iso;
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
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
  // Collapsed by default. The panel is the biggest thing on this page when it
  // is open, and typing one expense is the common visit.
  const [importing, setImporting] = useState(false);
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

  if (!profile) return <div className="skeleton h-96" />;

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
        title="Expenses"
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
              className="btn-primary w-full"
            >
              Add
            </button>
          </div>
        </div>
        {categories.length === 0 && (
          <p className="t-micro mt-2 text-caution">
            Add some budget categories first — an expense needs somewhere to go.
          </p>
        )}
      </Section>

      <Section
        title="Import from a bank CSV"
        action={
          <button className="btn-ghost" onClick={() => setImporting((v) => !v)}>
            {importing ? "Hide" : "Open importer"}
          </button>
        }
      >
        {importing ? (
          <ImportPanel categories={categories} />
        ) : (
          <p className="t-small text-muted">
            Export a statement from your bank and read it in here. Every row is
            shown with the date it parsed to, the amount, and the category it was
            matched to, before any of it is added — and importing only ever adds,
            so nothing you typed can be replaced by a bank&apos;s version of it.
          </p>
        )}
      </Section>

      <Section title="Recurring bills">
        <BillsCalendar templates={profile.recurring_templates ?? []} />
      </Section>

      {monthSeries.length > 1 && (
        <Section title="Spending by month">
          <BarsChart
            data={monthSeries}
            xKey="name"
            valueKey="value"
            tones={monthSeries.map(() => "accent" as const)}
            height={230}
          />
        </Section>
      )}

      <Section
        title={`Transactions · ${fmt(visibleTotal)} across ${visible.length}`}
        action={
          /* Wraps, and each select is capped at half the row.

             These are `w-auto`, so a select is as wide as its widest OPTION —
             which is a category name the user typed, not anything this page
             chose. On a touch device they are also 16px rather than 11px, so
             that they do not zoom the viewport on focus (see globals.css), and
             at that size the pair no longer fits one phone-width line.

             Capped at the ROW, not at half of it. `max-w-[48%]` was the first
             version and it truncated the value inside the control: the month
             filter read "September 202", a clipped date that still reads as a
             date. Wrapping already solves the pair — at their natural widths
             they are 215px and 200px against 335px available, so they simply
             take a line each. The cap now only bites when one select alone
             cannot fit, which needs a category name longer than the phone. */
          <div className="flex max-w-full flex-wrap justify-end gap-2">
            <select
              value={filterMonth}
              onChange={(e) => setFilterMonth(e.target.value)}
              className="t-micro w-auto max-w-full py-1"
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
              className="t-micro w-auto max-w-full py-1"
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
          <div className="card card-flush overflow-x-auto">
            <table>
              <thead>
                <tr>
                  {/* On a phone this is Date · Category · Amount.

                      AMOUNT IS THE COLUMN THIS TABLE EXISTS FOR AND IT WAS THE
                      ONE OFF SCREEN. The five columns are 557px against the
                      335px a 375px phone offers, and the order put Amount
                      fourth — so the page showed a list of transactions with
                      no amounts on it, inside a scroller with nothing marking
                      that there was more to the right.

                      Three things go, worth 222px between them: the note
                      (108px, the most secondary field and the one the
                      category already gestures at), the "($280/mo budgeted)"
                      annotation beside each category, and the ISO date, which
                      becomes "Sep 3" — the year is redundant under a filter
                      that names the month. All return at 640px. */}
                  <th>Date</th>
                  <th>Category</th>
                  <th className="hidden sm:table-cell">Note</th>
                  <th className="text-right">Amount</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visible.map((e) => {
                  const b = budgetFor(e.category);
                  return (
                    <tr key={e.id}>
                      <td className="font-num whitespace-nowrap">
                        <span className="sm:hidden">{shortDate(e.date)}</span>
                        <span className="hidden sm:inline">{e.date}</span>
                      </td>
                      <td className="text-ink">
                        {e.category}
                        {b > 0 && (
                          <span className="t-micro ml-1.5 hidden text-muted sm:inline">
                            ({fmt(b)}/mo budgeted)
                          </span>
                        )}
                      </td>
                      <td className="hidden text-muted sm:table-cell">{e.note || "—"}</td>
                      <td className="font-num text-right whitespace-nowrap text-ink">
                        {fmt(e.amount, 2)}
                      </td>
                      <td className="w-8 text-right">
                        <button
                          onClick={() => remove(e.id)}
                          aria-label="Delete expense"
                          className="btn-remove-quiet"
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
