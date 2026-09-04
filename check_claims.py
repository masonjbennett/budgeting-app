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
print("=" * 60)
print("CLAIMS: ok" if not failed else f"CLAIMS: {failed} wrong")
print("=" * 60)
sys.exit(1 if failed else 0)
