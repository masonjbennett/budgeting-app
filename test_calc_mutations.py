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
    # -- The portfolio X-ray ------------------------------------------
    ('the weighted expense ratio divides by the WHOLE portfolio rather than by the dollars whose fee is known, so a 401(k) full of untabled funds reads as cheap',
     ('                   / fee_value) if fee_value else None',
      '                   / total) if fee_value else None')),
    ('a fund the table does not carry resolves to a fee of ZERO, which reads as measured and takes the coverage banner off the page with it',
     ('    if not entry:\n        return None, None, None, False',
      '    if not entry:\n        return 0.0, None, None, True')),
    ('effective holdings counts the positions instead of weighting them, so a portfolio 60% in one line reads as diversified as one split evenly',
     ('        "effective_holdings": (1.0 / hhi) if hhi else None,',
      '        "effective_holdings": float(len(rows)) if hhi else None,')),
    ('duplicate detection matches on an EMPTY symbol, so every untabled 401(k) fund merges into one fictitious position',
     ('        if r["symbol"]:\n            by_symbol.setdefault(r["symbol"], []).append(r)',
      '        if True:\n            by_symbol.setdefault(r["symbol"], []).append(r)')),
    ('a half-typed zero-value row counts as a holding, diluting every percentage on the page with a position that does not exist',
     ('        if value <= 0:\n            # A zero row is something half-typed, not a holding.',
      '        if False:\n            # A zero row is something half-typed, not a holding.')),
    ('the fee drag is compounded over the WHOLE portfolio while the page says it was measured over the covered part',
     ('        gross, _ = project_investment(fee_value, 0, annual_return, years)',
      '        gross, _ = project_investment(total, 0, annual_return, years)')),
    ('the cash figure divides by CLASSIFIED dollars like the mix does, so the page prints two different percentages for the same money',
     ('        "cash_pct_of_total": _share(cash_value, total),',
      '        "cash_pct_of_total": _share(cash_value, cls_value),')),
    # -- Where a fee figure came from --------------------------------
    ('the sourced share divides by the WHOLE portfolio rather than by the money the fee was measured over, so a portfolio full of individual stocks reads as badly evidenced',
     ('        "sourced_pct": _share(sum(r["value"] for r in rows if r["src"]), fee_value),',
      '        "sourced_pct": _share(sum(r["value"] for r in rows if r["src"]), total),')),
    ('individual stocks and cash are counted as UNSOURCED, so the page names them as figures nobody checked when their zero is arithmetic',
     ('        "unsourced": [r["label"] or r["symbol"] or "(unnamed)" for r in rows\n                      if r["er"] is not None and not r["src"] and r["kind"] == "fund"],',
      '        "unsourced": [r["label"] or r["symbol"] or "(unnamed)" for r in rows\n                      if r["er"] is not None and not r["src"]],')),
    ('a hand-written ratio is reported as though it came from a filing, so the page claims a source for every fund in the table',
     ('    return entry["er"], entry["cls"], entry.get("region"), True, entry.get("src")',
      '    return entry["er"], entry["cls"], entry.get("region"), True, "0000000000-00-000000"')),
    # -- Look-through -------------------------------------------------
    ("a fund's weight is applied as a fraction rather than a percent, so a 40% holding becomes 40x the fund and the portfolio owns forty times itself",
     ('            add(k, name, tk, value * pct / 100.0, False)',
      '            add(k, name, tk, value * pct, False)')),
    ('the part of a fund NOT stored is quietly attributed to nobody and not counted either, so the page claims it saw a whole portfolio it saw two thirds of',
     ('        unseen_value += value * max(0.0, 100.0 - covered) / 100.0',
      '        unseen_value += 0.0')),
    ('cash is looked through as if it were a company, so it appears in a list of what you own shares of',
     ('        if kind == "cash":\n            # Cash is not a company and does not belong in a list of what you\n            # own. It is already reported on its own.\n            continue',
      '        if kind == "cash":\n            # Cash is not a company and does not belong in a list of what you\n            # own. It is already reported on its own.\n            add("CASH", "Cash", None, value, True)\n            continue')),
    ('a holding is called BOTH on the strength of being held directly alone, so the badge appears on every stock somebody owns',
     ('            "both": e["direct"] > 0 and e["via"] > 0,',
      '            "both": e["direct"] > 0,')),
    ('a fund with no stored holdings is dropped rather than named, so the portfolio silently shrinks to the funds this table happens to know',
     ('        if not entry:\n            unseen_value += value\n            unseen.append(r["label"] or r["symbol"] or "(unnamed)")\n            continue',
      '        if not entry:\n            continue')),

    # ── What an uncovered holding is (fund_kinds.py) ──────────────────
    ('the unreachable share is measured against the whole portfolio while the page calls it a share of what could not be measured, which understates it on every portfolio holding anything the table knows',
     ('        "pct_of_uncovered": _share(unreachable_value, total - fee_value),',
      '        "pct_of_uncovered": _share(unreachable_value, total),')),
    ('the name is read for every holding rather than only the uncovered ones, so a fund the table covers can be overruled by what somebody called it',
     ('        if not known:\n            plan_kind, plan_note = _unknown_kind(h.get("symbol"), h.get("label"))',
      '        if True:\n            plan_kind, plan_note = _unknown_kind(h.get("symbol"), h.get("label"))')),
    ('only the label is read, so a plan fund whose name was typed into the symbol box is not recognised',
     ('    text = " ".join(str(x or "") for x in (label, symbol)).strip()',
      '    text = str(label or "").strip()'),
     "fund_kinds.py"),
    ('a stable value contract is reported as a collective trust, which sends somebody looking for a fee disclosure that describes a different vehicle',
     ('    if _CIT.search(text):\n        return COLLECTIVE_TRUST, NOTES[COLLECTIVE_TRUST]\n    if _INSURANCE.search(text):\n        return INSURANCE_CONTRACT, NOTES[INSURANCE_CONTRACT]',
      '    if _CIT.search(text) or _INSURANCE.search(text):\n        return COLLECTIVE_TRUST, NOTES[COLLECTIVE_TRUST]'),
     "fund_kinds.py"),
    ('a note tells somebody what to do about a holding rather than what it is — the one thing this whole tool is built not to do',
     ('        "fee disclosure carries the fee."),',
      '        "fee disclosure carries the fee. You should sell it."),'),
     "fund_kinds.py"),
]

