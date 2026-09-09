"""A three-fund table that exercises every reporting path in the chore.

Not a fixture for the app — a driver for `refresh_fund_data.py`, which twice
died in a PRINT after fetching a hundred prospectuses because `er` may be
None and six then seven format sites assumed otherwise. Grepping for the
sites is what missed one both times; this runs them.

  FUBFX  er None, and its class is in none of its series' filings  -> the
         UNRESOLVED path, which is where the second crash was
  VSIBX  er None, same                                             -> ditto
  VTIP   er None but DOES resolve  -> the "was nothing, now sourced" path,
         which is the `abs(got - have)` comparison and the corrections table
  VTI    an ordinary sourced fund  -> the OK path, so a pass is not vacuous
"""

AS_OF = "2026-09-08"

FUNDS = {
    "FUBFX": {"name": "Fidelity U.S. Bond Index Class F", "er": None,
              "cls": "bond", "region": "us", "style": "aggregate_bond"},
    "VSIBX": {"name": "Vanguard Total International Bond Index Institutional Select",
              "er": None, "cls": "bond", "region": "intl", "style": "intl_bond"},
    "VTIP": {"name": "Vanguard Short-Term Inflation-Protected Securities ETF",
             "er": None, "cls": "bond", "region": "us", "style": "tips"},
    "VTI": {"name": "Vanguard Total Stock Market ETF", "er": 0.03,
            "cls": "equity", "region": "us", "style": "total_market"},
}

CLASS_ORDER = ["equity", "bond"]
CLASS_LABEL = {"equity": "Equity", "bond": "Bonds"}
REGION_LABEL = {"us": "US", "intl": "International"}


def lookup(sym):
    return FUNDS.get(str(sym or "").strip().upper())
