import { isRanked } from "./format";
import type { Setup } from "./types";

/**
 * The rows a reader can see on a screen, as a CSV they can open in a
 * spreadsheet. Every published number, none that is not published — an export
 * that quietly carried more than the site shows would be a second, unaudited
 * surface.
 *
 * RS keeps its published shape: a number, or the words for a listing too new to
 * rank. Writing 0 there would read as the weakest name in the market.
 */
const COLUMNS: { key: string; of: (s: Setup) => string | number | null | undefined }[] = [
  { key: "symbol", of: (s) => s.symbol },
  { key: "name", of: (s) => s.name },
  { key: "screen", of: (s) => s.screen },
  { key: "stage", of: (s) => s.stage },
  { key: "rs_rating", of: (s) => (isRanked(s.rs_rating) ? s.rs_rating : "not ranked yet") },
  { key: "close", of: (s) => s.close },
  { key: "pivot", of: (s) => s.pivot },
  { key: "now_vs_pivot_pct", of: (s) => s.now_vs_pivot_pct },
  { key: "base_weeks", of: (s) => s.base_weeks },
  { key: "base_depth_pct", of: (s) => s.base_depth_pct },
  { key: "from_52w_high_pct", of: (s) => s.from_52w_high_pct },
  { key: "price_vs_50ma_pct", of: (s) => s.price_vs_50ma_pct },
  { key: "tightening_atr_ratio", of: (s) => s.tightening_atr_ratio },
  { key: "volume_dryup_ratio", of: (s) => s.volume_dryup_ratio },
  { key: "industry", of: (s) => s.industry },
  { key: "days_until_earnings", of: (s) => s.catalysts?.days_until_earnings },
];

export function toCsv(setups: Setup[]): string {
  const lines = [COLUMNS.map((c) => c.key).join(",")];
  for (const setup of setups) {
    lines.push(COLUMNS.map((column) => cell(column.of(setup))).join(","));
  }
  return lines.join("\n") + "\n";
}

export function downloadCsv(filename: string, body: string) {
  const blob = new Blob([body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "number") return String(value);
  // A string starting =, +, - or @ is run as a formula by every spreadsheet
  // that opens this. Quoting alone does not stop it; the apostrophe does. A
  // negative number is not a string and never reaches here, so -3.4 stays -3.4.
  const escaped = /^[=+\-@]/.test(value) ? `'${value}` : value;
  return /[",\n]/.test(escaped) ? `"${escaped.replace(/"/g, '""')}"` : escaped;
}
