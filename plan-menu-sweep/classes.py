"""Share classes of funds the table ALREADY carries.

The gap list ranks funds the table has never heard of, and beyond the
target-date series it is a long tail with no natural stopping point — nothing
above 2 of 29 plans, against 28,500 tickered share classes in existence.
Picking "the top ten" off that tail would be arbitrary.

This is the part that is NOT arbitrary. Where a plan holds a share class of a
fund the table already carries — VIIIX against the 500 index it has as VFIAX,
VSIAX against the small-cap value it has as VBR — the table already claims to
carry that fund and simply does not recognise the ticker in front of the
reader. That is the "a series is carried whole" rule one level down, and it is
bounded by what is already in the table rather than by the market.

Each class has its OWN fee, so each needs the chore run against its own
filing. Never copy a sibling's number.
"""
import collections
import csv
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import clean
from detect import strip_label
from gaps import fkey
from fund_data import FUNDS

rows = [r for r in csv.DictReader(io.open("scc.csv", encoding="utf-8-sig"))
        if r["Entity Org Type"] == "30" and r["Class Ticker"].strip()]

# ticker -> its series key, and series key -> every tickered class
series_of, classes_of = {}, collections.defaultdict(list)
for r in rows:
    k = fkey(r["Series Name"])
    series_of[r["Class Ticker"].strip().upper()] = k
    classes_of[k].append(r)

HAVE_TICKERS = set(FUNDS)
# The series this table already carries, via the tickers it holds.
HAVE_SERIES = {series_of[t] for t in HAVE_TICKERS if t in series_of}

plans = collections.defaultdict(set)
dollars = collections.Counter()

for p in clean.menus(strict=True)[0]:
    for b, l, v in p["rows"]:
        if b != "mutualfund":
            continue
        k = fkey(strip_label(l))
        if not k or k not in HAVE_SERIES:
            continue
        # The table carries this fund. Does it carry the class a plan holds?
        # We cannot know the exact class from the name alone, so report the
        # series and let the chore decide which tickers to add.
        missing = [c for c in classes_of[k]
                   if c["Class Ticker"].strip().upper() not in HAVE_TICKERS]
        if missing:
            plans[k].add(p["co"])
            dollars[k] += v

print("Series the table CARRIES, where a tickered class is still missing\n")
print(f"{'plans':>5} {'dollars':>16}  {'have':10s} {'missing classes'}")
total_plans = set()
for k in sorted(plans, key=lambda x: (-len(plans[x]), -dollars[x])):
    have = sorted(t for t in HAVE_TICKERS if series_of.get(t) == k)
    miss = sorted(c["Class Ticker"].strip().upper() for c in classes_of[k]
                  if c["Class Ticker"].strip().upper() not in HAVE_TICKERS)
    total_plans |= plans[k]
    print(f"{len(plans[k]):5d} {dollars[k]:16,.0f}  {','.join(have):10s} "
          f"{','.join(miss)[:60]}")
print(f"\n{len(plans)} series, touching {len(total_plans)} of "
      f"{len(clean.menus(strict=True)[0])} plans, "
      f"${sum(dollars.values()):,.0f}")
