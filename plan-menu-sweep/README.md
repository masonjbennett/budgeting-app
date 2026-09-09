# What a 401(k) menu is actually made of

The evidence behind the numbers in `fund_kinds.py`, `web/README.md` rule 14 and
the `/portfolio` page's limits list. **It is in the repo for the same reason
`web/browser-checks/` is**: it cannot run in CI (it fetches ~50 SEC documents),
which is an argument about CI and not about storage. Two sessions once rebuilt
the browser checks from a paragraph of prose and the second rebuild shipped a
check that could not fail. A claim of "88.4%" with no runnable derivation
behind it would rot the same way.

## The frame, and why it is this one

A **Form 11-K** is the annual report a public company files for its own savings
plan. It carries Schedule H line 4i — the plan's complete list of investments,
grouped under headings the plan's auditor wrote. **766 were filed in 2026.**

EDGAR's quarterly index orders filings alphabetically by company, which is
uncorrelated with plan size, so a **fixed stride** is a clean sample and needs
no seed. Nothing here is remembered: the bucket for every holding is the
FILER'S OWN grouping heading ("Mutual funds", "Collective trust funds"), the
way filings-terminal prefers a filer's own subtotal to a reconstruction.

## What it found

48 plans sampled, 29 of them menu-shaped:

| | share of the fund dollars in a real menu |
|---|---|
| collective trusts | **88.4%** dollar-weighted, **67.0%** median plan |
| already in `fund_data.py` | 1.0% |
| registered + tickered, not in the table | 3.7% |
| did not resolve | 5.7% |

CIT is a majority in **18 of 29** plans and absent from 6. So widening the fund
table addresses about 4% of the money and **can never** address 88% — a
collective trust is a bank-maintained fund, not a registered investment
company, and files nothing with the SEC at all.

## Running it

Needs three SEC files in this directory (all public, all free). They are
gitignored — fetch them rather than committing 2MB of someone else's data:

```bash
UA="Your Name yoursite.com you@example.com"
curl -s --compressed -H "User-Agent: $UA" -o mf.json  https://www.sec.gov/files/company_tickers_mf.json
curl -s --compressed -H "User-Agent: $UA" -o ct.json  https://www.sec.gov/files/company_tickers.json
curl -s --compressed -H "User-Agent: $UA" -o scc.csv  https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-2026.csv
curl -s --compressed -H "User-Agent: $UA" -o form-2026-QTR2.idx https://www.sec.gov/Archives/edgar/full-index/2026/QTR2/form.idx
curl -s --compressed -H "User-Agent: $UA" -o form-2026-QTR3.idx https://www.sec.gov/Archives/edgar/full-index/2026/QTR3/form.idx
```

Then, in order:

```bash
python sweep11k.py 16     # fetch + extract 48 plans -> sweep11k.json (cached in cache/)
python clean.py           # the headline percentages
python detect.py          # score the SHIPPING fund_kinds.py against the filers' labels
python gaps.py            # which registered funds real menus hold that the table misses
python classes.py         # ...and which SHARE CLASSES of funds it already carries
python gen_classes.py     # emit fund_data.py rows for those (series-id keyed)
python gen_complete.py    # emit the rest of each series, so none is carried in part
python verify_classes.py  # every series the table touches is carried WHOLE
python sleeves.py VTINX   # what a fund-of-funds holds, and whether the table has it
```

`sched.py` is the shared 11-K fetcher and HTML-table extractor. Documents are
cached under `cache/`, so a re-run after the first is free. `sleeves.py` is the
odd one out — it reads a fund's own N-PORT live rather than the 11-K sample,
and it is here because it answered the question the look-through raised: which
fund is a target-date sleeve substituted from, and does the table carry it?

## "II" is a different fund, not a share class

`refresh_holdings.py` stripped **II** as a wrapper word, which was right while
the table held only the non-II funds — collapsing them was the only way to
resolve a target-date fund's bond sleeve at all. After the widening it became
wrong: it put BND and VTBIX on one key and `setdefault` picked by insertion
order, and they are genuinely different filings (**2 of 3 stored names in
common, 15.87% against 22.62% covered**). So the most common 401(k) holding
could have its bond sleeve substituted from the wrong fund, silently.

