"""Tests for the auth + cloud-sync layer in budget_app.py.

These drive the SHIPPING functions. The calculation suite next door
(test_stress.py) redefines its subjects, and has therefore been green for five
months over an April photocopy of the app — by the time this was written its copy
of calc_fica had already lost the filing-status argument the real one gained, so
that fix was never once tested. Nothing here re-implements anything: the module is
imported with streamlit and supabase replaced by stubs, so every assertion below
is about the code that actually ships.

Run:  .venv/Scripts/python.exe test_cloud.py
"""
import sys
import types

passed = failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


# ── Stubs ────────────────────────────────────────────────────────────

class _Sidebar:
    def __getattr__(self, _):
        return lambda *a, **k: None


class _StreamlitStub(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.session_state = {}
        self.secrets = {}
        self.sidebar = _Sidebar()

    def cache_resource(self, fn=None, **kw):
        return fn if fn else (lambda f: f)

    cache_data = cache_resource

    def __getattr__(self, _):
        return lambda *a, **k: None


class StubAuth:
    def __init__(self):
        self.raise_with = None
        self.session = None
        self.user = None
        self.signed_out = False
        self.refresh_calls = 0

    def _maybe_raise(self):
        if self.raise_with:
            raise self.raise_with

    def sign_in_with_password(self, _):
        self._maybe_raise()
        return types.SimpleNamespace(user=self.user, session=self.session)

    def sign_up(self, _):
        self._maybe_raise()
        return types.SimpleNamespace(user=self.user, session=self.session)

    def sign_out(self):
        self.signed_out = True

    def refresh_session(self, _token):
        self.refresh_calls += 1
        self._maybe_raise()
        return types.SimpleNamespace(user=self.user, session=self.session)


class StubPostgrest:
    def __init__(self):
        self.token = None

    def auth(self, token):
        self.token = token


class StubQuery:
    def __init__(self, client):
        self.c = client
        self.filters = {}
        self.op = None

    def upsert(self, row, **kw):
        self.op, self.row = "upsert", row
        return self

    def select(self, *a):
        self.op = "select"
        return self

    def eq(self, k, v):
        self.filters[k] = v
        return self

    def maybe_single(self):
        return self

    def execute(self):
        # Record the token the request WOULD have carried — this is what proves
        # a write runs as the user rather than as the public anon key.
        self.c.calls.append({"op": self.op, "token": self.c.postgrest.token,
                             "filters": dict(self.filters)})
        if self.c.raise_queue:
            raise self.c.raise_queue.pop(0)
        if self.op == "upsert":
            return types.SimpleNamespace(data=[self.row])
        return types.SimpleNamespace(data=self.c.stored)


class StubClient:
    def __init__(self):
        self.auth = StubAuth()
        self.postgrest = StubPostgrest()
        self.calls = []
        self.stored = None
        self.raise_queue = []

    def table(self, _name):
        return StubQuery(self)


created = []


def _fake_create_client(url, key):
    c = StubClient()
    c.url, c.key = url, key
    created.append(c)
    return c


st_stub = _StreamlitStub()
sys.modules["streamlit"] = st_stub
sys.modules["supabase"] = types.SimpleNamespace(create_client=_fake_create_client)
for m in ("plotly", "plotly.graph_objects", "plotly.express", "pandas", "numpy"):
    sys.modules.setdefault(m, types.ModuleType(m))

SRC = open("budget_app.py", encoding="utf-8").read()
HEAD = SRC[:SRC.index("# Color palette")]   # imports through the cloud layer


def load(secrets=True):
    """Re-exec the shipping head with a given secrets state.

    Re-execing rather than importing once is deliberate: `supabase = _init_supabase()`
    runs at module scope, so the missing-secret path can only be exercised by
    loading the module the way Streamlit Cloud would with the secret absent.
    """
    st_stub.session_state.clear()
    created.clear()
    st_stub.secrets = {"supabase": {"url": "https://stub.supabase.co", "key": "anon"}} if secrets else {}
    mod = types.ModuleType("app_head")
    exec(compile(HEAD, "budget_app.py", "exec"), mod.__dict__)
    return mod


def sign_in_state(app, token="tok-1"):
    st_stub.session_state.update({"user": {"id": "user-1", "email": "a@b.com"},
                                  "access_token": token, "refresh_token": "ref-1"})


class ConnectError(Exception):
    """Shaped like httpx.ConnectError — the real failure when the project was gone."""


print("=" * 64)
print("CLOUD / AUTH SUITE — driving the shipping functions in budget_app.py")
print("=" * 64)

# ── 1. The bug that shipped ──────────────────────────────────────────
print("\n--- a dead backend must never read as a wrong password ---")
app = load()
app.supabase.auth.raise_with = ConnectError("[Errno 11001] getaddrinfo failed")
r = app.auth_sign_in("a@b.com", "hunter22")
check("dead host -> service-down message, not a credentials message",
      not r["success"] and "reach the account service" in r["error"], r["error"])
check("dead host message does not blame the password",
      "password" not in r["error"].lower(), r["error"])

app = load()
app.supabase.auth.user = None
app.supabase.auth.session = None
r = app.auth_sign_in("a@b.com", "wrong")
check("genuinely wrong credentials -> 'Invalid email or password.'",
      not r["success"] and r["error"] == "Invalid email or password.", r["error"])

app = load()
app.supabase.auth.raise_with = ConnectError("connection timed out")
r = app.auth_sign_up("a@b.com", "hunter22")
check("sign-up on a dead host also reports the service, not the input",
      not r["success"] and "reach the account service" in r["error"], r["error"])

check("_is_unreachable: DNS failure", app._is_unreachable(ConnectError("getaddrinfo failed")))
check("_is_unreachable: plain auth rejection is NOT unreachable",
      not app._is_unreachable(Exception("Invalid login credentials")))

# ── 2. The import-time guard ─────────────────────────────────────────
print("\n--- a missing secret degrades, it does not take the app down ---")
try:
    app = load(secrets=False)
    imported = True
except Exception as e:
    imported, err = False, e
check("module imports with no [supabase] secret at all", imported)
if imported:
    check("cloud_configured() is False", app.cloud_configured() is False)
    check("supabase client is None", app.supabase is None)
    r = app.auth_sign_in("a@b.com", "x")
    check("login attempt returns the service message rather than raising",
          not r["success"] and "reach the account service" in r["error"])
    sign_in_state(app)
    ok, msg = app.cloud_save({"a": 1})
    check("cloud_save returns (False, message) rather than raising", ok is False and bool(msg))
    check("cloud_load returns None rather than raising", app.cloud_load() is None)

app = load()
check("with a secret present, cloud_configured() is True", app.cloud_configured() is True)

# ── 3. The anon-key hole ─────────────────────────────────────────────
print("\n--- database writes must carry the user's JWT, not the anon key ---")
app = load()
sign_in_state(app, token="jwt-alice")
ok, msg = app.cloud_save({"budget": 1})
db = st_stub.session_state["_db_client"]
check("save succeeded", ok, msg)
check("the request carried the user's access token",
      db.calls[-1]["token"] == "jwt-alice", str(db.calls[-1]))
check("the token is NOT the anon key", db.calls[-1]["token"] != "anon")
check("_db() built a client separate from the shared anon client",
      db is not app.supabase)
check("the shared anon client never had a token attached to it",
      app.supabase.postgrest.token is None)

# the concurrency hazard the comment in _db() is about
prev = db
st_stub.session_state["access_token"] = "jwt-bob"
db2 = app._db()
check("a changed token rebuilds the client instead of mutating the old one", db2 is not prev)
check("the new client carries the new token", db2.postgrest.token == "jwt-bob")
check("the previous client still holds only its own token", prev.postgrest.token == "jwt-alice")

# ── 4. Token expiry ──────────────────────────────────────────────────
print("\n--- an expired token refreshes once and retries ---")
app = load()
sign_in_state(app)
app.supabase.auth.user = types.SimpleNamespace(id="user-1", email="a@b.com")
app.supabase.auth.session = types.SimpleNamespace(access_token="tok-2", refresh_token="ref-2")
# first execute raises an expired-JWT error, second succeeds
client = app._db()
client.raise_queue = [Exception('{"message":"JWT expired"}')]
ok, msg = app.cloud_save({"x": 1})
check("save recovers after refreshing the token", ok, msg)
check("refresh_session was called exactly once", app.supabase.auth.refresh_calls == 1)
check("session state now holds the new access token",
      st_stub.session_state["access_token"] == "tok-2")

app = load()
sign_in_state(app)
app.supabase.auth.raise_with = Exception("refresh token not found")
client = app._db()
client.raise_queue = [Exception("JWT expired"), Exception("JWT expired")]
ok, msg = app.cloud_save({"x": 1})
check("a refresh that fails gives up rather than looping", ok is False)

app = load()
sign_in_state(app)
client = app._db()
client.raise_queue = [Exception('permission denied for table user_data')]
ok, msg = app.cloud_save({"x": 1})
check("a real permission denial is NOT retried as an expiry",
      ok is False and app.supabase.auth.refresh_calls == 0 and "Save failed" in msg, msg)

# ── 5. Load path ─────────────────────────────────────────────────────
print("\n--- load ---")
app = load()
sign_in_state(app)
app._db().stored = {"app_data": {"income": {"gross_salary": 90000}}}
got = app.cloud_load()
check("cloud_load returns the stored blob", got == {"income": {"gross_salary": 90000}}, str(got))
check("load filtered on the signed-in user's id",
      st_stub.session_state["_db_client"].calls[-1]["filters"] == {"user_id": "user-1"})

app = load()
sign_in_state(app)
app._db().stored = None
check("a brand-new user with no row loads None, not an error", app.cloud_load() is None)

app = load()
check("cloud_load with nobody signed in returns None", app.cloud_load() is None)
ok, _ = app.cloud_save({"x": 1})
check("cloud_save with nobody signed in returns False", ok is False)

# ── 6. Auto-save must stay quiet ─────────────────────────────────────
print("\n--- the background save records failures instead of shouting ---")
app = load()
sign_in_state(app)
app._db().raise_queue = [ConnectError("getaddrinfo failed")]
app.auto_save_debounced({"x": 1}, interval=0)
check("a failed auto-save records the reason", "_cloud_error" in st_stub.session_state)
check("the recorded reason names the service, not the user",
      "reach the account service" in st_stub.session_state["_cloud_error"])
calls_before = len(st_stub.session_state["_db_client"].calls)
app.auto_save_debounced({"x": 1}, interval=10)
check("an unreachable service is not retried on the very next render",
      len(st_stub.session_state["_db_client"].calls) == calls_before)

app = load()
sign_in_state(app)
st_stub.session_state["_cloud_error"] = "stale failure"
app.auto_save_debounced({"x": 1}, interval=0)
check("a later success clears the error banner", "_cloud_error" not in st_stub.session_state)

app = load()
app.auto_save_debounced({"x": 1}, interval=0)
check("auto-save with nobody signed in does nothing at all", not created[1:])

# ── 7. Sign-out ──────────────────────────────────────────────────────
print("\n--- sign-out leaves nothing behind ---")
app = load()
sign_in_state(app)
app._db()
st_stub.session_state["_cloud_error"] = "x"
app.auth_sign_out()
leftovers = [k for k in ("user", "access_token", "refresh_token", "_db_client",
                         "_db_token", "_cloud_error") if k in st_stub.session_state]
check("no token, client or user survives sign-out", not leftovers, str(leftovers))
check("is_logged_in() is False afterwards", app.is_logged_in() is False)

app = load(secrets=False)
app.auth_sign_out()
check("sign-out with no backend configured does not raise", True)

# ── 8. Sign-up ───────────────────────────────────────────────────────
print("\n--- sign-up ---")
app = load()
app.supabase.auth.user = types.SimpleNamespace(id="u2", email="new@b.com")
app.supabase.auth.session = types.SimpleNamespace(access_token="t", refresh_token="r")
r = app.auth_sign_up("new@b.com", "hunter22")
check("successful sign-up stores both tokens",
      r["success"] and st_stub.session_state["refresh_token"] == "r")

app = load()
app.supabase.auth.user = types.SimpleNamespace(id="u3", email="c@b.com")
app.supabase.auth.session = None          # Supabase's shape when confirmation is on
r = app.auth_sign_up("c@b.com", "hunter22")
check("a user with no session is reported as needing confirmation",
      not r["success"] and "confirm" in r["error"].lower(), r["error"])

app = load()
app.supabase.auth.raise_with = Exception("User already registered")
r = app.auth_sign_up("a@b.com", "hunter22")
check("a duplicate email says so", "already exists" in r["error"], r["error"])

print("\n" + "=" * 64)
print(f"RESULTS: {passed} passed, {failed} failed")
print("=" * 64)
sys.exit(1 if failed else 0)
