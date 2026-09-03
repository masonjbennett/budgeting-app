"use client";

/**
 * The cash-flow Sankey: gross pay in, everything it becomes out.
 *
 * COLOURS GO THROUGH THE `style` PROP, NOT AN SVG PRESENTATION ATTRIBUTE.
 * `fill="var(--s1)"` happens to resolve in this engine, but a custom property
 * is only guaranteed inside a CSS PROPERTY, and the failure mode of guessing
 * wrong is a diagram drawn in black on someone else's browser. Same reasoning
 * as tokens.ts, which is why Recharts is handed resolved values instead.
 *
 * HAND-ROLLED RATHER THAN RECHARTS', and that is a scope decision not a
 * preference. Recharts ships a Sankey with a generic force-style layout for
 * arbitrary graphs; this graph is not arbitrary. It has four fixed columns and
 * every node's children sum EXACTLY to the node — the engine guarantees it,
 * because `compute_take_home` defines take-home as the remainder. That
 * property makes the layout trivial: stack each node's children starting at
 * its own top edge and no ribbon can ever cross another. Fighting a general
 * solver into producing that, and then restyling its nodes and links anyway,
 * is more code than the eighty lines below.
 *
 * It also sidesteps the animation problem for free. Nothing here has an entry
 * animation to fail to complete, so there is no state in which it renders a
 * correctly-sized SVG with nothing inside it.
 *
 * NOTHING HERE COMPUTES MONEY. Values arrive from /api/cash-flow; this turns
 * them into rectangles and ribbons.
 */

import { useEffect, useId, useMemo, useRef, useState } from "react";

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

interface Placed extends FlowNode {
  x: number;
  y: number;
  h: number;
  /** How much of this node's height has been claimed by outgoing ribbons. */
  outUsed: number;
  inUsed: number;
}

const NODE_W = 11;
const GAP = 8;
const LABEL_MIN_H = 9;

/** A ribbon: two cubic curves, flat ends, filled. */
function ribbon(x0: number, y0: number, x1: number, y1: number, h0: number, h1: number) {
  const mx = (x0 + x1) / 2;
  return [
    `M${x0},${y0}`,
    `C${mx},${y0} ${mx},${y1} ${x1},${y1}`,
    `L${x1},${y1 + h1}`,
    `C${mx},${y1 + h1} ${mx},${y0 + h0} ${x0},${y0 + h0}`,
    "Z",
  ].join(" ");
}

