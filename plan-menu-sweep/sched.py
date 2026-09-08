"""Extract Schedule H line 4i (schedule of assets) from an 11-K filing.

The classification is the FILER'S OWN. An auditor groups the schedule under
headings - "Mutual funds", "Collective trust funds", "Common stock",
"Common/collective trusts" - and those are rows with a label and no value.
Using them beats classifying names myself, the same way filings-terminal
prefers a filer's own subtotal to a reconstruction.
"""
import gzip, io, json, re, sys, time, urllib.error, urllib.request, zlib
from html.parser import HTMLParser

UA = "Mason Bennett masonjbennett.com bennettmasonj@gmail.com"
PAUSE = 0.12
TIMEOUT = 90


import hashlib, os
CACHE = "cache"


def get(url, binary=False):
    os.makedirs(CACHE, exist_ok=True)
    cf = os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest())
    if os.path.exists(cf):
        raw = open(cf, "rb").read()
        return raw if binary else raw.decode("utf-8", "replace")
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
            open(cf, "wb").write(raw)
            return raw if binary else raw.decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


class Tables(HTMLParser):
    """All <table>s as lists of rows of cell strings, with the character
    offset of each table in the stripped-text stream so a table can be tied
    to the heading above it."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack = [], []
        self.text = []          # running plain text, for heading offsets
        self.cell = None

    def _t(self, s):
        self.text.append(s)

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append({"rows": [], "at": sum(len(x) for x in self.text)})
        elif tag in ("tr",) and self.stack:
            self.stack[-1]["rows"].append([])
        elif tag in ("td", "th") and self.stack:
            self.cell = []
        elif tag in ("br", "p", "div"):
            self._t(" ")

    def handle_endtag(self, tag):
        if tag == "table" and self.stack:
            self.tables.append(self.stack.pop())
        elif tag in ("td", "th") and self.stack and self.cell is not None:
            txt = "".join(self.cell).replace("​", " ").replace(" ", " ")
            txt = re.sub(r"\s+", " ", txt).strip()
            if self.stack[-1]["rows"]:
                self.stack[-1]["rows"][-1].append(txt)
            self.cell = None

    def handle_data(self, d):
        self._t(d)
        if self.cell is not None:
            self.cell.append(d)


NUM = re.compile(r"^\(?\$?\s*-?[\d,]+(?:\.\d+)?\)?$")


def as_num(s):
    s = s.strip().replace("$", "").replace(",", "").strip()
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").strip()
    if not s or not re.match(r"^-?\d+(\.\d+)?$", s):
        return None
    v = float(s)
    return -v if neg else v


def schedules(html):
    """Return [(heading_kind, rows)] for tables that look like a 4i schedule.

    rows are (label, value_or_None). A row with a label and no value is a
    grouping heading, which is the thing worth having.
    """
    p = Tables()
    try:
        p.feed(html)
    except Exception:
        pass
    plain = re.sub(r"\s+", " ", "".join(p.text))
    lower = "".join(p.text).lower()

    # offsets of every 4i heading in the raw text stream
    heads = [m.start() for m in re.finditer(
        r"schedule\s*h[^a-z]{0,12}line\s*4i|assets\s*\(held at end of year\)"
        r"|schedule of assets", lower)]
    if not heads:
        return []

    out = []
    for t in p.tables:
        # a schedule table is one that starts after some 4i heading and
        # within a reasonable distance of it
        near = [h for h in heads if 0 <= t["at"] - h < 6000]
        if not near:
            continue
        rows = []
        for r in t["rows"]:
            cells = [c for c in r if c.strip(" $*()") not in ("",)]
            if not cells:
                continue
            # The label is not reliably the first cell: a 4i schedule has (a)
            # and (b) columns, and an asterisk column, before the description.
            # Take the first cell carrying real words instead.
            # The description spans COLUMNS: a 4i schedule puts the issuer in
            # (b) and the instrument in (c), so taking the first word-bearing
            # cell reduced "Vanguard Institutional Index Fund" to "Vanguard".
            # Join them instead.
            parts = []
            for c in cells:
                w = c.strip(" *$")
                if as_num(w) is not None:
                    continue
                if len(re.sub(r"[^A-Za-z]", "", w)) >= 2:
                    parts.append(w)
            label = re.sub(r"\s+", " ", " ".join(parts)).strip()
            nums = [n for n in (as_num(c) for c in cells) if n is not None]
            if not label:
                continue
            rows.append((label, nums[-1] if nums else None))
        if len(rows) < 2:
            continue
        # A 4i heading also sits near the financial statements, so proximity
        # alone pulls in the statement of net assets and the statement of
        # changes. A schedule of assets never carries these lines.
        body = " ".join(l for l, _ in rows).lower()
        if re.search(r"net assets available for benefits|total additions|"
                     r"total deductions|benefits paid to participants|"
                     r"beginning of year|end of year", body):
            continue
        out.append(rows)
    return out
