"""Read every expense ratio in fund_data.py out of the fund's own SEC filing.

WHY THIS EXISTS. `fund_data.py` shipped with ratios compiled from memory and a
page that says so. A fee figure is the one output of the X-ray somebody might
act on, so the table needs a source. This is that source: the annual operating
expense table in a fund's prospectus is filed as structured XBRL, and this
reads the number the fund itself filed.

WHY IT IS A CHORE AND NOT A RUNTIME FETCH. The X-ray's whole design is that
the budget app has NO external data dependency — nothing outside it can take it
down or make it wrong. So this runs by hand, writes into the static table, and
the app keeps talking to nobody. It belongs beside the January refresh of
econ-2026.json and damodaran-2026.json.

THE CHAIN, and every link can fail honestly:

  ticker -> (cik, seriesId, classId)   SEC company_tickers_mf.json
         -> recent 485BPOS FOR THAT SERIES   EDGAR, queried BY SERIES ID
         -> the filing's facts, in one of two shapes
         -> oef:ExpensesOverAssets for that share class

SIX THINGS ABOUT THAT CHAIN, every one found by looking, and FOUR of them
were me asking the wrong question rather than the data being absent:

  * The element is `oef:ExpensesOverAssets`. The Open-End Fund taxonomy, not
    the older `rr:` one, and NOT `OperatingExpensesData` — which appears zero
    times in a real Vanguard filing despite being the name usually cited.
  * A CONTEXT ID IS NOT A DESCRIPTION. Vanguard, iShares and Fidelity name
    their contexts after what they describe
    (`ETFProspectusMember_S000002839_C000092055`), so "is the class id a
    substring of the contextRef" worked — for two thirds of the table.
    Schwab, Invesco and ARK use OPAQUE ids (`c125`, `c1003`) and declare the
    class INSIDE the context element as an explicit member. Eight funds
    reported "class in none of N filings", which reads as missing data and
    was really a lookup relying on somebody else's naming convention.
    `context_members` resolves the context; matching a substring of the id is
    kept only as the cheap first test.
  * EDGAR's `&series=` filter ON A CIK IS LOOSE. Asking for IVV's S000004310
    that way returns filings covering S000004320/21/22 — adjacent series in
    the same trust. Passing the SERIES ID in place of the CIK is the precise
    form. The loose version reported "class not in the instance" for every
    non-Vanguard fund, and Vanguard only worked because its newest filing
    happens to cover the funds asked for.
  * `index.json` IS TRUNCATED AT 1,000 ENTRIES. An iShares prospectus filing
    has more files than that, so its only .xml is not in the listing and the
    filing looks instance-less. The HTML filing index lists the primary
    document regardless of size, which is the fallback.
  * TWO FILING SHAPES. Vanguard and Fidelity file an extracted instance
    (`*_htm.xml`) with native `<oef:...>` elements — one carries 51 share
    classes, which is why documents are cached by accession. iShares, Schwab
    and Invesco file INLINE XBRL, where the facts are inside the prospectus
    HTML as `<ix:nonFraction name="oef:...">` and the derived `_htm.xml` path
    404s. Only the inline form carries a `scale`, and it is load-bearing —
    see `ratio_for`.

WHAT IT WILL NOT RESOLVE is now exactly three funds, and the reason is
STRUCTURAL rather than unfinished: SPY and SPLG are unit investment trusts and
GLD is a commodity trust. None files a fund prospectus of this shape and none
appears in `company_tickers_mf.json` at all, so no amount of work will source
them here. They keep their hand-written value and are reported as unsourced,
because a table that quietly claims a source it does not have is the defect
this whole exercise exists to remove — and the suite PINS them, so a future
run that appears to source one gets looked at rather than believed.

Run:  .venv/Scripts/python.exe refresh_fund_data.py           # report only
      .venv/Scripts/python.exe refresh_fund_data.py --write   # apply
"""

import gzip
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
import zlib

