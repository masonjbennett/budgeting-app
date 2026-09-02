# Supabase setup

**Done — the project is live and the round trip is verified** (2026-09-02): a value
changed in the app, saved, survived a log out and log back in.

The original project (`laxadcwngdufkllqrwqj`) no longer existed — free-tier projects
pause after about a week of inactivity and are reclaimed after that. This app went
untouched from April to September 2026, so it was gone. Keep this file as the record
of how it was rebuilt, and of the two mistakes below that cost the most time.

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

-- GRANTS. Postgres has two INDEPENDENT layers and the policies above are only the
-- second one: table PRIVILEGES decide whether a role may touch the table at all,
-- and RLS then decides which rows. Creating a table from the SQL editor does not
-- necessarily grant anything, and without these every request fails with
-- "permission denied for table user_data" (42501) — including a signed-in user's
-- save. That reads like an RLS problem and is not one, which is why it is worth
-- knowing the error code.
grant usage on schema public to anon, authenticated;

-- Signed-in users read and write; the policies above narrow that to their own row.
grant select, insert, update on public.user_data to authenticated;

-- anon gets SELECT only, and that is deliberate rather than sloppy: the read
-- policy requires auth.uid() = user_id, and an anonymous request has no
-- auth.uid(), so it matches zero rows. Granting it is what makes the keep-alive a
-- real canary — if RLS were ever switched off, anon would immediately start
-- seeing rows and the 6-hourly job fails. With no grant at all, anon is refused
-- either way and that regression would go unnoticed. anon never gets INSERT or
-- UPDATE, so writes are refused at both layers.

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

And check the grants landed, which is the layer below the policies:

```sql
select grantee, privilege_type
from information_schema.role_table_grants
where table_name = 'user_data' and grantee in ('anon','authenticated')
order by grantee, privilege_type;
```

You want `anon` with SELECT only, and `authenticated` with INSERT, SELECT, UPDATE.
If `anon` shows INSERT or UPDATE, revoke them — nothing anonymous should write.

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

### Two things that will go wrong

**"Email rate limit exceeded."** Supabase's built-in sender allows roughly 2-4
emails an hour on a free project, and it is per PROJECT, not per user — so a
couple of test signups exhaust it. You do not need the email: go to
**Authentication → Users**, find your account, and confirm it from the row's menu.
If the user is not listed at all the signup rolled back, in which case toggle
**Confirm email** off (Authentication → Sign In / Providers → Email), sign up, and
toggle it back on. Your account is then created confirmed and everyone else still
has to verify. If the app ever takes real signups, replace the built-in sender with
custom SMTP under Authentication → Emails.

**"Can't reach the account service right now."** The URL is wrong or unreachable.
It is `https://<ref>.supabase.co` — the two mistakes that produce this exact
message are pasting the dashboard page address
(`https://supabase.com/dashboard/project/<ref>/...`, which actually gives a 404
instead) and dropping `.supabase` to leave `https://<ref>.co`, which does not
resolve. Both happened during setup. Check the secret before assuming the app
needs a restart.

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