export default function Sankey({
  nodes,
  links,
  width = 900,
  height = 460,
  formatValue,
}: {
  nodes: FlowNode[];
  links: FlowLink[];
  width?: number;
  height?: number;
  formatValue: (v: number) => string;
}) {
  const gradientBase = useId().replace(/[^\w-]/g, "");
  const [hovered, setHovered] = useState<string | null>(null);

  // The viewBox is set to the container's REAL pixel width rather than a fixed
  // 900. With a fixed one, `width="100%" height={h}` makes the browser letterbox
  // the drawing — it scales to fit both axes, so a wider card leaves a band of
  // dead space rather than a wider diagram, and the labels drift off 11px.
  // Measuring keeps it 1:1: text at its true size and the ribbons using the
  // whole card. (setState from a ResizeObserver is a subscription, not a
  // synchronous set inside an effect body.)
  const wrapRef = useRef<HTMLDivElement>(null);
  const [measured, setMeasured] = useState<number | null>(null);
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) =>
      setMeasured(Math.round(entry.contentRect.width)),
    );
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const boxWidth = Math.max(560, measured ?? width);

  const layout = useMemo(() => {
    const columns = Math.max(...nodes.map((n) => n.column)) + 1;
    const byColumn: FlowNode[][] = Array.from({ length: columns }, () => []);
    for (const n of nodes) byColumn[n.column].push(n);

    // One scale for the whole diagram, set by the tallest column, so a ribbon's
    // thickness means the same amount everywhere. Sizing each column to its own
    // total would make take-home look the size of gross pay.
    const columnTotals = byColumn.map((col) => col.reduce((s, n) => s + n.value, 0));
    const tallest = Math.max(...columnTotals, 1);

    const colX = (c: number) =>
      columns === 1 ? 0 : (c * (boxWidth - NODE_W)) / (columns - 1);

    const parentOf = new Map<string, string>();
    for (const l of links) parentOf.set(l.target, l.source);

    /** Lay the whole thing out at a given pixels-per-dollar. */
    function place(scale: number) {
      const placed = new Map<string, Placed>();

      // Column 0 is stacked from the top; every later column is stacked under
      // the PARENT it flows from, which is what keeps the ribbons untangled.
      byColumn[0].forEach((n, i) => {
        const prior = byColumn[0].slice(0, i).reduce((s, p) => s + p.value, 0);
        placed.set(n.id, {
          ...n, x: colX(0), y: prior * scale + i * GAP,
          h: Math.max(1, n.value * scale), outUsed: 0, inUsed: 0,
        });
      });

      for (let c = 1; c < columns; c++) {
        // Children go in their parents' order, then in the order the engine
        // listed them — it already sorts each bucket's lines by size.
        const ordered = [...byColumn[c]].sort((a, b) => {
          const pa = placed.get(parentOf.get(a.id) ?? "");
          const pb = placed.get(parentOf.get(b.id) ?? "");
          if (pa && pb && pa.y !== pb.y) return pa.y - pb.y;
          return nodes.indexOf(a) - nodes.indexOf(b);
        });
        let gapsSoFar = 0;
        let lastParent: string | null = null;
        for (const n of ordered) {
          const parentId = parentOf.get(n.id);
          const parent = parentId ? placed.get(parentId) : undefined;
          if (!parent) continue;
          if (lastParent !== null && lastParent !== parentId) gapsSoFar += GAP;
          lastParent = parentId ?? null;
          const y = parent.y + parent.outUsed + gapsSoFar;
          const h = Math.max(1, n.value * scale);
          parent.outUsed += h;
          placed.set(n.id, { ...n, x: colX(c), y, h, outUsed: 0, inUsed: 0 });
        }
      }
      const bottom = Math.max(...[...placed.values()].map((p) => p.y + p.h), 0);
      return { placed, bottom };
    }

    // FIT BY MEASURING, NOT BY PREDICTING. Reserving
    // `(mostNodesInAnyColumn - 1) * GAP` up front over-reserves — the gaps that
    // actually accumulate are the ones along the DEEPEST path, not the widest
    // column — and on the demo budget that left 110px of a 634px box empty.
    // So: lay out once, measure what the box did not spend on money, and give
    // the rest back. The gap total does not depend on the scale, so the second
    // pass lands on `height` rather than approaching it.
    //
    // A third correction for the `max(1, …)` floor under sub-pixel nodes was
    // written and then DELETED. Driving the real component through the app's
    // import path with forty $1 categories — enough that the smallest node is
    // floored, `minNodeHeight: 1` — the drawing still landed at exactly 760 of
    // 760 with the guard removed, so nothing exercised it. An unexercised guard
    // is the `derivedOnly:` defect: it reads as protection and enforces
    // nothing. The residue it would have absorbed is bounded by a pixel, and
    // the svg does not clip (see `overflow: visible` below), so a fractional
    // overshoot shows rather than silently losing the bottom of a row.
    let scale = height / tallest;
    let result = place(scale);
    const overhead = result.bottom - tallest * scale;
    if (overhead > 0.5) {
      scale = Math.max(1e-9, (height - overhead) / tallest);
      result = place(scale);
    }
    const placed = result.placed;

    // Ribbons attach at the running offset inside each end, so several links
    // sharing a node stack rather than overlap.
    for (const p of placed.values()) { p.outUsed = 0; p.inUsed = 0; }
    const ribbons = links
      .map((l, i) => {
        const a = placed.get(l.source);
        const b = placed.get(l.target);
        if (!a || !b) return null;
        const h = Math.max(1, l.value * scale);
        const y0 = a.y + a.outUsed;
        const y1 = b.y + b.inUsed;
        a.outUsed += h;
        b.inUsed += h;
        return {
          // AN INDEX, NOT THE NODE NAMES. This was `${source}->${target}`, and
          // a budget line is a user-typed string: "Min. Debt Payments" makes an
          // id with SPACES in it, which `url(#...)` cannot reference. The
          // gradient silently failed to resolve and three of the ribbons —
          // exactly the three whose category names contained a space — painted
          // grey while their single-word siblings were correct. Nothing in the
          // console, and the diagram still looked like a diagram.
          key: `l${i}`,
          source: l.source,
          target: l.target,
          sourceLabel: a.label,
          targetLabel: b.label,
          value: l.value,
          d: ribbon(a.x + NODE_W, y0, b.x, y1, h, h),
          from: a.tone,
          to: b.tone,
        };
      })
      .filter(Boolean) as {
        key: string; source: string; target: string;
        sourceLabel: string; targetLabel: string; value: number;
        d: string; from: Token; to: Token;
      }[];

    return { placed: [...placed.values()], ribbons, columns };
  }, [nodes, links, boxWidth, height]);

  const lit = (id: string) =>
    hovered === null ||
    hovered === id ||
    layout.ribbons.some(
      (r) => (r.source === hovered && r.target === id) || (r.target === hovered && r.source === id),
    );

  return (
    <div ref={wrapRef}>
      <svg
        viewBox={`0 0 ${boxWidth} ${height}`}
        width="100%"
        height={height}
        role="img"
        aria-label="Where each month's gross pay goes"
        // Not clipped: the fit lands on `height` exactly, but a sub-pixel
        // residue from the minimum node height would otherwise have the bottom
        // of the smallest row quietly cut off instead of shown.
        style={{ overflow: "visible" }}
      >
      <defs>
        {layout.ribbons.map((r) => (
          <linearGradient key={r.key} id={`${gradientBase}-${r.key}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" style={{ stopColor: cssVar(r.from) }} />
            <stop offset="100%" style={{ stopColor: cssVar(r.to) }} />
          </linearGradient>
        ))}
      </defs>

      {layout.ribbons.map((r) => {
        const on = hovered === null || hovered === r.source || hovered === r.target;
        return (
          <path
            key={r.key}
            d={r.d}
            fill={`url(#${gradientBase}-${r.key})`}
            fillOpacity={on ? 0.34 : 0.08}
            style={{ transition: "fill-opacity .15s ease" }}
          >
            <title>{`${r.sourceLabel} → ${r.targetLabel}: ${formatValue(r.value)}`}</title>
          </path>
        );
      })}

      {layout.placed.map((n) => {
        const right = n.column >= layout.columns - 1 || n.x > 0.6 * boxWidth;
        const on = lit(n.id);
        return (
          <g
            key={n.id}
            opacity={on ? 1 : 0.35}
            style={{ transition: "opacity .15s ease" }}
            onMouseEnter={() => setHovered(n.id)}
            onMouseLeave={() => setHovered(null)}
          >
            <rect
              x={n.x}
              y={n.y}
              width={NODE_W}
              height={n.h}
              style={{ fill: cssVar(n.tone) }}
            />
            {/* A generous invisible target, so a 2px ribbon is still hoverable. */}
            <rect x={n.x - 4} y={n.y - 2} width={NODE_W + 8} height={n.h + 4} fill="transparent" />
            {n.h >= LABEL_MIN_H && (
              <text
                x={right ? n.x - 7 : n.x + NODE_W + 7}
                y={n.y + n.h / 2}
                textAnchor={right ? "end" : "start"}
                dominantBaseline="middle"
                fontSize={11}
                style={{ fill: cssVar("body"), pointerEvents: "none" }}
              >
                {n.label}
                <tspan
                  style={{ fill: cssVar("muted"), fontFamily: "var(--font-mono)" }}
                  fontSize={10}
                >
                  {"  "}
                  {formatValue(n.value)}
                </tspan>
              </text>
            )}
            <title>{`${n.label}: ${formatValue(n.value)}`}</title>
          </g>
        );
      })}
      </svg>
    </div>
  );
}
