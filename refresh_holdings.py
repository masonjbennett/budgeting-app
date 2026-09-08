"""Read each fund's largest holdings out of its N-PORT filing.

WHAT THIS BUYS. Without it the X-ray measures concentration across POSITIONS,
so someone holding NVDA directly and an S&P fund is told they hold less NVDA
than they do. With it the page can say "counting through your funds, NVIDIA is
9.4% of everything you own" — which the September research found is the one
feature no free manual-entry tool offers since Morningstar retired Instant
X-Ray in April 2025.

WHY N-PORT AND NOT THE ISSUERS' OWN FILES. The research recommended issuer
daily holdings CSVs (Rule 6c-11) over N-PORT, on FRESHNESS: N-PORT is public
60 days after quarter end and only the third month of each quarter is public,
so it runs up to ~4 months behind. That is the right call for a tool fetching
live, and the wrong one here. This is a CHORE that bakes a static table
refreshed about annually, so the table is stale by construction and a quarter
is well inside the noise; against that, issuer files cost five different
per-issuer scrapers and come with redistribution terms, while N-PORT is public
domain, one format, and reuses the ticker->series->filing chain
refresh_fund_data.py already has working. Freshness we do not need is not
worth a licensing question we would have to answer.

THE JOIN KEY IS THE COMPANY NAME, and the two obvious alternatives are both
unavailable:

  * TICKER is in 1 of 520 N-PORT holdings. Not an option.
  * CUSIP is on all of them and is a LICENSED identifier. Baking a few
    thousand into a public repo is a redistribution question nobody needs
    answered, and nothing here requires it.

So holdings are keyed on a normalised company name, and the user's ticker
reaches the same key space through SEC's company_tickers.json. Measured on
VOO's top 50: 50 of 50 resolve to a ticker. Two normalisations earn their
place — SEC appends the state of incorporation to a registrant's title
("BANK OF AMERICA CORP /DE/", "WELLS FARGO & COMPANY/MN") and fund filings
never do, and a spaceless second pass catches "Exxon Mobil Corp" against
SEC's "ExxonMobil Holdings Corp", which is the XOM holdco entry
filings-terminal already documents.

DEPTH IS TOP 50, AND THE REST IS REPORTED RATHER THAN IGNORED. Fifty names is
63% of VOO and 51% at twenty-five; the whole fund would be ~500 rows per fund
and a megabyte of static data for a long tail that changes nothing about
concentration. Each fund records what share of itself the stored names cover,
so the page can say how much of the portfolio it actually saw.

Run:  .venv/Scripts/python.exe refresh_holdings.py           # report only
      .venv/Scripts/python.exe refresh_holdings.py --write   # write fund_holdings.py
"""

import io
import json
import re
import sys

import refresh_fund_data as R

TOP_N = 50

# Suffixes that say what KIND of company it is rather than which company.
SUFFIX = re.compile(
    r"\b(INC|CORP|CORPORATION|COMPANY|CO|LTD|LIMITED|PLC|LLC|LP|NV|SA|AG|"
    r"HOLDINGS|HOLDING|GROUP|CLASS [A-C]|CL [A-C]|COM|THE|TRUST|"
    r"INTERNATIONAL|INTL)\b")

# A holding whose name reads like a fund is a second LEVEL, not a company: a
# target-date fund holds other funds. Detected so those funds can be reported
# as un-looked-through rather than silently listed as if "Vanguard Total Stock
# Market Index Fund" were a company somebody owns 40% of.
FUNDLIKE = re.compile(
    r"\b(FUND|ETF|INDEX|PORTFOLIO|TRUST|MONEY MARKET)\b", re.I)


# Words that say which SHARE CLASS or wrapper a fund is, rather than which
# fund. A target-date fund holds "Vanguard Total Stock Market Index Fund";
# the table calls the same thing "Vanguard Total Stock Market ETF" and
# "...Index Admiral". Stripping these makes all three "VANGUARD TOTAL STOCK
# MARKET", which is the level the holdings are actually shared at.
WRAPPER = re.compile(
    r"\b(FUND|FUNDS|ETF|INDEX|ADMIRAL|INVESTOR|INSTITUTIONAL|SHARES|SHARE|"
    r"CLASS|TRUST|II|III|PORTFOLIO|VANGUARD CMT)\b")


