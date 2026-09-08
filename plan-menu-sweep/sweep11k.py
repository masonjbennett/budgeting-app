"""What is actually IN a 401(k) menu, measured over real plans.

FRAME, selected not remembered: every Form 11-K filed in 2026 - the annual
report a public company files for its own savings plan, carrying Schedule H
line 4i, the plan's complete list of investments. 766 of them. Ordered
alphabetically by company name in EDGAR's quarterly index, which is
uncorrelated with plan size, so a fixed stride is a clean sample.

The bucket for each holding is THE FILER'S OWN grouping heading, not my
reading of the name.
"""
import io, json, re, sys, collections
import sched

STRIDE = int(sys.argv[1]) if len(sys.argv) > 1 else 16


def filings():
    out = []
    for f in ("form-2026-QTR2.idx", "form-2026-QTR3.idx"):
        for line in io.open(f, encoding="latin-1"):
            if line.startswith("11-K "):
                # fixed-width: form, company, cik, date, filename
                m = re.match(r"^11-K\s+(.+?)\s{2,}(\d+)\s+(\d{4}-\d\d-\d\d)\s+(\S+)$",
                             line.rstrip())
                if m:
                    out.append({"co": m.group(1).strip(), "cik": m.group(2),
                                "date": m.group(3), "path": m.group(4)})
    return out


def primary(cik, acc):
    """Largest .htm that is not an exhibit, a certification or an R-file."""
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/index.json"
    items = json.loads(sched.get(url))["directory"]["item"]
    best, bestsz = None, -1
    for i in items:
        n = i["name"]
        if not n.lower().endswith((".htm", ".html")):
            continue
        if re.match(r"^R\d+\.htm$", n) or "index" in n.lower():
            continue
        if re.search(r"ex[-_]?\d|ex\d|cert|consent", n, re.I):
            continue
        try:
            sz = int(i.get("size") or 0)
        except ValueError:
            sz = 0
        if sz > bestsz:
            best, bestsz = n, sz
    if best:
        return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{best}"
    return None


# Headings an auditor uses, mapped to what the thing IS. Order matters:
# "common collective trust" must be tested before "common stock".
BUCKETS = [
    ("employer",   r"employer securit|company stock|employer stock|"
                   r"common stock\s*[-–]\s*employer|unitized"),
    ("cit",        r"collective trust|common collective|collective invest|"
                   r"commingled|common/collective|group trust|"
                   r"collective fund|bank collective"),
    ("mutualfund", r"mutual fund|registered investment compan|open.end fund|"
                   r"^funds?$|mutual funds"),
    ("stable",     r"stable value|guaranteed|insurance contract|"
                   r"synthetic gic|investment contract|annuity"),
    ("security",   r"common stock|preferred stock|corporate bond|"
                   r"u\.?s\.? government|treasur|municipal|equit(y|ies)$|"
                   r"fixed income|asset.backed|mortgage"),
    ("cash",       r"cash equivalent|money market|short.term invest|^cash"),
    ("sdba",       r"self.directed|brokerage"),
    ("loans",      r"loans? to participant|notes receivable"),
    ("etf",        r"exchange.traded"),
]

SKIP_ROW = re.compile(
    r"^total\b|^subtotal\b|^net assets|^description|^identity of issue|^\(a\)|^\(b\)|^\(c\)|"
    r"^interest rate|^par value|^maturit|^cost\b|^current value|^shares?$|"
    r"^units?$|^see (accompanying|notes)|^column|^schedule|^december|^supplemental",
    re.I)


def bucket_of(heading):
    h = (heading or "").lower()
    for name, pat in BUCKETS:
        if re.search(pat, h):
            return name
    return None


def plan_rows(rows):
    """Walk a schedule top to bottom carrying the last grouping heading."""
    cur, out = None, []
    for label, val in rows:
        if SKIP_ROW.match(label):
            if re.match(r"^(sub)?total\b", label, re.I):
                # A "Total X" line CLOSES its group. Carrying the heading past
                # it put five individual common stocks (AES, Allegion, Acuity)
                # into the collective-trust bucket, because the stocks listed
                # after "Total Collective trust funds" inherited it.
                cur = None
            continue
        if val is None:
            b = bucket_of(label)
            if b:
                cur = b
            continue
        if re.match(r"^loans? to participant|^notes receivable", label, re.I):
            out.append(("loans", label, val))
            continue
        # Some filers carry the type IN THE ROW rather than as a group
        # heading ("Putnam Stable Value Fund Collective Investment Trust").
        # Still the filer's own classification, just placed differently, so
        # it is read only where the running heading gave nothing.
        out.append((cur or bucket_of(label) or "unbucketed", label, val))
    return out


def main():
    fl = filings()
    sample = fl[::STRIDE]
    print(f"# 11-K population {len(fl)}, stride {STRIDE} -> {len(sample)} plans",
          file=sys.stderr)
    res = []
    for i, f in enumerate(sample):
        acc = f["path"].rsplit("/", 1)[-1].replace(".txt", "").replace("-", "")
        rec = {"co": f["co"], "cik": f["cik"], "acc": acc, "rows": [], "err": None}
        try:
            u = primary(f["cik"], acc)
            if not u:
                rec["err"] = "no primary document"
            else:
                html = sched.get(u)
                S = sched.schedules(html)
                if not S:
                    rec["err"] = "no 4i schedule found"
                else:
                    # the schedule is the table with the most valued rows
                    for rows in S:
                        rec["rows"] += plan_rows(rows)
        except Exception as e:
            rec["err"] = f"{type(e).__name__}: {e}"
        res.append(rec)
        print(f"  [{i+1}/{len(sample)}] {f['co'][:40]:42s} "
              f"{len(rec['rows']):4d} rows {rec['err'] or ''}", file=sys.stderr)
    json.dump(res, io.open("sweep11k.json", "w", encoding="utf-8"))
    print("wrote sweep11k.json", file=sys.stderr)


if __name__ == "__main__":
    main()
