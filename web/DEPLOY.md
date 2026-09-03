# Deploying budget.masonjbennett.com

Written for the first deploy. `README.md` explains *why* each setting is what
it is; this is the click-by-click, in order, with what to check after each one.

**Do the whole of step 1–5 before attaching the domain.** A preview URL costs
nothing and is the only way to test the two things that cannot be tested
locally.

---

## 0. Before you start

The Streamlit app at **masonbennett-budget.streamlit.app** stays live and stays
the recruiter-safe link from masonjbennett.com throughout. Nothing here touches
it. Swap the link only after step 7.

You need: the GitHub repo pushed (it is 9 commits ahead as of this writing —
`git push` first), and the Supabase project reference `shxjjqcuuhqlvgpbujby`.

---

## 1. Create the Vercel project

1. Vercel dashboard → **Add New… → Project**.
2. Import **masonjbennett/budgeting-app**.
3. **Framework Preset**: Next.js (it will detect this once the root directory
   is set — do step 4 first if it guesses wrong).

Do **not** deploy yet. Set steps 2–4 first, or the first build fails on a
missing import and you will be reading a confusing error.

---

## 2. Root Directory  ← the one people get wrong

**Settings → General → Root Directory** = `web`

Then, directly underneath it, turn **ON**:

> ☑ **Include source files outside of the Root Directory in the Build Step**

Without that toggle the build cannot see `../calculations.py`, and
`scripts/sync-calculations.mjs` exits non-zero saying exactly that. That is the
intended failure — an API with no maths must not deploy — but it is a wasted
cycle if you know about it in advance.

---

## 3. Environment variables

**Settings → Environment Variables.** Add both, for **all three**
environments (Production, Preview, Development):

| Name | Value |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `https://shxjjqcuuhqlvgpbujby.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | the anon/public key from Supabase → Settings → API |

**Reuse the live project. Do not create a second one.** The Streamlit app and
this one are two front ends over one account and one `user_data` table; a
second Supabase project would give you two sets of credentials and two copies
of your data, silently.

Both names begin `NEXT_PUBLIC_` on purpose — they are meant to reach the
browser. The anon key is public by design and row-level security is what
protects the data (policies are in `../SUPABASE_SETUP.md`). **There is no
service-role key anywhere in this project and there must never be one**: the
Python function is a pure calculator and holds no credential at all.

The URL is the one place a typo costs an hour. Last time it was `<ref>.co`
instead of `<ref>.supabase.co`, and the app reported "Can't reach the account
service" — which reads like a dead project rather than a bad string.

---

## 4. Build settings

Leave every one of these on the default. Vercel reads `package.json`, and
`prebuild` already runs the sync and the token check:

- Build Command: default (`npm run build`)
- Install Command: default
- Output Directory: default

`vercel.json` in `web/` configures the Python function and nothing else.
**There is deliberately no production rewrite for `/api`** — see the section in
`README.md` before adding one. The pattern most FastAPI-on-Vercel posts show
would silently 404 every route here.

---

## 5. Deploy, and check the two things that only production can tell you

Hit **Deploy**. When it finishes you get a preview URL like
`budgeting-app-xxxx.vercel.app`.

**Check 1 — routing.** Open in a browser or run:

```bash
curl -s https://YOUR-PREVIEW-URL.vercel.app/api/health
```

Expect exactly `{"status":"ok","version":"5.0"}`.

If it **404s**, Vercel is serving `api/index.py` at the literal path `/api`
only. The fix is one line and is written up in `README.md` under "There is
deliberately NO production rewrite" — mount the FastAPI app at the root and let
the platform prefix, or reinstate a rewrite that preserves the path.

**Check 2 — the sync ran.** If the build log shows

```
sync-calculations: api/calculations.py <- ../calculations.py (… verified byte-for-byte)
```

then the shared engine was copied from the same commit that was built. If the
deploy instead **failed** with `ModuleNotFoundError: calculations`, step 2's
toggle is off. That is the failure working as designed — it refuses to ship an
API with no maths rather than shipping one with a stale copy.

---

## 6. Use it in anger, on a phone and on a desktop

Before the domain goes on. The things worth actually doing rather than glancing
at:

- **Sign in** with the account you already use on the Streamlit app. Your real
  profile should load — same project, same table, same row.
- **Change something and reload.** The save is debounced by 1.5s; the sidebar
  shows the state.
- **Dashboard → Year.** With a real profile the caveat banner tells you which
  months have nothing logged. That is the honest reading, not a bug.
- **Expenses → Open importer.** Feed it a real statement export from your bank.
  Check the date order and the sign convention it worked out, at the top of the
  panel, before you tick anything. Import only ever ADDS — nothing you typed
  can be replaced.
- **FIRE.** Move the stock slider and watch the curve and the stated real
  return move together.
- **On the phone**: the nav is an off-canvas drawer below `lg`. Every table
  scrolls inside its own box rather than the page.
- **Print one page** (⌘P / Ctrl+P). Navigation and buttons disappear and the
  palette forces to light, whatever theme you are in.

---

## 7. Only then: the domain

1. **Settings → Domains → Add** `budget.masonjbennett.com`.
2. Vercel gives you a CNAME. Add it wherever masonjbennett.com's DNS lives.
3. Wait for the certificate.
4. **Then** update the link on masonjbennett.com. It is in
   `mason-bennett-dashboard/src/App.jsx` — the budgeting-app project card and
   the recruiter-safe list both point at the Streamlit URL today.
5. Leave the Streamlit app running. It costs nothing, the keep-alive job in
   this repo already wakes it, and it is the fallback if anything here breaks.

---

## What NOT to do

- **Do not** add a `SUPABASE_SERVICE_ROLE_KEY`. Nothing here needs one and the
  API is architecturally incapable of using it — every route is a pure
  calculator over numbers the caller supplies, and `test_api.py` asserts that
  against the parsed AST.
- **Do not** commit `web/api/calculations.py` or `web/api/app_data.py`. They
  are generated at build time and gitignored. If an import fails locally, run
  `npm run sync`.
- **Do not** create a second Supabase project.
- **Do not** retire the Streamlit app in passing.
