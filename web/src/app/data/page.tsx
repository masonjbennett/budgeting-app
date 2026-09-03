"use client";

import { useRef, useState } from "react";

import { Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, sum, useFinance, type Profile } from "@/context/FinanceContext";

/** Every top-level key a Profile must carry, checked on import. */
const REQUIRED: (keyof Profile)[] = [
  "income",
  "budget",
  "expenses",
  "assets",
  "liabilities",
  "debts",
  "savings_goals",
  "investment",
  "itemized",
];

export default function DataPage() {
  const { profile, user, cloudConfigured, replaceProfile, resetToDemo, resetToEmpty } =
    useFinance();
  const fileRef = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [confirming, setConfirming] = useState<"demo" | "empty" | null>(null);

  if (!profile) return <div className="skeleton h-96" />;

  const download = () => {
    const blob = new Blob([JSON.stringify(profile, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `budget-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setMessage({ text: "Exported.", ok: true });
  };

  const upload = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text());
      // An import replaces everything, so a file that is merely JSON is not
      // enough — a missing key would blank a page rather than fail loudly.
      const missing = REQUIRED.filter((k) => !(k in parsed));
      if (missing.length) {
        setMessage({
          text: `Not a budget export — missing ${missing.join(", ")}.`,
          ok: false,
        });
        return;
      }
      replaceProfile(parsed as Profile);
      setMessage({ text: "Imported. Every page now reflects the file.", ok: true });
    } catch {
      setMessage({ text: "That file isn't valid JSON.", ok: false });
    }
  };

  const stats: [string, string][] = [
    ["Expenses logged", String(profile.expenses.length)],
    ["Budget categories", String(
      Object.keys(profile.budget.needs).length +
        Object.keys(profile.budget.wants).length +
        Object.keys(profile.budget.savings).length,
    )],
    ["Debts", String(profile.debts.length)],
    ["Savings goals", String(profile.savings_goals.length)],
    ["Net-worth snapshots", String(profile.net_worth_snapshots.length)],
    ["Assets tracked", fmt(sum(profile.assets))],
  ];

  return (
    <div>
      <PageHeader
        title="Settings"
        description="Where your figures live, and how to get them out."
      />

      <Section title="Storage">
        <div className="card">
          {!cloudConfigured ? (
            <p className="t-small text-body">
              Accounts are switched off for this deployment. Everything is calculated
              server-side but nothing is stored — your figures live in this browser tab
              only. Export below if you want to keep them.
            </p>
          ) : user ? (
            <>
              <p className="t-small text-body">
                Signed in as <strong className="text-ink">{user.email}</strong>.
                Changes save automatically a moment after you stop typing, and follow
                you to any browser you sign in from.
              </p>
              <p className="t-micro mt-2 leading-relaxed text-muted">
                Your row is readable only by your own account — the database enforces
                that, not the app.
              </p>
            </>
          ) : (
            <p className="t-small text-body">
              Not signed in. Everything works, but your figures live in this browser tab
              only and are gone when you close it. Sign in from the navigation to save
              them, or export below.
            </p>
          )}
        </div>
      </Section>

      <Section title="Your data at a glance">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          {stats.map(([label, value]) => (
            <div key={label} className="card">
              <p className="label leading-snug">{label}</p>
              <p className="font-num t-lead mt-1.5 font-medium text-ink">{value}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Export & import">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className="card">
            <h3 className="label">Export</h3>
            <p className="t-small mt-1.5 text-muted">
              Everything, as JSON — income, budget, expenses, net worth, debts and goals.
            </p>
            <button onClick={download} className="btn-primary mt-3">
              Download JSON
            </button>
          </div>
          <div className="card">
            <h3 className="label">Import</h3>
            <p className="t-small mt-1.5 text-muted">
              Replaces everything currently loaded. Export first if you want a way back.
            </p>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void upload(f);
                e.target.value = "";
              }}
            />
            <button onClick={() => fileRef.current?.click()} className="btn-secondary mt-3">
              Choose a file…
            </button>
          </div>
        </div>
        {message && (
          <p className={`t-small mt-3 ${message.ok ? "text-positive" : "text-critical"}`}>
            {message.text}
          </p>
        )}
      </Section>

      <Section title="Start over">
        <div className="card mark-critical">
          <p className="t-small text-body">
            Reset to the demo profile, or to an empty one. This replaces everything
            loaded now{user ? " and saves over your stored copy" : ""}.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {(["demo", "empty"] as const).map((which) => (
              <button
                key={which}
                onClick={async () => {
                  if (confirming !== which) {
                    setConfirming(which);
                    return;
                  }
                  setConfirming(null);
                  await (which === "demo" ? resetToDemo() : resetToEmpty());
                  setMessage({
                    text: which === "demo" ? "Demo profile loaded." : "Started empty.",
                    ok: true,
                  });
                }}
                onBlur={() => setConfirming(null)}
                className={confirming === which ? "btn-danger" : "btn-secondary"}
              >
                {confirming === which
                  ? "Click again to confirm"
                  : which === "demo"
                    ? "Load demo profile"
                    : "Start empty"}
              </button>
            ))}
          </div>
        </div>
      </Section>

      <Section title="About">
        <div className="card">
          <p className="t-small leading-relaxed text-body">
            Tax figures are IRS 2026 — Rev. Proc. 2025-32 as amended by the OBBBA — with
            brackets for all four filing statuses and every state plus DC. This is an
            estimate for planning, not tax advice, and it does not model credits,
            AMT, or the 2/37 limitation on itemized deductions at the top bracket.
          </p>
          <p className="t-small mt-3 leading-relaxed text-body">
            Every number on this site is calculated by one Python module, which the
            Streamlit version of this app and this one both import. It is covered by
            291 assertions, and none of them re-derive an expected answer with a second
            copy of the algorithm — that is how three copies of this maths came to
            disagree with each other in the first place.
          </p>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
