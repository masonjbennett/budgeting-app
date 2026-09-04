"use client";

/**
 * Importing a bank's CSV.
 *
 * THE PANEL DECIDES NOTHING. It reads a file, splits it into cells, and shows
 * what `/api/import-preview` says each row would become. Every judgement —
 * which column is which, whether 03/04 is March or April, whether -52.30 is a
 * purchase or a refund, whether the profile already holds a row — is made in
 * calculations.py, comes back with its evidence, and is printed here so it can
 * be overruled before anything is committed.
 *
 * NOTHING IS EVER OVERWRITTEN. An import only ever ADDS expenses. A row the
 * engine matches to one already held is shown, marked, and left unticked; it
 * can be ticked, and then it is added as a second expense rather than
 * replacing the first. There is no path through this component that edits or
 * removes an expense the person entered by hand — which is the whole reason a
 * preview exists rather than a "just import it" button.
 *
 * IT IS BUILT FOR A REAL FILE, WHICH IS THE SIZE OF A YEAR. The first thing
 * anyone does is export twelve months of one card. Measured on 1,200 rows, the
 * first version rendered a <select> of every budget category per row — 21,687
 * <option> elements, 35,469 DOM nodes and a page 60,190px tall — and because
 * one `skipped` Set drove all of them, ticking a single checkbox took 341–700ms
 * to paint. Three things fix that and each is load-bearing at that size: the
 * row is a MEMOIZED component so a tick re-renders one row; the table is
 * PAGED; and a FILTER puts the rows that need a decision in front of the
 * reader instead of asking them to scroll sixty thousand pixels.
 */

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Field } from "@/components/Field";
import { fmt, useFinance, type Expense } from "@/context/FinanceContext";
import {
  api,
  ApiError,
  type ImportMapping,
  type ImportPreview,
  type ImportRow,
} from "@/lib/api";
import { splitCsv } from "@/lib/csv";

/** 4MB of CSV is about fifteen years of one card. Past that the browser is
 *  reading a file that is not a statement, and the request would be refused
 *  server-side anyway — better to say so before the upload. */
const MAX_BYTES = 4_000_000;

/** Rows on screen at once. A hundred is about two screens, and it keeps the
 *  <option> count in the low thousands rather than the tens of thousands. */
const PAGE_SIZE = 100;

const ROLES: { key: keyof ImportMapping; label: string; help?: string }[] = [
  { key: "date", label: "Date" },
  { key: "description", label: "Description" },
  { key: "amount", label: "Amount" },
  { key: "debit", label: "Debit", help: "Only if money out has its own column" },
  { key: "credit", label: "Credit", help: "Ignored — money in is never imported" },
  { key: "category", label: "Category", help: "The bank's own, if it has one" },
];

type Filter = "all" | "attention" | "duplicate" | "blocked";

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "attention", label: "Needs a category" },
  { key: "duplicate", label: "Already recorded" },
  { key: "blocked", label: "Cannot import" },
];

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/* ── One row ────────────────────────────────────────────────────────────
   Memoized, and at this size that is not a micro-optimisation: without it
   every tick re-rendered all 1,200 rows and their selects, which measured
   341–700ms to paint. The callbacks it takes are stable (useCallback over
   functional setState) and `categories` is memoized by the page above, so
   React's shallow compare actually holds and only the row whose props
   changed re-renders.                                                     */
