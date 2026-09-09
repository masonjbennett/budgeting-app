"""Which registered funds do real 401(k) menus hold that the table misses?

Measured off the 11-K sweep, resolved to a ticker through SEC's own
series/class file. Ranked by how many PLANS hold it, not by dollars: one
enormous plan should not decide what a table for individuals carries.
"""
import csv, io, re, sys, collections
import clean
# The auditor appends its own classification to the row ("... Fund Mutual
# fund"), which fkey turns into a trailing "MUTUAL" that matches nothing in
# the table. Left in, it reported the whole Vanguard Target Retirement series
# as still missing AFTER it had been added. detect.py already strips it; the
# gap list has to use the same stripper or it measures the auditor's prose.
from detect import strip_label
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fund_data import FUNDS

WRAP = re.compile(
    r"\b(FUND|FUNDS|ETF|INDEX|ADMIRAL|INVESTOR|INSTITUTIONAL|INSTL|INST|"
    r"SHARES|SHARE|CLASS|TRUST|PORTFOLIO|THE|INC|SERIES|R\d|K\d?|[IVX]{1,3})\b")


def fkey(n):
    s = (n or "").upper().replace("&AMP;", "&")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", WRAP.sub(" ", s)).strip()


rows = [r for r in csv.DictReader(io.open("scc.csv", encoding="utf-8-sig"))
        if r["Entity Org Type"] == "30" and r["Class Ticker"].strip()]
byname = collections.defaultdict(list)
for r in rows:
    byname[fkey(r["Series Name"])].append(r)

HAVE = {fkey(v["name"]) for v in FUNDS.values()}
plans = collections.defaultdict(set)
dollars = collections.Counter()

for p in clean.menus(strict=True)[0]:
    for b, l, v in p["rows"]:
        if b != "mutualfund":
            continue
        k = fkey(strip_label(l))
        if not k or k in HAVE:
            continue
        hit = byname.get(k)
        if not hit:
            for kk in byname:
                if kk and len(kk) > 10 and (k.startswith(kk + " ") or k == kk):
                    hit = byname[kk]
                    break
        if hit:
            key = fkey(hit[0]["Series Name"])
            plans[key].add(p["co"])
            dollars[key] += v

print(f"{'plans':>5} {'dollars':>16}  {'tickers':32s} series")
for k in sorted(plans, key=lambda x: (-len(plans[x]), -dollars[x])):
    hit = byname[k]
    tick = ",".join(sorted({h["Class Ticker"].strip() for h in hit}))[:31]
    print(f"{len(plans[k]):5d} {dollars[k]:16,.0f}  {tick:32s} {hit[0]['Series Name'][:44]}")
