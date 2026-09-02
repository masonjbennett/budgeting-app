"use client";

import { useEffect, useState } from "react";

import { BarsChart } from "@/components/Chart";
import { Field, NumberInput, Section } from "@/components/Field";
import Footer from "@/components/Footer";
import PageHeader from "@/components/PageHeader";
import { api, type Reference } from "@/lib/api";
import { fmt, pct, useFinance } from "@/context/FinanceContext";

const BONUS_TYPES = ["None", "Annual (spread monthly)", "Annual (lump sum)"];

export default function IncomePage() {
  const { profile, dashboard, update } = useFinance();
  const [ref, setRef] = useState<Reference | null>(null);

  useEffect(() => {
    api.reference().then(setRef).catch(() => setRef(null));
  }, []);

  if (!profile || !dashboard) {
    return <div className="skeleton h-96 rounded-xl" />;
  }

  const inc = profile.income;
  const th = dashboard.take_home;
  const set = (patch: Partial<typeof inc>) =>
    update({ income: { ...inc, ...patch } });

  const contribDollars = th.contrib_401k;
  const hsaAnnual = th.hsa;
  const overK401 = ref ? contribDollars >= ref.k401_limit : false;
  const overHsa = ref ? hsaAnnual > ref.hsa_individual_limit : false;

  return (
    <div>
      <PageHeader
        title="Income Setup"
        description="Your salary, location and pre-tax deductions. Everything downstream — budget, savings rate, FIRE timeline — is calculated from this."
      />

      <Section title="Salary & location">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Gross annual salary">
            <NumberInput
              value={inc.gross_salary}
              onChange={(v) => set({ gross_salary: v })}
              step={1000}
              min={0}
              prefix="$"
            />
          </Field>
          <Field label="State">
            <select
              value={inc.state}
              onChange={(e) => set({ state: e.target.value })}
              disabled={!ref}
            >
              {(ref?.states ?? [inc.state]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Filing status">
            <select
              value={inc.filing_status}
              onChange={(e) => set({ filing_status: e.target.value })}
              disabled={!ref}
            >
              {(ref?.filing_statuses ?? [inc.filing_status]).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Student loan interest paid"
            help="Deductible up to $2,500, phasing out at higher incomes."
          >
            <NumberInput
              value={inc.student_loan_interest}
              onChange={(v) => set({ student_loan_interest: v })}
              step={100}
              min={0}
              prefix="$"
            />
          </Field>
        </div>
      </Section>

      <Section title="Bonus">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Field label="Bonus type">
            <select
              value={inc.bonus_type}
              onChange={(e) => set({ bonus_type: e.target.value })}
            >
              {BONUS_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
          <Field
            label="Bonus amount"
            help={
              inc.bonus_type === "None"
                ? "Not counted while the type is None."
                : "Taxed as ordinary income in this model."
            }
          >
            <NumberInput
              value={inc.bonus_amount}
              onChange={(v) => set({ bonus_amount: v })}
              step={1000}
              min={0}
              prefix="$"
              disabled={inc.bonus_type === "None"}
            />
          </Field>
        </div>
      </Section>

      <Section title="Pre-tax deductions">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Field
            label="401(k) contribution"
            help={
              ref ? (
                <>
                  {fmt(contribDollars)}/yr
                  {overK401 && (
                    <span className="text-yellow">
                      {" "}
                      · capped at the {fmt(ref.k401_limit)} IRS limit
                    </span>
                  )}
                </>
              ) : (
                `${fmt(contribDollars)}/yr`
              )
            }
          >
            <NumberInput
              value={inc.contribution_401k}
              onChange={(v) => set({ contribution_401k: v })}
              step={1}
              min={0}
              max={100}
              suffix="%"
            />
          </Field>
          <Field label="Health insurance" help={`${fmt(th.health)}/yr`}>
            <NumberInput
              value={inc.health_insurance}
              onChange={(v) => set({ health_insurance: v })}
              step={10}
              min={0}
              prefix="$"
              suffix="/mo"
            />
          </Field>
          <Field
            label="HSA"
            help={
              <>
                {fmt(hsaAnnual)}/yr
                {overHsa && ref && (
                  <span className="text-yellow">
                    {" "}
                    · above the {fmt(ref.hsa_individual_limit)} self-only limit
                  </span>
                )}
              </>
            }
          >
            <NumberInput
              value={inc.hsa}
              onChange={(v) => set({ hsa: v })}
              step={25}
              min={0}
              prefix="$"
              suffix="/mo"
            />
          </Field>
        </div>
      </Section>

      <Section title="Take-home pay">
        <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[
            ["Monthly take-home", fmt(th.monthly_take_home), "text-green"],
            ["Annual take-home", fmt(th.annual_take_home), "text-primary"],
            ["Total tax", fmt(th.total_tax), "text-red"],
            ["Effective rate", pct(th.effective_rate), "text-primary"],
          ].map(([label, value, tone]) => (
            <div key={label} className="card">
              <p className="text-[0.6875rem] font-medium uppercase tracking-[0.06em] text-muted">
                {label}
              </p>
              <p className={`mt-1 font-num text-[1.6rem] font-bold leading-none ${tone}`}>
                {value}
              </p>
            </div>
          ))}
        </div>

        <BarsChart
          title="Where the gross goes"
          data={[
            { name: "Gross", value: th.annual_gross },
            { name: "Pre-tax", value: th.pretax },
            { name: "Federal", value: th.fed_tax },
            { name: "State", value: th.state_tax },
            { name: "FICA", value: th.fica },
            { name: "Take-home", value: th.annual_take_home },
          ]}
          xKey="name"
          valueKey="value"
          colors={["#5b8def", "#818cf8", "#f87171", "#fb923c", "#fbbf24", "#4ade80"]}
          height={280}
        />

        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div className="card">
            <p className="text-[0.72rem] text-muted">Marginal federal rate</p>
            <p className="mt-0.5 font-num text-[1.1rem] text-primary">
              {pct(th.marginal_fed, 0)}
            </p>
          </div>
          <div className="card">
            <p className="text-[0.72rem] text-muted">Marginal state rate</p>
            <p className="mt-0.5 font-num text-[1.1rem] text-primary">
              {pct(th.marginal_state, 2)}
            </p>
            <p className="mt-1 text-[0.65rem] leading-snug text-muted">
              Your rate at this income — not {inc.state}&apos;s top bracket.
            </p>
          </div>
          <div className="card">
            <p className="text-[0.72rem] text-muted">Deduction taken</p>
            <p className="mt-0.5 font-num text-[1.1rem] text-primary">
              {fmt(th.deduction_taken)}
            </p>
            <p className="mt-1 text-[0.65rem] leading-snug text-muted">
              {th.itemizing
                ? "Itemized — larger than the standard deduction."
                : `Standard deduction for ${th.filing}.`}
            </p>
          </div>
        </div>
      </Section>

      <Footer />
    </div>
  );
}
