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

MOST OF THESE RATIOS NOW COME FROM THE FUND'S OWN SEC FILING, and the ones
that do carry a `src` — the accession the number was read out of. Run
`refresh_fund_data.py` to re-read them; it walks ticker -> series -> the
latest 485BPOS -> `oef:ExpensesOverAssets` for that share class.

THE ABSENCE OF `src` IS A REPORTED ANSWER, not an oversight. An entry without
one is still hand-written and the page SAYS so, naming it, because a blanket
claim over a mixed table is exactly the "last verified" defect this file
carried for one afternoon. Exactly three cannot be sourced this way and never
will be: SPY and SPLG are unit investment trusts and GLD is a commodity
trust — none of them files a fund prospectus of this shape, and none appears
in SEC's `company_tickers_mf.json` at all. **114 of 119 resolve.** The Schwab,
Invesco and ARK entries that once looked unfinished were the context-id defect
in `refresh_fund_data.py`, not missing data.

THE TABLE ITSELF HAS THE SAME THREE STATES the page reports. Most entries are
SOURCED. SPY, SPLG and GLD keep a HAND-WRITTEN ratio and are named as such.
FUBFX and VSIBX carry **no ratio at all** — `er` is None — because those two
share classes appear in none of their series' recent 485BPOS filings, so the
number is genuinely unknown. They are deliberately NOT given their sibling's:
the chore corrected 35 of the 41 classes added beside them, and the Vanguard
500 index runs 0.01% to 0.14% across four tickers. A fund with no ratio is
still carried for class and region, and the engine reports it uncovered for
fees rather than free.

A SERIES IS CARRIED WHOLE OR NOT AT ALL. Vanguard Target Retirement was here
with five of its twelve funds, so a saver born in 1990 was covered and one
born in 1988 was not, for no reason anybody chose — and a half-present series
is worse than an absent one, because it reads as coverage. The seven added in
September were also, independently, the seven most common funds MISSING from
this table across real 401(k) menus. See `fund_kinds.py` for that measurement,
and for the much larger thing it found: most of a real workplace menu is
collective trusts, which are not registered funds and can never be in here at
all. Widening this table is not the answer to that and never will be.

The first run corrected TEN of the ratios compiled from memory — VYM 0.06 ->
0.04, VEA and VB 0.05 -> 0.03, VWO 0.07 -> 0.06 and six more, every one of
them a Vanguard fee cut this table had not kept up with. Which is the whole
argument for the chore: they were all plausible and all wrong.

AS_OF is when the table was last COMPILED. Ratios are net, in PERCENT (0.03
means three basis points).

ANNUAL CHORE, alongside the January refresh of econ-2026.json,
damodaran-2026.json and NYSE_HOLIDAYS_2026: run `refresh_fund_data.py
--write`, read what it corrected, bump AS_OF, and check nothing has been
closed or merged.

