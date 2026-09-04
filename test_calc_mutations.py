"""Reintroduce each engine defect and require test_calc.py to catch it.

The companion to web/test_api_mutations.py, and it exists because that one
cannot do this job. Its mutations edit web/api/index.py, because any edit to
web/api/calculations.py ALSO trips the byte-for-byte sync check — so a mutation
there reports itself "caught" whatever the assertion aimed at it is worth.
There is no sync check between this file and calculations.py, so a mutation
here is caught only by an assertion that actually looks at the behaviour.

Every entry below is a defect that either shipped, or was measured and
rejected, or was found while writing the tests. None of them raises. Each one
produces a number that looks like a number, on a page whose whole claim is
that its numbers are worth trusting:

  * a year measured against the calendar rather than against the months that
    hold records, which reports someone thousands under budget for the crime
    of not having logged March;
  * a month in progress inside the variance, which reports rent paid on time as
    thirty times over budget;
  * a portfolio left compounding for someone whose budget does not balance;
  * a duplicate rule that either doubles a year of spending or refuses two real
    coffees bought on one day;
  * a column of shop names read as money.

Run:  .venv/Scripts/python.exe test_calc_mutations.py
"""
import re
import subprocess
import sys

PY = sys.executable
CALC = "calculations.py"

MUTATIONS = [
    # ── The month strip ──────────────────────────────────────────────
    ("a past month is judged against today's calendar, so August is 'not over' "
     "on the 4th of September and can never carry a verdict",
     ("    complete = key < here or (key == here and ref.day >= days_in_month)",
      "    complete = ref.day >= days_in_month")),
    ("the strip offers only the months that hold records, so a month nobody "
     "logged becomes a gap in the row rather than an answer",
     ("    start = min(keys) if keys else here",
      "    return sorted(set(keys)) or [here]")),
    ("a month string from the caller is trusted unvalidated, so a malformed "
     "one reaches the date arithmetic",
     ("    key = str(month) if (month and _is_month_key(month)) else here",
      "    key = str(month) if month else here")),
    ("the strip is unbounded, so a decade of imported history is a decade of "
     "buttons",
     ("    return out[-MONTH_STRIP_MAX:]", "    return out")),
    # ── The dashboard's health verdicts ──────────────────────────────
    ("a month in progress is GRADED, so the savings ring reads 70% green on "
     "the 4th and 100% for a month nobody has logged anything in yet",
     ('    if withheld and rate is not None:\n'
      '        savings_tone, savings_status = "info", None',
      '    if False and rate is not None:\n'
      '        savings_tone, savings_status = "info", None')),
    ("budget adherence is graded mid-month, so a profile holding one expense "
     "scores 15/15 'On track'",
     ('    elif withheld:\n'
      '        adherence_tone, adherence_status = "info", "Partial month"',
      '    elif False:\n'
      '        adherence_tone, adherence_status = "info", "Partial month"')),
    ("a month with nothing logged in it is treated as a month on record, so "
     "an empty log reads as having saved everything",
     ("    if not mine:\n        # Wording follows",
      "    if False:\n        # Wording follows")),
    ("categories with nothing logged against them are not reported, so the "
     "adherence score reads as a result rather than a count so far",
     ("    unlogged = sum(1 for name in cat_budget if name not in by_category)",
      "    unlogged = 0")),
    ("the savings bands lose a tier, so a negative rate reads the same as a "
     "thin positive one",
     ('    if rate >= 0:\n        return "critical", "Thin"',
      '    if rate >= -1e9:\n        return "critical", "Thin"')),
    ("debt-to-income treats no debt at all as merely healthy",
     ('    if pct == 0:\n        return "positive", "No debt"',
      '    if pct is None and False:\n        return "positive", "No debt"')),
    ("February is 28 days every year",
     ("    nxt = _date(year + 1, 1, 1) if month == 12 else _date(year, month + 1, 1)\n"
      "    return (nxt - _date(year, month, 1)).days",
      "    return [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]")),
    # ── The year so far ──────────────────────────────────────────────
    ("the year is measured against the CALENDAR rather than against the "
     "months that hold records (a missing March reads as being under budget)",
     ("    budget_documented = budget_monthly * documented_months",
      "    budget_documented = budget_monthly * months_complete")),
    ("the month IN PROGRESS is inside the variance, so rent paid on the 1st "
     "reads as thirty times over budget on the 2nd",
     ("    complete = [m for m in range(1, ref.month)]",
      "    complete = [m for m in range(1, ref.month + 1)]")),
    ("a year with no completed month reports a variance of zero rather than "
     "None, so 'no records yet' reads as 'exactly on budget'",
     ('    variance = (budget_documented - spent_documented) if documented_months else None',
      '    variance = budget_documented - spent_documented')),
    ("savings is measured over the whole elapsed year while spending is "
     "measured over the months on record",
     ("    take_home_documented = monthly_take_home * documented_months",
      "    take_home_documented = monthly_take_home * months_complete")),
    ("last year's expenses are counted in this year's total",
     ("        if d is None or d.year != year:",
      "        if d is None:")),

    # ── The savings-rate curve ───────────────────────────────────────
    ("time to independence uses the CLAMPED savings, so a budget that "
     "overspends leaves the portfolio quietly compounding to the target",
     ("        years = years_to_target(portfolio, raw_savings, fire_number, real_return)",
      "        years = years_to_target(portfolio, annual_savings, fire_number, real_return)")),
    ("a portfolio being drawn down faster than it grows returns a figure "
     "instead of None (the logarithm's guard removed)",
     ("    if base <= 0:\n        return None",
      "    if base <= 0:\n        base = 1.0")),
    ("the curve holds the target fixed instead of lowering it as the savings "
     "rate rises — half the reason the curve has the shape it does",
     ("        spending = annual_take_home * (1.0 - frac)",
      "        spending = annual_take_home * 0.7")),
    ("the expected return is a hardcoded assumption rather than the "
     "simulation's own means, so the page holds two different worlds",
     ("    nominal = stock_alloc * MC_STOCK_MEAN + (1.0 - stock_alloc) * MC_BOND_MEAN",
      "    nominal = 0.09")),
    ("fire_projection re-derives the time rather than calling years_to_target, "
     "so the marker can drift off the curve it is drawn on",
     ("        years = years_to_target(portfolio, raw_savings, fire_number, real_return)",
      "        years = (fire_number - portfolio) / raw_savings if raw_savings > 0 else None")),

    # ── Reading a bank's CSV ─────────────────────────────────────────
    ("a European 1.234,56 is read as US notation, so a $1,234 charge arrives "
     "as a rounding error",
     ("        if last_comma > last_dot:\n"
      "            kept = kept.replace(\".\", \"\").replace(\",\", \".\")\n"
      "        else:\n"
      "            kept = kept.replace(\",\", \"\")",
      "        kept = kept.replace(\",\", \"\")")),
    ("the duplicate rule matches instead of counting, so two real coffees "
     "bought on one day are both refused",
     ("            if index < len(already):\n                duplicate_of = already[index]",
      "            if already:\n                duplicate_of = already[0]")),
    ("nothing is compared against what is already held, so importing the same "
     "file twice doubles a year of spending",
     ("            already = held.get(key, [])",
      "            already = []")),
    ("column detection uses parse_amount, which strips non-digits — so a "
     "column of shop names outscores the amounts and STARBUCKS STORE 4 "
     "imports as a $4.00 charge",
     ("                        if col < len(r) and looks_like_amount(r[col]))",
      "                        if col < len(r) and parse_amount(r[col]) is not None)")),
    ("the sign convention is ignored, so an Amex export imports its refunds "
     "and drops every purchase",
     ("                is_spend = (value < 0) if spend_is_negative else (value > 0)",
      "                is_spend = value < 0")),
    ("an ambiguous date column is reported as proved, so a day-first file is "
     "silently read month-first with nothing on screen saying so",
     ('    return {"order": "MDY", "ambiguous": True, "proved": False,\n'
      '            "reason": "every day of the month is 12 or less, so the file does not say",',
      '    return {"order": "MDY", "ambiguous": False, "proved": True,\n'
      '            "reason": "month first",')),
    ("category matching drops the word boundary, so GYMBOREE becomes Gym and "
     "PARENTS MAGAZINE becomes Rent",
     ("        if not before.isalnum() and not after.isalnum():\n            return True",
      "        return True")),
    ("the shortest match wins, so UBER EATS is filed as Transportation and a "
     "category name loses to any shorter one",
     ("    candidates.sort(key=lambda c: (-c[0], -c[1], c[2], c[3]))",
      "    candidates.sort(key=lambda c: (c[0], -c[1], c[2], c[3]))")),
    ("the keyword table invents a budget line the person does not have",
     ("        own = by_lower.get(canonical.lower())",
      "        own = by_lower.get(canonical.lower()) or canonical")),
    ("the bank's own category wins outright, so Netflix is filed under "
     "Entertainment for a person who has a Subscriptions line",
     ("            fallback = (exact, \"bank category\")",
      "            return exact, \"bank category\"")),
    ("a row that cannot be imported is dropped rather than reported, so the "
     "preview's row count no longer matches the file",
     ('        rows.append({\n            "line": line,',
      '        if skip is not None:\n            continue\n'
      '        rows.append({\n            "line": line,')),
    ("the header row is treated as data, so a file with column names gains a "
     "transaction and one without loses its oldest",
     ("    if has_header is None:\n        has_header = detect_header(grid)",
      "    if has_header is None:\n        has_header = False")),
]

