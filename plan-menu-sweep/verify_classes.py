"""Is every SERIES the table touches carried WHOLE?

The rule fund_data.py states is that a series is carried whole or not at all —
a half-present series reads as coverage. This checks it against SEC's series
ids, which are exact, rather than against a normalised name, which is not:
`fkey` strips INDEX, II and INSTITUTIONAL, so it collapses "Total Bond Market
Index Fund" with "Total Bond Market II Index Fund" and "Fidelity Freedom 2040"
with "Fidelity Freedom Index 2040" — different funds.

Run after any widening.
"""
import csv, io, os, sys, collections

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fund_data import FUNDS

rows = [r for r in csv.DictReader(io.open("scc.csv", encoding="utf-8-sig"))
        if r["Entity Org Type"] == "30" and r["Class Ticker"].strip()]
series_of = {r["Class Ticker"].strip().upper(): r["Series ID"] for r in rows}
name_of = {r["Series ID"]: r["Series Name"].strip() for r in rows}
classes_of = collections.defaultdict(set)
for r in rows:
    classes_of[r["Series ID"]].add(r["Class Ticker"].strip().upper())

touched = collections.defaultdict(set)
unmapped = []
for t in FUNDS:
    s = series_of.get(t)
    if s:
        touched[s].add(t)
    else:
        unmapped.append(t)

partial = []
for s, have in sorted(touched.items()):
    missing = classes_of[s] - have
    if missing:
        partial.append((name_of.get(s, s), sorted(have), sorted(missing)))

print(f"{len(FUNDS)} tickers -> {len(touched)} SEC series "
      f"({len(unmapped)} not in SEC's class map: {sorted(unmapped)})")
if partial:
    print(f"\n{len(partial)} series carried in PART:")
    for nm, have, miss in partial:
        print(f"  {nm[:44]:46s} have {','.join(have)[:34]:36s} missing {','.join(miss)[:40]}")
else:
    print("\nevery series the table touches is carried WHOLE")
