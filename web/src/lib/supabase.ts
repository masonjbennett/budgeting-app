/**
 * The browser's Supabase client — auth and the one user_data row.
 *
 * Auth is browser-side by design. Row-level security enforces isolation (the
 * policies are in ../../SUPABASE_SETUP.md and every one of them is keyed to
 * auth.uid()), sessions persist properly across reloads, and the Python
 * function never sees a credential or holds a JWT. That last point matters:
 * the Streamlit app's `_db()` had to be rebuilt precisely because a shared,
 * cached client carried whichever user's token was attached last, and returned
 * one person's data to another. A stateless calculation API cannot have that
 * bug because it holds no state to confuse.
 *
 * The anon key is public by design — it grants nothing on its own. An
 * unauthenticated read of user_data returns zero rows, and the site's 6-hourly
 * keep-alive job fails if that ever stops being true.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

/**
 * null when the app is built without credentials.
 *
 * It returns null rather than throwing, and every caller checks. Creating a
 * client makes no network call, so a misconfigured or deleted project produces
 * an app that LOOKS fine and then tells people their password is wrong — which
 * is exactly what happened for four months in 2026. Local-only is a legitimate
 * mode here: everything except saving works without an account.
 */
export const supabase: SupabaseClient | null =
  url && key ? createClient(url, key, { auth: { persistSession: true } }) : null;

export const cloudConfigured = supabase !== null;

/** Whether a failure was the service being unreachable, or the credentials
 *  being wrong. Reporting the first as the second is how an outage turns into
 *  every visitor being told their password is bad. */
export function isUnreachable(error: unknown): boolean {
  const m = (error as { message?: string })?.message?.toLowerCase() ?? "";
  return (
    m.includes("failed to fetch") ||
    m.includes("networkerror") ||
    m.includes("load failed") ||
    m.includes("fetch failed") ||
    m.includes("timeout")
  );
}

export function authErrorMessage(error: unknown): string {
  if (isUnreachable(error)) {
    return "Can't reach the account service. Your data is safe in this browser — try again shortly.";
  }
  const m = (error as { message?: string })?.message ?? "";
  return m || "Something went wrong. Please try again.";
}
