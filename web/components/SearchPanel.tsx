"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { rsText } from "@/lib/format";
import type { SearchRow } from "@/lib/data";
import { PriceChange } from "./PriceChange";
import { Sparkline } from "./Sparkline";
import { TickerLink } from "./StockDrawer";

export function SearchPanel({
  rows, suggestions, themes,
}: {
  rows: SearchRow[];
  suggestions: { symbol: string; name: string }[];
  themes: { slug: string; name: string }[];
}) {
  const [query, setQuery] = useState("");

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return [];
    return rows
      .filter(
        (row) =>
          row.symbol.toLowerCase().startsWith(needle) ||
          row.name.toLowerCase().includes(needle) ||
          row.industry.toLowerCase().includes(needle),
      )
      .slice(0, 40);
  }, [query, rows]);

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <input
        className="control"
        style={{
          width: "100%", background: "var(--surface-2)",
          justifyContent: "flex-start", fontSize: "var(--size-lead)",
          minHeight: 52,
        }}
        placeholder="Ticker, company or industry"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-label="Search"
        autoComplete="off"
      />

      {!query && (
        <>
          <section>
            <div className="eyebrow">Recent breakouts</div>
            <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
              {suggestions.map((row) => (
                <TickerLink key={row.symbol} symbol={row.symbol} className="badge">
                  <span className="mono">{row.symbol}</span>
                </TickerLink>
              ))}
              {suggestions.length === 0 && (
                <span className="caption dim">Nothing broke out in the last session.</span>
              )}
            </div>
          </section>

          <section>
            <div className="eyebrow">Jump to theme</div>
            <div className="grid-2" style={{ gap: "var(--gap-sm)" }}>
              {themes.map((theme) => (
                <Link key={theme.slug} href={`/themes/${theme.slug}`} className="control footnote"
                      style={{ justifyContent: "flex-start" }}>
                  {theme.name}
                </Link>
              ))}
            </div>
          </section>
        </>
      )}

      {query && results.length === 0 && rows.length > 0 && (
        <p className="muted footnote">
          Nothing in the universe matches that. The universe is the liquid US common
          stocks only — under $5, under $300M, or thin, and a name never enters it.
        </p>
      )}

      {rows.length === 0 && (
        <p className="footnote" style={{ color: "var(--warn)" }}>
          The search index is empty, so nothing can match — this is not a statement
          about the ticker you typed. Run <code className="mono">python -m cli publish</code>{" "}
          to write it.
        </p>
      )}

      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        {results.map((row) => (
          <TickerLink key={row.symbol} symbol={row.symbol} className="card between"
                      style={{ padding: "var(--pad-md) var(--pad-lg)", width: "100%",
                               gap: "var(--gap-sm)" }}>
            <span className="grow" style={{ minWidth: 0 }}>
              <span className="mono">{row.symbol}</span>{" "}
              <span>{row.name}</span>
              <span className="caption dim"> · {row.industry}</span>
            </span>
            <span className="row" style={{ gap: "var(--gap-sm)", flexShrink: 0 }}>
              <Sparkline points={row.spark} changePct={row.spark_change_pct} />
              <PriceChange value={row.spark_change_pct} className="footnote" />
              <span className="num dim">{rsText(row.rs_rating)}</span>
            </span>
          </TickerLink>
        ))}
      </div>
    </div>
  );
}