def fundkey(name):
    """A fund's identity with its wrapper words removed."""
    s = (name or "").upper().replace("&AMP;", "&")
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = WRAPPER.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def key(name):
    s = (name or "").upper().replace("&AMP;", "&")
    s = s.split("/")[0]
    s = re.sub(r"[^A-Z0-9 ]+", " ", s)
    s = SUFFIX.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


def tight(name):
    return key(name).replace(" ", "")


def latest_nport(cik, series, count=6):
    """Recent NPORT-P filings for this series, newest first.

    Queried by SERIES ID in place of the CIK for the same reason
    refresh_fund_data.py does: browsing the CIK with `&series=` returns
    filings for adjacent series in the same trust.
    """
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           "&CIK=%s&type=NPORT-P&dateb=&owner=include&count=%d&output=atom"
           % (series, count))
    xml = R.get(url)
    accs = re.findall(r"accession-n[^>]*>([0-9-]+)<", xml)
    dates = re.findall(r"<filing-date>([^<]+)</filing-date>", xml)
    out, seen = [], set()
    for acc, date in zip(accs, dates):
        if acc in seen:
            continue
        seen.add(acc)
        base = ("https://www.sec.gov/Archives/edgar/data/%d/%s"
                % (cik, acc.replace("-", "")))
        out.append((acc, date, base))
    return out


HOLDING = re.compile(r"<invstOrSec>(.*?)</invstOrSec>", re.S)


def holdings_from(doc):
    """(name, pct, assetCat) for every position in an N-PORT document.

    `pctVal` is the position as a PERCENT of net assets, which is exactly the
    weight look-through needs — no division by a total this has to trust.
    """
    out = []
    for b in HOLDING.findall(doc):
        n = re.search(r"<name>([^<]*)", b)
        p = re.search(r"<pctVal>([-\d.eE]+)", b)
        c = re.search(r"<assetCat>([^<]*)", b)
        if not (n and p):
            continue
        try:
            pct = float(p.group(1))
        except ValueError:
            continue
        out.append((n.group(1).strip(), pct, c.group(1) if c else ""))
    return out


