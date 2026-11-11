"use client";

import { useEffect, useMemo, useState } from "react";
import type { MarketHeadline } from "@/lib/types";
import { useLiveNews } from "@/lib/useLiveNews";
import { PublisherMark } from "./PublisherMark";
import { TickerLink } from "./StockDrawer";

/**
 * The full headline list, with a filter.
 *
 * The filter is over tickers and publishers rather than a free-text search of
 * the headlines: a search box over a dozen or so titles would mostly return
 * nothing and feel broken, while "show me what was written about this name" is
 * the question somebody actually arrives with.
 *
 * A ruled list, time in the left column, the way the home page sets its
 * headlines: a box round every story made a hundred equal boxes, and the
 * law-firm notices took as much room as the reporting. Those now fold into
 * one line per day.
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

/** A technical state on the ticker chip, as an edge rather than a fill.
 *
 *  The chip's colour already means "this is tappable" and nothing else on the
 *  site uses it for a reading, so the state goes on the border where it cannot
 *  be confused with that. Absent when the name is on no screen at all, which
 *  is most of them — an edge on every chip would be an edge on none. */
function statusEdge(status: string | null | undefined): React.CSSProperties {
  if (status === "setting_up") return { borderLeft: "2px solid var(--gain)" };
  if (status === "failing") return { borderLeft: "2px solid var(--loss)" };
  return {};
}

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

/**
 * A day's law-firm notices as one line that opens.
 *
 * They were given less room before, but still a card each, and on most days
 * they outnumber the reporting. They are not hidden: the line says how many
 * landed and against which names, which is the only information in them, and
 * opens to the notices themselves.
 */
function LegalFold({ rows }: { rows: MarketHeadline[] }) {
  if (!rows.length) return null;
  const tickers = [...new Set(rows.flatMap((a) => a.tickers))];
  return (
    <details className="news-fold">
      <summary className="news-row">
        <span className="mono caption dim">{rows.length}×</span>
        <span className="footnote" style={{ color: "var(--text-secondary)" }}>
          {rows.length === 1 ? "One law-firm notice" : `${rows.length} law-firm notices`}
          {tickers.length > 0 && (
            <span className="mono dim"> · {tickers.slice(0, 10).join(" ")}
              {tickers.length > 10 && ` +${tickers.length - 10}`}</span>
          )}
          <span className="dim"> · show</span>
        </span>
      </summary>
      <div className="stack news-fold-body" style={{ gap: 6 }}>
        {rows.map((article) => (
          <div key={article.url} className="caption">
            <a href={article.url} target="_blank" rel="noopener noreferrer nofollow"
               style={{ color: "var(--text-muted)" }}>
              {article.title}
            </a>
            <span className="dim"> · {article.publisher} · {time(article.published_at)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}

export function NewsList({ articles: nightly }: { articles: MarketHeadline[] }) {
  // The nightly's list, with anything the hourly run found since on top.
  const articles = useLiveNews(nightly) as MarketHeadline[];
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState<"all" | "analysis" | "release">("all");
  const [limit, setLimit] = useState(PAGE);

  const now = useMemo(() => Date.now(), []);
  const needle = filter.trim().toUpperCase();

  const matched = useMemo(() => {
    // "Market analysis" excludes the law-firm wires AND the company's own
    // scheduling releases: both are filings rather than reporting, and the
    // point of the tab is to leave only what somebody wrote about the company.
    let rows = articles;
    if (kind === "analysis") rows = rows.filter((a) => a.kind === "analysis");
    if (kind === "release") rows = rows.filter((a) => a.kind === "release");
    if (!needle) return rows;
    return rows.filter((a) =>
      a.tickers.some((t) => t.includes(needle))
      || a.publisher.toUpperCase().includes(needle));
  }, [articles, needle, kind]);

  const counts = useMemo(() => ({
    all: articles.length,
    analysis: articles.filter((a) => a.kind === "analysis").length,
    release: articles.filter((a) => a.kind === "release").length,
  }), [articles]);

  // A new filter starts a new list. Carrying the old reveal across would show
  // sixty of one search and twenty of the next for no reason the reader can see.
  useEffect(() => { setLimit(PAGE); }, [needle, kind]);

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

      <div className="scroll-x" style={{ marginTop: "calc(var(--gap-md) * -1)" }}>
        <div className="row" style={{ gap: "var(--gap-xs)", paddingBottom: 4 }}>
          {([["all", "All stories"], ["analysis", "Market analysis"],
             ["release", "Company releases"]] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className="control caption"
              aria-pressed={kind === key}
              onClick={() => setKind(key)}
              style={{ whiteSpace: "nowrap" }}
            >
              {label} <span className="dim num">{counts[key]}</span>
            </button>
          ))}
        </div>
      </div>

      {shown.length === 0 ? (
        <p className="muted footnote" style={{ margin: 0 }}>
          Nothing filed against <span className="mono">{filter.trim()}</span> in
          what was published. That is a gap in the feed, not a statement about
          the company.
        </p>
      ) : (
        days.map(([day, rows]) => (
          <section key={day} className="stack" style={{ gap: 0 }}>
            <div className="ruled-head">
              <h2>{dayLabel(day, now)}</h2>
              <span className="caption dim" style={{ whiteSpace: "nowrap" }}>
                {rows.filter((a) => a.kind !== "legal").length} written
                {rows.some((a) => a.kind === "legal")
                  && ` · ${rows.filter((a) => a.kind === "legal").length} legal`}
              </span>
            </div>
            <div className="ruled-list">
              {rows.filter((a) => a.kind !== "legal").map((article) => (
                <article key={article.url} className="news-row">
                  <span className="mono caption dim">{time(article.published_at)}</span>
                  <div className="stack" style={{ gap: 4, minWidth: 0 }}>
                    <a
                      href={article.url}
                      target="_blank"
                      rel="noopener noreferrer nofollow"
                      style={{
                        fontWeight: article.prominent ? 600 : 500,
                        color: article.kind === "release" ? "var(--text-secondary)" : undefined,
                      }}
                    >
                      {article.title}
                    </a>
                    <div className="row wrap caption dim" style={{ gap: "var(--gap-xs)", alignItems: "center" }}>
                      <PublisherMark publisher={article.publisher} />
                      <span>{article.publisher}</span>
                      {article.kind === "release" && <span className="badge">Company release</span>}
                      {article.tickers.slice(0, 6).map((ticker) => (
                        <TickerLink
                          key={ticker}
                          symbol={ticker}
                          className="badge badge--ticker"
                          style={statusEdge(article.status?.[ticker])}
                        >
                          {ticker}
                        </TickerLink>
                      ))}
                      {article.tickers.length > 6 && <span>+{article.tickers.length - 6}</span>}
                    </div>
                  </div>
                </article>
              ))}
              <LegalFold rows={rows.filter((a) => a.kind === "legal")} />
            </div>
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
