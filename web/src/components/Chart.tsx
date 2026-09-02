"use client";

/**
 * Charts, on Recharts.
 *
 * ENTRY ANIMATIONS ARE OFF EVERYWHERE, and that is a correctness decision
 * rather than a taste one. Recharts renders a Pie's sectors as EMPTY <g> groups
 * until its entry animation finishes: ten sector groups with no <path> inside
 * them, a correctly sized SVG, and nothing in the console. Where the animation
 * does not run to completion the chart is permanently, silently blank. Measured
 * side by side on one page: identical pies with the flag on and off rendered 0
 * paths and 3 paths. This is the same family as the IntersectionObserver that
 * never fires in a throttled surface -- a visual nicety whose failure mode is
 * an empty panel where a number should be.
 *
 * The abandoned scaffold used plotly.js-dist-min for five trace types out of
 * the forty-odd it ships: 4.51 MB in a single chunk, 944 KB brotli, lazily
 * loaded but paid for on the dashboard, which is the landing page. Recharts
 * covers line, area, bar and pie natively at a fraction of that; the only chart
 * that needed building is the fan, which is stacked areas with a transparent
 * base — and that is a dozen lines rather than a megabyte.
 *
 * Everything here takes numbers and draws them. No chart computes anything.
 */

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";

export const SERIES_COLORS = [
  "#5b8def", "#4ade80", "#818cf8", "#fbbf24", "#f472b6",
  "#22d3ee", "#c084fc", "#fb923c", "#2dd4bf", "#e879f9",
];

const AXIS = { stroke: "rgba(255,255,255,0.06)", tick: { fill: "#666", fontSize: 11 } };
const GRID = "rgba(255,255,255,0.045)";