Removing the collapse made the substitution precise and **cost expansion**:
VTINX 83.1% -> 67.7%, VTTSX 99.4% -> 96.8%, the drop tracking each fund's
bond weight. `sleeves.py VTINX` then named the cost exactly rather than
leaving it to be guessed — Short-Term Inflation-Protected 16.12%, Total
International Bond II 15.42%, and 0.64% of Vanguard's internal Market
Liquidity sweep, which is not investable. Both real funds were added, carried
whole. The chore now REPORTS any remaining name collision instead of letting
insertion order decide it.

## Five things that were wrong before they were right

Each cost a cycle and none was visible in a headline number.

1. **The extractor pulled the financial statements too.** A 4i heading also
   sits near them, so proximity alone caught the statement of net assets. A
   schedule of assets never carries "Net assets available for benefits".
2. **Fund names span COLUMNS.** A 4i schedule puts the issuer in (b) and the
   instrument in (c), so taking the first word-bearing cell reduced "Vanguard
   Institutional Index Fund" to "Vanguard".
3. **A group heading survives a page break inside one HTML table.** AEP files
   its own stock and a hundred individual equities after "COMMON / COLLECTIVE
   TRUSTS" with no closing total, so they all scored as missed trusts. A
   `Total X` row closes its group, and `clean.menus(strict=True)` additionally
   drops schedules listing hundreds of securities — those are
   separately-managed-account plans, not menus.
4. **`detect.py` must strip the auditor's own label before scoring.** Rows read
   "Dodge & Cox Stock Fund Registered Investment Company". Scoring on that text
   measures the ability to read a classification a participant will never type;
   it is worth **19 points of recall** (84.4% against 65.6%), and the lower
   number is the honest one. Both are printed so the gap stays visible.
5. **`detect.py` drives the SHIPPING `fund_kinds.py`.** A hand-copied mirror of
   the rules here would test rules production no longer has — the `grid.js`
   lesson.

## Two keys, and they are not the same key

Matching a plan's LABEL to a fund can only be done on the NAME — a Schedule H
4i line carries no ticker. That is `fkey`, and it has to be loose: it strips
FUND, INDEX, ADMIRAL, INSTITUTIONAL, CLASS and so on to get "Vanguard 500
Index Fund Investor Shares" and "Vanguard 500 Index Admiral" onto one key.

**Enumerating the classes of a fund must use SEC's SERIES ID instead**, which
is exact. Using `fkey` for both crosses fund boundaries silently, because the
words it strips are sometimes the whole difference:

| collapses to one key | and they are |
|---|---|
| Total Bond Market Index / Total Bond Market **II** Index | different funds |
| Total Stock Market Index / **Institutional** Total Stock Market Index | different funds |
| Real Estate Index / Real Estate **II** Index | different funds |
| Fidelity Freedom 2040 (FFFFX) / Fidelity Freedom **Index** 2040 (FBIFX) | ~6x apart in fee |

Five classes reached `fund_data.py` through that collapse before it was caught
(VRTPX, VTBIX, VTBNX, VITNX, VITPX). They are real funds real plans hold, their
fees came from their own filings and their classifications were checked one by
one and are right — but nothing in the process had established that, which is
the part that mattered. `gen_classes.py` and `gen_complete.py` now enumerate by
series id; `verify_classes.py` checks the result.

`gaps.py` had a second version of the same family: it did not strip the
auditor's appended classification, so "…Fund Mutual fund" normalised to
"…MUTUAL", matched nothing, and it reported the whole Vanguard Target
Retirement series as still missing AFTER it had been added. It uses
`detect.strip_label` now.

## The ceiling, which is the real finding

Recall stops in the sixties at 100% precision because **a large share of
collective trusts are named exactly like mutual funds**: "MFS International
Equity Fund" is a trust at Clorox and at Bank of Montreal and is also a real
mutual fund; so are "S&P 500 Fund" and "Aggregate Bond Fund". No rule over
names separates those without calling real mutual funds trusts.

That is why `/portfolio` matches holdings on **ticker, exactly, and never on
name** — and why the detector may only ever refuse. It can never make a holding
covered, and the Python suite asserts that every coverage figure is identical
with it firing and with it silent.