const Row = memo(function Row({
  row,
  checked,
  category,
  categories,
  onToggle,
  onCategory,
}: {
  row: ImportRow;
  checked: boolean;
  category: string;
  categories: string[];
  onToggle: (line: number, next: boolean) => void;
  onCategory: (line: number, value: string) => void;
}) {
  const blocked = row.skip !== null;
  return (
    <tr className={blocked || !checked ? "opacity-55" : undefined}>
      <td data-label="Import">
        <input
          type="checkbox"
          aria-label={`Import line ${row.line}`}
          disabled={blocked}
          checked={!blocked && checked}
          onChange={(e) => onToggle(row.line, e.target.checked)}
        />
      </td>
      <td data-label="Line" className="font-num text-right text-muted">{row.line}</td>
      <td data-label="Date" className="font-num whitespace-nowrap">{row.date ?? "—"}</td>
      <td
        data-label="Description"
        className="max-w-[22rem] truncate text-body"
        title={row.description}
      >
        {row.description || "—"}
      </td>
      <td data-label="Amount" className="font-num text-right whitespace-nowrap text-ink">
        {row.amount === null ? "—" : fmt(row.amount, 2)}
      </td>
      <td data-label="Category">
        {blocked ? (
          <span className="text-muted">—</span>
        ) : (
          <select
            value={category}
            aria-label={`Category for line ${row.line}`}
            className="t-small w-auto py-1"
            onChange={(e) => onCategory(row.line, e.target.value)}
          >
            <option value="">— choose —</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        )}
      </td>
      <td data-label="Status" className="t-micro">
        {blocked ? (
          <span className="text-muted">{row.skip}</span>
        ) : row.duplicate_of ? (
          <span className="text-caution">already recorded</span>
        ) : row.category_source ? (
          <span className="text-muted">by {row.category_source}</span>
        ) : (
          <span className="text-muted">needs a category</span>
        )}
      </td>
    </tr>
  );
});