const money = (v: number) => {
  const a = Math.abs(v);
  if (a >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (a >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${Math.round(v)}`;
};

const exact = (v: number) =>
  `$${v.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

function TooltipBox({
  label,
  rows,
}: {
  label?: ReactNode;
  rows: { name: string; value: number; color: string }[];
}) {
  return (
    <div className="rounded-lg border border-white/10 bg-[#171717] px-3 py-2 shadow-xl">
      {label !== undefined && (
        <p className="mb-1 text-[0.7rem] font-medium text-dim">{label}</p>
      )}
      {rows.map((r) => (
        <p key={r.name} className="font-num text-[0.78rem] text-primary">
          <span
            className="mr-1.5 inline-block h-2 w-2 rounded-full align-middle"
            style={{ background: r.color }}
          />
          {r.name}: {exact(r.value)}
        </p>
      ))}
    </div>
  );
}

/* eslint-disable @typescript-eslint/no-explicit-any */
function moneyTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <TooltipBox
      label={label}
      rows={payload
        .filter((p: any) => p.value !== null && p.value !== undefined)
        .map((p: any) => ({
          name: p.name ?? p.dataKey,
          value: p.value,
          color: p.color ?? p.stroke ?? p.fill,
        }))}
    />
  );
}
/* eslint-enable @typescript-eslint/no-explicit-any */

export function Card({
  title,
  children,
  height = 300,
  action,
}: {
  title?: string;
  children: ReactNode;
  height?: number;
  action?: ReactNode;
}) {
  return (
    <div className="card">
      {(title || action) && (
        <div className="mb-3 flex items-center justify-between">
          {title && (
            <h3 className="text-[0.72rem] font-medium uppercase tracking-[0.08em] text-muted">
              {title}
            </h3>
          )}
          {action}
        </div>
      )}
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          {children as never}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ── Line / area over time ────────────────────────────────────────────

export function TrendChart({
  data,
  xKey,
  series,
  height = 300,
  title,
  xFormatter,
  action,
}: {
  data: Record<string, number | string>[];
  xKey: string;
  series: { key: string; name: string; color?: string; area?: boolean; dashed?: boolean }[];
  height?: number;
  title?: string;
  xFormatter?: (v: number | string) => string;
  action?: ReactNode;
}) {
  return (
    <Card title={title} height={height} action={action}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis
          dataKey={xKey}
          {...AXIS}
          tickFormatter={xFormatter as never}
          tickLine={false}
          axisLine={{ stroke: AXIS.stroke }}
        />
        <YAxis
          {...AXIS}
          tickFormatter={money}
          tickLine={false}
          axisLine={false}
          width={58}
        />
        <Tooltip content={moneyTooltip} />
        {series.length > 1 && (
          <Legend
            wrapperStyle={{ fontSize: 11, color: "#666", paddingTop: 8 }}
            iconType="plainline"
          />
        )}
        {series.map((s, i) => {
          const color = s.color ?? SERIES_COLORS[i % SERIES_COLORS.length];
          return (
            <Area
              key={s.key}
              isAnimationActive={false}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={color}
              strokeWidth={2}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              fill={color}
              fillOpacity={s.area === false ? 0 : 0.1}
              dot={false}
              activeDot={{ r: 3.5, strokeWidth: 0 }}
            />
          );
        })}
      </AreaChart>
    </Card>
  );
}

// ── Bars ─────────────────────────────────────────────────────────────

export function BarsChart({
  data,
  xKey,
  valueKey,
  colors,
  height = 280,
  title,
}: {
  data: Record<string, number | string>[];
  xKey: string;
  valueKey: string;
  colors?: string[];
  height?: number;
  title?: string;
}) {
  return (
    <Card title={title} height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} {...AXIS} tickLine={false} axisLine={{ stroke: AXIS.stroke }} />
        <YAxis {...AXIS} tickFormatter={money} tickLine={false} axisLine={false} width={58} />
        <Tooltip content={moneyTooltip} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
        <ReferenceLine y={0} stroke="rgba(255,255,255,0.14)" />
        <Bar dataKey={valueKey} radius={[4, 4, 0, 0]} maxBarSize={64} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={colors?.[i] ?? SERIES_COLORS[i % SERIES_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </Card>
  );
}

// ── Donut ────────────────────────────────────────────────────────────

export function DonutChart({
  data,
  height = 280,
  title,
}: {
  data: { name: string; value: number }[];
  height?: number;
  title?: string;
}) {
  // Radii are numbers, not percentages. Percentage radii inside a
  // ResponsiveContainer resolved to zero here: ten sector groups rendered with
  // no <path> inside them, so the card was blank with no console error and a
  // correctly-sized SVG. Deriving them from the height this component was given
  // is deterministic and cannot depend on when the container measures itself.
  const outer = Math.round(height * 0.44);
  const inner = Math.round(height * 0.3);

  return (
    <Card title={title} height={height}>
      <PieChart>
        <Pie
          data={data}
          dataKey="value"
          nameKey="name"
          isAnimationActive={false}
          cx="50%"
          cy="50%"
          innerRadius={inner}
          outerRadius={outer}
          paddingAngle={1.5}
          stroke="#09090b"
          strokeWidth={2}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
          ))}
        </Pie>
        <Tooltip content={moneyTooltip} />
      </PieChart>
    </Card>
  );
}

// ── Monte Carlo fan ──────────────────────────────────────────────────

/**
 * Percentile bands drawn as stacked areas over a transparent base.
 *
 * Recharts has no band primitive, so each band is [lower, upper - lower] with
 * the lower half invisible. The alternative — an area from zero for each
 * percentile, painted back to front — looks identical until a path goes
 * negative, where the fills cross and the picture inverts.
 */
export function FanChart({
  ages,
  bands,
  median,
  retireAge,
  height = 380,
  title,
}: {
  ages: number[];
  bands: { lower: number[]; upper: number[]; opacity: number; name: string }[];
  median: number[];
  retireAge: number;
  height?: number;
  title?: string;
}) {
  const data = ages.map((age, i) => {
    const row: Record<string, number> = { age, median: median[i] };
    bands.forEach((b, bi) => {
      row[`base${bi}`] = b.lower[i];
      row[`span${bi}`] = Math.max(0, b.upper[i] - b.lower[i]);
    });
    return row;
  });

  return (
    <Card title={title} height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="age" {...AXIS} tickLine={false} axisLine={{ stroke: AXIS.stroke }} />
        <YAxis {...AXIS} tickFormatter={money} tickLine={false} axisLine={false} width={58} />
        <Tooltip
          content={(props) =>
            moneyTooltip({
              ...props,
              label: `Age ${props.label}`,
              payload: (props.payload ?? []).filter((p) => p.dataKey === "median"),
            })
          }
        />
        <ReferenceLine y={0} stroke="#f87171" strokeDasharray="4 3" />
        <ReferenceLine
          x={retireAge}
          stroke="#fbbf24"
          strokeDasharray="4 3"
          label={{ value: "Retirement", fill: "#fbbf24", fontSize: 11, position: "top" }}
        />
        {bands.map((b, i) => [
          <Area
            key={`base${i}`}
            type="monotone"
            dataKey={`base${i}`}
            stackId={`b${i}`}
            stroke="none"
            fill="none"
            isAnimationActive={false}
          />,
          <Area
            key={`span${i}`}
            type="monotone"
            dataKey={`span${i}`}
            name={b.name}
            stackId={`b${i}`}
            stroke="none"
            fill="#5b8def"
            fillOpacity={b.opacity}
            isAnimationActive={false}
          />,
        ])}
        <Area
          type="monotone"
          isAnimationActive={false}
          dataKey="median"
          name="Median"
          stroke="#5b8def"
          strokeWidth={2.5}
          fill="none"
          dot={false}
        />
      </AreaChart>
    </Card>
  );
}

// ── Many faint paths ─────────────────────────────────────────────────

export function PathsChart({
  ages,
  paths,
  median,
  height = 340,
  title,
  yMax,
  note,
}: {
  ages: number[];
  paths: number[][];
  median: number[];
  height?: number;
  title?: string;
  /** Cap the axis. One lucky path can be an order of magnitude above the
   *  median, and left uncapped it sets the scale for everything else — the
   *  median and the whole accumulation phase flatten onto the zero line. */
  yMax?: number;
  note?: ReactNode;
}) {
  const data = ages.map((age, i) => {
    const row: Record<string, number> = { age, median: median[i] };
    paths.forEach((p, pi) => (row[`p${pi}`] = p[i]));
    return row;
  });
  const clipped = yMax
    ? paths.filter((p) => Math.max(...p) > yMax).length
    : 0;

  return (
    <>
      <Card title={title} height={height}>
      <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="age" {...AXIS} tickLine={false} axisLine={{ stroke: AXIS.stroke }} />
        <YAxis
          {...AXIS}
          tickFormatter={money}
          tickLine={false}
          axisLine={false}
          width={58}
          domain={yMax ? [0, yMax] : undefined}
          allowDataOverflow={Boolean(yMax)}
        />
        <ReferenceLine y={0} stroke="#f87171" strokeDasharray="4 3" />
        {paths.map((_, i) => (
          <Line
            key={i}
            type="monotone"
            dataKey={`p${i}`}
            stroke="#5b8def"
            strokeOpacity={0.16}
            strokeWidth={0.75}
            dot={false}
            isAnimationActive={false}
          />
        ))}
        <Line
          type="monotone"
          dataKey="median"
          stroke="#5b8def"
          strokeWidth={2.5}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
      </Card>
      {(note || clipped > 0) && (
        <p className="mt-2 text-[0.7rem] leading-snug text-muted">
          {note}
          {clipped > 0 && (
            <>
              {note ? " " : ""}
              {clipped} of {paths.length} paths run above the top of this axis.
            </>
          )}
        </p>
      )}
    </>
  );
}
