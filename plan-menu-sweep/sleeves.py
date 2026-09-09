"""What does a target-date fund actually hold, and does the table carry it?

Removing the "II" collapse from refresh_holdings.py made the substitution
precise and cost expansion coverage (VTINX 83.1% -> 67.7%). This reads the
sleeves out of the filing rather than guessing which fund is missing.
"""
import importlib.util as iu
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

spec = iu.spec_from_file_location("rh", os.path.join(ROOT, "refresh_holdings.py"))
rh = iu.module_from_spec(spec)
sys.modules["rh"] = rh
spec.loader.exec_module(rh)

import fund_data
import fund_holdings as fh

stored = {rh.fundkey(fund_data.FUNDS[s]["name"]): s for s in fh.HOLDINGS}

tmap = rh.R.ticker_map()
for sym in sys.argv[1:] or ["VTINX", "VTWNX", "VTTSX"]:
    cik, series, _cls = tmap[sym]
    rows = None
    for acc, date, base in rh.latest_nport(cik, series):
        rows = rh.holdings_from(rh.R.get(base + "/primary_doc.xml"))
        if rows:
            break
    rows.sort(key=lambda r: -r[1])
    print(f"\n{sym}  ({date})")
    for name, pct, _cat in rows:
        if pct <= 0:
            continue
        k = rh.fundkey(name)
        hit = stored.get(k)
        mark = f"-> {hit}" if hit else "** NOT IN THE TABLE **"
        print(f"   {pct:6.2f}%  {name[:52]:54s} {mark}")
