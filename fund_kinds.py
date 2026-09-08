"""What an UNCOVERED holding is, when the fund table has never heard of it.

DATA AND ONE RULE, NOT ARITHMETIC. Like `fund_data.py` this is stdlib-only and
is copied into web/api/ by scripts/sync-calculations.mjs. Edit THIS copy.

WHY THIS EXISTS. The X-ray had one kind of uncovered holding, and a person
reading it could not tell a typo from a vehicle no free tool on earth can see
inside. Those need different answers: a mistyped ticker is worth fixing and a
collective trust never will be.

WHAT A 401(k) MENU IS ACTUALLY MADE OF, measured rather than remembered. The
frame is every Form 11-K filed in 2026 - the annual report a public company
files for its own savings plan, carrying Schedule H line 4i, the plan's
complete list of investments. 766 of them, ordered alphabetically by company
in EDGAR's quarterly index, which is uncorrelated with plan size, so a fixed
stride is a clean sample. 48 sampled, 29 of them menu-shaped.

  Collective trusts are 88.4% of the fund dollars in those menus, 67.0% in
  the median plan, a majority in 18 of 29, and absent from 6.

A collective investment trust is a bank-maintained fund. It is NOT a
registered investment company: it has no ticker, files no prospectus and no
N-PORT, and appears in none of SEC's fund files. Neither the expense-ratio
chore nor the holdings chore can ever reach one, and neither can any other
free tool. That is a fact about the vehicle, not a gap in this table.

WHAT THIS CHANGES AND WHAT IT MUST NOT. It refines the EXPLANATION of a
holding that is already uncovered. It can never make one covered, never
supplies a fee, a class, a region or a holding, and never moves a percentage.
The X-ray's coverage figures are identical with it and without it, and the
suite asserts that.

THE THING IT DELIBERATELY DOES NOT DO. Some collective trusts carry the same
name as a mutual fund - "MFS International Equity Fund" is a collective trust
at Clorox and at Bank of Montreal, and it is also a real mutual fund. So a
NAME cannot be matched to the fund table: doing so would report a registered
fund's expense ratio for a vehicle that charges something else, which is worse
than the blank it replaces. Holdings are matched on TICKER, exactly, and a
collective trust has none. See README rule 14.

MEASURED, against the 655 menu lines in that sample, each labelled by the
plan auditor's own grouping heading ("Mutual funds", "Collective trust
funds"):

  precision 100.0%   recall 65.6%    on the fund NAME alone
  precision 100.0%   recall 84.4%    on the raw filing text

The first number is the honest one and is the one that matters: the second
includes the classification the auditor appends to the row ("... Collective
Investment Trust"), which a participant reading a statement will never type.
Precision is what is load-bearing here - calling a mutual fund a collective
trust would tell someone a fee exists nowhere when it is in the table - and
recall below 100% costs only the extra sentence, leaving the ordinary
"not in the table" answer.

THE CEILING IS REAL. Recall stops in the sixties because a large share of
collective trusts are named exactly like mutual funds: "S&P 500 Fund",
"Aggregate Bond Fund", "Blackrock Short-Term Investment Fund". No rule over
names can separate those without calling real mutual funds trusts, and that
trade is the wrong way round.
"""

import re

# The frame, so the numbers above can be re-derived rather than believed.
MEASURED_AS_OF = "2026-09-08"
MEASURED_PLANS = 29
MEASURED_LINES = 655

# A collective trust is denominated in UNITS and maintained by a BANK or
# TRUST COMPANY. Both are legal facts about the vehicle rather than house
# style, which is why "Trust Unit D", "Unit Class 3" and "Loomis Sayles Trust
# Company Core Plus Fixed Income Fund" are evidence and "Institutional Class"
# is not.
#
# Deliberately NOT here: "MFO" and "RET BLEND", each worth 9 and 13 more
# lines at no measured cost. Both are one filer's shorthand inside a filing,
# not something a participant reads on a statement, and a rule fitted to the
# filer that prompted it is the trap this project keeps refusing.
_CIT = re.compile(
    r"\bcollective\b|\bcommingled\b|\bgroup trust\b|\bnon-?lendable\b|"
    r"\bnon[- ]?sl\b|\bnsl\b|\bsecurities lending\b|\bcit\b|\bcif\b|"
    r"\bunit(ized)?\s+(class|trust)\b|\bunit\s+[a-z0-9]{1,3}\b|"
    r"\btrust\s+(co|company)\b|"
    r"\btrust,?\s+(i{1,3}|iv|v|select|unit|class|[a-z]\b)|"
    r"\btrust\s*$|\bpool\b|\bdaily liquidity\b|\beb dl\b", re.I)

# A stable value or guaranteed option is an insurance contract or a trust
# holding them. Same structural answer as a collective trust - nothing is
# filed - but a different sentence, because the fee is disclosed differently.
_INSURANCE = re.compile(
    r"\bstable value\b|\bstable return\b|\bguaranteed\b|\binsurance contract\b|"
    r"\bsynthetic gic\b|\bgic\b|\bfixed annuity\b|\bmanaged income\b|"
    r"\bprincipal protection\b", re.I)

# A brokerage window is not one holding at all - it is an account holding
# many, so no single figure could describe it.
_SDBA = re.compile(
    r"\bself[- ]directed\b|\bbrokerage(link| window| account)?\b|"
    r"\bpersonal choice retirement\b|\bpcra\b", re.I)


COLLECTIVE_TRUST = "collective_trust"
INSURANCE_CONTRACT = "insurance_contract"
BROKERAGE_WINDOW = "brokerage_window"

# What each is, and where the number this tool cannot supply actually lives.
# Phrased as a fact plus where to look, never as an instruction - the posture
# the whole X-ray is built around.
NOTES = {
    COLLECTIVE_TRUST: (
        "This reads like a collective investment trust - a fund a bank runs "
        "for retirement plans. It is not a registered fund, so it has no "
        "ticker and files no prospectus or holdings report with the SEC. "
        "Nothing here can read its fee or see inside it. Your plan's annual "
        "fee disclosure carries the fee."),
    INSURANCE_CONTRACT: (
        "This reads like a stable value or guaranteed option, which is an "
        "insurance contract rather than a fund. It files nothing with the "
        "SEC, so its cost is not readable here. Your plan's annual fee "
        "disclosure carries it."),
    BROKERAGE_WINDOW: (
        "This reads like a self-directed brokerage window, which is an "
        "account rather than a single holding. Enter what you hold inside "
        "it as separate lines and the rest of this page will cover them."),
}


def unknown_kind(symbol="", label=""):
    """(kind, note) for a holding the fund table does not cover, or (None, None).

    Reads the LABEL - what the person typed off their statement - and the
    symbol, since a plan fund often has no ticker and people put the name in
    whichever box is in front of them.

    Order is deliberate. A brokerage window is tested first because its name
    can carry a trust word ("Fidelity BrokerageLink"), and it is the one of
    the three that is not a fund at all.
    """
    text = " ".join(str(x or "") for x in (label, symbol)).strip()
    if not text:
        return None, None
    if _SDBA.search(text):
        return BROKERAGE_WINDOW, NOTES[BROKERAGE_WINDOW]
    if _CIT.search(text):
        return COLLECTIVE_TRUST, NOTES[COLLECTIVE_TRUST]
    if _INSURANCE.search(text):
        return INSURANCE_CONTRACT, NOTES[INSURANCE_CONTRACT]
    return None, None
