"use client";

/**
 * The one navigation, at every width.
 *
 * The version this replaces was a `fixed w-60 z-50` rail that was never hidden,
 * while `main` only took its left margin at `lg`. On a 375px screen it covered
 * 64% of the viewport with the dashboard behind it and no way to dismiss it —
 * `elementFromPoint(60, 300)` returned a sidebar element. The app was unusable
 * on a phone, which is where a link from a CV gets opened.
 *
 * So: a rail at `lg` and up, a top bar plus an off-canvas drawer below it. One
 * source of destinations, one account panel, one theme control — the two forms
 * are layout, not two components that can drift apart.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

import { useFinance } from "@/context/FinanceContext";

type Dest = { name: string; href: string; hint: string };

const GROUPS: { label: string; items: Dest[] }[] = [
  {
    label: "Overview",
    items: [{ name: "Dashboard", href: "/", hint: "Where you stand this month" }],
  },
  {
    label: "Manage",
    items: [
      { name: "Income", href: "/income", hint: "Salary, state, pre-tax deductions" },
      { name: "Budget", href: "/budget", hint: "Allocate your take-home" },
      { name: "Expenses", href: "/expenses", hint: "What you actually spent" },
    ],
  },
  {
    label: "Grow",
    items: [
      { name: "Net Worth", href: "/net-worth", hint: "Assets less liabilities" },
      { name: "Goals", href: "/goals", hint: "What you're saving towards" },
      { name: "Debt", href: "/debt", hint: "Avalanche against snowball" },
    ],
  },
  {
    label: "Plan",
    items: [
      { name: "Investments", href: "/investments", hint: "Compound projections" },
      { name: "FIRE", href: "/fire", hint: "Monte Carlo retirement model" },
      { name: "Taxes", href: "/tax", hint: "2026 federal and state" },
    ],
  },
];

const SETTINGS: Dest = { name: "Settings", href: "/data", hint: "Storage, export, reset" };

const ALL: Dest[] = [...GROUPS.flatMap((g) => g.items), SETTINGS];

/* ── Theme ───────────────────────────────────────────────────────────── */

type Theme = "light" | "dark" | "system";
const THEME_KEY = "mjb_budget_theme";

/**
 * The stored theme, read during render rather than corrected after one.
 *
 * The DOM is the source of truth here, not localStorage: the inline script in
 * layout.tsx has already stamped `data-theme` on <html> before first paint, so
 * reading the attribute agrees with what the viewer is actually looking at even
 * if storage is unreadable. Storage is only written, never trusted to render.
 *
 * `useSyncExternalStore` also fixes a real defect and not just a lint error —
 * reading this in an effect renders the toggle on "Auto" for one frame and then
 * moves the highlight, on every page load, for anyone who has chosen a theme.
 */
const themeListeners = new Set<() => void>();

function emitThemeChange() {
  for (const l of themeListeners) l();
}

