"use client";

/**
 * The cash-flow Sankey, with the sentences that keep it honest.
 *
 * The diagram's whole claim is that it is a FLOW: every stage sums to the one
 * before it. The engine guarantees that and returns `balanced`; if it were ever
 * false the picture would be a lie no reader could detect by looking, so this
 * refuses to draw it and says why. Same shape as the segments tab in
 * filings-terminal, where a breakdown that does not foot is not shown.
 *
 * Three states the diagram cannot express, so they are written instead:
 *   - a figure that is genuinely zero this month (no state tax in Texas) gets
 *     no ribbon, and is named in the caption rather than silently absent;
 *   - a plan that allocates MORE than take-home has no unallocated remainder
 *     and is not a flow at all — that is said in words, above the diagram;
 *   - no income entered at all, where there is nothing to draw.
 */

import { useEffect, useState } from "react";

import Sankey from "@/components/Sankey";
import { fmt, useFinance } from "@/context/FinanceContext";
import { api, ApiError, type CashFlow } from "@/lib/api";

export default function CashFlowPanel() {
  const { profile } = useFinance();
  const [flow, setFlow] = useState<CashFlow | null>(null);
  const [error, setError] = useState<string | null>(null);

  const income = profile?.income;
  const budget = profile?.budget;
  const itemized = profile?.itemized;
  const key = JSON.stringify([income, budget, itemized]);

  useEffect(() => {
    if (!income || !budget) return;
    let live = true;
    api
      .cashFlow({ income, itemized, budget })
      .then((f) => live && (setFlow(f), setError(null)))
      .catch((e) =>
        live && setError(e instanceof ApiError ? e.message : "Could not work out the flow"),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  if (error) {
    return <div className="card mark-critical t-small text-critical">{error}</div>;
  }
  if (!flow) return <div className="skeleton h-[26rem]" />;

  if (flow.gross <= 0) {
    return (
      <div className="card py-9 text-center">
        <p className="t-small text-muted">
          Nothing to trace yet — this needs a salary to flow from.
        </p>
      </div>
    );
  }

  if (!flow.balanced) {
    // Not drawable: a Sankey whose stages do not sum is a picture of a flow
    // rather than a flow, and nothing on screen would give that away.
    return (
      <div className="card mark-critical">
        <p className="t-small text-body">
          The stages of this month do not add up — {fmt(flow.residual)} is
          unaccounted for between gross pay and where it went, so the diagram is
          not drawn. That is a bug in the engine rather than in your figures.
        </p>
      </div>
    );
  }

  // Height follows the number of category rows, so a 16-line budget does not
  // get 16 ribbons crammed into 380px.
  const leaves = flow.nodes.filter((n) => n.column === 3).length;
  const height = Math.max(400, Math.min(760, 250 + leaves * 24));

  const kept = flow.gross > 0 ? (flow.take_home / flow.gross) * 100 : 0;

  return (
    <div className="card">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
        <p className="t-small text-body">
          Of <span className="font-num text-ink">{fmt(flow.gross)}</span> gross a month you
          keep <span className="font-num text-ink">{fmt(flow.take_home)}</span> —{" "}
          <span className="font-num">{kept.toFixed(0)}%</span>.
        </p>
        {flow.deficit > 0 ? (
          <p className="t-micro text-critical">
            The plan allocates {fmt(flow.deficit)} more than take-home covers.
          </p>
        ) : (
          <p className="t-micro text-muted">
            <span className="font-num">{fmt(flow.unallocated)}</span> of it is unallocated.
          </p>
        )}
      </div>

      <div className="overflow-x-auto">
        <div className="min-w-[640px] pr-2">
          <Sankey
            nodes={flow.nodes}
            links={flow.links}
            height={height}
            formatValue={(v) => fmt(v)}
          />
        </div>
      </div>

      <p className="t-micro mt-4 border-t border-hair-soft pt-3 text-muted">
        Every stage sums to the one before it — take-home is what is left after
        pre-tax deductions and the three taxes, so the widths are the money
        rather than an impression of it. Tax figures are annual, shown monthly;
        a band too thin to carry a label names itself on hover.
        {flow.omitted.length > 0 && (
          <> Zero this month, so not drawn: {flow.omitted.join(", ")}.</>
        )}
      </p>
    </div>
  );
}