WHY THERE IS NO HOLDINGS COUNT. An earlier draft carried an approximate count
of underlying positions per fund, to support "this gives you 3,600 holdings and
this gives you one". Nothing in slice 1 reads it, and fifty numbers nobody
verified sitting in a table that looks verified is how a fabricated figure ends
up quoted. Add it when something needs it, with a source.
"""

# The date this table was COMPILED. Not the date it was checked — see above.
AS_OF = "2026-09-08"

# cls: equity | bond | cash | real_estate | commodity | multi_asset
# region: us | intl | global | None when the concept does not apply or is not
#         established — None is not "us", and the X-ray reports region coverage
#         separately for exactly that reason.
FUNDS = {
    # ── Vanguard ETFs ────────────────────────────────────────────────
    "VTI":   {"name": "Vanguard Total Stock Market ETF",   "er": 0.03, "cls": "equity", "region": "us",     "style": "total_market", "src": "0000036405-26-000181"},
    "VOO":   {"name": "Vanguard S&P 500 ETF",              "er": 0.03, "cls": "equity", "region": "us",     "style": "large_cap", "src": "0000036405-26-000181"},
    "VXUS":  {"name": "Vanguard Total International Stock ETF", "er": 0.05, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VT":    {"name": "Vanguard Total World Stock ETF",    "er": 0.06, "cls": "equity", "region": "global", "style": "total_market", "src": "0001193125-26-077485"},
    "VEA":   {"name": "Vanguard FTSE Developed Markets ETF", "er": 0.03, "cls": "equity", "region": "intl", "style": "developed", "src": "0000923202-26-000059"},
    "VWO":   {"name": "Vanguard FTSE Emerging Markets ETF", "er": 0.06, "cls": "equity", "region": "intl",  "style": "emerging", "src": "0001193125-26-077485"},
    "VTV":   {"name": "Vanguard Value ETF",                "er": 0.03, "cls": "equity", "region": "us",     "style": "large_value", "src": "0000036405-26-000181"},
    "VUG":   {"name": "Vanguard Growth ETF",               "er": 0.03, "cls": "equity", "region": "us",     "style": "large_growth", "src": "0000036405-26-000181"},
    "VYM":   {"name": "Vanguard High Dividend Yield ETF",  "er": 0.04, "cls": "equity", "region": "us",     "style": "dividend", "src": "0001193125-26-077482"},
    "VIG":   {"name": "Vanguard Dividend Appreciation ETF", "er": 0.04, "cls": "equity", "region": "us",    "style": "dividend", "src": "0000734383-26-000129"},
    "VB":    {"name": "Vanguard Small-Cap ETF",            "er": 0.03, "cls": "equity", "region": "us",     "style": "small_cap", "src": "0000036405-26-000181"},
    "VO":    {"name": "Vanguard Mid-Cap ETF",              "er": 0.03, "cls": "equity", "region": "us",     "style": "mid_cap", "src": "0000036405-26-000181"},
    "VNQ":   {"name": "Vanguard Real Estate ETF",          "er": 0.13, "cls": "real_estate", "region": "us", "style": "reit", "src": "0000734383-26-000129"},
    "BND":   {"name": "Vanguard Total Bond Market ETF",    "er": 0.03, "cls": "bond",   "region": "us",     "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "BNDX":  {"name": "Vanguard Total International Bond ETF", "er": 0.07, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},

    # ── Vanguard mutual funds ────────────────────────────────────────
    "VTSAX": {"name": "Vanguard Total Stock Market Index Admiral", "er": 0.04, "cls": "equity", "region": "us",   "style": "total_market", "src": "0000036405-26-000181"},
    "VFIAX": {"name": "Vanguard 500 Index Admiral",        "er": 0.04, "cls": "equity", "region": "us",     "style": "large_cap", "src": "0000036405-26-000181"},
    "VTIAX": {"name": "Vanguard Total International Stock Index Admiral", "er": 0.09, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VBTLX": {"name": "Vanguard Total Bond Market Index Admiral", "er": 0.04, "cls": "bond", "region": "us",  "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VTWAX": {"name": "Vanguard Total World Stock Index Admiral", "er": 0.09, "cls": "equity", "region": "global", "style": "total_market", "src": "0001193125-26-077485"},

    # ── Vanguard Target Retirement ───────────────────────────────────
    # One ratio across the series; the glide path differs, the fee does not.
    # multi_asset, not equity: a target-date fund holds bonds and the mix is
    # the whole point of it, so calling it equity would misstate the class
    # mix of the single most common 401(k) default holding.
    "VTTSX": {"name": "Vanguard Target Retirement 2060",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VFFVX": {"name": "Vanguard Target Retirement 2055",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VFIFX": {"name": "Vanguard Target Retirement 2050",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VFORX": {"name": "Vanguard Target Retirement 2040",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VTHRX": {"name": "Vanguard Target Retirement 2030",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    # THE SERIES IS CARRIED WHOLE, and it was not: five of its twelve funds
    # were here, so a saver born in 1990 was covered and one born in 1988 was
    # not, for no reason anybody chose. A half-present series is worse than an
    # absent one because it reads as coverage.
    #
    # These seven are also the SEVEN MOST COMMON funds missing from this table
    # across real 401(k) menus — 2035 and 2045 in 5 of 29 plans each, ahead of
    # every other gap — measured off the Form 11-K sample described in
    # fund_kinds.py rather than picked by hand.
    "VTTHX": {"name": "Vanguard Target Retirement 2035",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VTIVX": {"name": "Vanguard Target Retirement 2045",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VTTVX": {"name": "Vanguard Target Retirement 2025",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VTWNX": {"name": "Vanguard Target Retirement 2020",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VLXVX": {"name": "Vanguard Target Retirement 2065",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VSVNX": {"name": "Vanguard Target Retirement 2070",   "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},
    "VTINX": {"name": "Vanguard Target Retirement Income", "er": 0.08, "cls": "multi_asset", "region": "global", "style": "target_date", "src": "0001193125-26-024962"},


    # ── Plan share classes of funds already above ────────────────────
    #
    # A 401(k) holds VIIIX or VSMAX where a brokerage holds VOO or VB: the
    # same fund, a different share class, its own ticker and its OWN FEE.
    # The table already claimed to carry these funds and simply did not
    # recognise the ticker in front of the reader - "a series is carried
    # whole" one level down.
    #
    # NOT picked by hand and not the top of a long tail. Beyond the
    # target-date series the funds this table has never heard of are spread
    # thin - nothing above 2 of 29 real plans, against 28,500 tickered share
    # classes in existence - so "the top ten" would be arbitrary. This set is
    # bounded by what is ALREADY here: 11 series where a sampled plan held a
    # class the table lacked, touching 7 of 26 plans. See plan-menu-sweep/.
    #
    # Every fee below was read from that CLASS's own filing. A class fee is
    # not its sibling's - VFFSX is 0.01% against VFIAX's 0.04% - so any entry
    # the chore could not source was deleted rather than left carrying a
    # copied number.
    "VFFSX": {"name": "Vanguard 500 Index Institutional Select", "er": 0.01, "cls": "equity", "region": "us", "style": "large_cap", "src": "0000036405-26-000181"},
    "VFINX": {"name": "Vanguard 500 Index Investor", "er": 0.14, "cls": "equity", "region": "us", "style": "large_cap", "src": "0000036405-26-000181"},
    "NAESX": {"name": "Vanguard Small-Cap Index Investor", "er": 0.17, "cls": "equity", "region": "us", "style": "small_cap", "src": "0000036405-26-000181"},
    "VSCIX": {"name": "Vanguard Small-Cap Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "small_cap", "src": "0000036405-26-000181"},
    "VSCPX": {"name": "Vanguard Small-Cap Index Institutional Plus", "er": 0.02, "cls": "equity", "region": "us", "style": "small_cap", "src": "0000036405-26-000181"},
    "VSMAX": {"name": "Vanguard Small-Cap Index Admiral", "er": 0.05, "cls": "equity", "region": "us", "style": "small_cap", "src": "0000036405-26-000181"},
    "VIMAX": {"name": "Vanguard Mid-Cap Index Admiral", "er": 0.05, "cls": "equity", "region": "us", "style": "mid_cap", "src": "0000036405-26-000181"},
    "VIMSX": {"name": "Vanguard Mid-Cap Index Investor", "er": 0.17, "cls": "equity", "region": "us", "style": "mid_cap", "src": "0000036405-26-000181"},
    "VMCIX": {"name": "Vanguard Mid-Cap Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "mid_cap", "src": "0000036405-26-000181"},
    "VMCPX": {"name": "Vanguard Mid-Cap Index Institutional Plus", "er": 0.02, "cls": "equity", "region": "us", "style": "mid_cap", "src": "0000036405-26-000181"},
    "VEIEX": {"name": "Vanguard Emerging Markets Stock Index Investor", "er": 0.29, "cls": "equity", "region": "intl", "style": "emerging", "src": "0001193125-26-077485"},
    "VEMAX": {"name": "Vanguard Emerging Markets Stock Index Admiral", "er": 0.13, "cls": "equity", "region": "intl", "style": "emerging", "src": "0001193125-26-077485"},
    "VEMIX": {"name": "Vanguard Emerging Markets Stock Index Institutional", "er": 0.06, "cls": "equity", "region": "intl", "style": "emerging", "src": "0001193125-26-077485"},
    "VEMRX": {"name": "Vanguard Emerging Markets Stock Index Institutional Plus", "er": 0.05, "cls": "equity", "region": "intl", "style": "emerging", "src": "0001193125-26-077485"},
    "VHYAX": {"name": "Vanguard High Dividend Yield Index Admiral", "er": 0.08, "cls": "equity", "region": "us", "style": "dividend", "src": "0001193125-26-077482"},
    "VGSIX": {"name": "Vanguard Real Estate Index Investor", "er": 0.27, "cls": "real_estate", "region": "us", "style": "reit", "src": "0000734383-26-000129"},
    "VGSLX": {"name": "Vanguard Real Estate Index Admiral", "er": 0.13, "cls": "real_estate", "region": "us", "style": "reit", "src": "0000734383-26-000129"},
    "VGSNX": {"name": "Vanguard Real Estate Index Institutional", "er": 0.11, "cls": "real_estate", "region": "us", "style": "reit", "src": "0000734383-26-000129"},
    "VRTPX": {"name": "Vanguard Real Estate II Index Institutional Plus", "er": 0.08, "cls": "real_estate", "region": "us", "style": "reit", "src": "0000106444-26-000213"},
    "VGTSX": {"name": "Vanguard Total International Stock Index Investor", "er": 0.17, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VTISX": {"name": "Vanguard Total International Stock Index Institutional Select", "er": 0.046, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VTPSX": {"name": "Vanguard Total International Stock Index Institutional Plus", "er": 0.05, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VTSNX": {"name": "Vanguard Total International Stock Index Institutional", "er": 0.06, "cls": "equity", "region": "intl", "style": "total_market", "src": "0001193125-26-077488"},
    "VBMFX": {"name": "Vanguard Total Bond Market Index Investor", "er": 0.15, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VBMPX": {"name": "Vanguard Total Bond Market Index Institutional Plus", "er": 0.02, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VBTIX": {"name": "Vanguard Total Bond Market Index Institutional", "er": 0.025, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VTBIX": {"name": "Vanguard Total Bond Market II Index Investor", "er": 0.09, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VTBNX": {"name": "Vanguard Total Bond Market II Index Institutional", "er": 0.02, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VTBSX": {"name": "Vanguard Total Bond Market Index Institutional Select", "er": 0.01, "cls": "bond", "region": "us", "style": "aggregate_bond", "src": "0000794105-26-000106"},
    "VITNX": {"name": "Vanguard Institutional Total Stock Market Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market", "src": "0000862084-26-000057"},
    "VITPX": {"name": "Vanguard Institutional Total Stock Market Index Institutional Plus", "er": 0.02, "cls": "equity", "region": "us", "style": "total_market", "src": "0000862084-26-000057"},
    "VITSX": {"name": "Vanguard Total Stock Market Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market", "src": "0000036405-26-000181"},
    "VSMPX": {"name": "Vanguard Total Stock Market Index Institutional Plus", "er": 0.02, "cls": "equity", "region": "us", "style": "total_market", "src": "0000036405-26-000181"},
    "VSTSX": {"name": "Vanguard Total Stock Market Index Institutional Select", "er": 0.01, "cls": "equity", "region": "us", "style": "total_market", "src": "0000036405-26-000181"},
    "VTSMX": {"name": "Vanguard Total Stock Market Index Investor", "er": 0.06, "cls": "equity", "region": "us", "style": "total_market", "src": "0000036405-26-000181"},
    "VIGAX": {"name": "Vanguard Growth Index Admiral", "er": 0.05, "cls": "equity", "region": "us", "style": "large_growth", "src": "0000036405-26-000181"},
    "VIGIX": {"name": "Vanguard Growth Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "large_growth", "src": "0000036405-26-000181"},
    "VIGRX": {"name": "Vanguard Growth Index Investor", "er": 0.17, "cls": "equity", "region": "us", "style": "large_growth", "src": "0000036405-26-000181"},
    "VIVAX": {"name": "Vanguard Value Index Investor", "er": 0.17, "cls": "equity", "region": "us", "style": "large_value", "src": "0000036405-26-000181"},
    "VIVIX": {"name": "Vanguard Value Index Institutional", "er": 0.03, "cls": "equity", "region": "us", "style": "large_value", "src": "0000036405-26-000181"},
    "VVIAX": {"name": "Vanguard Value Index Admiral", "er": 0.05, "cls": "equity", "region": "us", "style": "large_value", "src": "0000036405-26-000181"},


    # ── The rest of each series above, so none is carried in part ────
    #
    # Not held by any sampled plan; these close the rule this file states
    # about itself. `verify_classes.py` in plan-menu-sweep/ found five series
    # carried in PART after the pass above, which is the state the docstring
    # calls worse than absent because it reads as coverage.
    #
    # Enumerated by SEC SERIES ID. A normalised name is NOT a safe key here:
    # it strips INDEX, II and INSTITUTIONAL, so it collapses "Total Bond
    # Market Index" with "Total Bond Market II Index" and "Fidelity Freedom
    # 2040" with "Fidelity Freedom Index 2040" - different funds, and the
    # Fidelity pair differ about sixfold in fee.
    "VDIPX": {"name": "Vanguard Developed Markets Index Institutional Plus", "er": 0.02, "cls": "equity", "region": "intl", "style": "developed", "src": "0000923202-26-000059"},
    "VDVIX": {"name": "Vanguard Developed Markets Index Investor", "er": 0.16, "cls": "equity", "region": "intl", "style": "developed", "src": "0000923202-26-000059"},
    "VTMGX": {"name": "Vanguard Developed Markets Index Admiral", "er": 0.05, "cls": "equity", "region": "intl", "style": "developed", "src": "0000923202-26-000059"},
    "VTMNX": {"name": "Vanguard Developed Markets Index Institutional", "er": 0.03, "cls": "equity", "region": "intl", "style": "developed", "src": "0000923202-26-000059"},
    "VDADX": {"name": "Vanguard Dividend Appreciation Index Admiral", "er": 0.07, "cls": "equity", "region": "us", "style": "dividend", "src": "0000734383-26-000129"},
    "FUBFX": {"name": "Fidelity U.S. Bond Index Class F", "er": None, "cls": "bond", "region": "us", "style": "aggregate_bond"},
    "VTWIX": {"name": "Vanguard Total World Stock Index Institutional", "er": 0.07, "cls": "equity", "region": "global", "style": "total_market", "src": "0001193125-26-077485"},
    "VSIBX": {"name": "Vanguard Total International Bond Index Institutional Select", "er": None, "cls": "bond", "region": "intl", "style": "intl_bond"},
    "VTABX": {"name": "Vanguard Total International Bond Index Admiral", "er": 0.1, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},
    "VTIBX": {"name": "Vanguard Total International Bond Index Investor", "er": 0.13, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},
    "VTIFX": {"name": "Vanguard Total International Bond Index Institutional", "er": 0.03, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},


    # -- The two sleeves a target-date fund holds and this table did not ----
    #
    # NOT guessed. Removing the "II" collapse made the fund-of-funds
    # substitution precise and dropped VTINX's expansion from 83.1% to 67.7%;
    # reading the sleeves straight out of its N-PORT named the cost exactly:
    # Short-Term Inflation-Protected 16.12% and Total International Bond II
    # 15.42%, plus 0.64% of Vanguard's internal Market Liquidity sweep, which
    # is not investable and is already a WRAPPER word. Both are carried WHOLE,
    # every class. The look-through demonstrated the need; nothing here was
    # picked because it sounded common.
    #
    # Ratios below are placeholders and carry no `src` until the chore runs.
    "VTIIX": {"name": "Vanguard Total International Bond II Index Investor", "er": 0.11, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},
    "VTILX": {"name": "Vanguard Total International Bond II Index Institutional", "er": 0.07, "cls": "bond", "region": "intl", "style": "intl_bond", "src": "0001193125-26-077489"},
    "VTAPX": {"name": "Vanguard Short-Term Inflation-Protected Securities Index Admiral", "er": 0.06, "cls": "bond", "region": "us", "style": "tips", "src": "0001193125-26-024963"},
    "VTIP":  {"name": "Vanguard Short-Term Inflation-Protected Securities ETF", "er": 0.03, "cls": "bond", "region": "us", "style": "tips", "src": "0001193125-26-024963"},
    "VTIPX": {"name": "Vanguard Short-Term Inflation-Protected Securities Index Investor", "er": 0.14, "cls": "bond", "region": "us", "style": "tips", "src": "0001193125-26-024963"},
    "VTSPX": {"name": "Vanguard Short-Term Inflation-Protected Securities Index Institutional", "er": 0.03, "cls": "bond", "region": "us", "style": "tips", "src": "0001193125-26-024963"},

    # ── iShares ──────────────────────────────────────────────────────
    "IVV":   {"name": "iShares Core S&P 500 ETF",          "er": 0.03, "cls": "equity", "region": "us",     "style": "large_cap", "src": "0001193125-26-318131"},
    "ITOT":  {"name": "iShares Core S&P Total US Stock Market ETF", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market", "src": "0001193125-26-318131"},
    "IJH":   {"name": "iShares Core S&P Mid-Cap ETF",      "er": 0.05, "cls": "equity", "region": "us",     "style": "mid_cap", "src": "0001193125-26-318131"},
    "IJR":   {"name": "iShares Core S&P Small-Cap ETF",    "er": 0.06, "cls": "equity", "region": "us",     "style": "small_cap", "src": "0001193125-26-318131"},
    "IEFA":  {"name": "iShares Core MSCI EAFE ETF",        "er": 0.07, "cls": "equity", "region": "intl",   "style": "developed", "src": "0001193125-25-291438"},
    "IEMG":  {"name": "iShares Core MSCI Emerging Markets ETF", "er": 0.09, "cls": "equity", "region": "intl", "style": "emerging", "src": "0001193125-25-327007"},
    "AGG":   {"name": "iShares Core US Aggregate Bond ETF", "er": 0.03, "cls": "bond",  "region": "us",     "style": "aggregate_bond", "src": "0001193125-26-275730"},

    # ── State Street / SPDR ──────────────────────────────────────────
    # SPY is here because people hold it, and its ratio is an order of
    # magnitude above SPLG's for the same index — which is the single
    # clearest thing this tool can show someone.
    "SPY":   {"name": "SPDR S&P 500 ETF Trust",            "er": 0.0945, "cls": "equity", "region": "us",   "style": "large_cap"},
    "SPLG":  {"name": "SPDR Portfolio S&P 500 ETF",        "er": 0.02, "cls": "equity", "region": "us",     "style": "large_cap"},
    "SPTM":  {"name": "SPDR Portfolio S&P 1500 Composite Stock Market ETF", "er": 0.03, "cls": "equity", "region": "us", "style": "total_market", "src": "0001193125-25-250041"},

    # ── Invesco ──────────────────────────────────────────────────────
    "QQQ":   {"name": "Invesco QQQ Trust",                 "er": 0.18, "cls": "equity", "region": "us",     "style": "nasdaq100", "src": "0001104659-25-123273"},
    "QQQM":  {"name": "Invesco NASDAQ 100 ETF",            "er": 0.15, "cls": "equity", "region": "us",     "style": "nasdaq100", "src": "0001104659-25-122454"},
    "RSP":   {"name": "Invesco S&P 500 Equal Weight ETF",  "er": 0.20, "cls": "equity", "region": "us",     "style": "large_cap", "src": "0001104659-26-102475"},

    # ── Schwab ───────────────────────────────────────────────────────
    "SWPPX": {"name": "Schwab S&P 500 Index Fund",         "er": 0.02, "cls": "equity", "region": "us",     "style": "large_cap", "src": "0000884546-26-000041"},
    "SWTSX": {"name": "Schwab Total Stock Market Index Fund", "er": 0.03, "cls": "equity", "region": "us",  "style": "total_market", "src": "0000884546-26-000041"},
    "SCHB":  {"name": "Schwab US Broad Market ETF",        "er": 0.03, "cls": "equity", "region": "us",     "style": "total_market", "src": "0001104659-25-123308"},
    "SCHD":  {"name": "Schwab US Dividend Equity ETF",     "er": 0.06, "cls": "equity", "region": "us",     "style": "dividend", "src": "0001104659-25-123308"},
    "SCHF":  {"name": "Schwab International Equity ETF",   "er": 0.03, "cls": "equity", "region": "intl",   "style": "developed", "src": "0001104659-25-123308"},
    "SCHG":  {"name": "Schwab US Large-Cap Growth ETF",    "er": 0.04, "cls": "equity", "region": "us",     "style": "large_growth", "src": "0001104659-25-123308"},

    # ── Fidelity ─────────────────────────────────────────────────────
    # The ZERO funds really are 0.00, and that is the one place in this table
    # where a zero is a measurement. They are also index funds available only
    # in a Fidelity account, which is why they are worth carrying.
    "FXAIX": {"name": "Fidelity 500 Index Fund",           "er": 0.015, "cls": "equity", "region": "us",    "style": "large_cap", "src": "0000819118-26-000072"},
    "FSKAX": {"name": "Fidelity Total Market Index Fund",  "er": 0.015, "cls": "equity", "region": "us",    "style": "total_market", "src": "0000819118-26-000072"},
    "FTIHX": {"name": "Fidelity Total International Index Fund", "er": 0.06, "cls": "equity", "region": "intl", "style": "total_market", "src": "0000035315-25-001299"},
    "FXNAX": {"name": "Fidelity US Bond Index Fund",       "er": 0.025, "cls": "bond",  "region": "us",     "style": "aggregate_bond", "src": "0000035315-25-001071"},
    "FZROX": {"name": "Fidelity ZERO Total Market Index Fund", "er": 0.00, "cls": "equity", "region": "us", "style": "total_market", "src": "0000819118-25-000470"},
    "FNILX": {"name": "Fidelity ZERO Large Cap Index Fund", "er": 0.00, "cls": "equity", "region": "us",    "style": "large_cap", "src": "0000819118-25-000470"},
    "FZILX": {"name": "Fidelity ZERO International Index Fund", "er": 0.00, "cls": "equity", "region": "intl", "style": "total_market", "src": "0000819118-25-000470"},

    # ── Popular active and thematic ──────────────────────────────────
    # Carried because someone holding one should see what it costs beside the
    # index fund next to it, which is a fact, not a verdict on the strategy.
    "ARKK":  {"name": "ARK Innovation ETF",                "er": 0.75, "cls": "equity", "region": "us",     "style": "thematic", "src": "0001213900-25-115285"},
    "JEPI":  {"name": "JPMorgan Equity Premium Income ETF", "er": 0.35, "cls": "equity", "region": "us",    "style": "income", "src": "0001193125-25-246367"},
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
