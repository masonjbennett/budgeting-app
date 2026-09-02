"use client";

/**
 * The app's single store: the profile, the derived figures, and the account.
 *
 * TWO RULES HOLD THIS TOGETHER.
 *
 * 1. No maths. Not a ratio, not a rate, not a projection. Everything numeric
 *    comes from the API, which is a thin skin over calculations.py. The one
 *    exception is adding up numbers a user typed — totalling a column of assets
 *    is not a rule anyone can get wrong in a way that misleads. The moment
 *    something needs a threshold, a denominator or a formula, it belongs in
 *    Python. Both previous versions of this app worked out debt-to-income and
 *    emergency-fund coverage in the display layer and both got them wrong the
 *    same two ways.
 *
 * 2. Nothing is invented. If a number is not known it is null and the UI says
 *    so. The abandoned scaffold drew sparklines from hardcoded arrays and
 *    printed "+$1,700 from last month" as a literal, next to a real balance.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";

import { api, ApiError, type Dashboard, type Debt, type Income } from "@/lib/api";
import { authErrorMessage, cloudConfigured, supabase } from "@/lib/supabase";

// ── The profile ──────────────────────────────────────────────────────

export interface Expense {
  id: string;
  date: string;
  amount: number;
  category: string;
  note: string;
}

export interface Goal {
  name: string;
  target: number;
  current: number;
  deadline: string;
  priority?: number;
}

export interface Snapshot {
  date: string;
  assets: number;
  liabilities: number;
  net_worth: number;
}

export interface Profile {
  income: Income;
  budget: {
    needs: Record<string, number>;
    wants: Record<string, number>;
    savings: Record<string, number>;
  };
  expenses: Expense[];
  recurring_templates: { name: string; amount: number; category: string; day: number }[];
  net_worth_snapshots: Snapshot[];
  assets: Record<string, number>;
  liabilities: Record<string, number>;
  debts: Debt[];
  savings_goals: Goal[];
  investment: {
    starting_amount: number;
    monthly_contribution: number;
    annual_return: number;
    time_horizon: number;
    employer_match_pct: number;
    employer_match_limit: number;
  };
  itemized: Record<string, number>;
}

type Status = "loading" | "ready" | "error";

/** One shape for both, so a caller never has to narrow a union to
 *  find out whether it may read `message`. */
export interface AuthResult {
  error?: string;
  message?: string;
}

interface Ctx {
  profile: Profile | null;
  dashboard: Dashboard | null;
  status: Status;
  error: string | null;
  /** Set while a save is in flight or has just failed, for the sidebar. */
  saveState: "idle" | "saving" | "saved" | "error";
  user: User | null;
  cloudConfigured: boolean;
  update: (patch: Partial<Profile>) => void;
  replaceProfile: (p: Profile) => void;
  resetToDemo: () => Promise<void>;
  resetToEmpty: () => Promise<void>;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signUp: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
}

const FinanceContext = createContext<Ctx | null>(null);

export function useFinance() {
  const ctx = useContext(FinanceContext);
  if (!ctx) throw new Error("useFinance must be used inside <FinanceProvider>");
  return ctx;
}

const SAVE_DEBOUNCE_MS = 1500;

