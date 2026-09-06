"""Reference data for the portfolio X-ray: expense ratios and what a fund is.

DATA, NOT RULES. calculations.py is 2,700 lines of rules and this is a lookup
table; keeping them apart is why the table can be refreshed by someone reading
an issuer's page without touching an engine that has mutation tests behind it.

Stdlib only, like its siblings, and copied into web/api/ by
scripts/sync-calculations.mjs at predev and prebuild. Edit THIS copy.

WHAT IS HERE AND WHAT IS NOT. Roughly the funds an ordinary person actually
holds — the big three issuers' index funds, the common target-date series, and
the handful of popular active and thematic funds. Not a universe. A symbol that
is not here is UNKNOWN, which is a reported answer with its own coverage
percentage, never a zero. A zero expense ratio for a fund nobody checked is the
same defect as "Preferred dividends 0.00" on a company that files none: it
reads as measured.

NOT ONE RATIO BELOW HAS BEEN VERIFIED. They were compiled from memory, they
are plausible, and they are the one output of this tool that somebody might
act on. `AS_OF` is therefore the date the table was COMPILED, not the date it
was checked — and the page says exactly that, because "last verified" over
numbers nobody verified is a worse defect than a wrong ratio: it is a false
claim about how much the figure can be trusted.

TO VERIFY: the issuer's own fund page is the source and a fund's prospectus is
the citable one. They are net ratios in PERCENT (0.03 means three basis
points). When it is done, change `AS_OF` to `VERIFIED_ON` and update the two
sentences on the page that currently disclaim it — grep for "not yet checked".

ANNUAL CHORE, alongside the January refresh of econ-2026.json,
damodaran-2026.json and NYSE_HOLIDAYS_2026: re-read every ratio below, bump
the date, and check nothing has been closed or merged.

WHY THERE IS NO HOLDINGS COUNT. An earlier draft carried an approximate count
of underlying positions per fund, to support "this gives you 3,600 holdings and
this gives you one". Nothing in slice 1 reads it, and fifty numbers nobody
verified sitting in a table that looks verified is how a fabricated figure ends
up quoted. Add it when something needs it, with a source.
"""

# The date this table was COMPILED. Not the date it was checked — see above.
AS_OF = "2026-09-06"

