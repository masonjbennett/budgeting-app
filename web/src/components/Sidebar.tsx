"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useFinance } from "@/context/FinanceContext";

function SaveIndicator() {
  const { saveState, user } = useFinance();
  if (!user || saveState === "idle") return null;
  const map = {
    saving: ["bg-yellow", "Saving\u2026"],
    saved: ["bg-green", "Saved"],
    error: ["bg-red", "Save failed \u2014 your data is still in this browser"],
  } as const;
  const [dot, text] = map[saveState];
  return (
    <p className="mt-1.5 flex items-center gap-1.5 px-2 text-[0.62rem] leading-snug text-muted">
      <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      {text}
    </p>
  );
}

function UserBadge() {
  const { user, signIn, signUp, signOut, cloudConfigured } = useFinance();
  const [showAuth, setShowAuth] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [message, setMessage] = useState<{ text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState(false);

  // Saving is the ONLY thing an account buys. Every calculation on this site
  // works signed out, so a missing or unreachable Supabase project degrades to
  // local-only rather than blanking the app -- the failure that ran for four
  // months telling every visitor their password was wrong.
  if (!cloudConfigured) {
    return (
      <p className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.02] px-2 py-2 text-[0.68rem] leading-snug text-muted">
        Accounts are off for this deployment. Everything still works \u2014 your
        figures just live in this browser.
      </p>
    );
  }

  const submit = async () => {
    setBusy(true);
    setMessage(null);
    const result = mode === "login"
      ? await signIn(email, password)
      : await signUp(email, password);
    setBusy(false);
    if (result.error) {
      setMessage({ text: result.error, ok: false });
    } else if (result.message) {
      setMessage({ text: result.message, ok: true });
    } else {
      setShowAuth(false);
      setEmail("");
      setPassword("");
    }
  };

  if (user) {
    return (
      <div className="mt-2 rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-2">
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 text-[0.55rem] font-bold text-white">
            {user.email?.[0]?.toUpperCase() || "U"}
          </div>
          <p className="flex-1 truncate text-[0.7rem] text-dim">{user.email}</p>
          <button
            onClick={signOut}
            className="text-[0.62rem] text-muted transition-colors hover:text-dim"
          >
            Log out
          </button>
        </div>
        <SaveIndicator />
      </div>
    );
  }

  if (showAuth) {
    return (
      <div className="mt-2 space-y-2 rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-3">
        <div className="flex gap-1 text-[0.68rem]">
          {(["login", "signup"] as const).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setMessage(null); }}
              className={`flex-1 rounded py-1 ${
                mode === m ? "bg-white/[0.08] text-primary" : "text-muted"
              }`}
            >
              {m === "login" ? "Log in" : "Sign up"}
            </button>
          ))}
        </div>
        <input
          type="email"
          placeholder="Email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="text-[0.75rem]"
        />
        <input
          type="password"
          placeholder="Password"
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !busy && submit()}
          className="text-[0.75rem]"
        />
        {message && (
          <p className={`text-[0.65rem] leading-snug ${message.ok ? "text-green" : "text-red"}`}>
            {message.text}
          </p>
        )}
        <button
          onClick={submit}
          disabled={busy || !email || !password}
          className="w-full rounded bg-accent py-1.5 text-[0.72rem] font-medium text-white transition-colors hover:brightness-110 disabled:opacity-40"
        >
          {busy ? "\u2026" : mode === "login" ? "Log in" : "Create account"}
        </button>
        <button
          onClick={() => { setShowAuth(false); setMessage(null); }}
          className="w-full text-[0.65rem] text-muted hover:text-dim"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <button
      onClick={() => setShowAuth(true)}
      className="mt-2 w-full rounded-md border border-white/[0.06] bg-white/[0.03] px-2 py-2 text-left text-[0.72rem] text-muted transition-all hover:border-white/[0.1] hover:text-dim"
    >
      Sign in to save across devices
    </button>
  );
}