# SEC's fair-access policy wants a declared User-Agent with real contact
# details, and caps requests. Same string filings-terminal uses.
UA = "Mason Bennett masonjbennett.com bennettmasonj@gmail.com"
PAUSE = 0.15          # under SEC's 10/sec, with room to spare
TIMEOUT = 60

MF_TICKERS = "https://www.sec.gov/files/company_tickers_mf.json"


def get(url, binary=False):
    # gzip is asked for because these documents are large and SEC serves them
    # compressed happily — but urllib does NOT decompress for you the way
    # curl --compressed does, and decoding gzip bytes as UTF-8 yields a string
    # that fails at character 0 rather than anywhere informative.
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
            if "gzip" in enc:
                raw = gzip.decompress(raw)
            elif "deflate" in enc:
                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
            time.sleep(PAUSE)
            if binary:
                return raw
            return raw.decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def ticker_map():
    """symbol -> (cik, seriesId, classId). Only open-end funds are in here."""
    d = json.loads(get(MF_TICKERS))
    out = {}
    for row in d["data"]:
        if len(row) >= 4 and row[3]:
            out[str(row[3]).strip().upper()] = (int(row[0]), row[1], row[2])
    return out


def candidates_485(cik, series, count=10):
    """Recent 485BPOS filings FOR THIS SERIES, newest first.

    Queried with the SERIES ID in place of the CIK, which EDGAR accepts and
    which is the only precise form. Browsing the CIK with `&series=` is LOOSE:
    asking for IVV's S000004310 that way returns filings whose instances cover
    S000004320/21/22 instead, and reported "class not in the instance" for
    every non-Vanguard fund in the table — which reads as missing data and is
    really the wrong document. Vanguard only worked by luck, because its
    newest filing happens to cover the funds asked for.
    """
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           "&CIK=%s&type=485BPOS&dateb=&owner=include&count=%d&output=atom"
           % (series, count))
    xml = get(url)
    accs = re.findall(r"accession-n[^>]*>([0-9-]+)<", xml)
    dates = re.findall(r"<filing-date>([^<]+)</filing-date>", xml)
    out, seen = [], set()
    for acc, date in zip(accs, dates):
        if acc in seen:
            continue
        seen.add(acc)
        nodash = acc.replace("-", "")
        base = ("https://www.sec.gov/Archives/edgar/data/%d/%s" % (cik, nodash))
        out.append((acc, date, base))
    return out


_docs = {}


def document_for(base, accession):
    """The document carrying this filing's facts, cached by accession.

    TWO SHAPES, and the second is why the first attempt found nothing for
    three issuers:

      * Vanguard and Fidelity file an EXTRACTED instance (`*_htm.xml`) with
        native `<oef:ExpensesOverAssets>` elements.
      * iShares, Schwab and Invesco file INLINE XBRL — the facts live inside
        the prospectus HTML as `<ix:nonFraction name="oef:...">`, and there is
        no extracted instance to fetch (the derived `_htm.xml` path 404s).

    `index.json` cannot be relied on to find either: it is TRUNCATED AT 1,000
    entries, and an iShares prospectus filing has more files than that, so its
    only .xml simply is not in the listing. The filing's HTML index page lists
    the primary document regardless of size, so that is the fallback.
    """
    if accession in _docs:
        return _docs[accession]

    doc = None
    # 1. The extracted instance, when the filing has one.
    try:
        idx = json.loads(get(base + "/index.json"))
        names = [i["name"] for i in idx["directory"]["item"]]
        xmls = [n for n in names
                if n.endswith(".xml")
                and not re.search(r"_(cal|def|lab|pre|ref)\.xml$", n)
                and not n.endswith("-index.xml")]
        xmls.sort(key=lambda n: (not n.endswith("_htm.xml"), n))
        for name in xmls[:3]:
            cand = get(base + "/" + name)
            if "oef:ExpensesOverAssets" in cand:
                doc = cand
                break
    except Exception:                                # noqa: BLE001
        pass

    # 2. The inline-XBRL primary document, found via the HTML index.
    if doc is None:
        try:
            page = get("%s/%s-index.htm" % (base, accession))
            hrefs = re.findall(r'href="(/(?:ix\?doc=/)?Archives/[^"]+\.htm)"', page)
            for href in hrefs[:3]:
                href = href.replace("/ix?doc=", "")
                cand = get("https://www.sec.gov" + href)
                if "oef:ExpensesOverAssets" in cand:
                    doc = cand
                    break
        except Exception:                            # noqa: BLE001
            pass

    _docs[accession] = doc
    return doc


