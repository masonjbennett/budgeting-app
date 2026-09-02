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
      <label className="mb-1.5 block text-[0.78rem] font-medium text-dim">{label}</label>
      {children}
      {help && <p className="mt-1 text-[0.68rem] leading-snug text-muted">{help}</p>}
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
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[0.8125rem] text-muted">
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
        // Padding is an INLINE STYLE, not a `pl-7` utility class. globals.css
        // styles `input[type="number"]` by element+attribute (specificity
        // 0,1,1), which beats a `.pl-7` class (0,1,0) — so the utility was dead
        // and the "$" rendered directly on top of the value. Same shape as the
        // Streamlit sidebar rules that lost to a matched descendant selector: a
        // dead style rule is invisible until you measure it. Verified: padding
        // was 12px with the class, and the prefix's right edge sat at exactly
        // the x where the text began.
        style={{
          paddingLeft: prefix ? "1.75rem" : undefined,
          paddingRight: suffix ? "2rem" : undefined,
          ...rest.style,
        }}
        className={`font-num ${className}`}
      />
      {suffix && (
        <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-[0.8125rem] text-muted">
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
      <div className="mb-4 flex items-center gap-3">
        <h2 className="text-[0.72rem] font-medium uppercase tracking-[0.1em] text-muted">
          {title}
        </h2>
        <div className="h-px flex-1 bg-white/[0.06]" />
        {action}
      </div>
      {children}
    </section>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="card py-10 text-center text-[0.85rem] text-dim">{children}</div>
  );
}
