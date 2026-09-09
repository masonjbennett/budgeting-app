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

WHAT THOSE NUMBERS ARE MEASURED ON, AND WHAT THEY ARE NOT. The corpus is
401(k) menu lines. A brokerage statement is a different population: it
carries registered vehicles that are CALLED a trust - a gold or bitcoin
trust, a fund company's series trust - which no plan menu holds, so 100%
precision there says nothing about them. An outside review reproduced nine
of them being called collective trusts. A name that merely ENDS in "Trust"
is therefore weak evidence: counted only when it is the only thing typed,
refused beside a ticker (a collective trust has none), and worded as a
maybe. See `_TRUST_ONLY`. The corpus figures above are unchanged by that.
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
#
# The class markers after "Trust" are WHOLE WORDS: "Trust I", "Trust V" and
# "Trust Select" are share classes; "Trust Income" and "Trust Value" are not,
# and an unanchored `i` or `v` read them as one. Anchoring changed nothing on
# the 655 corpus lines and cleared three registered funds.
_CIT = re.compile(
    r"\bcollective\b|\bcommingled\b|\bgroup trust\b|\bnon-?lendable\b|"
    r"\bnon[- ]?sl\b|\bnsl\b|\bsecurities lending\b|\bcit\b|\bcif\b|"
    r"\bunit(ized)?\s+(class|trust)\b|\bunit\s+[a-z0-9]{1,3}\b|"
    r"\btrust\s+(co|company)\b|"
    r"\btrust,?\s+(i{1,3}|iv|v|select|unit|class|[a-z])\b|"
    r"\bpool\b|\bdaily liquidity\b|\beb dl\b", re.I)

# A name that merely ENDS in "Trust" is weak evidence, kept apart from the
# markers above because it is the one clause a registered vehicle can also
# satisfy: "iShares Gold Trust", "Grayscale Bitcoin Trust" and "MFS Series
# Trust" are SEC-registered and tickered, and none appears in any 401(k)
# menu, so the corpus the numbers above were measured on cannot see them. By
# name alone "Vanguard Institutional 500 Index Trust" (a collective trust)
# and a gold trust are the same shape. The ticker is the discriminator - a
# collective trust has none - so this clause counts only when it is the ONLY
# thing typed, is refused beside a symbol, and gets the hedged note below.
# Measured: dropping it instead would cost 3 of the 655 corpus lines and,
# worse, the bare Vanguard trusts that are the most common real case.
_TRUST_ONLY = re.compile(r"\btrust\s*$", re.I)

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
# Not a kind: the hedged wording for a collective trust identified by a
# trailing "Trust" and nothing else, the one shape a registered vehicle
# shares. Kept in NOTES so every check over the notes covers it too.
TRUST_BY_NAME = "trust_by_name"

# What each is, and where the number this tool cannot supply actually lives.
# Phrased as a fact plus where to look, never as an instruction - the posture
# the whole X-ray is built around.
NOTES = {
    COLLECTIVE_TRUST: (
        "This reads like a collective investment trust — a fund a bank "
        "runs for retirement plans. It is not a registered fund, so it has "
        "no ticker and files no prospectus or holdings report with the SEC. "
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
    TRUST_BY_NAME: (
        "This is named like a collective investment trust — a fund a bank "
        "runs for retirement plans, which has no ticker and files nothing "
        "with the SEC, so nothing here can read its fee. If that is what it "
        "is, your plan's annual fee disclosure carries the fee. Some "
        "registered funds are also called a trust — a gold or bitcoin "
        "trust, or a fund company's series trust — and those have a ticker; "
        "typed in the symbol box it is looked up as a fund rather than read "
        "as a name."),
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
    # Trailing "Trust" alone, and only when ONE box was filled: a collective
    # trust has no ticker, so beside a symbol the plain "not in the table"
    # answer is the right one. Tested per box rather than on `text`, or the
    # join order above would be doing this job silently.
    lone = [s for s in (str(label or "").strip(), str(symbol or "").strip()) if s]
    if len(lone) == 1 and _TRUST_ONLY.search(lone[0]):
        return COLLECTIVE_TRUST, NOTES[TRUST_BY_NAME]
    if _INSURANCE.search(text):
        return INSURANCE_CONTRACT, NOTES[INSURANCE_CONTRACT]
    return None, None