const NAV_GROUPS = [
  {
    label: "Overview",
    items: [
      { name: "Dashboard", href: "/", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>) },
    ],
  },
  {
    label: "Manage",
    items: [
      { name: "Income", href: "/income", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M12 2v20M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" /></svg>) },
      { name: "Budget", href: "/budget", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>) },
      { name: "Expenses", href: "/expenses", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>) },
    ],
  },
  {
    label: "Grow",
    items: [
      { name: "Net Worth", href: "/net-worth", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" /></svg>) },
      { name: "Goals", href: "/goals", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></svg>) },
      { name: "Debt", href: "/debt", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M19 14l-7 7m0 0l-7-7m7 7V3" /></svg>) },
    ],
  },
  {
    label: "Plan",
    items: [
      { name: "Investments", href: "/investments", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M7 12l3-3 3 3 4-4M8 21l4-4 4 4M3 4h18M4 4h16v12a1 1 0 01-1 1H5a1 1 0 01-1-1V4z" /></svg>) },
      { name: "FIRE", href: "/fire", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M17.657 18.657A8 8 0 016.343 7.343S7 9 9 10c0-2 .5-5 2.986-7C14 5 16.09 5.777 17.656 7.343A7.975 7.975 0 0120 13a7.975 7.975 0 01-2.343 5.657z" /><path d="M9.879 16.121A3 3 0 1012.015 11L11 14H9c0 .768.293 1.536.879 2.121z" /></svg>) },
      { name: "Taxes", href: "/tax", icon: (<svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}><path d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" /></svg>) },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed top-0 left-0 h-full w-60 bg-[#0a0a0a] flex flex-col z-50 border-r border-white/[0.06]">
      {/* Logo */}
      <div className="px-4 h-14 flex items-center gap-3 border-b border-white/[0.06] shrink-0">
        <div className="w-7 h-7 rounded-md bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-blue-500/20">
          <svg className="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20">
            <path d="M4 4a2 2 0 00-2 2v1h16V6a2 2 0 00-2-2H4zM18 9H2v5a2 2 0 002 2h12a2 2 0 002-2V9zM4 13a1 1 0 011-1h1a1 1 0 110 2H5a1 1 0 01-1-1zm5-1a1 1 0 100 2h1a1 1 0 100-2H9z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-[0.82rem] font-semibold text-white truncate leading-tight">Budget Tracker</p>
          <p className="text-[0.62rem] text-slate-500 truncate">Personal Finance</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto py-3 px-2.5">
        {NAV_GROUPS.map((group, gi) => (
          <div key={group.label} className={gi > 0 ? "mt-6" : ""}>
            <p className="text-[0.62rem] font-semibold uppercase tracking-[0.1em] text-slate-600 px-2 mb-1.5">
              {group.label}
            </p>
            <div className="space-y-[1px]">
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`group flex items-center gap-2.5 px-2 py-[7px] rounded-md text-[0.8rem] transition-all duration-150 relative ${
                      active
                        ? "bg-white/[0.08] text-white font-medium"
                        : "text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]"
                    }`}
                  >
                    {active && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-blue-500 rounded-r-full" />
                    )}
                    <span className={`shrink-0 transition-colors duration-150 ${active ? "text-blue-400" : "text-slate-600 group-hover:text-slate-400"}`}>
                      {item.icon}
                    </span>
                    <span>{item.name}</span>
                    {active && (
                      <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500 shadow-[0_0_6px_rgba(59,130,246,0.6)]" />
                    )}
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-white/[0.06] px-2.5 py-2.5">
        <Link
          href="/data"
          className={`group flex items-center gap-2.5 px-2 py-[7px] rounded-md text-[0.8rem] transition-all duration-150 ${
            pathname === "/data"
              ? "bg-white/[0.08] text-white font-medium"
              : "text-slate-600 hover:text-slate-400 hover:bg-white/[0.04]"
          }`}
        >
          <svg className={`w-4 h-4 shrink-0 ${pathname === "/data" ? "text-blue-400" : "text-slate-600 group-hover:text-slate-400"}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
            <path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <span>Settings</span>
        </Link>

        {/* User */}
        <UserBadge />
      </div>
    </aside>
  );
}