# An entry may name the file it mutates. `fund_kinds.py` is a second module
# the engine imports, and a rule living there is no less shipped for it — but
# it could not be mutated while this harness only knew one filename, so its
# assertions would have gone unchecked. Neither file has a sync check against
# it here, which is what makes a mutation in either one honest.
ORIGINALS = {f: open(f, "rb").read() for f in (CALC, "fund_kinds.py")}
survived = []

print("=" * 70)
print("ENGINE MUTATIONS — each one produces a plausible wrong number")
print("=" * 70)

try:
    for entry in MUTATIONS:
        label, edits = entry[0], entry[1]
        target = entry[2] if len(entry) > 2 else CALC
        original = ORIGINALS[target]
        edits = edits if isinstance(edits, list) else [edits]
        src = original.decode("utf-8")
        missing = [old for old, _ in edits if old not in src]
        if missing:
            print(f"  [SETUP FAIL] pattern not found — {label}")
            survived.append(label)
            continue
        for old, new in edits:
            src = src.replace(old, new, 1)
        open(target, "w", encoding="utf-8", newline="").write(src)
        r = subprocess.run([PY, "test_calc.py"], capture_output=True, text=True)
        open(target, "wb").write(original)

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
    for _f, _b in ORIGINALS.items():
        open(_f, "wb").write(_b)

print()
if survived:
    print(f"{len(survived)} MUTATION(S) SURVIVED — those assertions cannot fail:")
    for s in survived:
        print(f"  - {s}")
    sys.exit(1)
print(f"all {len(MUTATIONS)} mutations caught; calculations.py restored")