export default function ImportPanel({ categories }: { categories: string[] }) {
  const { profile, update } = useFinance();

  const [fileName, setFileName] = useState<string | null>(null);
  const [grid, setGrid] = useState<string[][] | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<string | null>(null);

  // Overrides. Each is null until the reader disagrees with the engine, so an
  // untouched control shows what was DECIDED rather than a default that
  // happens to match it.
  const [hasHeader, setHasHeader] = useState<boolean | null>(null);
  const [mapping, setMapping] = useState<ImportMapping | null>(null);
  const [dateOrder, setDateOrder] = useState<string | null>(null);
  const [sign, setSign] = useState<string | null>(null);

  const [skipped, setSkipped] = useState<Set<number>>(new Set());
  const [catFor, setCatFor] = useState<Record<number, string>>({});
  const [fallback, setFallback] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [page, setPage] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFileName(null);
    setGrid(null);
    setPreview(null);
    setError(null);
    setHasHeader(null);
    setMapping(null);
    setDateOrder(null);
    setSign(null);
    setSkipped(new Set());
    setCatFor({});
    setFallback("");
    setFilter("all");
    setPage(0);
    if (inputRef.current) inputRef.current.value = "";
  };

  const onFile = async (file: File) => {
    setDone(null);
    if (file.size > MAX_BYTES) {
      setError(
        `${file.name} is ${Math.round(file.size / 1_000_000)}MB. A statement export is ` +
          `normally well under 4MB — check this is the right file.`,
      );
      return;
    }
    const text = await file.text();
    const rows = splitCsv(text);
    if (rows.length === 0) {
      setError(`${file.name} has no rows in it.`);
      return;
    }
    setError(null);
    setFileName(file.name);
    setGrid(rows);
    setHasHeader(null);
    setMapping(null);
    setDateOrder(null);
    setSign(null);
    setSkipped(new Set());
    setCatFor({});
    setFilter("all");
    setPage(0);
  };

  const request = grid &&
    profile && {
      grid,
      has_header: hasHeader,
      mapping,
      date_order: dateOrder,
      sign,
      categories,
      existing: profile.expenses,
    };
  const key = JSON.stringify(
    request && [hasHeader, mapping, dateOrder, sign, categories, grid?.length, fileName],
  );

  useEffect(() => {
    if (!request) return;
    let live = true;
    api
      .importPreview(request)
      .then((p) => {
        if (!live) return;
        setPreview(p);
        setError(null);
        setPage(0);
        // A row the engine matched to one already held starts UNTICKED. It is
        // the only default in this panel that is a judgement, and it is the
        // conservative one: not importing something twice costs a click to
        // undo, and importing it twice is a wrong total nobody will notice.
        setSkipped(
          new Set(p.rows.filter((r) => r.duplicate_of !== null).map((r) => r.line)),
        );
      })
      .catch((e) => {
        if (!live) return;
        setPreview(null);
        setError(e instanceof ApiError ? e.message : "Could not read that file.");
      });
    return () => {
      live = false;
    };
    // Keyed by VALUE, not by the request object: it is rebuilt on every render,
    // and re-uploading the file on each keystroke elsewhere would be a request
    // per character.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Functional updates, so these two are stable for the life of the panel and
  // React.memo on the row actually holds.
  const onToggle = useCallback((line: number, next: boolean) => {
    setSkipped((prev) => {
      const s = new Set(prev);
      if (next) s.delete(line);
      else s.add(line);
      return s;
    });
  }, []);
  const onCategory = useCallback((line: number, value: string) => {
    setCatFor((prev) => ({ ...prev, [line]: value }));
  }, []);

  const rows = useMemo(() => preview?.rows ?? [], [preview]);
  const categoryOf = useCallback(
    (line: number, suggested: string | null) => catFor[line] ?? suggested ?? fallback,
    [catFor, fallback],
  );

  const committable = useMemo(
    () =>
      rows.filter(
        (r) => r.skip === null && !skipped.has(r.line) && categoryOf(r.line, r.category),
      ),
    [rows, skipped, categoryOf],
  );
  const needCategory = useMemo(
    () =>
      rows.filter(
        (r) => r.skip === null && !skipped.has(r.line) && !categoryOf(r.line, r.category),
      ),
    [rows, skipped, categoryOf],
  );

  const counts = useMemo(
    () => ({
      all: rows.length,
      attention: rows.filter((r) => r.skip === null && !categoryOf(r.line, r.category))
        .length,
      duplicate: rows.filter((r) => r.duplicate_of !== null).length,
      blocked: rows.filter((r) => r.skip !== null).length,
    }),
    [rows, categoryOf],
  );

  const filtered = useMemo(() => {
    if (filter === "attention")
      return rows.filter((r) => r.skip === null && !categoryOf(r.line, r.category));
    if (filter === "duplicate") return rows.filter((r) => r.duplicate_of !== null);
    if (filter === "blocked") return rows.filter((r) => r.skip !== null);
    return rows;
  }, [rows, filter, categoryOf]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, pages - 1);
  const shown = filtered.slice(current * PAGE_SIZE, current * PAGE_SIZE + PAGE_SIZE);

  if (!profile) return null;

  const columnName = (i: number | null) => {
    if (i === null) return "—";
    const named = preview?.columns[i];
    return named && named.trim() ? named : `Column ${i + 1}`;
  };

  const width = grid ? Math.max(...grid.map((r) => r.length)) : 0;

  const commit = () => {
    setBusy(true);
    // EVERY committable row, not the page on screen. A commit that acted on
    // the visible page would import a hundred rows of twelve hundred and
    // report success.
    const entries: Expense[] = committable.map((r) => ({
      id: newId(),
      date: r.date as string,
      amount: r.amount as number,
      category: categoryOf(r.line, r.category),
      note: r.description,
    }));
    // Additive, always. The existing list is carried through untouched — there
    // is deliberately no merge step, because a merge is where a note somebody
    // typed gets replaced by a bank's description of the same charge.
    update({ expenses: [...entries, ...profile.expenses] });
    setDone(
      `${entries.length} transaction${entries.length === 1 ? "" : "s"} added from ${fileName}.`,
    );
    setBusy(false);
    reset();
  };

  return (
    <div className="space-y-4">
      {/* ── Choose a file ─────────────────────────────────────────── */}
      <div className="card">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={inputRef}
            type="file"
            accept=".csv,text/csv,text/plain"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void onFile(f);
            }}
          />
          <button className="btn-secondary" onClick={() => inputRef.current?.click()}>
            Choose a CSV
          </button>
          {fileName ? (
            <p className="t-small text-body">
              <span className="text-ink">{fileName}</span>
              {grid && (
                <span className="text-muted">
                  {" · "}
                  {grid.length} row{grid.length === 1 ? "" : "s"}, {width} column
                  {width === 1 ? "" : "s"}
                </span>
              )}
            </p>
          ) : (
            <p className="t-small text-muted">
              Export a statement from your bank and pick it here. Nothing is sent
              anywhere until you have looked at it.
            </p>
          )}
          {fileName && (
            <button className="btn-ghost ml-auto" onClick={reset}>
              Clear
            </button>
          )}
        </div>
        {error && <p className="t-small mt-3 text-critical">{error}</p>}
        {done && <p className="t-small mt-3 text-positive">{done}</p>}
      </div>

      {preview && (
        <>
          {/* ── What was decided, and why ────────────────────────── */}
          <div className="card">
            <h4 className="label mb-3">What this file looks like</h4>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field
                label="First row"
                help={
                  preview.has_header
                    ? "It has no date in it, so it reads as column names."
                    : "It has a date in it, so it reads as a transaction."
                }
              >
                <select
                  value={preview.has_header ? "header" : "data"}
                  onChange={(e) => setHasHeader(e.target.value === "header")}
                >
                  <option value="header">Column names</option>
                  <option value="data">A transaction</option>
                </select>
              </Field>

              <Field
                label="Date order"
                help={
                  preview.date_order.proved ? (
                    preview.date_order.reason
                  ) : (
                    <span className="text-caution">{preview.date_order.reason}</span>
                  )
                }
              >
                <select
                  value={preview.date_order.order}
                  onChange={(e) => setDateOrder(e.target.value)}
                >
                  <option value="MDY">Month first — 03/04 is 4 March</option>
                  <option value="DMY">Day first — 03/04 is 3 April</option>
                  <option value="YMD">Year first — 2026-03-04</option>
                </select>
              </Field>

              <Field
                label="Spending is written"
                help={
                  preview.sign.convention === "debit column" ? (
                    preview.sign.reason
                  ) : preview.sign.ambiguous ? (
                    <span className="text-caution">
                      {preview.sign.reason} — an even split, so check this one.
                    </span>
                  ) : (
                    preview.sign.reason
                  )
                }
              >
                <select
                  value={preview.sign.convention}
                  disabled={preview.sign.convention === "debit column"}
                  onChange={(e) => setSign(e.target.value)}
                >
                  {preview.sign.convention === "debit column" ? (
                    <option value="debit column">In its own debit column</option>
                  ) : (
                    <>
                      <option value="negative">Negative — Chase, most banks</option>
                      <option value="positive">Positive — Amex, some cards</option>
                    </>
                  )}
                </select>
              </Field>
            </div>

            <h4 className="label mt-6 mb-3">
              Columns {preview.mapping_suggested && <span>· worked out from the file</span>}
            </h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {ROLES.map((role) => (
                <Field key={role.key} label={role.label} help={role.help}>
                  <select
                    value={preview.mapping[role.key] ?? ""}
                    onChange={(e) =>
                      setMapping({
                        ...preview.mapping,
                        [role.key]: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                  >
                    <option value="">— none —</option>
                    {Array.from({ length: width }, (_, i) => (
                      <option key={i} value={i}>
                        {columnName(i)}
                      </option>
                    ))}
                  </select>
                </Field>
              ))}
            </div>
          </div>

          {/* ── The rows ─────────────────────────────────────────── */}
          <div className="card">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h4 className="label">
                {preview.summary.total} row{preview.summary.total === 1 ? "" : "s"} ·{" "}
                {committable.length} to add · {fmt(preview.summary.amount)}
              </h4>
              <div className="flex items-center gap-2">
                {/* These act on what the FILTER is showing, and say so. Acting
                    globally while a filter is on would tick rows the reader
                    cannot see — the same class of surprise as a commit that
                    acted on the visible page only. */}
                <button
                  className="btn-ghost"
                  onClick={() =>
                    setSkipped((prev) => {
                      const s = new Set(prev);
                      for (const r of filtered) s.delete(r.line);
                      return s;
                    })
                  }
                >
                  Tick all{filter === "all" ? "" : " shown"}
                </button>
                <button
                  className="btn-ghost"
                  onClick={() =>
                    setSkipped((prev) => {
                      const s = new Set(prev);
                      for (const r of filtered) s.add(r.line);
                      return s;
                    })
                  }
                >
                  Untick all{filter === "all" ? "" : " shown"}
                </button>
              </div>
            </div>

            {/* A year of one card is over a thousand rows. Nobody reads that,
                and nobody should have to: the rows worth a decision are the
                ones with no category and the ones already held. */}
            {rows.length > PAGE_SIZE && (
              <div className="tab-list mb-3 flex-wrap">
                {FILTERS.map((f) => (
                  <button
                    key={f.key}
                    className={`tab ${filter === f.key ? "tab-active" : ""}`}
                    onClick={() => {
                      setFilter(f.key);
                      setPage(0);
                    }}
                    disabled={counts[f.key] === 0}
                  >
                    {f.label} · {counts[f.key]}
                  </button>
                ))}
              </div>
            )}

            {preview.summary.duplicates > 0 && (
              <p className="t-small mb-3 text-caution">
                {preview.summary.duplicates} row
                {preview.summary.duplicates === 1 ? " matches an expense" : "s match expenses"}{" "}
                already recorded on the same day for the same amount, so{" "}
                {preview.summary.duplicates === 1 ? "it is" : "they are"} unticked.
                Ticking one adds it as a second expense — nothing here ever replaces
                what you entered by hand.
              </p>
            )}

            {preview.summary.uncategorised > 0 && (
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <p className="t-small text-muted">
                  {preview.summary.uncategorised} row
                  {preview.summary.uncategorised === 1 ? "" : "s"} could not be matched
                  to one of your categories. Put them in
                </p>
                <select
                  value={fallback}
                  onChange={(e) => setFallback(e.target.value)}
                  className="t-small w-auto py-1"
                >
                  <option value="">— pick each one below —</option>
                  {categories.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* `table-cards` stacks each row into label/value lines below
                640px — see globals.css. The importer is the one table in the
                app that cannot be made to fit a phone by dropping columns:
                its category <select> alone is ~146px at touch type size, and
                a row carries TWO controls because it is a decision, not a
                readout. Measured before the change: 736px of table in a 335px
                scroller, 401px of it off screen. */}
            <div className="overflow-x-auto">
              <table className="table-cards">
                <thead>
                  <tr>
                    <th className="w-8" />
                    <th className="text-right">Line</th>
                    <th>Date</th>
                    <th>Description</th>
                    <th className="text-right">Amount</th>
                    <th>Category</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((r) => (
                    <Row
                      key={r.line}
                      row={r}
                      checked={!skipped.has(r.line)}
                      category={categoryOf(r.line, r.category)}
                      categories={categories}
                      onToggle={onToggle}
                      onCategory={onCategory}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            {filtered.length === 0 && (
              <p className="t-small py-6 text-center text-muted">
                Nothing in this file matches that filter.
              </p>
            )}

            {filtered.length > PAGE_SIZE && (
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  className="btn-secondary"
                  onClick={() => setPage(current - 1)}
                  disabled={current === 0}
                >
                  ← Previous
                </button>
                <p className="t-small text-muted">
                  <span className="font-num">
                    {current * PAGE_SIZE + 1}–
                    {Math.min((current + 1) * PAGE_SIZE, filtered.length)}
                  </span>{" "}
                  of <span className="font-num">{filtered.length}</span>
                  {filter === "all" ? " rows" : " matching"}
                </p>
                <button
                  className="btn-secondary"
                  onClick={() => setPage(current + 1)}
                  disabled={current >= pages - 1}
                >
                  Next →
                </button>
              </div>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <button
              className="btn-primary"
              onClick={commit}
              disabled={busy || committable.length === 0}
            >
              Add {committable.length} transaction{committable.length === 1 ? "" : "s"}
            </button>
            {needCategory.length > 0 && (
              <p className="t-small text-caution">
                {needCategory.length} ticked row{needCategory.length === 1 ? "" : "s"} still
                {needCategory.length === 1 ? " needs" : " need"} a category and will be
                left out.
              </p>
            )}
            <p className="t-micro ml-auto text-muted">
              {preview.summary.skipped > 0 && (
                <>{preview.summary.skipped} row(s) cannot be imported · </>
              )}
              Adding never replaces an expense you already have.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
