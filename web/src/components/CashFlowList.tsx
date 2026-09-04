"use client";

/**
 * The cash flow as a list, for screens the Sankey cannot fit.
 *
 * WHY THIS EXISTS. The diagram is four columns of ribbon and needs about 560px
 * to carry its labels, so the panel wraps it in `overflow-x-auto` with a
 * `min-w-[640px]` inner box. That keeps it off the page's scrollbar and every
 * horizontal-overflow check passes — but measured at 375px, the scroller is
 * 293px of a 640px diagram and **20 of its 22 labels are off screen**. What a
 * phone showed was "Gross pay $8,750" and "FICA $669", with "State tax $3" and
 * "Federal tax $" clipped mid-figure at the edge — a truncated number that
 * still reads as a number, which is the defect this codebase has now met three
 * times. Everything the panel is FOR, which is where the money goes, was in
 * the half nobody sees. The caption even told the reader that a thin band
 * "names itself on hover", on a device that has no hover.
 *
 * WHY A LIST RATHER THAN A NARROWER DIAGRAM. A Sankey's whole claim is that
 * the widths are the money. Squeezed to 293px the widths survive and the
 * labels do not, so it keeps the claim and loses the reading. A list keeps the
 * reading and states the proportion with a bar instead.
 *
 * IT IS THE SAME GRAPH, DERIVED FROM THE SAME LINKS. Every node that is the
 * source of a link becomes a group; its targets become the rows. Nothing is
 * hardcoded about stages, so this cannot drift from the diagram when
 * `cash_flow` changes shape — a new stage appears in both or in neither.
 *
 * NO ARITHMETIC IS REPORTED. The bar's width is a proportion of its own
 * group's total, which is layout in exactly the sense the Sankey's ribbon
 * heights are layout, and it is never printed as a figure. Every number on
 * screen is one the engine sent.
 */

import { cssVar, type Token } from "@/lib/tokens";

export interface FlowNode {
  id: string;
  label: string;
  column: number;
  value: number;
  tone: Token;
}
export interface FlowLink {
  source: string;
  target: string;
  value: number;
}

export default function CashFlowList({
  nodes,
  links,
  formatValue,
}: {
  nodes: FlowNode[];
  links: FlowLink[];
  formatValue: (v: number) => string;
}) {
  const byId = new Map(nodes.map((n) => [n.id, n]));

  // Every node that feeds something, in the order the diagram lays them out.
  // A Map keyed by source keeps the first-seen order of the links, which is
  // the order the engine emitted them.
  const groups: { parent: FlowNode; rows: { node: FlowNode; value: number }[] }[] = [];
  const seen = new Map<string, number>();
  for (const l of links) {
    const parent = byId.get(l.source);
    const child = byId.get(l.target);
    if (!parent || !child) continue;
    let at = seen.get(l.source);
    if (at === undefined) {
      at = groups.length;
      seen.set(l.source, at);
      groups.push({ parent, rows: [] });
    }
    groups[at].rows.push({ node: child, value: l.value });
  }

  if (!groups.length) return null;

  return (
    <div className="mt-1">
      {groups.map(({ parent, rows }) => {
        // The denominator is what this group actually distributes, not the
        // parent's own value: they are equal wherever the flow balances, and
        // where they are not, a bar against the parent would understate every
        // row by the same amount and look like a rounding error.
        const total = rows.reduce((s, r) => s + r.value, 0);
        return (
          <div key={parent.id} className="mb-5 last:mb-0">
            <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-hair pb-1.5">
              <span className="label text-[10px] text-ink">{parent.label} divides into</span>
              <span className="font-num t-micro text-muted">{formatValue(parent.value)}</span>
            </div>
            {rows.map(({ node, value }) => (
              <div key={node.id} className="mb-2 last:mb-0">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="t-small text-body">{node.label}</span>
                  <span className="font-num t-small whitespace-nowrap text-ink">
                    {formatValue(value)}
                  </span>
                </div>
                {/* The proportion, as the diagram's ribbon width would have
                    shown it. `aria-hidden` because the figure beside it is
                    the accessible statement of the same thing. */}
                <div
                  className="mt-1 h-[3px] w-full overflow-hidden rounded-[1px] bg-hair-soft"
                  aria-hidden="true"
                >
                  <div
                    className="h-full"
                    style={{
                      width: total > 0 ? `${(value / total) * 100}%` : "0%",
                      background: cssVar(node.tone),
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}
