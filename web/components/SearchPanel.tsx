"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { rsText } from "@/lib/format";
import type { SearchRow } from "@/lib/data";
import { PriceChange } from "./PriceChange";
import { Sparkline } from "./Sparkline";
import { WatchStar } from "./WatchStar";
import { TickerLink } from "./StockDrawer";

export function SearchPanel({
  rows, suggestions, themes,
}: {
  rows: SearchRow[];
  suggestions: { symbol: string; name: string; holding: boolean | null }[];
  themes: {
    slug: string; name: string;
    members?: number; judged?: number; above_50ma?: number;
    participation_pct?: number | null;
  }[];
}) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  // "/" jumps to the box, the way every terminal-ish tool does. Ignored while
  // the caret is already in a field, or the shortcut would eat the character.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "/" || event.metaKey || event.ctrlKey || event.altKey) return;
      const active = document.activeElement;
      const tag = active?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA"
          || (active as HTMLElement | null)?.isContentEditable) return;
      event.preventDefault();
      input.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

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
      <div style={{ position: "relative" }}>
        <input
          ref={input}
          className="control"
          style={{
            width: "100%", background: "var(--surface-2)",
            justifyContent: "flex-start", fontSize: "var(--size-lead)",
            minHeight: 52, paddingRight: 44,
            // A ring rather than a colour change, so the box does not move and
            // nothing else on the row reflows when it lights up.
            boxShadow: focused ? "0 0 0 2px var(--brand-muted)" : undefined,
            borderColor: focused ? "var(--brand-ink)" : undefined,
            transition: "box-shadow 120ms ease, border-color 120ms ease",
          }}
          placeholder="Ticker, company or industry"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          aria-label="Search"
          autoComplete="off"
        />
        {/* The hint is for a keyboard, so it hides the moment there is typing
            and never appears where there is no keyboard to press it on. */}
        {!query && (
          <span
            aria-hidden
            className="hide-on-touch caption dim mono"
            style={{
              position: "absolute", right: 12, top: "50%",
              transform: "translateY(-50%)", pointerEvents: "none",
              border: "1px solid var(--border-strong)", borderRadius: 4,
              padding: "1px 5px", opacity: focused ? 0 : 0.8,
              transition: "opacity 120ms ease",
            }}
          >
            /
          </span>
        )}
      </div>

      {!query && (
        <>
          <section>
            <div className="eyebrow">Recent breakouts</div>
            <div className="row wrap" style={{ gap: "var(--gap-xs)" }}>
              {suggestions.map((row) => (
                <TickerLink
                  key={row.symbol}
                  symbol={row.symbol}
                  className="badge badge--ticker"
                  style={row.holding === null ? undefined : {
                    borderColor: row.holding ? "var(--gain)" : "var(--warn)",
                  }}
                  title={row.holding === null ? undefined
                    : row.holding ? "still above the level it cleared"
                    : "back below the level it cleared"}
                >
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
                      style={{ justifyContent: "flex-start", gap: "var(--gap-sm)" }}>
                  <span className="grow" style={{ minWidth: 0 }}>{theme.name}</span>
                  {theme.members ? (
                    <span className="caption dim num" style={{ flexShrink: 0, opacity: 0.6 }}>
                      {theme.members}
                    </span>
                  ) : null}
                  <Participation pct={theme.participation_pct ?? null} />
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
          /* The row is a div, not one big TickerLink, because the star is a
             button and a button inside a button is invalid markup -- the tap
             would have opened the drawer instead of saving the ticker. The
             link covers the text; the star sits beside it. */
          <div key={row.symbol} className="card between"
               style={{ padding: "var(--pad-md) var(--pad-lg)", width: "100%",
                        gap: "var(--gap-sm)" }}>
            <TickerLink symbol={row.symbol} className="grow"
                        style={{ minWidth: 0, display: "block" }}>
              <span className="mono" style={{ color: "var(--link)" }}>{row.symbol}</span>{" "}
              <span>{row.name}</span>
              <span className="caption dim"> · {row.industry}</span>
            </TickerLink>
            <span className="row" style={{ gap: "var(--gap-sm)", flexShrink: 0 }}>
              <Sparkline points={row.spark} changePct={row.spark_change_pct} />
              <PriceChange value={row.spark_change_pct} className="footnote" />
              <span className="num dim">{rsText(row.rs_rating)}</span>
              <WatchStar symbol={row.symbol} />
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** How much of a theme is holding above its own 50-day line.
 *
 * Deliberately faint. It is a coarse reading — a count of names over one
 * average — and drawing it at full strength beside the theme's own name would
 * give it more authority than a count of that kind deserves.
 */
function Participation({ pct }: { pct: number | null }) {
  if (pct === null) return null;
  return (
    <span
      aria-hidden
      title={`${pct.toFixed(0)}% above their 50-day line`}
      style={{
        width: 26, height: 3, borderRadius: "var(--radius-pill)", flexShrink: 0,
        background: "var(--border-stronger)", overflow: "hidden", display: "block",
      }}
    >
      <span style={{
        display: "block", height: "100%", width: `${Math.min(Math.max(pct, 0), 100)}%`,
        background: "var(--gain)", opacity: 0.7,
      }} />
    </span>
  );
}