NATIVE = re.compile(
    r"<oef:ExpensesOverAssets\s+contextRef=\"([^\"]+)\"[^>]*>([^<]*)<", re.S)
INLINE = re.compile(
    r"<ix:nonFraction([^>]*name=\"oef:ExpensesOverAssets\"[^>]*)>([^<]*)<", re.S)
CONTEXT = re.compile(
    r"<(?:\w+:)?context\s+id=\"([^\"]+)\"(.*?)</(?:\w+:)?context>", re.S)

_ctx_cache = {}


def _attr(blob, name):
    m = re.search(r'%s=\"([^\"]*)\"' % name, blob)
    return m.group(1) if m else None


def context_members(doc):
    """contextId -> the text of every dimension member it declares.

    THIS IS THE GENERAL FORM AND THE SHORTCUT IT REPLACES WAS A NAMING
    CONVENTION. Vanguard, iShares and Fidelity name their contexts after the
    thing they describe — `ETFProspectusMember_S000002839_C000092055` — so
    "is the class id a substring of the contextRef" worked, and worked for
    two thirds of the table. Schwab, Invesco and ARK use OPAQUE ids (`c125`,
    `c1003`), and for those the class is declared INSIDE the context element
    as an explicit member. The class was in the document all along; the
    lookup was asking the wrong question, which is why eight funds reported
    "class in none of N filings" as though the data were missing.
    """
    key = id(doc)
    if key in _ctx_cache:
        return _ctx_cache[key]
    out = {}
    for cid, body in CONTEXT.findall(doc):
        out[cid] = body
    _ctx_cache[key] = out
    return out


def ratio_for(doc, class_id):
    """The filed total annual operating expense ratio for one share class.

    Returned as a PERCENT, because that is what fund_data.py stores.

    THE SCALE IS LOAD-BEARING AND ONLY THE INLINE FORM HAS IT. A native
    instance states the fraction outright (0.0003 -> 0.03%). An inline fact
    states a DISPLAY value with a `scale`: iShares files `0.50` with
    scale="-2", meaning 0.005, i.e. 0.50%. Reading the text and ignoring the
    scale would put every iShares, Schwab and Invesco fee out by a factor of
    one hundred — and 0.50 is a perfectly plausible-looking expense ratio, so
    nothing downstream would have looked wrong.
    """
    if not doc:
        return None, None

    ctxs = context_members(doc)

    def matches(ref):
        # The class either names the context, or is declared inside it.
        if class_id in ref:
            return True
        return class_id in ctxs.get(ref, "")

    for ref, val in NATIVE.findall(doc):
        if matches(ref):
            try:
                return round(float(val.strip().replace(",", "")) * 100.0, 4), ref
            except ValueError:
                return None, ref

    for attrs, val in INLINE.findall(doc):
        ref = _attr(attrs, "contextRef") or ""
        if not matches(ref):
            continue
        try:
            raw = float(val.strip().replace(",", ""))
        except ValueError:
            return None, ref
        scale = int(_attr(attrs, "scale") or 0)
        if (_attr(attrs, "sign") or "") == "-":
            raw = -raw
        return round(raw * (10.0 ** scale) * 100.0, 4), ref

    return None, None


