"use client";

import { useEffect, useState } from "react";

import { BarsChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { api, ApiError, type Reference, type RothComparison } from "@/lib/api";
import { fmt, pct, useFinance } from "@/context/FinanceContext";

const ITEMIZED_ROWS: { key: string; label: string; help: string }[] = [
  { key: "mortgage_interest", label: "Mortgage interest", help: "On up to $750k of acquisition debt." },
  { key: "salt", label: "State & local taxes", help: "Capped — the cap phases down above $505k MAGI." },
  { key: "charitable", label: "Charitable giving", help: "Itemizers deduct above a 0.5% of AGI floor." },
  { key: "medical", label: "Medical expenses", help: "Only the part above 7.5% of AGI counts." },
];

export default function TaxPage() {
  const { profile, dashboard } = useFinance();
  const { update } = useFinance();
  const [ref, setRef] = useState<Reference | null>(null);
  const [futureRate, setFutureRate] = useState(15);
  const [rothYears, setRothYears] = useState(30);
  const [rothReturn, setRothReturn] = useState(7);
  const [roth, setRoth] = useState<RothComparison | null>(null);
  const [saltCap, setSaltCap] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.reference().then(setRef).catch(() => setRef(null));
  }, []);

  const th = dashboard?.take_home;
  const contribution = th?.contrib_401k ?? 0;
  const currentRate = th ? (th.marginal_fed + th.marginal_state) / 100 : 0;
  const magi = th?.agi ?? 0;
  const filing = th?.filing ?? "Single";

  useEffect(() => {
    if (!th) return;
    let live = true;
    Promise.all([
      api.rothVsTraditional({
        contribution,
        current_rate: currentRate,
        future_rate: futureRate / 100,
        annual_return: rothReturn,
        years: rothYears,
      }),
      api.saltCap(magi, filing),
    ])
      .then(([r, s]) => {
        if (!live) return;
        setRoth(r);
        setSaltCap(s.effective_cap);
        setError(null);
      })
      .catch((e) => live && setError(e instanceof ApiError ? e.message : "Calculation failed"));
    return () => {
      live = false;
    };
  }, [th, contribution, currentRate, futureRate, rothReturn, rothYears, magi, filing]);

  if (!profile || !dashboard || !th) return <div className="skeleton h-96" />;

  const itemized = profile.itemized;
  const setItemized = (k: string, v: number) =>
    update({ itemized: { ...itemized, [k]: v } });

  return (
    <div>
      <PageHeader
        title="Taxes"
        description="2026 federal and state liability from IRS Rev. Proc. 2025-32 as amended by the OBBBA. An estimate, not a return."
      />

      <Section title="This year">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {(
            [
              ["Total tax", fmt(th.total_tax), "text-critical"],
              ["Effective rate", pct(th.effective_rate), "text-ink"],
              ["Marginal federal", pct(th.marginal_fed, 0), "text-ink"],
              ["Marginal state", pct(th.marginal_state, 2), "text-ink"],
            ] as const
          ).map(([label, value, tone]) => (
            <div key={label} className="card">
              <p className="label">{label}</p>
              <p className={`font-num t-h3 mt-1.5 leading-none font-medium ${tone}`}>{value}</p>
            </div>
          ))}
        </div>

        <div className="mt-3">
          <BarsChart
            data={[
              { name: "Federal", value: th.fed_tax },
              { name: "State", value: th.state_tax },
              { name: "FICA", value: th.fica },
            ]}
            xKey="name"
            valueKey="value"
            tones={["critical", "s5", "caution"]}
            height={230}
          />
        </div>

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            ["Gross income", fmt(th.annual_gross)],
            ["AGI", fmt(th.agi)],
            ["Taxable income", fmt(th.taxable)],
          ].map(([label, value]) => (
            <div key={label} className="card">
              <p className="label">{label}</p>
              <p className="font-num t-lead mt-1 text-ink">{value}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Standard vs itemized">
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {ITEMIZED_ROWS.map((r) => (
            <Field
              key={r.key}
              label={r.label}
              help={
                r.key === "salt" && saltCap !== null
                  ? `${r.help} Yours: ${fmt(saltCap)}.`
                  : r.help
              }
            >
              <NumberInput
                value={itemized[r.key] ?? 0}
                onChange={(v) => setItemized(r.key, v)}
                step={500}
                min={0}
                prefix="$"
              />
            </Field>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div className={`card ${!th.itemizing ? "mark-accent" : ""}`}>
            <div className="flex items-baseline justify-between gap-2">
              <p className="label">Standard</p>
              {!th.itemizing && <span className="badge badge-positive">Taken</span>}
            </div>
            <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
              {fmt(th.std_ded)}
            </p>
            <p className="t-micro mt-1.5 text-muted">For {th.filing} in 2026.</p>
          </div>
          <div className={`card ${th.itemizing ? "mark-accent" : ""}`}>
            <div className="flex items-baseline justify-between gap-2">
              <p className="label">Itemized</p>
              {th.itemizing && <span className="badge badge-positive">Taken</span>}
            </div>
            <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
              {fmt(th.itemized_total)}
            </p>
            <p className="t-micro mt-1.5 text-muted">
              After the SALT cap and the AGI floors on charity and medical.
            </p>
          </div>
        </div>
        <p className="t-micro mt-3 leading-relaxed text-muted">
          Whichever is larger is the one used, and it is used everywhere — take-home,
          savings rate, the dashboard and the FIRE timeline all read the same figure.
          A tax page that recommends itemizing while the rest of the app assumes the
          standard deduction is the shape of a real bug this app used to have.
        </p>
      </Section>

      <Section title="Roth vs Traditional">
        <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Field label="Expected retirement tax rate">
            <NumberInput
              value={futureRate}
              onChange={setFutureRate}
              step={1}
              min={0}
              max={60}
              suffix="%"
            />
          </Field>
          <Field label="Years until retirement">
            <NumberInput
              value={rothYears}
              onChange={(v) => setRothYears(Math.round(v))}
              step={1}
              min={1}
              max={60}
            />
          </Field>
          <Field label="Expected return">
            <NumberInput
              value={rothReturn}
              onChange={setRothReturn}
              step={0.5}
              min={0}
              max={20}
              suffix="%"
            />
          </Field>
        </div>

        {error && (
          <div className="card mark-critical t-small text-critical">{error}</div>
        )}

        {roth && (
          <>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className={`card ${roth.better === "Traditional" ? "mark-accent" : ""}`}>
                <p className="label">Traditional (pre-tax)</p>
                <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                  {fmt(roth.traditional_after_tax)}
                </p>
                <p className="t-micro mt-1.5 text-muted">
                  Contribute {fmt(roth.contribution)}/yr pre-tax → grows to{" "}
                  {fmt(roth.traditional_future)} → {futureRate}% tax on withdrawal.
                </p>
              </div>
              <div className={`card ${roth.better !== "Traditional" ? "mark-accent" : ""}`}>
                <p className="label">Roth (post-tax)</p>
                <p className="font-num t-h3 mt-1.5 leading-none font-medium text-ink">
                  {fmt(roth.roth_future)}
                </p>
                <p className="t-micro mt-1.5 text-muted">
                  Pay {pct(roth.current_rate * 100, 0)} tax now → invest{" "}
                  {fmt(roth.roth_invested)}/yr → nothing owed on withdrawal.
                </p>
              </div>
            </div>

            <div className="card mark-accent mt-3">
              {roth.better === "Equivalent" ? (
                <>
                  <p className="t-base font-semibold text-ink">They come out the same</p>
                  <p className="t-small mt-1 leading-relaxed text-body">
                    Your combined marginal rate now ({pct(roth.current_rate * 100, 1)})
                    equals the rate you expect in retirement, and at equal rates the two
                    are mathematically identical — whatever the contribution, the return
                    or the horizon. Roth still has the edge on things this model does not
                    price: no required minimum distributions, and tax diversification
                    against rates changing.
                  </p>
                </>
              ) : (
                <>
                  <p className="t-base font-semibold text-ink">
                    {roth.better} comes out ahead by {fmt(roth.difference)}
                  </p>
                  <p className="t-small mt-1 leading-relaxed text-body">
                    Your combined federal and state marginal rate is{" "}
                    {pct(roth.current_rate * 100, 1)} now against {futureRate}% expected
                    in retirement.{" "}
                    {roth.better === "Traditional"
                      ? "Deferring at the higher rate and paying at the lower one is the whole advantage."
                      : "Paying at today's lower rate and withdrawing tax-free is the whole advantage — early career is usually when this is true."}
                  </p>
                </>
              )}
            </div>
          </>
        )}
      </Section>

      {ref && (
        <Section title={`${th.filing} brackets · 2026`}>
          <div className="card card-flush overflow-x-auto">
            <table>
              <thead>
                <tr>
                  <th>Taxable income</th>
                  <th className="text-right">Rate</th>
                </tr>
              </thead>
              <tbody>
                {(ref.federal_brackets[th.filing] ?? []).map(([ceiling, rate], i, all) => {
                  const floor = i === 0 ? 0 : (all[i - 1][0] ?? 0);
                  const active =
                    th.taxable > floor && (ceiling === null || th.taxable <= ceiling);
                  return (
                    <tr key={i}>
                      <td className={active ? "font-medium text-ink" : undefined}>
                        <span className="font-num">
                          {fmt(floor)} – {ceiling === null ? "and above" : fmt(ceiling)}
                        </span>
                        {active && (
                          <span className="badge badge-info ml-2">you are here</span>
                        )}
                      </td>
                      <td className="font-num text-right">{(rate * 100).toFixed(0)}%</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>
      )}

      <Footer />
    </div>
  );
}
