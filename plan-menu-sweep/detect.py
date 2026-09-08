"""Score the SHIPPING detector against the filers' own labels.

Drives budgeting-app/fund_kinds.py directly. A hand-copied mirror of the
rules here would test rules production no longer has - the grid.js lesson.

THE TRAP THIS AVOIDS. Auditors append the classification to the row -
"Dodge & Cox Stock Fund Registered Investment Company", "Putnam Stable Value
Fund Collective Investment Trust". A detector tested on THAT text is scoring
its ability to read a label the participant will never type. So every
trailing classification phrase is stripped before the detector sees the name,
and the score is reported both ways so the gap stays visible.
"""
import json, io, re, sys, collections

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fund_kinds

# The auditor's own classification, appended to the description. Stripped
# only where it is a TRAILING segment - "Commingled Pool" mid-name is part of
# the product ("Fidelity Freedom Index 2050 Commingled Pool Class T").
FILER_LABEL = re.compile(
    r"[\s,;/-]*(registered investment compan(y|ies)|mutual funds?|"
    r"common\s*/?\s*collective trust(\s*fund)?|collective investment trust|"
    r"collective trust(\s*fund)?|common collective trust(\s*fund)?|"
    r"commingled (trust )?fund|group trust|"
    r"n\s*/\s*[ar]|shares?|units?)\s*$", re.I)


def strip_label(s):
    prev = None
    while prev != s:
        prev = s
        s = FILER_LABEL.sub("", s).strip(" .,-/")
    return s


def detect(name):
    kind, note = fund_kinds.unknown_kind("", name)
    return kind


def corpus():
    import clean
    out = []
    for p in clean.menus(strict=True)[0]:
        for b, l, v in p["rows"]:
            if b in ("cit", "mutualfund"):
                out.append((b, l, v, p["co"]))
    return out


def score(rows, strip):
    tp = fp = fn = tn = 0
    misses, falses = [], []
    for truth, label, v, co in rows:
        name = strip_label(label) if strip else label
        got = detect(name)
        is_cit = truth == "cit"
        if is_cit and got:
            tp += 1
        elif is_cit and not got:
            fn += 1
            misses.append((name, co))
        elif not is_cit and got:
            fp += 1
            falses.append((name, co, got))
        else:
            tn += 1
    return tp, fp, fn, tn, misses, falses


if __name__ == "__main__":
    rows = corpus()
    ncit = sum(1 for r in rows if r[0] == "cit")
    print(f"corpus: {len(rows)} filer-labelled menu lines "
          f"({ncit} CIT, {len(rows) - ncit} mutual fund)\n")
    for strip in (False, True):
        tp, fp, fn, tn, misses, falses = score(rows, strip)
        prec = tp / (tp + fp) * 100 if tp + fp else 100.0
        rec = tp / (tp + fn) * 100 if tp + fn else 0
        tag = ("name only (filer's classification STRIPPED) -- the honest one"
               if strip else
               "raw filing text (includes the auditor's own label)")
        print(f"{tag}")
        print(f"   precision {prec:5.1f}%   recall {rec:5.1f}%   "
              f"tp {tp} fp {fp} fn {fn} tn {tn}")
    tp, fp, fn, tn, misses, falses = score(rows, True)
    print(f"\n--- FALSE positives (a mutual fund called unreachable): {len(falses)}")
    for n, co, g in falses[:10]:
        print(f"   {g:18s} {n[:56]}   [{co[:16]}]")