export function FinanceProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<Ctx["saveState"]>("idle");
  const [user, setUser] = useState<User | null>(null);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Every recompute carries a sequence number. Without it a slow earlier
  // response can land after a faster later one and overwrite the newer figures
  // with older ones — with a number that looks entirely plausible.
  const seq = useRef(0);

  const recompute = useCallback(async (p: Profile) => {
    const mine = ++seq.current;
    try {
      const d = await api.dashboard({
        income: p.income,
        itemized: p.itemized,
        debts: p.debts,
        budget_needs: p.budget.needs,
        assets: p.assets,
      });
      if (mine === seq.current) {
        setDashboard(d);
        setError(null);
      }
    } catch (e) {
      if (mine === seq.current) {
        setDashboard(null);
        setError(e instanceof ApiError ? e.message : "Could not calculate your figures.");
      }
    }
  }, []);

  const persist = useCallback(
    (p: Profile, u: User | null) => {
      const db = supabase;   // narrowing does not survive into the callback
      if (!db || !u) return;
      if (saveTimer.current) clearTimeout(saveTimer.current);
      saveTimer.current = setTimeout(async () => {
        setSaveState("saving");
        const { error: err } = await db
          .from("user_data")
          .upsert({ user_id: u.id, app_data: p }, { onConflict: "user_id" });
        setSaveState(err ? "error" : "saved");
      }, SAVE_DEBOUNCE_MS);
    },
    [],
  );

  // ── Boot ───────────────────────────────────────────────────────────
  useEffect(() => {
    let cancelled = false;

    (async () => {
      let loaded: Profile | null = null;

      if (supabase) {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        if (session?.user && !cancelled) {
          setUser(session.user);
          const { data: row } = await supabase
            .from("user_data")
            .select("app_data")
            .eq("user_id", session.user.id)
            .maybeSingle();
          if (row?.app_data) loaded = row.app_data as Profile;
        }
      }

      if (!loaded) {
        try {
          loaded = (await fetch("/api/state").then((r) => r.json())) as Profile;
        } catch {
          if (!cancelled) {
            setStatus("error");
            setError("Could not load your starting profile. Reload to try again.");
          }
          return;
        }
      }

      if (cancelled) return;
      setProfile(loaded);
      setStatus("ready");
      await recompute(loaded);
    })();

    const sub = supabase?.auth.onAuthStateChange((_e, session) => {
      setUser(session?.user ?? null);
    });

    return () => {
      cancelled = true;
      sub?.data.subscription.unsubscribe();
    };
  }, [recompute]);

  // ── Mutations ──────────────────────────────────────────────────────
  const update = useCallback(
    (patch: Partial<Profile>) => {
      setProfile((prev) => {
        if (!prev) return prev;
        const next = { ...prev, ...patch };
        void recompute(next);
        persist(next, user);
        return next;
      });
    },
    [recompute, persist, user],
  );

  const replaceProfile = useCallback(
    (p: Profile) => {
      setProfile(p);
      void recompute(p);
      persist(p, user);
    },
    [recompute, persist, user],
  );

  const loadStarting = useCallback(
    async (demo: boolean) => {
      const p = (await fetch(`/api/state?demo=${demo}`).then((r) => r.json())) as Profile;
      replaceProfile(p);
    },
    [replaceProfile],
  );

  const resetToDemo = useCallback(() => loadStarting(true), [loadStarting]);
  const resetToEmpty = useCallback(() => loadStarting(false), [loadStarting]);

  // ── Account ────────────────────────────────────────────────────────
  const signIn = useCallback(
    async (email: string, password: string): Promise<AuthResult> => {
      if (!supabase) return { error: "Accounts are not configured for this deployment." };
      const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
      if (err) return { error: authErrorMessage(err) };
      setUser(data.user);
      const { data: row } = await supabase
        .from("user_data")
        .select("app_data")
        .eq("user_id", data.user.id)
        .maybeSingle();
      if (row?.app_data) replaceProfile(row.app_data as Profile);
      return {};
    },
    [replaceProfile],
  );

  const signUp = useCallback(async (email: string, password: string): Promise<AuthResult> => {
    if (!supabase) return { error: "Accounts are not configured for this deployment." };
    const { error: err } = await supabase.auth.signUp({ email, password });
    if (err) return { error: authErrorMessage(err) };
    return { message: "Check your email to confirm the account, then log in." };
  }, []);

  const signOut = useCallback(async () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    await supabase?.auth.signOut();
    setUser(null);
    setSaveState("idle");
    await loadStarting(true);
  }, [loadStarting]);

  const value = useMemo<Ctx>(
    () => ({
      profile,
      dashboard,
      status,
      error,
      saveState,
      user,
      cloudConfigured,
      update,
      replaceProfile,
      resetToDemo,
      resetToEmpty,
      signIn,
      signUp,
      signOut,
    }),
    [profile, dashboard, status, error, saveState, user, update, replaceProfile,
     resetToDemo, resetToEmpty, signIn, signUp, signOut],
  );

  return <FinanceContext.Provider value={value}>{children}</FinanceContext.Provider>;
}

// ── Small display helpers (formatting only — no rules) ────────────────

export function fmt(v: number | null | undefined, decimals = 0): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `$${v.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })}`;
}

export function pct(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  return `${v.toFixed(decimals)}%`;
}

export function sum(o: Record<string, number>): number {
  return Object.values(o).reduce((a, b) => a + (Number(b) || 0), 0);
}
