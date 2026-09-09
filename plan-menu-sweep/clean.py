"""One corpus, cleaned once, used by every measurement.

A group heading can survive a page break inside one HTML table: AEP files
its own stock and a hundred individual equities after "COMMON / COLLECTIVE
TRUSTS" with no closing total, so the heading carried onto them. Rather than
guess where the section ended, drop rows that ARE a company - a schedule line
whose name matches an SEC registrant exactly is a share of that company, not
a fund. Same name index the holdings chore already keys on.
"""
import json, io, re, collections

SUFFIX = re.compile(
    r"\b(INC|CORP|CORPORATION|COMPANY|CO|LTD|LIMITED|PLC|LLC|LP|NV|SA|AG|"
    r"HOLDINGS|HOLDING|GROUP|CLASS [A-C]|CL [A-C]|COM|THE|NEW|ADR)\b")


def ckey(name):
    s = (name or "").upper().replace("&AMP;", "&")
    s = s.split("/")[0]
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


_ct = json.load(io.open("ct.json", encoding="utf-8"))
REGISTRANTS = {ckey(v["title"]) for v in _ct.values()}
REGISTRANTS.discard("")

FUNDLIKE = {"mutualfund", "cit", "stable", "cash", "etf"}


def is_company(label):
    k = ckey(label)
    return bool(k) and k in REGISTRANTS


def menus(path="sweep11k.json", strict=False):
    """Menu-shaped plans with company shares removed from the fund buckets.

    `strict` also drops plans whose schedule lists hundreds of individual
    line items. A participant menu has tens of options; AEP's schedule runs
    to 287 securities rows, and it is at a page break inside that list that
    the collective-trust heading leaked onto its equities. Those plans stay
    in the dollar aggregate (their CIT lines are real and are the menu) and
    are kept out of the DETECTOR corpus, where a hundred mislabelled stocks
    would be scored as missed collective trusts."""
    d = json.load(io.open(path, encoding="utf-8"))
    out, dropped = [], 0
    for p in d:
        if not p["rows"]:
            continue
        rows = []
        for b, l, v in p["rows"]:
            if b in FUNDLIKE and is_company(l):
                dropped += 1
                continue
            rows.append((b, l, v))
        t = collections.Counter()
        for b, l, v in rows:
            t[b] += v
        tot = sum(t.values())
        if not tot or (t["security"] + t["unbucketed"]) / tot > 0.5:
            continue
        if sum(t[b] for b in FUNDLIKE) <= 0:
            continue
        if strict and (len([1 for b, _, _ in rows
                            if b in ("security", "unbucketed")]) > 100):
            continue
        out.append({"co": p["co"], "rows": rows, "t": t,
                    "fund": sum(t[b] for b in FUNDLIKE)})
    return out, dropped


if __name__ == "__main__":
    import statistics
    m, dropped = menus()
    print(f"dropped {dropped} rows that match an SEC registrant by name")
    print(f"menu-shaped plans: {len(m)}")
    g = sum(x["fund"] for x in m)
    cit = sum(x["t"]["cit"] for x in m)
    print(f"\nfund-like dollars ${g:,.0f}")
    print(f"  collective trusts   ${cit:,.0f}  {100*cit/g:.1f}%  (dollar-weighted)")
    sh = [100 * x["t"]["cit"] / x["fund"] for x in m]
    print(f"  median plan         {statistics.median(sh):.1f}%")
    print(f"  CIT is a majority   {sum(1 for s in sh if s > 50)}/{len(m)} plans")
    print(f"  no CIT at all       {sum(1 for s in sh if s == 0)}/{len(m)} plans")