def main():
    write = "--write" in sys.argv
    sys.path.insert(0, ".")
    import fund_data

    print("Resolving %d funds against SEC filings\n" % len(fund_data.FUNDS))
    tmap = ticker_map()

    agree, moved, unresolved = [], [], []
    sources = {}

    for sym in sorted(fund_data.FUNDS):
        have = fund_data.FUNDS[sym]["er"]
        ent = tmap.get(sym)
        if not ent:
            unresolved.append((sym, have, "not an open-end fund in SEC's map"))
            print("  %-6s %6.4f%%  -- not in company_tickers_mf.json" % (sym, have))
            continue
        cik, series, cls = ent
        got = acc = date = None
        try:
            cands = candidates_485(cik, series)
            if not cands:
                unresolved.append((sym, have, "no 485BPOS for the series"))
                print("  %-6s %6.4f%%  -- no 485BPOS found" % (sym, have))
                continue
            # Newest filing that actually carries this share class.
            for cand_acc, cand_date, base in cands:
                doc = document_for(base, cand_acc)
                val, _ctx = ratio_for(doc, cls)
                if val is not None:
                    got, acc, date = val, cand_acc, cand_date
                    break
        except Exception as e:                       # noqa: BLE001
            unresolved.append((sym, have, "fetch failed: %s" % e))
            print("  %-6s %6.4f%%  -- %s" % (sym, have, e))
            continue

        if got is None:
            unresolved.append(
                (sym, have, "class %s in none of %d recent 485BPOS" % (cls, len(cands))))
            print("  %-6s %6.4f%%  -- class not in any of %d filings"
                  % (sym, have, len(cands)))
            continue

        sources[sym] = {"er": got, "acc": acc, "date": date}
        if abs(got - have) < 1e-9:
            agree.append(sym)
            print("  %-6s %6.4f%%  OK   %s %s" % (sym, got, acc, date))
        else:
            moved.append((sym, have, got))
            print("  %-6s %6.4f%% <- was %.4f%%   %s %s" % (sym, got, have, acc, date))

    print("\n%d confirmed, %d corrected, %d unresolved"
          % (len(agree), len(moved), len(unresolved)))
    if moved:
        print("\nCorrections:")
        for sym, was, now in moved:
            print("  %-6s %.4f%% -> %.4f%%" % (sym, was, now))
    if unresolved:
        print("\nUnsourced (keeping the hand-written value, and SAYING so):")
        for sym, have, why in unresolved:
            print("  %-6s %.4f%%  %s" % (sym, have, why))

    out = "fund_sources.json"
    io.open(out, "w", encoding="utf-8", newline="\n").write(
        json.dumps(sources, indent=2, sort_keys=True) + "\n")
    print("\nWrote %s (%d sourced ratios)" % (out, len(sources)))

    if not write:
        print("\nReport only. Re-run with --write to apply the corrections.")
        return 0

    src = io.open("fund_data.py", encoding="utf-8").read()
    fixed = tagged = 0

    for sym, was, now in moved:
        # Anchored on the symbol's own entry so a value shared with another
        # fund cannot be rewritten on the wrong row.
        pat = re.compile(r'("%s":\s*\{[^}]*?"er":\s*)([0-9.]+)' % re.escape(sym))
        src, k = pat.subn(lambda m: m.group(1) + repr(now), src, count=1)
        fixed += k

    # PROVENANCE, PER ENTRY. `src` is the accession the ratio was read out of,
    # and its ABSENCE is what lets the page say which figures are the fund's
    # own filed number and which are still hand-written. A blanket claim over
    # a mixed table would be the "last verified" defect all over again.
    for sym in sorted(sources):
        acc = sources[sym]["acc"]
        entry = re.search(r'"%s":\s*\{[^}]*\}' % re.escape(sym), src)
        if not entry:
            continue
        if '"src"' in entry.group(0):
            pat = re.compile(r'("%s":\s*\{[^}]*?"src":\s*)"[^"]*"' % re.escape(sym))
            src, k = pat.subn(lambda m: m.group(1) + '"' + acc + '"', src, count=1)
        else:
            pat = re.compile(
                r'("%s":\s*\{[^}]*?"style":\s*"[^"]*")' % re.escape(sym))
            src, k = pat.subn(
                lambda m: m.group(1) + ', "src": "' + acc + '"', src, count=1)
        tagged += k

    io.open("fund_data.py", "w", encoding="utf-8", newline="\n").write(src)
    print("Applied %d of %d corrections and tagged %d of %d sources"
          % (fixed, len(moved), tagged, len(sources)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
