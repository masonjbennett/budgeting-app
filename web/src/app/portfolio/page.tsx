"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";

import { DonutChart } from "@/components/Chart";
import { Empty, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import StatusCard from "@/components/StatusCard";
import { api, ApiError, type Xray } from "@/lib/api";
import { fmt, pct, useFinance, type Holding } from "@/context/FinanceContext";

/**
 * The portfolio X-ray.
 *
 * DELIBERATELY NOT IN THE NAV. This route is absent from `GROUPS` in
 * components/Nav.tsx, and `ALL` — which the command palette reads — is derived
 * from GROUPS, so staying out of one keeps it out of both. Reachable by URL.
 *
 * NO ARITHMETIC HERE. Every percentage, weight, total and projection below
 * arrives from /api/portfolio. The only numbers this file produces are array
 * indices. That rule is why the app's maths stopped existing in three
 * disagreeing copies, and a portfolio page is exactly where a "quick" weight
 * calculation would grow back.
 */

const KINDS = [
  { v: "fund", label: "Fund / ETF" },
  { v: "stock", label: "Individual stock" },
  // Employer stock is still a stock for every lookup — same class, same
  // (absent) fee. It rides on this control rather than a seventh column
  // because it is a property of ONE row and the first version guessed which,
  // marking the largest position and labelling the wrong holding.
  { v: "employer", label: "Employer stock" },
  { v: "cash", label: "Cash" },
];

/** A COUNT, not money. `fmt` is a currency formatter and rendered "effective
 *  holdings" as $3.5. Formatting, not arithmetic — the figure is the
 *  engine's. */
function count(v: number | null | undefined, decimals = 1): string {
  return v === null || v === undefined ? "\u2014" : v.toFixed(decimals);
}

const ACCOUNTS = ["401(k)", "Roth IRA", "Traditional IRA", "HSA", "Brokerage", "Other"];

/* A layout effect on the client, an ordinary one on the server — where it does
   nothing either way and React warns if you ask for the layout variant. The
   measurement has to run BEFORE paint, or the reader sees one frame of the
   grid it is about to replace. Copied from /compare deliberately: same
   mechanism, same class, so there is one stacking rule and not two. */
const useMeasure = typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * Below this share of the money measured, the fee figures stop being the
 * headline and the caveat takes their place.
 *
 * A JUDGEMENT, and there is no gap in the distribution to read it off — this
 * is not the segment gate. It is set where a figure stops describing the
 * portfolio someone is looking at and starts describing a subset of it. The
 * page always PRINTS the actual coverage beside the number, so the threshold
 * decides only which of the two is said first.
 */
const FEE_COVERAGE_FLOOR = 60;

function blankHolding(): Holding {
  // The id is generated and never derived from the label. It keys the rows and
  // anything SVG downstream, and a label is user-typed: /budget lost three
  // Sankey ribbons to ids built from category names, because `url(#...)`
  // cannot reference an id with a space in it.
  return {
    id: `h${Date.now().toString(36)}${Math.random().toString(36).slice(2, 7)}`,
    symbol: "",
    label: "",
    value: 0,
    account: ACCOUNTS[0],
    kind: "fund",
    employer_stock: false,
  };
}

export default function PortfolioPage() {
  const { profile, update } = useFinance();
  // The result carries the KEY it was measured for, and the render below uses
  // it only while that key still matches. Two things fall out of that: an
  // effect that never calls setState synchronously (deleting every holding
  // simply stops matching), and no frame in which last portfolio's figures sit
  // under this portfolio's holdings — which on a page of percentages would
  // look like a live answer rather than a stale one.
  const [result, setResult] = useState<{
    key: string;
    xray: Xray | null;
    error: string | null;
  } | null>(null);

  const holdings = useMemo(() => profile?.holdings ?? [], [profile?.holdings]);
  const inv = profile?.investment;

  const setHoldings = useCallback(
    (next: Holding[]) => update({ holdings: next }),
    [update],
  );

  const key = JSON.stringify([holdings, inv?.annual_return, inv?.time_horizon]);

  useEffect(() => {
    if (!inv || holdings.length === 0) return;
    let live = true;
    api
      .portfolio({
        holdings,
        annual_return: inv.annual_return,
        years: inv.time_horizon,
      })
      .then((r) => live && setResult({ key, xray: r, error: null }))
      .catch((e) =>
        live &&
        setResult({
          key,
          xray: null,
          // A dead network and a bad response are different problems and the
          // page says which, rather than blaming the reader's holdings.
          error: e instanceof ApiError ? e.message : "Could not read the portfolio.",
        }),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const fresh = result && result.key === key ? result : null;
  const xray = fresh?.xray ?? null;
  const error = fresh?.error ?? null;

  /* STACK BY MEASUREMENT, not by a breakpoint.
     `table-cards` — the importer's class — asks "is this a phone", and it is
     gated at 639px. That is the wrong question here and the measurement says
     so: this table needs 684px and fits from 768px up, so between 640 and 767
     it rendered as a grid with **174px hidden at 640px, including VALUE** —
     the column carrying the money. The /goals band all over again, and the
     fourth time in this codebase that a table has hidden the column it exists
     to show.
     Widening `table-cards`' own gate was the tempting fix and is wrong: the
     importer shares it, and stacking a 1,200-row import at tablet width costs
     it 7,635px of page height for nothing.
     So this uses `/compare`'s `table-stacked` — ungated, applied when the grid
     would overflow its own scroller — which means ONE stacking rule for both
     pages rather than a second breakpoint that goes stale the moment a column
     changes. `needed` is remembered because only a rendered GRID can say what
     the grid needs: stacked, the table is `display: block` and its scrollWidth
     is merely the scroller's. It cannot paint the wrong thing first, because
     the table renders only once there are holdings and those arrive
     client-side, so there is no server render of it to disagree with. */
  const scroller = useRef<HTMLDivElement | null>(null);
  const [stacked, setStacked] = useState(false);
  const needed = useRef(0);
  const rowKey = holdings.length;

  useMeasure(() => {
    needed.current = 0;
    setStacked(false);
  }, [rowKey]);

  useMeasure(() => {
    const el = scroller.current;
    if (!el) return;
    const decide = () => {
      if (!stacked) needed.current = el.scrollWidth;
      setStacked(needed.current > el.clientWidth);
    };
    decide();
    const ro = new ResizeObserver(decide);
    ro.observe(el);
    return () => ro.disconnect();
  }, [stacked, rowKey]);

  const patch = (i: number, p: Partial<Holding>) =>
    setHoldings(holdings.map((h, j) => (j === i ? { ...h, ...p } : h)));

  const coverage = xray?.expense.coverage_pct;
  const feeLed = coverage !== null && coverage !== undefined && coverage >= FEE_COVERAGE_FLOOR;

  return (
    <>
      <PageHeader
        title="Portfolio X-Ray"
        description="What a list of holdings actually adds up to — concentration, fees and mix. Values are the dollar amounts you enter, not live prices, and nothing here is fetched from anywhere."
      />

      {/* ── The coverage banner, above everything ──────────────────────

          Not a footnote. Every figure on this page is measured over some
          share of the money, and a fee ratio taken across a third of a
          portfolio is indistinguishable from one taken across all of it. */}
      {xray && xray.expense.uncovered.length > 0 && (
        <div className="card mb-8 border-caution">
          <p className="label text-caution">Measured over {pct(coverage)} of this portfolio</p>
          <p className="t-small mt-2 text-body">
            {fmt(xray.expense.uncovered_value)} is in {xray.expense.uncovered.length}{" "}
            {xray.expense.uncovered.length === 1 ? "holding" : "holdings"} this tool has no
            fee or classification data for, so the figures below describe the rest:{" "}
            <span className="text-ink">{xray.expense.uncovered.join(", ")}</span>.
          </p>
          <p className="t-micro mt-2 text-muted">
            401(k) menus often hold institutional share classes with no public ticker, which
            is the usual reason. Concentration and the position weights are unaffected — they
            need no lookup.
          </p>
        </div>
      )}

      {error && (
        <div className="card mb-8 border-critical">
          <p className="label text-critical">Could not measure</p>
          <p className="t-small mt-2 text-body">{error}</p>
        </div>
      )}

      {/* ── Holdings entry ─────────────────────────────────────────── */}
      <Section
        title="Holdings"
        action={
          <button className="btn-secondary" onClick={() => setHoldings([...holdings, blankHolding()])}>
            Add a holding
          </button>
        }
      >
        {holdings.length === 0 ? (
          <Empty>
            Add what someone holds — a ticker, what it is, and how many dollars are in it.
            Dollars rather than shares, because a share count would need a live price.
          </Empty>
        ) : (
          <div ref={scroller} className="card card-flush overflow-x-auto">
            {/* Stacked into label/value lines whenever the grid would not
                fit, from `data-label` on the cells rather than a second block
                of JSX — one rendering, so a column cannot say one thing on a
                phone and another on a laptop. Every cell in this row is a
                DECISION: dropping columns the way the four data tables do left
                a 375px phone with both selects at ZERO width and no way to say
                that a holding is cash, a stock, or the employer's. */}
            <table className={stacked ? "table-stacked" : undefined}>
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Name</th>
                  <th>Type</th>
                  <th>Account</th>
                  <th className="text-right">Value</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {holdings.map((h, i) => (
                  <tr key={h.id}>
                    <td data-label="Symbol">
                      <input
                        type="text"
                        value={h.symbol}
                        onChange={(e) => patch(i, { symbol: e.target.value.toUpperCase() })}
                        placeholder="VTI"
                        aria-label={`Symbol for holding ${i + 1}`}
                        className="font-num w-24"
                      />
                    </td>
                    <td data-label="Name">
                      <input
                        type="text"
                        value={h.label}
                        onChange={(e) => patch(i, { label: e.target.value })}
                        placeholder="What they call it"
                        aria-label={`Name for holding ${i + 1}`}
                      />
                    </td>
                    <td data-label="Type">
                      <select
                        value={h.employer_stock ? "employer" : h.kind}
                        onChange={(e) =>
                          patch(
                            i,
                            e.target.value === "employer"
                              ? { kind: "stock", employer_stock: true }
                              : { kind: e.target.value, employer_stock: false },
                          )
                        }
                        aria-label={`Type of holding ${i + 1}`}
                        className="t-micro w-auto py-1"
                      >
                        {KINDS.map((k) => (
                          <option key={k.v} value={k.v}>
                            {k.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td data-label="Account">
                      <select
                        value={h.account}
                        onChange={(e) => patch(i, { account: e.target.value })}
                        aria-label={`Account for holding ${i + 1}`}
                        className="t-micro w-auto py-1"
                      >
                        {ACCOUNTS.map((a) => (
                          <option key={a} value={a}>
                            {a}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td data-label="Value" className="text-right">
                      <NumberInput
                        value={h.value}
                        onChange={(v) => patch(i, { value: v })}
                        step={100}
                        min={0}
                        prefix="$"
                        aria-label={`Value of holding ${i + 1}`}
                        className="w-32 text-right"
                      />
                    </td>
                    <td className="w-8 text-right">
                      <button
                        className="btn-remove-quiet"
                        aria-label={`Remove holding ${i + 1}`}
                        onClick={() => setHoldings(holdings.filter((_, j) => j !== i))}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      </Section>

      {xray && xray.total > 0 && (
        <>
          {/* ── Concentration. Needs no lookup, so it has no coverage. ── */}
          <Section title={`What this is — ${fmt(xray.total)} across ${xray.concentration.count}`}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatusCard
                label="Largest position"
                value={pct(xray.concentration.largest_pct)}
                status={xray.concentration.largest ?? "—"}
                tone="info"
              />
              <StatusCard
                label="Effective holdings"
                value={count(xray.concentration.effective_holdings)}
                status={`of ${xray.concentration.count} held`}
                tone="info"
                description="The number of equal-sized positions this portfolio is as concentrated as. Across positions only."
              />
              {xray.concentration.count > 5 && (
                <StatusCard
                  label="Top five"
                  value={pct(xray.concentration.top5_pct)}
                  status="of the portfolio"
                  tone="info"
                />
              )}
              <StatusCard
                label="Cash"
                value={pct(xray.cash_pct_of_total)}
                status="of the whole portfolio"
                tone="info"
              />
            </div>

            {xray.concentration_understated && (
              <p className="t-small mt-4 text-muted">
                These are position weights, and they are the <em>lowest</em> the real figures
                can be. {xray.fund_count === 1 ? "The fund" : `The ${xray.fund_count} funds`} here
                hold companies this tool cannot see inside, so anything also held directly is
                more concentrated than the table shows.
              </p>
            )}
          </Section>

          {/* ── Fees ──────────────────────────────────────────────── */}
          <Section title="What it costs">
            {xray.expense.weighted_er === null ? (
              <Empty>
                No holding here has a fee this tool could look up, so there is nothing to
                measure — not a fee of zero.
              </Empty>
            ) : (
              <div className="card">
                {feeLed ? (
                  <>
                    <p className="font-num t-h2 text-ink">{pct(xray.expense.weighted_er, 2)}</p>
                    <p className="t-small mt-1 text-body">
                      weighted average expense ratio — {fmt(xray.expense.annual_cost)} a year,
                      measured over {pct(coverage)} of the portfolio.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="label text-caution">Too little of this portfolio to lead with</p>
                    <p className="t-small mt-2 text-body">
                      Only {pct(coverage)} of the money has a fee this tool could look up. Over
                      that share the weighted expense ratio is{" "}
                      <span className="font-num text-ink">{pct(xray.expense.weighted_er, 2)}</span>{" "}
                      ({fmt(xray.expense.annual_cost)} a year) — but that describes{" "}
                      {fmt(xray.expense.covered_value)}, not {fmt(xray.total)}.
                    </p>
                  </>
                )}

                {xray.fee_drag && (
                  <p className="t-small mt-4 border-t border-hair pt-4 text-body">
                    Left alone for {xray.fee_drag.years} years at {pct(xray.fee_drag.rate)},
                    that fee costs{" "}
                    <span className="font-num text-caution">{fmt(xray.fee_drag.cost)}</span> —{" "}
                    {fmt(xray.fee_drag.with_fees)} instead of {fmt(xray.fee_drag.without_fees)} on
                    the {fmt(xray.fee_drag.on_value)} it could be measured over. Same projection
                    the Investments page uses, so the two cannot disagree.
                  </p>
                )}

                {/* Provenance, split rather than blanket. Most ratios are
                    now the fund's own filed figure; the rest are not, and
                    saying "verified" over the mixture would be the claim this
                    page removed once already. */}
                {xray.expense.unsourced.length === 0 ? (
                  <p className="t-micro mt-4 text-muted">
                    Every expense ratio here is the fund&rsquo;s own filed figure, read
                    from its SEC prospectus filing. Table last compiled {xray.as_of}.
                  </p>
                ) : (
                  <p className="t-micro mt-4 text-muted">
                    {pct(xray.expense.sourced_pct)} of the measured money uses the
                    fund&rsquo;s own filed expense ratio, read from its SEC prospectus
                    filing. The rest &mdash;{" "}
                    <span className="text-caution">{xray.expense.unsourced.join(", ")}</span>{" "}
                    &mdash; is a hand-written figure not yet checked against a filing.
                    Table last compiled {xray.as_of}.
                  </p>
                )}
              </div>
            )}
          </Section>

          {/* ── Mix ───────────────────────────────────────────────── */}
          <Section title="What it is made of">
            <div className="grid gap-4 lg:grid-cols-2">
              {xray.mix.class_rows.length > 0 ? (
                <DonutChart
                  title="By asset class"
                  data={xray.mix.class_rows.map((r) => ({ name: r.label, value: r.value }))}
                  total={pct(xray.mix.class_coverage_pct)}
                  totalLabel="of the portfolio classified"
                />
              ) : (
                <Empty>Nothing here could be classified.</Empty>
              )}

              <div className="card">
                <p className="label text-ink">By region</p>
                {xray.mix.region_rows.length === 0 ? (
                  <p className="t-small mt-3 text-muted">
                    Nothing here carries a region in this data.
                  </p>
                ) : (
                  <table className="mt-3">
                    <tbody>
                      {xray.mix.region_rows.map((r) => (
                        <tr key={r.key}>
                          <td className="text-ink">{r.label}</td>
                          <td className="font-num text-right">{pct(r.pct)}</td>
                          <td className="font-num text-right text-muted">{fmt(r.value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <p className="t-micro mt-3 text-muted">
                  Measured over {pct(xray.mix.region_coverage_pct)} of the portfolio.
                  {xray.mix.region_unknown_stock_value > 0 && (
                    <>
                      {" "}
                      {fmt(xray.mix.region_unknown_stock_value)} of that is individual stocks,
                      which carry no region here — a US listing is usually a US company, and
                      &ldquo;usually&rdquo; is not a measurement.
                    </>
                  )}
                </p>
              </div>
            </div>
          </Section>

          {/* ── The two things worth saying out loud ──────────────── */}
          {(xray.duplicates.length > 0 || xray.employer_stock) && (
            <Section title="Worth knowing">
              <div className="grid gap-4 sm:grid-cols-2">
                {xray.employer_stock && (
                  <div className="card border-caution">
                    <p className="label text-caution">Employer stock</p>
                    <p className="t-small mt-2 text-body">
                      <span className="font-num text-ink">{pct(xray.employer_stock.pct)}</span> of
                      the portfolio ({fmt(xray.employer_stock.value)}) is{" "}
                      {xray.employer_stock.names.join(", ")}. The position and the paycheck are
                      the same company.
                    </p>
                  </div>
                )}
                {xray.duplicates.map((d) => (
                  <div key={d.symbol} className="card">
                    <p className="label text-ink">{d.symbol} is held twice</p>
                    <p className="t-small mt-2 text-body">
                      {fmt(d.value)} ({pct(d.pct)}) across {d.accounts.join(" and ")}. It reads as
                      two holdings and it is one bet.
                    </p>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* ── Look-through ──────────────────────────────────────
              The one thing here nobody can work out for themselves, and the
              one the September research found no free manual-entry tool has
              offered since Morningstar retired Instant X-Ray in April 2025. */}
          {xray.lookthrough.positions.length > 0 && (
            <Section title="What you own, counting through the funds">
              <div className="card mb-4">
                <p className="t-small text-body">
                  Measured across{" "}
                  <span className="font-num text-ink">
                    {pct(xray.lookthrough.seen_pct)}
                  </span>{" "}
                  of the portfolio. Each fund stores its largest holdings, not all of
                  them, so {fmt(xray.lookthrough.unseen_value)} is not attributed to any
                  company here — and every figure below is therefore the{" "}
                  <em>lowest</em> it can be.
                  {xray.lookthrough.unseen.length > 0 && (
                    <>
                      {" "}
                      <span className="text-caution">
                        {xray.lookthrough.unseen.join(", ")}
                      </span>{" "}
                      {xray.lookthrough.unseen.length === 1 ? "has" : "have"} no holdings
                      data at all.
                    </>
                  )}
                </p>
              </div>

              <div className="card card-flush overflow-x-auto">
                <table>
                  <thead>
                    <tr>
                      <th>Company</th>
                      <th className="hidden sm:table-cell text-right">Held directly</th>
                      <th className="hidden sm:table-cell text-right">Through funds</th>
                      <th className="text-right">Total</th>
                      <th className="text-right">Of portfolio</th>
                    </tr>
                  </thead>
                  <tbody>
                    {xray.lookthrough.positions.slice(0, 12).map((p) => (
                      <tr key={p.key}>
                        <td className="text-ink">
                          {p.name}
                          {p.ticker && (
                            <span className="font-num t-micro ml-2 text-muted">
                              {p.ticker}
                            </span>
                          )}
                          {p.both && (
                            <span className="badge badge-caution t-micro ml-2">
                              both
                            </span>
                          )}
                        </td>
                        <td className="font-num hidden sm:table-cell text-right text-muted">
                          {p.direct > 0 ? fmt(p.direct) : "—"}
                        </td>
                        <td className="font-num hidden sm:table-cell text-right text-muted">
                          {p.via > 0 ? fmt(p.via) : "—"}
                        </td>
                        <td className="font-num text-right whitespace-nowrap">
                          {fmt(p.value)}
                        </td>
                        <td className="font-num text-right text-ink">{pct(p.pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* The sentence the whole feature exists for. Only rendered when
                  it is TRUE of this portfolio — a page that always says it is
                  a page that has not measured anything. */}
              {xray.lookthrough.positions.some((p) => p.both) && (
                <p className="t-small mt-4 text-body">
                  Marked <span className="badge badge-caution t-micro">both</span>{" "}
                  means you hold it outright <em>and</em> through a fund. The funds are
                  the part you cannot see on a statement:{" "}
                  {xray.lookthrough.positions
                    .filter((p) => p.both)
                    .slice(0, 3)
                    .map((p) => `${p.name} ${pct(p.pct)}`)
                    .join(", ")}
                  .
                </p>
              )}

              <p className="t-micro mt-3 text-muted">
                Fund holdings from each fund&rsquo;s own N-PORT filing with the SEC,
                most recent as of {xray.lookthrough.as_of}.
              </p>
            </Section>
          )}

          {/* ── Positions ─────────────────────────────────────────── */}
          <Section title="Every position">
            <div className="card card-flush overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Holding</th>
                    <th className="hidden sm:table-cell">Account</th>
                    <th className="text-right">Value</th>
                    <th className="text-right">Weight</th>
                    <th className="text-right">Fee</th>
                  </tr>
                </thead>
                <tbody>
                  {xray.positions.map((p) => (
                    <tr key={p.id}>
                      <td className="text-ink">
                        {p.label || p.symbol || "(unnamed)"}
                        {p.symbol && p.label && (
                          <span className="font-num t-micro ml-2 text-muted">{p.symbol}</span>
                        )}
                      </td>
                      <td className="hidden text-muted sm:table-cell">{p.account || "—"}</td>
                      <td className="font-num text-right whitespace-nowrap">{fmt(p.value)}</td>
                      <td className="font-num text-right">{pct(p.weight)}</td>
                      <td className="font-num text-right">
                        {p.er === null ? (
                          <span className="t-micro text-caution">not in table</span>
                        ) : (
                          pct(p.er, 2)
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Section>

          {/* ── What this cannot do ───────────────────────────────── */}
          <Section title="What this does not measure">
            <div className="card">
              <ul className="t-small space-y-2 text-body">
                <li>
                  The concentration figures at the top are measured across{" "}
                  <em>positions</em> and cannot see inside a fund, so the real figure is
                  higher wherever a fund and a stock hold the same company. The
                  look-through table does see inside, but only as far as each
                  fund&rsquo;s largest holdings &mdash; it names a floor, never a ceiling.
                </li>
                <li>
                  Expense ratios come from a table of common funds, most of them read
                  from the fund&rsquo;s own SEC prospectus filing; any that were not are
                  named above. Anything not in the table at all is reported as
                  uncovered, never as free.
                </li>
                <li>
                  Values are what was typed in, on the date it was typed. Nothing here is a
                  live price.
                </li>
                <li>
                  Every figure is a statement about the portfolio as entered. None of it is a
                  recommendation to buy, sell or hold anything.
                </li>
              </ul>
            </div>
          </Section>
        </>
      )}

      <Footer />
    </>
  );
}
