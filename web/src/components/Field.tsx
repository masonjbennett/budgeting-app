"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export function Field({
  label,
  help,
  children,
}: {
  label: string;
  help?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="t-small mb-1.5 block font-medium text-body">{label}</label>
      {children}
      {help && <p className="t-micro mt-1 text-muted">{help}</p>}
    </div>
  );
}

/**
 * A number input that lets you clear it.
 *
 * `value={n} onChange={e => set(+e.target.value)}` is the obvious version and
 * it is unusable: deleting the last digit gives "" which coerces to 0, so the
 * field refills with a zero under the cursor and you cannot type "1200" over
 * "800" without fighting it. This keeps the raw string while focused and only
 * reports a number, so an empty box stays empty and commits as `empty` (0 by
 * default) when you leave it.
 */
export function NumberInput({
  value,
  onChange,
  step = 1,
  min,
  max,
  prefix,
  suffix,
  empty = 0,
  className = "",
  ...rest
}: {
  value: number;
  onChange: (v: number) => void;
  step?: number;
  min?: number;
  max?: number;
  prefix?: string;
  suffix?: string;
  empty?: number;
  className?: string;
} & Omit<React.InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "step" | "min" | "max">) {
  const [draft, setDraft] = useState<string | null>(null);
  const focused = useRef(false);

  useEffect(() => {
    if (!focused.current) setDraft(null);
  }, [value]);

  const shown = draft ?? (Number.isFinite(value) ? String(value) : "");

  const commit = (raw: string) => {
    if (raw.trim() === "" || raw === "-" || raw === ".") return onChange(empty);
    const n = Number(raw);
    if (!Number.isFinite(n)) return;
    onChange(min !== undefined && n < min ? min : max !== undefined && n > max ? max : n);
  };

  return (
    <div className="relative">
      {prefix && (
        <span className="t-small pointer-events-none absolute top-1/2 left-2.5 -translate-y-1/2 text-muted">
          {prefix}
        </span>
      )}
      <input
        {...rest}
        type="number"
        inputMode="decimal"
        step={step}
        min={min}
        max={max}
        value={shown}
        onFocus={() => (focused.current = true)}
        onChange={(e) => {
          setDraft(e.target.value);
          commit(e.target.value);
        }}
        onBlur={(e) => {
          focused.current = false;
          setDraft(null);
          commit(e.target.value);
        }}
        // Padding was an INLINE STYLE here rather than a `pl-7` utility, because
        // globals.css styled `input[type="number"]` UNLAYERED (specificity
        // 0,1,1 and above every utility layer), so the class was dead and the
        // "$" rendered directly on top of the value. The element rules now live
        // in `@layer base`, so a utility beats them and the class works — but
        // the inline style stays, because it is the one form that cannot be
        // beaten by anything and this is a control that must not break again.
        // Measured before the layer fix: padding stayed at 12px with the class
        // applied, and the prefix's right edge sat exactly at the x where the
        // text began.
        style={{
          paddingLeft: prefix ? "1.5rem" : undefined,
          paddingRight: suffix ? "2rem" : undefined,
          ...rest.style,
        }}
        className={`font-num ${className}`}
      />
      {suffix && (
        <span className="t-small pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-muted">
          {suffix}
        </span>
      )}
    </div>
  );
}

export function Section({
  title,
  action,
  children,
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="mb-10">
      {/* The slug wraps, and the hairline keeps a minimum width.

          This row is [bar] [title] [hairline] [action] and it used to be a
          single unwrappable line. Both halves of it are sized by things the
          page does not control: the title can carry a formatted total, and an
          action holding a <select> is as wide as the widest CATEGORY NAME THE
          USER TYPED. So no fixed layout is safe, and at 375px /expenses'
          "Transactions · $3,091 across 13" ran 107px past the right edge of
          the phone — the one page-level horizontal overflow in the app.

          The minimum on the hairline is load-bearing rather than cosmetic. It
          is what makes the row wrap BEFORE it overflows: `flex-1` has a basis
          of 0, so the rule surrenders its width silently and the row reports
          that it fits right up until it does not. Two more headers ("Import
          from a bank CSV", and /fire's) were measured sitting at exactly the
          available width with a rule of ZERO — a slug with no rule, one
          character from overflowing. */}
      <div className="mb-4 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="h-[3px] w-6 shrink-0 bg-accent" aria-hidden="true" />
        <h2 className="label text-[11px] text-ink">{title}</h2>
        <div className="rule min-w-6 flex-1" />
        {/* ml-auto is a no-op on one line — the hairline has already taken the
            free space — and right-aligns the action when it wraps, which is
            where it sits when it does not. */}
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="card t-small py-9 text-center text-muted">{children}</div>
  );
}
