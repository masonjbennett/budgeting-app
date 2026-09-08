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
```

`sched.py` is the shared 11-K fetcher and HTML-table extractor. Documents are
cached under `cache/`, so a re-run after the first is free.

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