def main():
    write = "--write" in sys.argv
    sys.path.insert(0, ".")
    import fund_data

    print("Reading holdings for %d funds\n" % len(fund_data.FUNDS))
    tmap = R.ticker_map()

    ct = json.loads(R.get("https://www.sec.gov/files/company_tickers.json"))
    bykey, bytight = {}, {}
    for row in ct.values():
        k, t = key(row["title"]), tight(row["title"])
        if k:
            bykey.setdefault(k, row["ticker"])
            bytight.setdefault(t, row["ticker"])

    out, skipped = {}, []
    for sym in sorted(fund_data.FUNDS):
        ent = tmap.get(sym)
        if not ent:
            skipped.append((sym, "not an open-end fund in SEC's map"))
            print("  %-6s -- not in SEC's fund map" % sym)
            continue
        cik, series, _cls = ent
        try:
            rows = None
            for acc, date, base in latest_nport(cik, series):
                doc = R.get(base + "/primary_doc.xml")
                rows = holdings_from(doc)
                if rows:
                    break
            if not rows:
                skipped.append((sym, "no N-PORT holdings found"))
                print("  %-6s -- no N-PORT holdings" % sym)
                continue
        except Exception as e:                              # noqa: BLE001
            skipped.append((sym, "fetch failed: %s" % e))
            print("  %-6s -- %s" % (sym, e))
            continue

        total = sum(p for _n, p, _c in rows if p > 0)
        rows.sort(key=lambda r: -r[1])
        top = [r for r in rows if r[1] > 0][:TOP_N]
        covered = sum(p for _n, p, _c in top)
        fundlike = sum(p for n, p, _c in top if FUNDLIKE.search(n))

        entries = []
        for name, pct, _cat in top:
            k = key(name)
            tk = bykey.get(k) or bytight.get(tight(name))
            entries.append((k, name, round(pct, 4), tk))

        out[sym] = {
            "src": acc, "asof": date,
            "covered": round(covered, 2),
            "total": round(total, 2),
            "fundlike": round(fundlike, 2),
            "top": entries,
        }
        matched = sum(1 for e in entries if e[3])
        flag = "  FUND-OF-FUNDS" if fundlike > covered * 0.5 else ""
        print("  %-6s %3d names, %5.1f%% of the fund, %d/%d -> ticker  %s %s"
              % (sym, len(entries), covered, matched, len(entries), date, flag))

    # ── Second level: a fund of funds holds FUNDS, not companies ──────
    #
    # Five target-date funds in the table hold 7 names covering ~100% of
    # themselves, none of which is a company — they are the other Vanguard
    # index funds. Listing those as holdings would put "Vanguard Total Stock
    # Market Index Fund" in somebody's top position at 54%, which is true and
    # useless: they want to know they own NVIDIA. A target-date fund is also
    # the single most common 401(k) holding, so leaving it un-looked-through
    # would miss the most common real portfolio there is.
    #
    # So each fund-like holding is resolved to a fund already read above and
    # replaced by ITS names, weighted. Anything that does not resolve (a money
    # market sweep, a derivative line) is left out and shows up in the gap
    # between `covered` and 100.
    byfund = {}
    for sym, v in out.items():
        byfund.setdefault(fundkey(fund_data.FUNDS[sym]["name"]), sym)

    expanded = []
    for sym, v in list(out.items()):
        if v["fundlike"] <= v["covered"] * 0.5:
            continue
        merged, resolved = {}, 0.0
        for k, name, pct, tk in v["top"]:
            target = byfund.get(fundkey(name))
            if not target or target == sym:
                continue
            inner = out[target]
            resolved += pct
            for ik, iname, ipct, itk in inner["top"]:
                w = pct / 100.0 * ipct
                cur = merged.get(ik)
                if cur:
                    merged[ik] = (ik, cur[1], round(cur[2] + w, 4), cur[3] or itk)
                else:
                    merged[ik] = (ik, iname, round(w, 4), itk)
        if not merged:
            print("  %-6s -- fund of funds, none of its holdings resolved" % sym)
            continue
        top = sorted(merged.values(), key=lambda r: -r[2])[:TOP_N]
        v["top"] = top
        v["covered"] = round(sum(r[2] for r in top), 2)
        v["expanded_from"] = round(resolved, 2)
        expanded.append((sym, resolved, v["covered"], len(top)))

    for sym, resolved, covered, n in expanded:
        print("  %-6s fund of funds: %.1f%% resolved into other funds, "
              "%d names, %.1f%% of itself" % (sym, resolved, n, covered))

    print("\n%d funds with holdings, %d skipped" % (len(out), len(skipped)))
    for sym, why in skipped:
        print("  %-6s %s" % (sym, why))

    if not write:
        print("\nReport only. Re-run with --write to write fund_holdings.py.")
        return 0

    lines = ['"""Each fund\'s largest holdings, read from its N-PORT filing.',
             "",
             "GENERATED by refresh_holdings.py. Do not hand-edit: the next run",
             "overwrites it, and a hand-typed weight has no filing behind it.",
             "",
             "`covered` is the share of the fund these names account for, and it is",
             "NOT 100 — the tail is deliberately not stored. Anything reading this",
             "has to report that, or it claims to have seen a whole portfolio it",
             "only saw two thirds of.",
             '"""',
             "",
             "AS_OF = %r" % max((v["asof"] for v in out.values()), default=""),
             "",
             "# ticker -> {src, asof, covered, total, fundlike, top: [(key, name, pct, ticker)]}",
             "HOLDINGS = {"]
    for sym in sorted(out):
        v = out[sym]
        lines.append("    %r: {" % sym)
        lines.append('        "src": %r, "asof": %r,' % (v["src"], v["asof"]))
        lines.append('        "covered": %r, "total": %r, "fundlike": %r,'
                     % (v["covered"], v["total"], v["fundlike"]))
        if v.get("expanded_from"):
            lines.append('        "expanded_from": %r,' % v["expanded_from"])
        lines.append('        "top": [')
        for k, name, pct, tk in v["top"]:
            lines.append("            (%r, %r, %r, %r)," % (k, name, pct, tk))
        lines.append("        ],")
        lines.append("    },")
    lines.append("}")
    lines.append("")
    io.open("fund_holdings.py", "w", encoding="utf-8", newline="\n").write(
        "\n".join(lines) + "\n")
    print("\nWrote fund_holdings.py (%d funds)" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
