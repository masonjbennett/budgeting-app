"use client";

/**
 * The recurring bills, on the days of the month they land.
 *
 * `recurring_templates` has been in the data model since the Streamlit app and
 * only the TypeScript TYPE referenced it — no page had ever drawn it. There is
 * no arithmetic here worth the name: these are amounts the user typed, on days
 * the user typed, laid out on a grid.
 *
 * It shows a MONTH SHAPE rather than a real calendar, deliberately. A bill on
 * day 31 does not exist in February, and a grid keyed to a specific month would
 * have to decide what to do about that; a 1–31 shape makes no claim about which
 * month it is and cannot be wrong about one. The days that have nothing on them
 * stay visible, because the gaps are the useful part — that is where a bill can
 * go.
 */

import { fmt, type Profile } from "@/context/FinanceContext";

type Recurring = Profile["recurring_templates"][number];

export default function BillsCalendar({ templates }: { templates: Recurring[] }) {
  if (!templates.length) {
    return (
      <div className="card t-small py-8 text-center text-muted">
        No recurring bills recorded. They live in your profile data — import a file
        that has them, or the demo profile ships with four.
      </div>
    );
  }

  const byDay = new Map<number, Recurring[]>();
  for (const t of templates) {
    const day = Math.min(31, Math.max(1, Math.round(t.day)));
    byDay.set(day, [...(byDay.get(day) ?? []), t]);
  }
  const total = templates.reduce((s, t) => s + t.amount, 0);
  const busiest = Math.max(...templates.map((t) => t.amount), 1);

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="t-small text-body">
          {templates.length} recurring bill{templates.length === 1 ? "" : "s"} ·{" "}
          <span className="font-num text-ink">{fmt(total)}</span> a month
        </p>
        <p className="t-micro text-muted">Day of the month, not a specific one</p>
      </div>

      <div className="grid grid-cols-7 gap-px overflow-hidden rounded-sm border border-hair bg-hair">
        {Array.from({ length: 31 }, (_, i) => i + 1).map((day) => {
          const bills = byDay.get(day) ?? [];
          return (
            <div
              key={day}
              className={`min-h-[62px] p-1.5 ${bills.length ? "bg-raise" : "bg-card"}`}
            >
              <p className="font-num t-micro text-muted">{day}</p>
              {bills.map((b) => (
                <p
                  key={`${b.name}-${b.amount}`}
                  className="mt-1 truncate text-[10px] leading-tight text-body"
                  title={`${b.name} — ${fmt(b.amount)} (${b.category})`}
                >
                  <span
                    className="mr-1 inline-block h-1.5 w-1.5 align-middle bg-accent"
                    style={{ opacity: 0.35 + 0.65 * (b.amount / busiest) }}
                    aria-hidden="true"
                  />
                  {b.name}
                </p>
              ))}
            </div>
          );
        })}
        {/* 31 does not divide by 7, so the last row is short and the grid's
            own backing colour showed through as a solid tan block — which
            reads as a rendering fault rather than as "the month ended". */}
        {Array.from({ length: (7 - (31 % 7)) % 7 }, (_, i) => (
          <div key={`pad-${i}`} className="min-h-[62px] bg-card" aria-hidden="true" />
        ))}
      </div>

      <ul className="mt-4 grid list-none grid-cols-1 gap-x-6 gap-y-1 p-0 sm:grid-cols-2">
        {[...templates]
          .sort((a, b) => a.day - b.day)
          .map((t) => (
            <li key={`${t.name}-${t.day}`} className="t-small flex items-baseline gap-2">
              <span className="font-num t-micro w-8 shrink-0 text-muted">
                {t.day}
              </span>
              <span className="flex-1 truncate text-body">{t.name}</span>
              <span className="t-micro text-muted">{t.category}</span>
              <span className="font-num text-ink">{fmt(t.amount)}</span>
            </li>
          ))}
      </ul>
    </div>
  );
}
