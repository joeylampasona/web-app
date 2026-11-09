"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { EarningsReadCard } from "./QuarterlyPanel";
import type { EarningsFile } from "@/lib/types";

/**
 * The reads, newest report first, with a filter on the final read and a
 * search. Shows a page at a time: in the middle of a reporting season there
 * are dozens a day, and every card is a dozen lines.
 */
const FILTERS = [
  { key: "all", label: "All" },
  { key: "shown", label: "Proof shown" },
  { key: "pending", label: "Proof pending" },
  { key: "real", label: "Growth real" },
  { key: "weak", label: "Growth weak" },
] as const;
type FilterKey = typeof FILTERS[number]["key"];
const PAGE = 12;

export function EarningsReads({ file }: { file: EarningsFile }) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);

  const rows = useMemo(() => {
    const q = query.trim().toUpperCase();
    return file.reads.filter((r) => {
      if (q && !r.symbol.includes(q) && !(r.name ?? "").toUpperCase().includes(q)) return false;
      if (filter === "shown") return r.verdict.proof === "SHOWN";
      if (filter === "pending") return r.verdict.proof === "PENDING";
      if (filter === "real") return r.verdict.growth === "REAL";
      if (filter === "weak") return r.verdict.growth === "WEAK";
      return true;
    });
  }, [file.reads, filter, query]);

  const more = useMemo(() => {
    const q = query.trim().toUpperCase();
    return q ? file.more.filter((r) => r.symbol.includes(q) || r.name.toUpperCase().includes(q))
      : file.more;
  }, [file.more, query]);

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <input type="search" className="control" aria-label="Search the reads"
               placeholder="Ticker or company" value={query}
               onChange={(e) => { setQuery(e.target.value); setShown(PAGE); }}
               style={{ flex: "1 1 160px", maxWidth: 240, background: "var(--surface-2)",
                        minHeight: "var(--h-control)" }} />
        <div className="row wrap" style={{ gap: "var(--gap-xs)" }} role="group" aria-label="Filter by final read">
          {FILTERS.map((f) => (
            <button key={f.key} type="button" className="control footnote"
                    aria-pressed={filter === f.key}
                    onClick={() => { setFilter(f.key); setShown(PAGE); }}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {rows.length === 0 ? (
        <p className="muted footnote" style={{ margin: 0 }}>No read matches.</p>
      ) : (
        <div className="read-grid">
          {rows.slice(0, shown).map((r) => (
            <EarningsReadCard key={`${r.symbol}-${r.report_date}`} r={r}
                              symbol={r.symbol} name={r.name} />
          ))}
        </div>
      )}
      {rows.length > shown && (
        <button type="button" className="control" style={{ alignSelf: "center" }}
                onClick={() => setShown((n) => n + PAGE)}>
          Show {Math.min(PAGE, rows.length - shown)} more of {rows.length - shown}
        </button>
      )}

      {more.length > 0 && filter === "all" && (
        <div className="stack" style={{ gap: "var(--gap-xs)" }}>
          <div className="footnote muted">
            Earlier in the window: {more.length} more reads, each on the stock&rsquo;s own page
          </div>
          <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
            {more.map((r) => (
              <Link key={r.symbol} href={`/stocks/${r.symbol}`} className="badge badge--ticker"
                    title={`${r.name} · reported ${r.report_date} · growth ${r.growth}, proof ${r.proof}`}>
                {r.symbol}
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
