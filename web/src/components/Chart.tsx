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
 * COLOUR COMES FROM TOKENS, NEVER FROM A LITERAL. A caller names a meaning
 * ("positive", "s3") and `usePalette` resolves it against whatever globals.css
 * currently says, re-reading when the theme changes. The ten arbitrary hues
 * this replaced were picked to be distinct from each other and had no
 * relationship to anything else on the page.
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
  ReferenceArea,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ReactNode } from "react";

import { SERIES, usePalette, type Palette, type Token } from "@/lib/tokens";

/** Grid rules only where they help a value be read: horizontal, hairline, no
 *  cage. Built per render because the palette follows the theme. */
function axisProps(p: Palette) {
  return {
    stroke: p.hair,
    tick: { fill: p.muted, fontSize: 10, fontFamily: "var(--font-mono)" },
  };
}

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
    <div className="rounded-sm border border-hair bg-card px-3 py-2">
      {label !== undefined && <p className="label mb-1.5">{label}</p>}
      {rows.map((r) => (
        <p key={r.name} className="t-small flex items-center gap-2 text-ink">
          <span
            className="h-[2px] w-3 shrink-0"
            style={{ background: r.color }}
            aria-hidden="true"
          />
          <span className="text-body">{r.name}</span>
          <span className="font-num ml-auto pl-3">{exact(r.value)}</span>
        </p>
      ))}
    </div>
  );
}

