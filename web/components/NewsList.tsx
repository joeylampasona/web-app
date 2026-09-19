"use client";

import { useEffect, useMemo, useState } from "react";
import type { MarketHeadline } from "@/lib/types";
import { TickerLink } from "./StockDrawer";

/**
 * The full headline list, with a filter.
 *
 * The filter is over tickers and publishers rather than a free-text search of
 * the headlines: a search box over a dozen or so titles would mostly return
 * nothing and feel broken, while "show me what was written about this name" is
 * the question somebody actually arrives with.
 *
 * Grouped by day, because a reader scanning a week wants to know whether five
 * stories landed on one afternoon or were spread across it. That difference is
 * the whole signal in a headline list.
 *
 * Twenty at a time. All hundred at once is fifteen thousand pixels, about
 * seventeen phone screens, and a page that long reads as a wall rather than a
 * list. The rest are one tap away and the count says how many, so nobody has
 * to guess whether the scroll is nearly over.
 */

const PAGE = 20;

function dayKey(iso: string): string {
  return (iso || "").slice(0, 10);
}

function dayLabel(iso: string, now: number): string {
  const day = Date.parse(`${iso}T12:00:00Z`);
  if (Number.isNaN(day)) return iso;
  const days = Math.round((now - day) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return new Date(day).toLocaleDateString("en-US", {
    timeZone: "UTC", weekday: "long", day: "numeric", month: "short",
  });
}

function time(iso: string): string {
  const at = Date.parse(iso);
  if (Number.isNaN(at)) return "";
  return new Date(at).toLocaleTimeString("en-US", {
    hour: "numeric", minute: "2-digit",
  });
}

export function NewsList({ articles }: { articles: MarketHeadline[] }) {
  const [filter, setFilter] = useState("");
  const [limit, setLimit] = useState(PAGE);

  const now = useMemo(() => Date.now(), []);
  const needle = filter.trim().toUpperCase();

  const matched = useMemo(() => {
    if (!needle) return articles;
    return articles.filter((a) =>
      a.tickers.some((t) => t.includes(needle))
      || a.publisher.toUpperCase().includes(needle));
  }, [articles, needle]);

  // A new filter starts a new list. Carrying the old reveal across would show
  // sixty of one search and twenty of the next for no reason the reader can see.
  useEffect(() => { setLimit(PAGE); }, [needle]);

  const shown = matched.slice(0, limit);
  const remaining = matched.length - shown.length;

  const days = useMemo(() => {
    const out = new Map<string, MarketHeadline[]>();
    for (const article of shown) {
      const key = dayKey(article.published_at);
      const held = out.get(key);
      if (held) held.push(article);
      else out.set(key, [article]);
    }
    return [...out.entries()].sort((a, b) => b[0].localeCompare(a[0]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matched, limit]);

  if (articles.length === 0) {
    return (
      <p className="muted footnote">
        No headlines were published in the last run. The feed is fetched once a
        night with everything else, so this fills in after the next one.
      </p>
    );
  }

  return (
    <div className="stack" style={{ gap: "var(--gap-lg)" }}>
      <label className="stack" style={{ gap: "var(--gap-xs)" }}>
        <span className="footnote muted">Filter by ticker or publisher</span>
        <input
          className="control"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          placeholder="NVDA, Reuters…"
          style={{ width: "100%" }}
        />
      </label>

      {shown.length === 0 ? (
        <p className="muted footnote" style={{ margin: 0 }}>
          Nothing filed against <span className="mono">{filter.trim()}</span> in
          what was published. That is a gap in the feed, not a statement about
          the company.
        </p>
      ) : (
        days.map(([day, rows]) => (
          <section key={day} className="stack" style={{ gap: "var(--gap-sm)" }}>
            <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
              <div className="eyebrow" style={{ marginBottom: 0 }}>
                {dayLabel(day, now)}
              </div>
              <span className="caption dim" style={{ whiteSpace: "nowrap" }}>
                {rows.length} {rows.length === 1 ? "story" : "stories"}
              </span>
            </div>
            {rows.map((article) => (
              <article key={article.url} className="card stack"
                       style={{ gap: "var(--gap-xs)" }}>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer nofollow"
                  style={{ color: "var(--text-primary)" }}
                >
                  {article.title}
                </a>
                <div className="row wrap" style={{ gap: "var(--gap-xs)", alignItems: "baseline" }}>
                  {article.tickers.slice(0, 6).map((ticker) => (
                    <TickerLink key={ticker} symbol={ticker} className="badge">
                      {ticker}
                    </TickerLink>
                  ))}
                  {article.tickers.length > 6 && (
                    <span className="caption dim">+{article.tickers.length - 6}</span>
                  )}
                </div>
                <div className="caption dim">
                  {article.publisher}
                  {time(article.published_at) && ` · ${time(article.published_at)}`}
                </div>
              </article>
            ))}
          </section>
        ))
      )}

      {remaining > 0 && (
        <button
          type="button"
          className="control"
          onClick={() => setLimit((held) => held + PAGE)}
          style={{ width: "100%" }}
        >
          Show {Math.min(PAGE, remaining)} more
          <span className="dim">
            {" "}· {remaining} left
          </span>
        </button>
      )}
    </div>
  );
}
