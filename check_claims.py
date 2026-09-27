"""The figures the SITE states about itself must be true.

The About block on /data said the engine was covered by "291 assertions" for
long enough to be wrong by a hundred and twenty — a claim about how carefully
the numbers are checked, with nothing checking it. That is this project's
oldest lesson pointed at its own copy: a value nothing reads is a value nothing
is enforcing, and it goes stale silently.

So the number is derived here from the suites themselves rather than trusted.
`calculations.py` is the module the sentence is about, and the two suites that
drive it directly are `test_calc.py` and `test_stress.py` — `test_cloud.py` is
auth and storage, and `web/test_api.py` covers the ROUTES, which are a skin
over the module rather than the module.

The READMEs are checked the same way and for the same reason. On Sep 26 2026
the public README said "Three suites, 210 assertions" against a measured 711,
and web/README.md said 413 and "22 engine defects" against 559 and 59 — three
documents, three different numbers, none of them right. A count written in two
places drifts; written in three it is already wrong somewhere.

This costs about fifty seconds, because the mutation counts are derived by
running the harnesses rather than by reading a number out of them.

Run:  .venv/Scripts/python.exe check_claims.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "web" / "src" / "app" / "data" / "page.tsx"
SUITES = ["test_calc.py", "test_stress.py"]

failed = 0


def check(name, ok, detail=""):
    global failed
    if ok:
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}" + (f" — {detail}" if detail else ""))


def suite_total():
    """What the two suites actually assert, by running them."""
    total = 0
    for suite in SUITES:
        r = subprocess.run([sys.executable, suite], cwd=ROOT,
                           capture_output=True, text=True)
        m = re.search(r"RESULTS: (\d+) passed, (\d+) failed", r.stdout)
        if not m:
            check(f"{suite} reported a result at all", False, "no RESULTS line")
            return None
        if m.group(2) != "0":
            check(f"{suite} is green", False, f"{m.group(2)} failing")
            return None
        print(f"         {suite}: {m.group(1)}")
        total += int(m.group(1))
    return total


_counts = {}


def suite_count(rel, cwd=None):
    """How many assertions a suite actually makes, by running it."""
    if rel not in _counts:
        r = subprocess.run([sys.executable, Path(rel).name],
                           cwd=cwd or ROOT, capture_output=True, text=True)
        m = re.search(r"RESULTS: (\d+) passed, (\d+) failed", r.stdout)
        _counts[rel] = int(m.group(1)) if m and m.group(2) == "0" else None
    return _counts[rel]


def mutation_count(rel, cwd=None):
    """How many mutations a harness actually catches, by running it."""
    if rel not in _counts:
        r = subprocess.run([sys.executable, Path(rel).name],
                           cwd=cwd or ROOT, capture_output=True, text=True)
        m = re.search(r"all (\d+) mutations caught", r.stdout)
        _counts[rel] = int(m.group(1)) if m else None
    return _counts[rel]


print("\n--- the About block's claims about this app ---")

src = PAGE.read_text(encoding="utf-8")

stated = re.search(r"covered by\s+([\d,]+)\s*\n?\s*assertions", src)
check("the About block states an assertion count", stated is not None,
      "no 'covered by N assertions' in data/page.tsx")

actual = suite_total()
check("both suites ran and are green", actual is not None)

if stated and actual is not None:
    n = int(stated.group(1).replace(",", ""))
    check("and the number it states is the number they assert", n == actual,
          f"page says {n}, the suites assert {actual}")

# The other half of the same sentence: it claims every assertion runs the
# shipping module rather than a copy. A suite that redefines the maths would
# make that false, which is exactly how the previous version stayed green for
# five months without executing the app.
MATHS = ("def compute_take_home", "def calc_federal_tax", "def calc_state_tax",
         "def simulate_payoff", "def project_investment", "def run_monte_carlo")
mirrors = []
for suite in SUITES:
    text = (ROOT / suite).read_text(encoding="utf-8")
    mirrors += [f"{suite}:{d}" for d in MATHS if d in text]
check("no suite keeps its own copy of the maths to check the answer against",
      not mirrors, ", ".join(mirrors))

for suite in SUITES:
    text = (ROOT / suite).read_text(encoding="utf-8")
    check(f"{suite} imports the shipping module",
          re.search(r"^(import calculations|from calculations import)", text, re.M) is not None)

print()

# --- the same test, pointed at the two READMEs -------------------------------
# Every number below is a claim a reader can check by running the thing it
# names. Each is derived here rather than trusted, so a suite that grows makes
# the README wrong LOUDLY instead of quietly.

print("\n--- what the READMEs claim about the suites ---")

CLAIMS = [
    # (file, regex capturing one number, what to call it, what it should equal)
    ("README.md", r"Four suites, ([\d,]+) assertions", "README: the four-suite total",
     lambda: _sum("test_calc.py", "test_stress.py", "test_cloud.py", "web/test_api.py")),
    ("README.md", r"python test_calc\.py\s+#\s*(\d+)", "README: test_calc's own line", lambda: suite_count("test_calc.py")),
    ("README.md", r"python test_stress\.py\s+#\s*(\d+)", "README: test_stress's own line", lambda: suite_count("test_stress.py")),
    ("README.md", r"python test_cloud\.py\s+#\s*(\d+)", "README: test_cloud's own line", lambda: suite_count("test_cloud.py")),
    ("README.md", r"python web/test_api\.py\s+#\s*(\d+)", "README: test_api's own line",
     lambda: suite_count("web/test_api.py", ROOT / "web")),
    ("README.md", r"python test_calc_mutations\.py\s+#\s*(\d+) engine defects", "README: the engine-mutation count",
     lambda: mutation_count("test_calc_mutations.py")),
    ("web/README.md", r"test_calc / test_cloud / test_stress\s+([\d,]+) assertions", "web/README: the three-suite total",
     lambda: _sum("test_calc.py", "test_cloud.py", "test_stress.py")),
    ("web/README.md", r"test_calc_mutations\.py\s+(\d+) engine defects", "web/README: the engine-mutation count",
     lambda: mutation_count("test_calc_mutations.py")),
    ("web/README.md", r"test_api\.py\s+(\d+) assertions", "web/README: test_api's count",
     lambda: suite_count("web/test_api.py", ROOT / "web")),
    ("web/README.md", r"test_api_mutations\.py\s+(\d+) shipped bugs", "web/README: the route-mutation count",
     lambda: mutation_count("web/test_api_mutations.py", ROOT / "web")),
]


def _sum(*rels):
    ns = [suite_count(r, ROOT / "web" if r.startswith("web/") else None) for r in rels]
    return None if None in ns else sum(ns)


for fname, pattern, label, expected in CLAIMS:
    text = (ROOT / fname).read_text(encoding="utf-8")
    m = re.search(pattern, text)
    if not m:
        check(label, False, "the README no longer states this in the shape this check reads "
                            "— teach it the new shape rather than deleting the check")
        continue
    want = expected()
    if want is None:
        check(label, False, "could not derive the real number (a suite failed or did not report)")
        continue
    said = int(m.group(1).replace(",", ""))
    check(label, said == want, f"README says {said}, the suite reports {want}")

print("=" * 60)
print("CLAIMS: ok" if not failed else f"CLAIMS: {failed} wrong")
print("=" * 60)
sys.exit(1 if failed else 0)
