"use client";

import { useState } from "react";

import { TrendChart } from "@/components/Chart";
import { Empty, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { fmt, sum, useFinance, type Snapshot } from "@/context/FinanceContext";

function Ledger({
  title,
  rows,
  onChange,
  onRemove,
  onAdd,
  tone,
}: {
  title: string;
  rows: Record<string, number>;
  onChange: (name: string, v: number) => void;
  onRemove: (name: string) => void;
  onAdd: (name: string) => void;
  tone: "positive" | "critical";
}) {
  const [name, setName] = useState("");
  const total = sum(rows);
  return (
    <div className="card">
      <div className="mb-4 flex items-baseline justify-between border-b border-hair-soft pb-2.5">
        <h3 className="label">{title}</h3>
        <span
          className={`font-num t-lead font-medium ${
            tone === "positive" ? "text-positive" : "text-critical"
          }`}
        >
          {fmt(total)}
        </span>
      </div>
      <div className="space-y-2.5">
        {Object.entries(rows).map(([n, v]) => (
          <div key={n} className="flex items-center gap-2">
            <label className="t-small w-28 shrink-0 truncate text-body" title={n}>
              {n}
            </label>
            <NumberInput
              value={v}
              onChange={(nv) => onChange(n, nv)}
              step={100}
              min={0}
              prefix="$"
            />
            <button onClick={() => onRemove(n)} aria-label={`Remove ${n}`} className="btn-remove">
              ✕
            </button>
          </div>
        ))}
      </div>
      <div className="mt-3 flex gap-2">
        <input
          type="text"
          placeholder="Add a row…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && name.trim()) {
              onAdd(name.trim());
              setName("");
            }
          }}
        />
        <button
          onClick={() => {
            if (name.trim()) {
              onAdd(name.trim());
              setName("");
            }
          }}
          disabled={!name.trim()}
          className="btn-secondary shrink-0"
        >
          Add
        </button>
      </div>
    </div>
  );
}

export default function NetWorthPage() {
  const { profile, dashboard, update } = useFinance();
  if (!profile || !dashboard) return <div className="skeleton h-96" />;

  const assets = profile.assets;
  const liabilities = profile.liabilities;
  const totalA = sum(assets);
  const totalL = sum(liabilities);
  const net = totalA - totalL;

  const snapshots = [...profile.net_worth_snapshots].sort((a, b) =>
    a.date.localeCompare(b.date),
  );
  const todayISO = new Date().toISOString().slice(0, 10);
  const alreadyToday = snapshots.some((s) => s.date === todayISO);

  const logSnapshot = () => {
    const entry: Snapshot = {
      date: todayISO,
      assets: totalA,
      liabilities: totalL,
      net_worth: net,
    };
    update({
      net_worth_snapshots: [
        ...profile.net_worth_snapshots.filter((s) => s.date !== todayISO),
        entry,
      ],
    });
  };

  return (
    <div>
      <PageHeader
        title="Net Worth"
        description="What you own less what you owe. Liquid rows here also decide your emergency-fund coverage on the dashboard."
      />

      <div className="stagger mb-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {(
          [
            ["Total assets", fmt(totalA), "text-positive"],
            ["Total liabilities", fmt(totalL), "text-critical"],
            ["Net worth", fmt(net), net >= 0 ? "text-ink" : "text-critical"],
          ] as const
        ).map(([label, value, tone]) => (
          <div key={label} className="card">
            <p className="label">{label}</p>
            <p className={`font-num t-h3 mt-1.5 leading-none font-medium ${tone}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="mb-10 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Ledger
          title="Assets"
          rows={assets}
          tone="positive"
          onChange={(n, v) => update({ assets: { ...assets, [n]: v } })}
          onRemove={(n) => {
            const next = { ...assets };
            delete next[n];
            update({ assets: next });
          }}
          onAdd={(n) => !(n in assets) && update({ assets: { ...assets, [n]: 0 } })}
        />
        <Ledger
          title="Liabilities"
          rows={liabilities}
          tone="critical"
          onChange={(n, v) => update({ liabilities: { ...liabilities, [n]: v } })}
          onRemove={(n) => {
            const next = { ...liabilities };
            delete next[n];
            update({ liabilities: next });
          }}
          onAdd={(n) =>
            !(n in liabilities) && update({ liabilities: { ...liabilities, [n]: 0 } })
          }
        />
      </div>

      <div className="card mark-accent mb-10">
        <p className="t-small text-body">
          <strong className="font-num text-ink">
            {fmt(dashboard.liquid_assets)} counted as liquid
          </strong>
          {dashboard.emergency_fund_counted.length > 0 ? (
            <> — from {dashboard.emergency_fund_counted.join(", ")}.</>
          ) : (
            <> — nothing here reads as cash.</>
          )}{" "}
          Rows are matched by name, because the schema has no liquidity flag: a
          retirement or brokerage row is excluded even when the word
          &ldquo;savings&rdquo; is in it.
        </p>
      </div>

      <Section
        title="Snapshots"
        action={
          <button onClick={logSnapshot} className="btn-secondary">
            {alreadyToday ? "Update today's snapshot" : "Log today's snapshot"}
          </button>
        }
      >
        {snapshots.length < 2 ? (
          <Empty>
            {snapshots.length === 0
              ? "No snapshots yet. Log one now and again next month to start a trend."
              : "One snapshot logged. A second is needed before there is a line to draw."}
          </Empty>
        ) : (
          <TrendChart
            data={snapshots.map((s) => ({
              date: s.date,
              "Net worth": s.net_worth,
              Assets: s.assets,
              Liabilities: s.liabilities,
            }))}
            xKey="date"
            series={[
              { key: "Net worth", name: "Net worth", tone: "accent" },
              { key: "Assets", name: "Assets", tone: "s2", area: false },
              { key: "Liabilities", name: "Liabilities", tone: "critical", area: false },
            ]}
            height={320}
          />
        )}
      </Section>

      <Footer />
    </div>
  );
}
