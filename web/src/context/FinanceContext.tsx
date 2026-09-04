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
import {
  clearLocalProfile,
  demoNoteState,
  isUntouchedDemo,
  markUntouchedDemo,
  readLocalProfile,
  writeLocalProfile,
} from "@/lib/localProfile";

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

/** One "what if" — the income block plus a city, which is where every
 *  dimension worth varying lives. */
export interface Scenario {
  name: string;
  income: Income;
  city: string;
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
  /** Optional, so a profile exported before the Compare page still imports. */
  scenarios?: Scenario[];
  baseline_city?: string;
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
  /** The served demo profile is loaded and nothing has been edited yet. The
   *  dashboard says so, once, rather than leaving a reader to wonder whose
   *  figures these are. */
  showingUntouchedDemo: boolean;
  dismissDemoNote: () => void;
  /** Which month the dashboard is showing; null means the reader's own. */
  month: string | null;
  setMonth: (m: string | null) => void;
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
  // Read after mount, never during render: localStorage during render is a
  // hydration mismatch, and the server has no browser to ask.
  const [showingUntouchedDemo, setShowingUntouchedDemo] = useState(false);
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

  /* WHICH MONTH THE DASHBOARD IS SHOWING.

     In memory, deliberately: it survives a nav click, because React state does,
     and resets to the current month on a reload. That is the same rule the main
     site applies to its segment state — a returning reader must land on the
     obvious thing rather than wherever they wandered last time.

     It lives here rather than on the page because the dashboard payload is
     fetched here. Nothing else reads `health`, and the fields the other five
     pages DO read — take_home, liquid_assets, top_bracket, dti, the emergency
     fund — are all month-independent, so a month change cannot move them. */
  const [month, setMonthState] = useState<string | null>(null);
  const monthRef = useRef<string | null>(null);

  /** Today, in the READER's timezone. `toISOString()` converts to UTC first
   *  and so returns yesterday for anyone west of Greenwich after 5pm — which
   *  on the last day of a month would tell the engine the month is not over
   *  when it is, and on the 1st that it is a month it has left. */
  const localToday = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate(),
    ).padStart(2, "0")}`;
  };

  const recompute = useCallback(async (p: Profile) => {
    const mine = ++seq.current;
    try {
      const d = await api.dashboard({
        income: p.income,
        itemized: p.itemized,
        debts: p.debts,
        budget_needs: p.budget.needs,
        assets: p.assets,
        // The month's spending and the whole budget, because the savings rate
        // and budget adherence are measured over them. They were worked out in
        // page.tsx for the simple reason that this call never sent the data.
        expenses: p.expenses,
        budget: p.budget,
        // The READER's date. The server's is a month ahead of somebody in
        // Chicago on New Year's Eve, and this decides which month is "this
        // one" and whether it is over.
        today: localToday(),
        // undefined, not null: omitted means "the reader's own month", and
        // the engine decides that rather than the request carrying a guess.
        month: monthRef.current ?? undefined,
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

  /* Moving the strip refetches, because the month is an INPUT to the figures
     rather than a filter over them: which records count, how much of the month
     has elapsed, and whether it can carry a verdict at all are all decided in
     `health_report`. Filtering client-side would be the display layer deciding
     three of those. */
  const setMonth = useCallback(
    (m: string | null) => {
      monthRef.current = m;
      setMonthState(m);
      if (profile) void recompute(profile);
    },
    [profile, recompute],
  );

  const persist = useCallback(
    (p: Profile, u: User | null) => {
      const db = supabase;   // narrowing does not survive into the callback
      // NO ACCOUNT IS NOT NO STORAGE. This returned here and wrote nothing,
      // so a signed-out visitor — the default, and anyone following the link —
      // lost every figure on a refresh. Client-side navigation hid it, because
      // the context lives in the layout; a reload did not. See lib/localProfile.
      if (!u) {
        writeLocalProfile(p);
        return;
      }
      if (!db) return;
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

      // The account first, then this browser's own copy, then the served
      // starting profile. Only reached when there is no user: a stale local
      // copy must never shadow the account.
      if (!loaded) loaded = readLocalProfile();

      let fromServer = false;
      if (!loaded) {
        try {
          loaded = (await fetch("/api/state").then((r) => r.json())) as Profile;
          fromServer = true;
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
      // `fromServer` only: a profile restored from the account or from this
      // browser's own copy is the reader's, whatever it started as. The flag
      // survives reloads so the note does not reappear after being dismissed,
      // and does not appear at all for someone who has edited anything.
      if (fromServer) {
        // Unseen becomes "show". A previous DISMISSAL is respected: without a
        // stored profile there is nothing else to tell this visit apart from
        // a first one, so removing the key on dismiss simply brought the note
        // back on the next load.
        const seen = demoNoteState();
        if (seen === "dismissed") {
          setShowingUntouchedDemo(false);
        } else {
          markUntouchedDemo(true);
          setShowingUntouchedDemo(true);
        }
      } else {
        setShowingUntouchedDemo(isUntouchedDemo());
      }
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
      // Any edit and these are no longer "the demo, untouched".
      markUntouchedDemo(false);
      setShowingUntouchedDemo(false);
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
      // An empty profile needs no explaining; the demo does.
      markUntouchedDemo(demo);
      setShowingUntouchedDemo(demo);
    },
    [replaceProfile],
  );

  const dismissDemoNote = useCallback(() => {
    markUntouchedDemo(false);
    setShowingUntouchedDemo(false);
  }, []);

  const resetToDemo = useCallback(() => loadStarting(true), [loadStarting]);
  const resetToEmpty = useCallback(() => loadStarting(false), [loadStarting]);

  // ── Account ────────────────────────────────────────────────────────
  const signIn = useCallback(
    async (email: string, password: string): Promise<AuthResult> => {
      if (!supabase) return { error: "Accounts are not configured for this deployment." };
      const { data, error: err } = await supabase.auth.signInWithPassword({ email, password });
      if (err) return { error: authErrorMessage(err) };
      setUser(data.user);
      // The account is the source of truth from here, and a local copy left
      // behind would be read on the next signed-out load as if it were this
      // person's — on a shared machine, somebody else's figures.
      clearLocalProfile();
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
      showingUntouchedDemo,
      dismissDemoNote,
      month,
      setMonth,
      signIn,
      signUp,
      signOut,
    }),
    [profile, dashboard, status, error, saveState, user, update, replaceProfile,
     resetToDemo, resetToEmpty, showingUntouchedDemo, dismissDemoNote,
     month, setMonth, signIn, signUp, signOut],
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

/**
 * A large figure, shortened for display — `$36.0M`.
 *
 * Formatting, not a rule: it decides nothing and changes no answer, which is
 * the same standing `fmt`, `pct` and the charts' axis ticks already have. It
 * exists because the FIRE page rendered $36,033,288 beside $148,039,029 at the
 * same size, and at a glance those two read as the same number. Every caller
 * shows the exact value as well — abbreviating and then hiding the real figure
 * would be trading one unreadable number for a vaguer one.
 */
export function abbr(v: number | null | undefined, decimals = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "—";
  const a = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (a >= 1_000_000_000) return `${sign}$${(a / 1_000_000_000).toFixed(decimals)}B`;
  if (a >= 1_000_000) return `${sign}$${(a / 1_000_000).toFixed(decimals)}M`;
  if (a >= 100_000) return `${sign}$${(a / 1_000).toFixed(0)}k`;
  return fmt(v);
}

export function sum(o: Record<string, number>): number {
  return Object.values(o).reduce((a, b) => a + (Number(b) || 0), 0);
}
