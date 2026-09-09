"""Emit fund_data.py rows for the missing share classes of funds already here.

TWO KEYS, AND THEY ARE NOT THE SAME KEY. Matching a plan's LABEL to a fund can
only be done on the name, because a 4i schedule carries no ticker — that is
`fkey`. But ENUMERATING the classes of that fund must use SEC's **series id**,
which is exact.

The first version used `fkey` for both and it crossed a series boundary
silently: `fkey` strips INDEX, II and INSTITUTIONAL, so "Vanguard Total Bond
Market Index Fund" and "Vanguard Total Bond Market **II** Index Fund" collapse
to one key, as do "Fidelity Freedom 2040" (active, FFFFX) and "Fidelity Freedom
**Index** 2040" (FBIFX) — different funds, and the Fidelity pair differ roughly
sixfold in fee. Five of the 41 classes shipped that way (VRTPX, VTBIX, VTBNX,
VITNX, VITPX). They are real funds real plans hold and their classifications
were checked and are right, but nothing in the process had established that.

`cls`, `region` and `style` are COPIED from the sibling already in the table:
those describe the FUND, and a share class of the 500 index fund is still
equity / us / large_cap. `er` is copied only as a PLACEHOLDER and carries no
`src`, which is the honest UNSOURCED state — then `refresh_fund_data.py` reads
each class's own ratio out of its own filing. **A class fee is not its
sibling's**: the chore corrected 35 of the 41, and the Vanguard 500 index runs
0.01% to 0.14% across four tickers. Anything the chore cannot source must be
DELETED rather than left carrying a copied number.
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

series_of = {}                      # ticker -> series id (EXACT)
classes_of = collections.defaultdict(list)   # series id -> its classes
byname = collections.defaultdict(set)        # fkey(name) -> series ids
for r in rows:
    t = r["Class Ticker"].strip().upper()
    series_of[t] = r["Series ID"]
    classes_of[r["Series ID"]].append(r)
    byname[fkey(r["Series Name"])].add(r["Series ID"])

HAVE = set(FUNDS)
# The SERIES this table already carries, via the tickers it holds.
HAVE_SERIES = {}
for t in HAVE:
    s = series_of.get(t)
    if s:
        HAVE_SERIES.setdefault(s, t)

wanted = collections.OrderedDict()
for p in clean.menus(strict=True)[0]:
    for b, l, v in p["rows"]:
        if b != "mutualfund":
            continue
        # name -> candidate series ids, then keep only those the table has.
        for s in byname.get(fkey(strip_label(l)), ()):
            if s in HAVE_SERIES:
                wanted.setdefault(s, HAVE_SERIES[s])

out = []
for s, sib in wanted.items():
    e = FUNDS[sib]
    for c in sorted(classes_of[s], key=lambda c: c["Class Ticker"]):
        t = c["Class Ticker"].strip().upper()
        if t in HAVE:
            continue
        name = re.sub(r"\s+", " ",
                      f'{c["Series Name"].strip()} {c["Class Name"].strip()}')
        name = name.replace(" Fund ", " ").replace(" Shares", "").strip()
        out.append((t, name, e, c["Series Name"].strip()))

print(f"# {len(out)} classes across {len(wanted)} series already in the table")
print("# every one enumerated by SERIES ID, so none crosses a fund boundary")
for t, name, e, series in out:
    reg = f'"{e["region"]}"' if e.get("region") else "None"
    print(f'    "{t}": {{"name": "{name}", "er": {e["er"]}, '
          f'"cls": "{e["cls"]}", "region": {reg}, "style": "{e["style"]}"}},')
