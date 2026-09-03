"""Reintroduce each shipped bug and require test_api.py to catch it.

Every mutation below is a defect that ACTUALLY SHIPPED — in the Streamlit app,
in the abandoned Next.js scaffold, or both. If the suite stays green on one of
them, that assertion is decoration and the bug can arrive a third time.

Run:  .venv/Scripts/python.exe test_api_mutations.py     (from web/)
"""
import os
import re
import subprocess
import sys

PY = os.path.join(".venv", "Scripts", "python.exe")
API = os.path.join("api", "index.py")
CALC = os.path.join("api", "calculations.py")

MUTATIONS = [
    (API,
     "DTI reads the budget category name, not the debts entered "
     "(shipped in both earlier versions: $35,000 of student loans read 'Debt-Free')",
     ("    service, service_source = monthly_debt_service(debts, req.budget_needs)",
      '    service = req.budget_needs.get("Min. Debt Payments", 0)\n'
      '    service_source = "budget"')),
    (API,
     "DTI divides by take-home while grading on lender bands defined on gross",
     ('    gross_monthly = th["annual_gross"] / 12',
      '    gross_monthly = th["monthly_take_home"]')),
    (API,
     "emergency fund looks up the literal asset key 'Savings' "
     "(rename the row and coverage reads 0.0 as though measured)",
     ("    ef_months, ef_counted = emergency_fund_months(req.assets, monthly_needs)",
      '    ef_counted = ["Savings"]\n'
      '    ef_months = (req.assets.get("Savings", 0) / monthly_needs) if monthly_needs else 0.0')),
    (API,
     "unmeasurable emergency-fund coverage returns 0.0 instead of null",
     ("        \"emergency_fund_months\": ef_months,",
      "        \"emergency_fund_months\": ef_months or 0.0,")),
    (API,
     "the -1 'never pays off' sentinel is returned as if it were a duration",
     ('            "never_pays_off": months == -1,',
      '            "never_pays_off": False,')),
    # THE MATCH INPUTS RENDERED AND THE PROJECTION IGNORED THEM. That is what
    # shipped: two fields on the Investments page feeding nothing, so a matched
    # 401(k) was understated by the most reliable return in the whole model.
    (API,
     "the projection ignores the employer match it was handed",
     ("        req.start, req.monthly, req.rate, req.years, req.salary,",
      "        req.start, req.monthly, req.rate, req.years, 0,")),
    # An unknown city falling back to the national average is a wrong answer
    # wearing a right one's clothes — the same shape as the emergency fund
    # reading 0.0 months as though it had been measured.
    # Mutating the ROUTE rather than the engine on purpose. Any edit to
    # api/calculations.py also trips the byte-for-byte sync check, so a CALC
    # mutation would report itself "caught" even if the assertion it is aimed
    # at were decoration. Here only the cost-of-living assertion can fail.
    (API,
     "an unknown city silently falls back to the national average",
     ('    return {"comparison": col_compare(req.salary, req.from_city, req.to_city)}',
      '    return {"comparison": col_compare(req.salary, req.from_city, req.to_city)\n'
      '            or col_compare(req.salary, "National Average", req.to_city)}')),
    (API,
     "the investment route returns the tuple transposed",
     ("    values, contributions, match = project_investment_with_match(",
      "    contributions, values, match = project_investment_with_match(")),
    # The top tax bracket's ceiling is float("inf"), which is not JSON. There
    # are TWO independent guards and removing either one alone changes nothing,
    # so a mutation that removes one is not a defect and correctly survives:
    #   * the explicit `None if c == float("inf")` conversion, and
    #   * the `-> Dict[str, Any]` annotation, which makes FastAPI serialise
    #     through pydantic, whose ser_json_inf_nan default is already "null".
    # Removing BOTH is the real failure: json.dumps raises "Out of range float
    # values are not JSON compliant" and the route 500s. Measured all three ways
    # before writing this. The conversion stays even though pydantic would cover
    # it, because a default in someone else's library is not a guarantee this
    # code gets to keep.
    (API,
     "the infinite top-bracket ceiling reaches json.dumps (BOTH guards removed)",
     [("        return [[None if c == float(\"inf\") else c, r] for c, r in rows]",
       "        return [[c, r] for c, r in rows]"),
      ("def reference() -> Dict[str, Any]:", "def reference():")]),
    (API,
     "a route grows its own arithmetic instead of calling the engine",
     ('    monthly = calc_social_security(req.annual_salary, req.claiming_age)',
      '    monthly = req.annual_salary / 12 * (1 + 0.0) * 0.4')),
    (CALC,
     "the synced calculations.py is edited in place, so it is no longer the "
     "repo's copy",
     ("def calc_fica(gross, filing=\"Single\"):",
      "def calc_fica(gross, filing=\"Single\"):\n    return 0.0  # tampered")),
]

originals = {f: open(f, "rb").read() for f in {m[0] for m in MUTATIONS}}
survived = []

print("=" * 66)
print("API MUTATIONS — each is a defect that actually shipped")
print("=" * 66)

try:
    for path, label, edits in MUTATIONS:
        # A mutation may need SEVERAL edits at once. Where something is only a
        # defect once two independent guards are gone, applying one edit at a
        # time proves nothing: each survives alone and the pair is never tested.
        edits = edits if isinstance(edits, list) else [edits]
        src = originals[path].decode("utf-8")
        if [old for old, _ in edits if old not in src]:
            print(f"  [SETUP FAIL] pattern not found — {label}")
            survived.append(label)
            continue
        for old, new in edits:
            src = src.replace(old, new, 1)
        open(path, "w", encoding="utf-8", newline="").write(src)
        r = subprocess.run([PY, "test_api.py"], capture_output=True, text=True)
        open(path, "wb").write(originals[path])

        m = re.search(r"RESULTS: (\d+) passed, (\d+) failed", r.stdout)
        if r.returncode == 0 and m and m.group(2) == "0":
            print(f"  [SURVIVED] {label}")
            survived.append(label)
        else:
            n = m.group(2) if m else "crash"
            first = next((l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l),
                         "(suite crashed)")
            print(f"  [caught: {n} fail(s)] {label}")
            print(f"       {first[:110]}")
finally:
    for f, blob in originals.items():
        open(f, "wb").write(blob)

print()
if survived:
    print(f"{len(survived)} MUTATION(S) SURVIVED — those assertions cannot fail:")
    for s in survived:
        print(f"  - {s}")
    sys.exit(1)
print(f"all {len(MUTATIONS)} mutations caught; files restored")