original = open(CALC, "rb").read()
survived = []

print("=" * 70)
print("ENGINE MUTATIONS — each one produces a plausible wrong number")
print("=" * 70)

try:
    for label, edits in MUTATIONS:
        edits = edits if isinstance(edits, list) else [edits]
        src = original.decode("utf-8")
        missing = [old for old, _ in edits if old not in src]
        if missing:
            print(f"  [SETUP FAIL] pattern not found — {label}")
            survived.append(label)
            continue
        for old, new in edits:
            src = src.replace(old, new, 1)
        open(CALC, "w", encoding="utf-8", newline="").write(src)
        r = subprocess.run([PY, "test_calc.py"], capture_output=True, text=True)
        open(CALC, "wb").write(original)

        m = re.search(r"RESULTS: (\d+) passed, (\d+) failed", r.stdout)
        if r.returncode == 0 and m and m.group(2) == "0":
            print(f"  [SURVIVED] {label}")
            survived.append(label)
        else:
            n = m.group(2) if m else "crash"
            first = next((l.strip() for l in r.stdout.splitlines() if "[FAIL]" in l),
                         "(suite crashed)")
            print(f"  [caught: {n} fail(s)] {label[:88]}")
            print(f"       {first[:112]}")
finally:
    open(CALC, "wb").write(original)

print()
if survived:
    print(f"{len(survived)} MUTATION(S) SURVIVED — those assertions cannot fail:")
    for s in survived:
        print(f"  - {s}")
    sys.exit(1)
print(f"all {len(MUTATIONS)} mutations caught; calculations.py restored")
