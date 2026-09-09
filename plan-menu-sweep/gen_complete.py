"""Emit the classes needed to carry every series in the table WHOLE.

gen_classes.py adds classes a SAMPLED PLAN held. This closes the rule the
table states about itself: a series is carried whole or not at all. Keyed on
SEC series ids throughout — never on a normalised name, which collapses
"Total Bond Market Index" with "Total Bond Market II Index".

Fees are placeholders with no `src`; run refresh_fund_data.py --write after.
"""
import collections, csv, io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fund_data import FUNDS

rows = [r for r in csv.DictReader(io.open("scc.csv", encoding="utf-8-sig"))
        if r["Entity Org Type"] == "30" and r["Class Ticker"].strip()]
series_of = {r["Class Ticker"].strip().upper(): r["Series ID"] for r in rows}
classes_of = collections.defaultdict(list)
for r in rows:
    classes_of[r["Series ID"]].append(r)

touched = collections.defaultdict(set)
for t in FUNDS:
    s = series_of.get(t)
    if s:
        touched[s].add(t)

out = []
for s, have in sorted(touched.items()):
    sib = sorted(have)[0]
    e = FUNDS[sib]
    for c in sorted(classes_of[s], key=lambda c: c["Class Ticker"]):
        t = c["Class Ticker"].strip().upper()
        if t in FUNDS:
            continue
        name = re.sub(r"\s+", " ",
                      f'{c["Series Name"].strip()} {c["Class Name"].strip()}')
        name = name.replace(" Fund ", " ").replace(" Shares", "").strip()
        out.append((t, name, e))

print(f"# {len(out)} classes needed to carry every series whole")
for t, name, e in out:
    reg = f'"{e["region"]}"' if e.get("region") else "None"
    print(f'    "{t}": {{"name": "{name}", "er": {e["er"]}, '
          f'"cls": "{e["cls"]}", "region": {reg}, "style": "{e["style"]}"}},')
