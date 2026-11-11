import { NextResponse } from "next/server";
import { getSearchIndex } from "@/lib/data";

/**
 * The best dozen matches for what has been typed, for the search that opens
 * from any page. The search page itself ships the whole index, which is right
 * for a page that exists to search; a palette on every page cannot, so it
 * asks here and gets back only the rows it draws.
 *
 * Ranked the way a ticker box is expected to behave: the exact symbol, then
 * symbols that start with it, then company names, then industries.
 */
export const dynamic = "force-dynamic";
const MAX = 12;

export function GET(request: Request) {
  const needle = (new URL(request.url).searchParams.get("q") ?? "").trim().toLowerCase().slice(0, 40);
  if (!needle) return NextResponse.json({ rows: [] });
  const scored: { score: number; row: ReturnType<typeof getSearchIndex>[number] }[] = [];
  for (const row of getSearchIndex()) {
    const symbol = row.symbol.toLowerCase();
    const name = row.name.toLowerCase();
    const score = symbol === needle ? 0
      : symbol.startsWith(needle) ? 1
      : name.startsWith(needle) ? 2
      : name.includes(needle) ? 3
      : row.industry.toLowerCase().includes(needle) ? 4 : -1;
    if (score >= 0) scored.push({ score, row });
  }
  const rs = (v: number | string) => (typeof v === "number" ? v : -1);
  scored.sort((a, b) => a.score - b.score || rs(b.row.rs_rating) - rs(a.row.rs_rating));
  const rows = scored.slice(0, MAX).map(({ row }) => ({
    symbol: row.symbol, name: row.name, industry: row.industry,
    rs_rating: row.rs_rating, spark: row.spark ?? null,
    close: row.close ?? null, change_pct: row.change_pct ?? null,
    layer: row.layer ?? null, screens: row.on_screen?.length ?? 0,
  }));
  return NextResponse.json({ rows, total: scored.length },
    { headers: { "Cache-Control": "public, max-age=300" } });
}
