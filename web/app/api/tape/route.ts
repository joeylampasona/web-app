import { NextResponse } from "next/server";
import { getSearchIndex } from "@/lib/data";

/**
 * The last close and day's move for a short list of names: a reader's
 * watchlist, for the tape strip. Read from the search index the nightly
 * already wrote, so the strip never opens a stock file per name.
 */
export const dynamic = "force-dynamic";
const MAX = 50;

export function GET(request: Request) {
  const raw = new URL(request.url).searchParams.get("symbols") ?? "";
  const wanted = raw.split(",").map((s) => s.trim().toUpperCase())
    .filter((s) => /^[A-Z.\-]{1,8}$/.test(s)).slice(0, MAX);
  if (!wanted.length) return NextResponse.json({ rows: [] });
  const bySymbol = new Map(getSearchIndex().map((row) => [row.symbol, row]));
  const rows = wanted.flatMap((symbol) => {
    const row = bySymbol.get(symbol);
    return row ? [{
      symbol, close: row.close ?? null, change_pct: row.change_pct ?? null,
      rs_rating: typeof row.rs_rating === "number" ? row.rs_rating : null,
    }] : [];
  });
  return NextResponse.json({ rows }, { headers: { "Cache-Control": "private, max-age=300" } });
}
