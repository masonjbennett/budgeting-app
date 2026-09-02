# Supabase setup

The original project (`laxadcwngdufkllqrwqj`) no longer exists — free-tier projects
pause after about a week of inactivity and are reclaimed after that. This app went
untouched from April to September 2026, so it was gone.

Everything on the app side is already rebuilt and tested. What's left is standing up
a project and pasting two values into three places. Roughly ten minutes.

---

## 1. Create the project

[supabase.com/dashboard](https://supabase.com/dashboard) → **New project**.

- Name it something you'll recognise in a year — `budgeting-app` rather than the
  random slug.
- Save the database password somewhere; you won't need it for this app, but you
  will if you ever open the SQL editor from another machine.
- Region: closest to you.

## 2. Create the table and its policies

Project → **SQL Editor** → **New query**, paste all of this, **Run**.

```sql
-- One row per user. The blob is the whole app state; the app has always stored
-- it that way and there is no reason to normalise a document nobody queries.
create table if not exists public.user_data (
  user_id    uuid primary key references auth.users (id) on delete cascade,
  app_data   jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table public.user_data enable row level security;

-- SELECT and UPDATE and INSERT are three separate policies on purpose.
--
-- The app saves with upsert, which is INSERT ... ON CONFLICT DO UPDATE, and
-- Postgres checks the INSERT policy on the insert attempt and the UPDATE policy
-- on the conflict branch. With only an update policy, a brand-new user's first
-- save fails and every save after it succeeds — which is the worst possible
-- shape for a bug, because it works the moment you test it a second time.
drop policy if exists "read own row"   on public.user_data;
drop policy if exists "insert own row" on public.user_data;
drop policy if exists "update own row" on public.user_data;

create policy "read own row" on public.user_data
  for select using (auth.uid() = user_id);

create policy "insert own row" on public.user_data
  for insert with check (auth.uid() = user_id);

create policy "update own row" on public.user_data
  for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

-- No delete policy. Nothing in the app deletes a row, so nothing should be able to.

create or replace function public.touch_user_data()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists user_data_touch on public.user_data;
create trigger user_data_touch
  before update on public.user_data
  for each row execute function public.touch_user_data();
```

Then check it took — this should return one row saying `rowsecurity = true`:

```sql
select tablename, rowsecurity from pg_tables where tablename = 'user_data';
select policyname, cmd from pg_policies where tablename = 'user_data';
```

You want `rowsecurity` true and three policies: SELECT, INSERT, UPDATE.

## 3. Turn off email confirmation (or don't)

**Authentication → Sign In / Providers → Email.**

If **Confirm email** is ON, a new account can't log in until they click a link, and
the app will say so ("Check your email to confirm the account, then log in") rather
than pretending it worked. That's the correct behaviour either way — it's a product
call, not a bug.

For a portfolio demo I'd turn it **off**, so someone can try the app end to end in
thirty seconds. If you ever put real data in it, turn it back on.

## 4. Copy the two values

**Project Settings → API.**

- **Project URL** — `https://<ref>.supabase.co`
- **anon / public key** — the long one labelled `anon`. Not `service_role`. The
  `service_role` key bypasses row-level security entirely; it must never go
  anywhere near a client app or a repository.

## 5. Paste them in three places

**a. Streamlit Cloud** — your app → **Settings → Secrets**:

```toml
[supabase]
url = "https://<ref>.supabase.co"
key = "<anon key>"
```

**b. Locally** — `.streamlit/secrets.toml` in this repo (already gitignored):

```toml
[supabase]
url = "https://<ref>.supabase.co"
key = "<anon key>"
```

**c. GitHub, on the `masonjbennett.com` site repo** — Settings → Secrets and
variables → Actions → **New repository secret**, twice:

| Name | Value |
| --- | --- |
| `SUPABASE_URL` | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | the anon key |

That last one is what stops this happening again. The 6-hourly keep-alive now reads
`user_data` unauthenticated: the request keeps the project from idling, and it
**fails the job** if the read ever comes back with rows — because that would mean
row-level security is off and the anon key, which ships inside the app, can read
everyone's finances. Until you add those secrets the step logs `skipping` and passes.

## 6. Check it

```bash
.venv/Scripts/python.exe test_cloud.py
```

Then run the app, create an account, change something, hard-refresh, log back in
and confirm your change is there.

If the deployed app still says accounts are unavailable a minute after you save the
secret, **Reboot app** from the Streamlit Cloud dashboard. Streamlit re-runs the
script in a long-lived process and does not always pick up a new secret without a
restart — the same mechanism that broke the deploy on 2026-09-01 when a new name was
added to `calculations.py`.

---

## What the app does now that it didn't before

- **A missing or wrong secret no longer takes the app down.** It used to read
  `st.secrets` at module scope, so one bad value meant every page was an error
  screen — with `showErrorDetails = false`, a blank one. Now the login block is
  replaced by a line saying accounts are unavailable, and everything else works.
- **A dead backend no longer reads as a wrong password.** That was the actual
  visible symptom of the old project disappearing.
- **Database calls carry the user's JWT.** They previously went through the shared
  anon client, so with RLS on nothing would have worked, and with RLS off any
  visitor could have read or overwritten any other user's row. This is the reason
  step 2 matters.
- **Tokens refresh.** Access tokens expire after an hour; a save after that used to
  fail with a 401 that looked like a permissions problem.
- **The auto-save stopped shouting.** A background failure now shows one line in the
  sidebar instead of a red banner on the page.

## Known limit, deliberately not worked around

**A browser refresh logs you out.** Streamlit has no cookie API, so the only place
to persist a session is `st.session_state`, which is per-connection. The obvious
workaround — putting the token in a URL query parameter — would write a credential
into the address bar, browser history, and any referrer header the page emits. Not
worth it. Log in again; the data is on the server, not in the tab.
