"use client";

/**
 * Where a signed-out visitor's figures live between page loads.
 *
 * WHY THIS EXISTS. `persist()` writes to Supabase and returns immediately
 * without a user, and there was no localStorage anywhere — so for a signed-out
 * visitor, which is the default and what anyone following the link is, nothing
 * was written down at all. Client-side navigation kept the work because the
 * context lives in the layout, but a REFRESH lost it: measured, a budget
 * category added and then reloaded was gone, and the app's own copy said the
 * figures were "gone when you close it", which understated a refresh, a deep
 * link, and a restored tab.
 *
 * The account remains the way to carry figures BETWEEN browsers. This only
 * stops one browser forgetting them between two page loads.
 *
 * FOUR GUARDS, EACH FROM A LESSON THIS PROJECT HAS ALREADY PAID FOR.
 *
 * 1. NEVER STORE AN EMPTY OR FAILED PAYLOAD. The main site cached an empty
 *    200 for six hours and a server-side fix could not reach anyone holding
 *    one. `isProfile` rejects anything without the shape's required keys, so a
 *    half-loaded or error object cannot be written and cannot be read back.
 * 2. THE KEY IS VERSIONED. A schema change makes every stored profile
 *    unreadable rather than subtly wrong; bump the version and the old ones
 *    are ignored, which is the only way to invalidate a copy already sitting
 *    in a browser in the wild.
 * 3. EVERY ACCESS IS WRAPPED. Private mode, disabled site data and a full
 *    quota all THROW rather than returning null, and an exception here would
 *    take down the whole app on boot.
 * 4. SIGNED IN, SUPABASE WINS. The account is the source of truth the moment
 *    there is one; this store is only consulted when there is no user, and is
 *    cleared on sign-in so a stale local copy can never shadow the account.
 */

import type { Profile } from "@/context/FinanceContext";

const KEY = "mjb_budget_profile_v1";

/** The keys a Profile cannot be missing. Not a full validation — enough that a
 *  truncated write, an error object or a payload from a different app is
 *  refused rather than rendered as somebody's finances. */
const REQUIRED = [
  "income", "budget", "expenses", "assets", "liabilities",
  "debts", "savings_goals", "investment",
] as const;

export function isProfile(v: unknown): v is Profile {
  if (!v || typeof v !== "object") return false;
  const o = v as Record<string, unknown>;
  if (!REQUIRED.every((k) => k in o && o[k] !== null && o[k] !== undefined)) return false;
  const b = o.budget as Record<string, unknown> | undefined;
  if (!b || typeof b !== "object") return false;
  return ["needs", "wants", "savings"].every((k) => typeof b[k] === "object" && b[k] !== null);
}

export function clearLocalProfile(): void {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to do */
  }
}

export function readLocalProfile(): Profile | null {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(KEY);
  } catch {
    // Storage is unavailable, not corrupt. Nothing to clean up, and calling
    // removeItem here would throw for the same reason.
    return null;
  }
  if (!raw) return null;

  try {
    const parsed: unknown = JSON.parse(raw);
    if (isProfile(parsed)) return parsed;
  } catch {
    // Fall through: unparseable is just another kind of unusable.
  }
  /* Drop it, whether it failed to PARSE or failed the shape check.

     The first version only cleared on a failed shape check, and left
     unparseable JSON in place — the app rendered correctly off the served
     profile, so nothing looked wrong, while a dead entry sat in that browser
     forever paying a failed parse on every load. Both routes out of this
     function have to clean up or one of them is a leak nobody sees. */
  clearLocalProfile();
  return null;
}

export function writeLocalProfile(p: Profile): void {
  try {
    if (!isProfile(p)) return;
    window.localStorage.setItem(KEY, JSON.stringify(p));
  } catch {
    /* private mode, or quota. Losing the copy is the old behaviour, not a
       regression, and it must never take the app down. */
  }
}