function subscribeTheme(onChange: () => void): () => void {
  themeListeners.add(onChange);
  // Another tab of the same app is the only other writer.
  window.addEventListener("storage", onChange);
  return () => {
    themeListeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function readTheme(): Theme {
  const stamped = document.documentElement.dataset.theme;
  return stamped === "dark" || stamped === "light" ? stamped : "system";
}

function readServerTheme(): Theme {
  return "system";
}

function useTheme(): [Theme, (t: Theme) => void] {
  const theme = useSyncExternalStore(subscribeTheme, readTheme, readServerTheme);

  const apply = useCallback((t: Theme) => {
    // The attribute IS the state, so it is set first and the store re-read.
    if (t === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = t;
    try {
      if (t === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, t);
    } catch {
      /* private mode, cleared storage — the theme still applied for this
         session; only the memory of it across reloads is lost */
    }
    emitThemeChange();
  }, []);

  return [theme, apply];
}

function ThemeToggle({ compact = false }: { compact?: boolean }) {
  const [theme, setTheme] = useTheme();
  const opts: { v: Theme; label: string }[] = [
    { v: "light", label: "Light" },
    { v: "dark", label: "Dark" },
    { v: "system", label: "Auto" },
  ];
  return (
    <div
      role="group"
      aria-label="Colour theme"
      className={`tab-list w-full ${compact ? "" : "mt-2"}`}
    >
      {opts.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => setTheme(o.v)}
          aria-pressed={theme === o.v}
          className={`tab flex-1 px-0 text-[11px] ${theme === o.v ? "tab-active" : ""}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ── Account ─────────────────────────────────────────────────────────── */

function SaveDot() {
  const { saveState, user } = useFinance();
  if (!user || saveState === "idle") return null;
  const map = {
    saving: ["bg-caution", "Saving…"],
    saved: ["bg-positive", "Saved"],
    error: ["bg-critical", "Not saved — still in this browser"],
  } as const;
  const [dot, text] = map[saveState];
  return (
    <p className="mt-2 flex items-start gap-1.5 text-[11px] leading-snug text-muted">
      <span className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      {text}
    </p>
  );
}

function Account() {
  const { user, signIn, signUp, signOut, cloudConfigured } = useFinance();
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  if (!cloudConfigured) {
    return (
      <p className="text-[11px] leading-snug text-muted">
        Accounts are off for this deployment. Everything still works — your figures
        just live in this browser.
      </p>
    );
  }

  if (user) {
    return (
      <div>
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-xs bg-accent font-mono text-[10px] font-bold text-card">
            {user.email?.[0]?.toUpperCase() ?? "U"}
          </span>
          <span className="min-w-0 flex-1 truncate t-small text-body" title={user.email}>
            {user.email}
          </span>
          <button onClick={signOut} className="btn-ghost text-[11px]">
            Sign out
          </button>
        </div>
        <SaveDot />
      </div>
    );
  }

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="btn-secondary w-full text-[12px]">
        Sign in to save
      </button>
    );
  }

  const submit = async () => {
    setBusy(true);
    setMsg(null);
    const r = mode === "login" ? await signIn(email, password) : await signUp(email, password);
    setBusy(false);
    if (r.error) setMsg({ text: r.error, ok: false });
    else if (r.message) setMsg({ text: r.message, ok: true });
    else {
      setOpen(false);
      setEmail("");
      setPassword("");
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="tab-list w-full">
        {(["login", "signup"] as const).map((m) => (
          <button
            key={m}
            onClick={() => {
              setMode(m);
              setMsg(null);
            }}
            className={`tab flex-1 px-0 text-[11px] ${mode === m ? "tab-active" : ""}`}
          >
            {m === "login" ? "Sign in" : "Create"}
          </button>
        ))}
      </div>
      <input
        type="email"
        placeholder="Email"
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="t-small"
      />
      <input
        type="password"
        placeholder="Password"
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && !busy && submit()}
        className="t-small"
      />
      {msg && (
        <p className={`text-[11px] leading-snug ${msg.ok ? "text-positive" : "text-critical"}`}>
          {msg.text}
        </p>
      )}
      <button
        onClick={submit}
        disabled={busy || !email || !password}
        className="btn-primary w-full text-[12px]"
      >
        {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
      </button>
      <button onClick={() => setOpen(false)} className="btn-ghost text-[11px]">
        Cancel
      </button>
    </div>
  );
}

/* ── Destinations ────────────────────────────────────────────────────── */

function Destinations({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-5" aria-label="Sections">
      {GROUPS.map((group) => (
        <div key={group.label}>
          <p className="label mb-1.5 px-2.5">{group.label}</p>
          <ul className="flex list-none flex-col gap-px p-0">
            {group.items.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    onClick={onNavigate}
                    aria-current={active ? "page" : undefined}
                    title={item.hint}
                    className={`relative block rounded-xs px-2.5 py-[7px] text-[13.5px] transition-colors ${
                      active
                        ? "bg-raise font-medium text-ink"
                        : "text-body hover:bg-raise hover:text-ink"
                    }`}
                  >
                    {active && (
                      <span className="absolute top-1/2 left-0 h-3.5 w-[2px] -translate-y-1/2 bg-accent" />
                    )}
                    {item.name}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}

function Wordmark() {
  return (
    <Link href="/" className="flex items-baseline gap-2 no-underline">
      <span className="font-display text-[19px] leading-none text-ink">Budget</span>
      <span className="label !text-[9px]">Planner</span>
    </Link>
  );
}

/* ── The component ───────────────────────────────────────────────────── */

export default function Nav() {
  const pathname = usePathname();
  // The drawer remembers WHICH route it was opened over, and is closed by
  // definition on any other one. A drawer that survives navigation hides the
  // page you just asked for; deriving that during render rather than
  // correcting it in an effect means the new page is never painted with the
  // drawer still over it, and it covers browser back/forward as well as the
  // links, which an onClick handler alone would not.
  const [openedOver, setOpenedOver] = useState<string | null>(null);
  const open = openedOver === pathname;
  const setOpen = useCallback(
    (next: boolean) => setOpenedOver(next ? pathname : null),
    [pathname],
  );
  const openerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        // The raw setter, not `setOpen` — it is stable, so the listener does
        // not have to be torn down and rebuilt every time the route changes.
        setOpenedOver(null);
        openerRef.current?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    panelRef.current?.querySelector<HTMLElement>("a, button")?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open]);

  const current = ALL.find((d) => d.href === pathname);

  return (
    <>
      {/* ── Mobile bar ─────────────────────────────────────────────── */}
      <header className="fixed inset-x-0 top-0 z-40 flex h-14 items-center gap-3 border-b border-hair bg-paper px-4 lg:hidden">
        <button
          ref={openerRef}
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          aria-expanded={open}
          className="btn-ghost -ml-1 !p-2"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
            <path d="M2 4.5h14M2 9h14M2 13.5h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
        <Wordmark />
        {current && current.href !== "/" && (
          <>
            <span className="text-faint" aria-hidden="true">/</span>
            <span className="truncate text-[13px] text-muted">{current.name}</span>
          </>
        )}
      </header>

      {/* ── Drawer ─────────────────────────────────────────────────── */}
      <div
        onClick={() => setOpen(false)}
        aria-hidden="true"
        className={`fixed inset-0 z-40 bg-ink/35 transition-opacity duration-200 lg:hidden ${
          open ? "opacity-100" : "pointer-events-none opacity-0"
        }`}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        className={`fixed inset-y-0 left-0 z-50 flex w-[16rem] flex-col border-r border-hair bg-paper transition-transform duration-200 ease-out lg:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-14 shrink-0 items-center justify-between border-b border-hair px-4">
          <Wordmark />
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              openerRef.current?.focus();
            }}
            aria-label="Close navigation"
            className="btn-ghost !p-2"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-5">
          <Destinations onNavigate={() => setOpen(false)} />
        </div>
        <div className="shrink-0 border-t border-hair px-3 py-3">
          <Link
            href={SETTINGS.href}
            className="mb-2 block rounded-xs px-2.5 py-[7px] text-[13.5px] text-body hover:bg-raise hover:text-ink"
          >
            {SETTINGS.name}
          </Link>
          <Account />
          <ThemeToggle />
        </div>
      </div>

      {/* ── Desktop rail ───────────────────────────────────────────── */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[13rem] flex-col border-r border-hair bg-paper lg:flex">
        <div className="flex h-[4.25rem] shrink-0 items-center border-b border-hair px-4">
          <Wordmark />
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-5">
          <Destinations />
        </div>
        <div className="shrink-0 border-t border-hair px-3 py-3">
          <Link
            href={SETTINGS.href}
            aria-current={pathname === SETTINGS.href ? "page" : undefined}
            className={`mb-2 block rounded-xs px-2.5 py-[7px] text-[13.5px] transition-colors ${
              pathname === SETTINGS.href
                ? "bg-raise font-medium text-ink"
                : "text-body hover:bg-raise hover:text-ink"
            }`}
          >
            {SETTINGS.name}
          </Link>
          <Account />
          <ThemeToggle />
        </div>
      </aside>
    </>
  );
}
