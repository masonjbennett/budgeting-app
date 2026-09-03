/**
 * Splitting a CSV into cells.
 *
 * THIS IS THE ONLY PART OF THE IMPORT THAT IS ALLOWED TO BE IN TYPESCRIPT, and
 * the line is worth stating precisely, because "parse the CSV" sounds like one
 * job and is two. Turning bytes into a grid of strings is text handling: it
 * decides nothing about money, and getting it wrong is not subtle — the
 * preview table renders the garbage and no date column is found. Deciding what
 * those strings MEAN — which column is the date, whether 03/04 is March or
 * April, whether -52.30 is a purchase or a refund, whether a row is already in
 * the profile — is a pile of rules that fail silently, and every one of them
 * is in calculations.py where it can be tested.
 *
 * RFC 4180, plus the two things real exports do that it does not: a delimiter
 * that is not always a comma, and line endings of every kind.
 */

/** Delimiters seen in the wild. Comma first, so it wins a tie. */
const DELIMITERS = [",", ";", "\t", "|"];

/**
 * One pass of RFC 4180: quoted fields may hold the delimiter, a newline, or a
 * doubled quote. Everything outside quotes is literal.
 *
 * A trailing newline does NOT produce a final empty row — every export ends
 * with one, and an empty row at the bottom of the preview reads as a
 * transaction that failed to parse.
 */
export function splitCsv(text: string, delimiter?: string): string[][] {
  const d = delimiter ?? detectDelimiter(text);
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  let i = 0;

  // A byte-order mark survives a "Save as CSV" from Excel and would otherwise
  // become part of the first header's name, so "Date" never matches.
  if (text.charCodeAt(0) === 0xfeff) i = 1;

  const endField = () => {
    row.push(field);
    field = "";
  };
  const endRow = () => {
    endField();
    rows.push(row);
    row = [];
  };

  while (i < text.length) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        quoted = false;
        i += 1;
        continue;
      }
      field += c;
      i += 1;
      continue;
    }
    if (c === '"' && field === "") {
      quoted = true;
      i += 1;
      continue;
    }
    if (c === d) {
      endField();
      i += 1;
      continue;
    }
    if (c === "\r" || c === "\n") {
      endRow();
      // CRLF is one ending, not two.
      i += c === "\r" && text[i + 1] === "\n" ? 2 : 1;
      continue;
    }
    field += c;
    i += 1;
  }
  // Only close a final row if anything was on it.
  if (field !== "" || row.length) endRow();

  // Rows that are entirely empty are blank lines, not transactions.
  return rows.filter((r) => r.some((cell) => cell.trim() !== ""));
}

/**
 * Which character separates the columns.
 *
 * Not a rule about money — it decides how many columns there are, and a wrong
 * answer puts the whole line in column one, which is the most visible possible
 * failure: no date column is found and the preview shows one column of raw
 * text. Chosen by consistency rather than by count, because a description
 * field full of commas beats a semicolon on raw frequency while producing a
 * different number of columns on every row.
 */
export function detectDelimiter(text: string): string {
  let best = ",";
  let bestScore = -1;
  for (const d of DELIMITERS) {
    const rows = splitCsv(text, d).slice(0, 8);
    if (rows.length === 0) continue;
    const widths = rows.map((r) => r.length);
    const consistent = widths.every((w) => w === widths[0]);
    // Consistent beats wide: two columns on every row is a real split, and
    // seventeen columns on one row and three on the next is not.
    const score = (consistent ? 1000 : 0) + (widths[0] > 1 ? widths[0] : -1);
    if (score > bestScore) {
      best = d;
      bestScore = score;
    }
  }
  return best;
}