/* Recharts calls a `content` function itself rather than mounting it as a
   component, so this must not use hooks. It needs none: every colour in the
   payload is already the resolved token the chart was drawn with. */
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
        <div className="mb-3 flex items-center justify-between gap-3">
          {title && <h3 className="label">{title}</h3>}
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
  series: { key: string; name: string; tone?: Token; area?: boolean; dashed?: boolean }[];
  height?: number;
  title?: string;
  xFormatter?: (v: number | string) => string;
  action?: ReactNode;
}) {
  const p = usePalette();
  const AXIS = axisProps(p);
  return (
    <Card title={title} height={height} action={action}>
      <AreaChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={p.hairSoft} vertical={false} />
        <XAxis
          dataKey={xKey}
          {...AXIS}
          tickFormatter={xFormatter as never}
          tickLine={false}
          axisLine={{ stroke: p.hair }}
        />
        <YAxis {...AXIS} tickFormatter={money} tickLine={false} axisLine={false} width={58} />
        <Tooltip content={moneyTooltip} />
        {series.length > 1 && (
          <Legend
            wrapperStyle={{
              fontSize: 11,
              color: p.muted,
              fontFamily: "var(--font-mono)",
              paddingTop: 8,
            }}
            iconType="plainline"
          />
        )}
        {series.map((s, i) => {
          const color = p[s.tone ?? SERIES[i % SERIES.length]];
          return (
            <Area
              key={s.key}
              isAnimationActive={false}
              type="monotone"
              dataKey={s.key}
              name={s.name}
              stroke={color}
              strokeWidth={1.75}
              strokeDasharray={s.dashed ? "4 3" : undefined}
              fill={color}
              fillOpacity={s.area === false ? 0 : 0.09}
              dot={false}
              activeDot={{ r: 3, strokeWidth: 0 }}
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
  tones,
  height = 280,
  title,
  reference,
  bands,
  action,
}: {
  data: Record<string, number | string>[];
  xKey: string;
  valueKey: string;
  /** One token per bar. Omitted, the bars walk the categorical series. */
  tones?: Token[];
  height?: number;
  title?: string;
  /** A horizontal rule to read the bars against — a monthly budget, say.
   *  Drawn behind them, dashed, so it cannot be mistaken for a series. */
  reference?: { value: number; label: string };
  /** Ranges of the category axis to shade, for stretches where there is no
   *  data at all. A zero-height bar renders as NOTHING in Recharts, so a
   *  month with no records is otherwise indistinguishable from the gap
   *  between two bars — see the note in the JSX below. */
  bands?: { from: string; to: string; label?: string }[];
  action?: ReactNode;
}) {
  const p = usePalette();
  const AXIS = axisProps(p);
  return (
    <Card title={title} height={height} action={action}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={p.hairSoft} vertical={false} />
        <XAxis dataKey={xKey} {...AXIS} tickLine={false} axisLine={{ stroke: p.hair }} />
        <YAxis {...AXIS} tickFormatter={money} tickLine={false} axisLine={false} width={58} />
        <Tooltip content={moneyTooltip} cursor={{ fill: p.hairSoft, fillOpacity: 0.5 }} />
        {/* Shaded FIRST so the bars and the rule paint over it. A stretch with
            no data is marked rather than drawn, because there is no honest
            height to draw: Recharts renders a zero-value bar as no element at
            all, so seven months with nothing logged were indistinguishable
            from seven months that did not exist — under a note telling the
            reader to look for faint bars that were never there. */}
        {bands?.map((b, i) => (
          <ReferenceArea
            key={i}
            x1={b.from}
            x2={b.to}
            fill={p.hairSoft}
            fillOpacity={0.75}
            stroke="none"
            label={{
              value: b.label,
              position: "insideTop",
              fill: p.muted,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
            }}
          />
        ))}
        <ReferenceLine y={0} stroke={p.hair} />
        {reference && (
          <ReferenceLine
            y={reference.value}
            stroke={p.muted}
            strokeDasharray="4 3"
            // WITHOUT THIS THE RULE IS INVISIBLE EXACTLY WHEN IT MATTERS.
            // Recharts sizes the Y axis from the data alone, so a budget above
            // every bar falls outside the domain and is silently dropped —
            // which is the case of someone spending UNDER their budget, the
            // one this line exists to show.
            ifOverflow="extendDomain"
            label={{
              value: reference.label,
              position: "insideTopRight",
              fill: p.muted,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
            }}
          />
        )}
        <Bar dataKey={valueKey} radius={[2, 2, 0, 0]} maxBarSize={54} isAnimationActive={false}>
          {data.map((_, i) => (
            <Cell key={i} fill={p[tones?.[i] ?? SERIES[i % SERIES.length]]} />
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
  const p = usePalette();
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
          paddingAngle={1}
          stroke={p.card}
          strokeWidth={1.5}
        >
          {data.map((_, i) => (
            <Cell key={i} fill={p[SERIES[i % SERIES.length]]} />
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
  const p = usePalette();
  const AXIS = axisProps(p);
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
      {/* top: 20, not 8, because THIS chart carries a `position: "top"`
          reference label and the others do not.

          Recharts puts that label ABOVE the plot area, and the surface is
          `overflow: hidden`. With 8px of headroom against a 13px label,
          "Retirement" was measured starting 7px above the SVG's own top edge
          — more than half of it clipped, so the glyph tops were sliced and it
          read as nonsense. Unlike the axis date that looked cut and was not,
          this one loses real ink. */}
      <AreaChart data={data} margin={{ top: 20, right: 12, left: 4, bottom: 4 }}>
        <CartesianGrid stroke={p.hairSoft} vertical={false} />
        <XAxis dataKey="age" {...AXIS} tickLine={false} axisLine={{ stroke: p.hair }} />
        <YAxis {...AXIS} tickFormatter={money} tickLine={false} axisLine={false} width={58} />
        <Tooltip
          content={(props) =>
            moneyTooltip({
              ...props,
              label: `Age ${props.label}`,
              payload: (props.payload ?? []).filter((q) => q.dataKey === "median"),
            })
          }
        />
        <ReferenceLine y={0} stroke={p.critical} strokeDasharray="4 3" />
        <ReferenceLine
          x={retireAge}
          stroke={p.caution}
          strokeDasharray="4 3"
          label={{
            value: "Retirement",
            fill: p.caution,
            fontSize: 10,
            fontFamily: "var(--font-mono)",
            position: "top",
          }}
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
            fill={p.accent}
            fillOpacity={b.opacity}
            isAnimationActive={false}
          />,
        ])}
        <Area
          type="monotone"
          isAnimationActive={false}
          dataKey="median"
          name="Median"
          stroke={p.accent}
          strokeWidth={2}
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
  const p = usePalette();
  const AXIS = axisProps(p);
  const data = ages.map((age, i) => {
    const row: Record<string, number> = { age, median: median[i] };
    paths.forEach((q, pi) => (row[`p${pi}`] = q[i]));
    return row;
  });
  const clipped = yMax ? paths.filter((q) => Math.max(...q) > yMax).length : 0;

  return (
    <>
      <Card title={title} height={height}>
        <LineChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={p.hairSoft} vertical={false} />
          <XAxis dataKey="age" {...AXIS} tickLine={false} axisLine={{ stroke: p.hair }} />
          <YAxis
            {...AXIS}
            tickFormatter={money}
            tickLine={false}
            axisLine={false}
            width={58}
            domain={yMax ? [0, yMax] : undefined}
            allowDataOverflow={Boolean(yMax)}
          />
          <ReferenceLine y={0} stroke={p.critical} strokeDasharray="4 3" />
          {paths.map((_, i) => (
            <Line
              key={i}
              type="monotone"
              dataKey={`p${i}`}
              stroke={p.accent}
              strokeOpacity={0.16}
              strokeWidth={0.75}
              dot={false}
              isAnimationActive={false}
            />
          ))}
          <Line
            type="monotone"
            dataKey="median"
            stroke={p.accent}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </Card>
      {(note || clipped > 0) && (
        <p className="t-micro mt-2 text-muted">
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

// ── Distribution ─────────────────────────────────────────────────────

/**
 * A histogram of ending balances.
 *
 * The fan chart answers "what is the range"; this answers "what is the shape",
 * and they are not the same question. A run can have a comfortable median and
 * a long tail of failures — the band chart hides that and this does not, which
 * is why the failing bins are coloured separately rather than being one more
 * bar of the same colour.
 *
 * The Y axis is a COUNT, not money, so it does not use the money formatter —
 * the axis label says what it is counting.
 */
export function HistogramChart({
  bins,
  height = 280,
  title,
  failBelow = 0,
  formatBin,
  note,
}: {
  bins: { start: number; end: number; count: number }[];
  height?: number;
  title?: string;
  /** Bins whose upper edge is at or below this are outcomes that ran out. */
  failBelow?: number;
  formatBin: (v: number) => string;
  note?: ReactNode;
}) {
  const p = usePalette();
  const AXIS = axisProps(p);
  const data = bins.map((b) => {
    // A bin is a failure only when its WHOLE range is at or below the line.
    // The engine isolates the ran-out paths into a zero-width bin of their
    // own precisely so this test can be true of them and of nothing else.
    const failed = b.end <= failBelow;
    return {
      label: formatBin(b.start),
      count: b.count,
      failed,
      range: b.start === b.end ? formatBin(b.start)
        : `${formatBin(b.start)} – ${formatBin(b.end)}`,
    };
  });

  return (
    <>
      <Card title={title} height={height}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 4, bottom: 4 }}>
          <CartesianGrid stroke={p.hairSoft} vertical={false} />
          <XAxis dataKey="label" {...AXIS} tickLine={false} axisLine={{ stroke: p.hair }} interval="preserveStartEnd" />
          <YAxis {...AXIS} tickLine={false} axisLine={false} width={44} allowDecimals={false} />
          <Tooltip
            cursor={{ fill: p.hairSoft, fillOpacity: 0.5 }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const row = payload[0].payload as (typeof data)[number];
              return (
                <div className="rounded-sm border border-hair bg-card px-3 py-2">
                  <p className="label mb-1">{row.range}</p>
                  <p className="t-small text-ink">
                    <span className="font-num">{row.count}</span> path
                    {row.count === 1 ? "" : "s"}
                    {row.failed && <span className="text-critical"> · ran out</span>}
                  </p>
                </div>
              );
            }}
          />
          <Bar dataKey="count" radius={[2, 2, 0, 0]} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.failed ? p.critical : p.accent} />
            ))}
          </Bar>
        </BarChart>
      </Card>
      {note && <p className="t-micro mt-2 text-muted">{note}</p>}
    </>
  );
}

// ── Savings rate against years to independence ───────────────────────

/**
 * The curve, with the reader's own position marked on it.
 *
 * Three things here are not the house style elsewhere and each is deliberate.
 *
 * The Y axis is YEARS, so it does not take the shared money formatter — a
 * duration rendered as "$23" is exactly the kind of thing a shared formatter
 * does silently, and this is the one chart in the app whose values are not
 * money.
 *
 * `connectNulls` is FALSE. A savings rate that never reaches the target comes
 * back as null, and Recharts' default is to bridge the gap — drawing a
 * confident line straight through the region where the answer is "never". The
 * line stops instead, and the note under the chart says so in words.
 *
 * The marker is drawn in bronze, which is otherwise reserved for a caution.
 * It is spent here because this is the one mark on the page that is about the
 * reader rather than about the model, and teal would make it a third series.
 */
export function SavingsCurveChart({
  points,
  current,
  height = 320,
  title,
  note,
  action,
}: {
  points: { savings_rate: number; years: number | null; fire_number: number }[];
  /** Where the reader is now. Omitted where it cannot be measured. */
  current?: { savings_rate: number; years: number } | null;
  height?: number;
  title?: string;
  note?: ReactNode;
  action?: ReactNode;
}) {
  const p = usePalette();
  const AXIS = axisProps(p);

  /* Recharts calls this itself rather than mounting it, so it uses no hooks —
     the palette is closed over from the render that drew the chart. */
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const tip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null;
    const d = payload[0].payload;
    return (
      <div className="rounded-sm border border-hair bg-card px-3 py-2">
        <p className="label mb-1.5">Saving {d.savings_rate}% of take-home</p>
        <p className="t-small text-ink">
          <span className="font-num">
            {d.years === null ? "never" : `${d.years.toFixed(1)} years`}
          </span>
          {d.years !== null && <span className="text-muted"> to independence</span>}
        </p>
        <p className="t-micro mt-1 text-muted">
          Target <span className="font-num">{exact(d.fire_number)}</span>
        </p>
      </div>
    );
  };
  /* eslint-enable @typescript-eslint/no-explicit-any */

  return (
    <>
      <Card title={title} height={height} action={action}>
        <LineChart data={points} margin={{ top: 14, right: 16, left: 4, bottom: 18 }}>
          <CartesianGrid stroke={p.hairSoft} vertical={false} />
          <XAxis
            dataKey="savings_rate"
            type="number"
            domain={["dataMin", "dataMax"]}
            {...AXIS}
            tickFormatter={(v: number) => `${v}%`}
            tickLine={false}
            axisLine={{ stroke: p.hair }}
            label={{
              value: "Savings rate",
              position: "insideBottom",
              offset: -12,
              fill: p.muted,
              fontSize: 10,
              fontFamily: "var(--font-mono)",
            }}
          />
          <YAxis
            {...AXIS}
            tickFormatter={(v: number) => `${v}y`}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={tip} />
          {current && (
            <ReferenceLine
              x={current.savings_rate}
              stroke={p.caution}
              strokeDasharray="3 3"
              label={{
                value: `you · ${current.years.toFixed(0)}y`,
                position: "top",
                fill: p.caution,
                fontSize: 10,
                fontFamily: "var(--font-mono)",
              }}
            />
          )}
          <Line
            isAnimationActive={false}
            type="monotone"
            dataKey="years"
            name="Years"
            stroke={p.accent}
            strokeWidth={1.75}
            dot={false}
            activeDot={{ r: 3, strokeWidth: 0 }}
            connectNulls={false}
          />
          {current && (
            <ReferenceDot
              x={current.savings_rate}
              y={current.years}
              r={4}
              fill={p.caution}
              stroke={p.card}
              strokeWidth={1.5}
            />
          )}
        </LineChart>
      </Card>
      {note && <p className="t-micro mt-2 leading-relaxed text-muted">{note}</p>}
    </>
  );
}