# cls: equity | bond | cash | real_estate | commodity | multi_asset
# region: us | intl | global | None when the concept does not apply or is not
#         established — None is not "us", and the X-ray reports region coverage
#         separately for exactly that reason.
FUNDS = {
    # ── Vanguard ETFs ────────────────────────────────────────────────
    "VTI":   {"name": "Vanguard Total Stock Market ETF",   "er": 0.03, "cls": "equity", "region": "us",     "style": "total_market"},
    "VOO":   {"name": "Vanguard S&P 500 ETF",              "er": 0.03, "cls": "equity", "region": "us",     "style": "large_cap"},
    "VXUS":  {"name": "Vanguard Total International Stock ETF", "er": 0.05, "cls": "equity", "region": "intl", "style": "total_market"},
    "VT":    {"name": "Vanguard Total World Stock ETF",    "er": 0.06, "cls": "equity", "region": "global", "style": "total_market"},
    "VEA":   {"name": "Vanguard FTSE Developed Markets ETF", "er": 0.05, "cls": "equity", "region": "intl", "style": "developed"},
    "VWO":   {"name": "Vanguard FTSE Emerging Markets ETF", "er": 0.07, "cls": "equity", "region": "intl",  "style": "emerging"},
    "VTV":   {"name": "Vanguard Value ETF",                "er": 0.04, "cls": "equity", "region": "us",     "style": "large_value"},
    "VUG":   {"name": "Vanguard Growth ETF",               "er": 0.04, "cls": "equity", "region": "us",     "style": "large_growth"},
    "VYM":   {"name": "Vanguard High Dividend Yield ETF",  "er": 0.06, "cls": "equity", "region": "us",     "style": "dividend"},
    "VIG":   {"name": "Vanguard Dividend Appreciation ETF", "er": 0.05, "cls": "equity", "region": "us",    "style": "dividend"},
    "VB":    {"name": "Vanguard Small-Cap ETF",            "er": 0.05, "cls": "equity", "region": "us",     "style": "small_cap"},
    "VO":    {"name": "Vanguard Mid-Cap ETF",              "er": 0.04, "cls": "equity", "region": "us",     "style": "mid_cap"},
    "VNQ":   {"name": "Vanguard Real Estate ETF",          "er": 0.13, "cls": "real_estate", "region": "us", "style": "reit"},
    "BND":   {"name": "Vanguard Total Bond Market ETF",    "er": 0.03, "cls": "bond",   "region": "us",     "style": "aggregate_bond"},
    "BNDX":  {"name": "Vanguard Total International Bond ETF", "er": 0.07, "cls": "bond", "region": "intl", "style": "intl_bond"},

    # ── Vanguard mutual funds ────────────────────────────────────────
    "VTSAX": {"name": "Vanguard Total Stock Market Index Admiral", "er": 0.04, "cls": "equity", "region": "us",   "style": "total_market"},
    "VFIAX": {"name": "Vanguard 500 Index Admiral",        "er": 0.04, "cls": "equity", "region": "us",     "style": "large_cap"},
    "VTIAX": {"name": "Vanguard Total International Stock Index Admiral", "er": 0.09, "cls": "equity", "region": "intl", "style": "total_market"},
    "VBTLX": {"name": "Vanguard Total Bond Market Index Admiral", "er": 0.05, "cls": "bond", "region": "us",  "style": "aggregate_bond"},
    "VTWAX": {"name": "Vanguard Total World Stock Index Admiral", "er": 0.10, "cls": "equity", "region": "global", "style": "total_market"},

    # ── Vanguard Target Retirement ───────────────────────────────────
    # One ratio across the series; the glide path differs, the fee does not.
    # multi_asset, not equity: a target-date fund holds bonds and the mix is
    # the whole point of it, so calling it equity would misstate the class
    # mix of the single most common 401(k) default holding.
    "VTTSX": {"name": "Vanguard Target Retirement 2060",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date"},
    "VFFVX": {"name": "Vanguard Target Retirement 2055",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date"},
    "VFIFX": {"name": "Vanguard Target Retirement 2050",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date"},
    "VFORX": {"name": "Vanguard Target Retirement 2040",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date"},
    "VTHRX": {"name": "Vanguard Target Retirement 2030",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date"},

    # ── iShares ──────────────────────────────────────────────────────
    "IVV":   {"name": "iShares Core S&P 500 ETF",          "er": 0.03, "cls": "equity", "region": "us",     "style": "large_cap"},
    "ITOT":  {"name": "iShares Core S&P Total US Stock Market ETF", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market"},
    "IJH":   {"name": "iShares Core S&P Mid-Cap ETF",      "er": 0.05, "cls": "equity", "region": "us",     "style": "mid_cap"},
    "IJR":   {"name": "iShares Core S&P Small-Cap ETF",    "er": 0.06, "cls": "equity", "region": "us",     "style": "small_cap"},
    "IEFA":  {"name": "iShares Core MSCI EAFE ETF",        "er": 0.07, "cls": "equity", "region": "intl",   "style": "developed"},
    "IEMG":  {"name": "iShares Core MSCI Emerging Markets ETF", "er": 0.09, "cls": "equity", "region": "intl", "style": "emerging"},
    "AGG":   {"name": "iShares Core US Aggregate Bond ETF", "er": 0.03, "cls": "bond",  "region": "us",     "style": "aggregate_bond"},

    # ── State Street / SPDR ──────────────────────────────────────────
    # SPY is here because people hold it, and its ratio is an order of
    # magnitude above SPLG's for the same index — which is the single
    # clearest thing this tool can show someone.
    "SPY":   {"name": "SPDR S&P 500 ETF Trust",            "er": 0.0945, "cls": "equity", "region": "us",   "style": "large_cap"},
    "SPLG":  {"name": "SPDR Portfolio S&P 500 ETF",        "er": 0.02, "cls": "equity", "region": "us",     "style": "large_cap"},
    "SPTM":  {"name": "SPDR Portfolio S&P 1500 Composite Stock Market ETF", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market"},

    # ── Invesco ──────────────────────────────────────────────────────
    "QQQ":   {"name": "Invesco QQQ Trust",                 "er": 0.20, "cls": "equity", "region": "us",     "style": "nasdaq100"},
    "QQQM":  {"name": "Invesco NASDAQ 100 ETF",            "er": 0.15, "cls": "equity", "region": "us",     "style": "nasdaq100"},
    "RSP":   {"name": "Invesco S&P 500 Equal Weight ETF",  "er": 0.20, "cls": "equity", "region": "us",     "style": "large_cap"},

    # ── Schwab ───────────────────────────────────────────────────────
    "SWPPX": {"name": "Schwab S&P 500 Index Fund",         "er": 0.02, "cls": "equity", "region": "us",     "style": "large_cap"},
    "SWTSX": {"name": "Schwab Total Stock Market Index Fund", "er": 0.03, "cls": "equity", "region": "us",  "style": "total_market"},
    "SCHB":  {"name": "Schwab US Broad Market ETF",        "er": 0.03, "cls": "equity", "region": "us",     "style": "total_market"},
    "SCHD":  {"name": "Schwab US Dividend Equity ETF",     "er": 0.06, "cls": "equity", "region": "us",     "style": "dividend"},
    "SCHF":  {"name": "Schwab International Equity ETF",   "er": 0.06, "cls": "equity", "region": "intl",   "style": "developed"},
    "SCHG":  {"name": "Schwab US Large-Cap Growth ETF",    "er": 0.04, "cls": "equity", "region": "us",     "style": "large_growth"},

    # ── Fidelity ─────────────────────────────────────────────────────
    # The ZERO funds really are 0.00, and that is the one place in this table
    # where a zero is a measurement. They are also index funds available only
    # in a Fidelity account, which is why they are worth carrying.
    "FXAIX": {"name": "Fidelity 500 Index Fund",           "er": 0.015, "cls": "equity", "region": "us",    "style": "large_cap"},
    "FSKAX": {"name": "Fidelity Total Market Index Fund",  "er": 0.015, "cls": "equity", "region": "us",    "style": "total_market"},
    "FTIHX": {"name": "Fidelity Total International Index Fund", "er": 0.06, "cls": "equity", "region": "intl", "style": "total_market"},
    "FXNAX": {"name": "Fidelity US Bond Index Fund",       "er": 0.025, "cls": "bond",  "region": "us",     "style": "aggregate_bond"},
    "FZROX": {"name": "Fidelity ZERO Total Market Index Fund", "er": 0.00, "cls": "equity", "region": "us", "style": "total_market"},
    "FNILX": {"name": "Fidelity ZERO Large Cap Index Fund", "er": 0.00, "cls": "equity", "region": "us",    "style": "large_cap"},
    "FZILX": {"name": "Fidelity ZERO International Index Fund", "er": 0.00, "cls": "equity", "region": "intl", "style": "total_market"},

    # ── Popular active and thematic ──────────────────────────────────
    # Carried because someone holding one should see what it costs beside the
    # index fund next to it, which is a fact, not a verdict on the strategy.
    "ARKK":  {"name": "ARK Innovation ETF",                "er": 0.75, "cls": "equity", "region": "us",     "style": "thematic"},
    "JEPI":  {"name": "JPMorgan Equity Premium Income ETF", "er": 0.35, "cls": "equity", "region": "us",    "style": "income"},
    "GLD":   {"name": "SPDR Gold Shares",                  "er": 0.40, "cls": "commodity", "region": None,  "style": "gold"},
}

# The classes the X-ray reports a mix over. Order is display order — equities
# first because that is where the risk is, cash last because it is the
# residual someone is usually surprised by.
CLASS_ORDER = ["equity", "multi_asset", "real_estate", "commodity", "bond", "cash"]

CLASS_LABEL = {
    "equity": "Stocks",
    "multi_asset": "Target-date / mixed",
    "real_estate": "Real estate",
    "commodity": "Commodities",
    "bond": "Bonds",
    "cash": "Cash",
}

REGION_LABEL = {"us": "United States", "intl": "International", "global": "Global"}


def lookup(symbol):
    """The table's entry for a symbol, or None. Case- and space-insensitive.

    Someone typing holdings in by hand writes "vti" and pastes " VOO " out of a
    statement, and a table miss is indistinguishable on the page from a fund
    nobody has added — it lands in the uncovered bucket either way. So the
    normalising happens here, once, rather than at each call site.
    """
    if not symbol:
        return None
    return FUNDS.get(str(symbol).strip().upper())
