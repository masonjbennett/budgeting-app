"use client";

/**
 * What a raise is actually worth.
 *
 * The whole pay stub is run twice server-side rather than a marginal rate
 * applied to the increment, because a raise moves more than tax: a 401(k) set
 * as a PERCENT of salary rises with it. Splitting that out is the difference
 * between "your raise mostly vanished" and the truth, which is that some of it
 * was saved.
 *
 * FICA on the increment comes from `marginal_fica_rate`. Above the Social
 * Security wage base the marginal rate falls from 7.65% to 1.45% because the
 * 6.2% has already stopped — so the average rate, which is the number a naive
 * version reaches for, overstates the tax on a raise by up to five times, for
 * exactly the earners who ask.
 */

import { useEffect, useState } from "react";

import { Field, NumberInput } from "@/components/Field";
import { fmt, pct } from "@/context/FinanceContext";
import { api, ApiError, type Income, type RaiseImpact } from "@/lib/api";

export default function RaisePanel({
  income,
  itemized,
}: {
  income: Income;
  itemized: Record<string, number>;
}) {
  const [increase, setIncrease] = useState(10_000);
  const [result, setResult] = useState<RaiseImpact | null>(null);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify([income, itemized, increase]);
  useEffect(() => {
    let live = true;
    api
      .raiseImpact({ income, itemized, increase })
      .then((r) => live && (setResult(r), setError(null)))
      .catch((e) =>
        live && setError(e instanceof ApiError ? e.message : "Could not model the raise"),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-1">
        <Field
          label="Raise"
          help="Modelled by running your whole pay stub again at the higher salary, not by applying a rate to the difference."
        >
          <NumberInput
            value={increase}
            onChange={setIncrease}
            step={1000}
            min={0}
            prefix="$"
          />
        </Field>
      </div>

      {error && (
        <div className="card mark-critical t-small text-critical lg:col-span-2">{error}</div>
      )}

      {result && !error && (
        <div className="lg:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                ["Take-home", `+${fmt(result.take_home_increase)}`, "text-positive"],
                ["Per month", `+${fmt(result.monthly_take_home_increase)}`, "text-positive"],
                ["Tax", `+${fmt(result.tax_increase)}`, "text-critical"],
                ["Into your 401(k)", `+${fmt(result.pretax_increase)}`, "text-ink"],
              ] as const
            ).map(([label, value, tone]) => (
              <div key={label} className="card">
                <p className="label">{label}</p>
                <p className={`font-num t-lead mt-1.5 leading-none font-medium ${tone}`}>
                  {value}
                </p>
              </div>
            ))}
          </div>
          <p className="t-small mt-3 leading-relaxed text-body">
            You keep{" "}
            <strong className="font-num text-ink">
              {result.kept_share_pct === null ? "—" : pct(result.kept_share_pct, 0)}
            </strong>{" "}
            of a {fmt(result.increase)} raise as take-home.{" "}
            {result.pretax_increase > 0 && (
              <>
                {fmt(result.pretax_increase)} of the rest is not lost — a 401(k) set as a
                percentage of salary rises with it, so that part is saved rather than
                spent.{" "}
              </>
            )}
            Marginal rates on the increment: {pct(result.marginal_fed, 0)} federal,{" "}
            {pct(result.marginal_state, 2)} state,{" "}
            <span className="font-num">{pct(result.marginal_fica_pct, 2)}</span> FICA.
            {result.marginal_fica_pct < 7 && (
              <>
                {" "}
                FICA is below 7.65% because you are past the Social Security wage base,
                where the 6.2% stops — the average rate would overstate the tax on this
                raise several times over.
              </>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
