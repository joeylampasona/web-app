"use client";

import Link from "next/link";
import type { MarketHeadline } from "@/lib/types";
import { useLiveNews } from "@/lib/useLiveNews";
import { TickerLink } from "./StockDrawer";

/**
 * Recent headlines across the names the site follows.
 *
 * This is the only part of the home page that is somebody else's editorial
 * judgement rather than a number we computed, and it keeps the treatment the
 * stock pages already use: what was published, by whom, when, linking out.
 * Never the article body, never a summary of our own, and no ordering except
 * newest first -- which is the only ordering that is a fact rather than an
 * opinion about which story matters.
 *
 * The tickers are shown because they are how the article reached this list at
 * all, and they make it checkable: a headline filed against four names the
 * site follows is a different thing from one filed against one.
 */

const MAX = 6;

function ago(iso: string, now: number): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso.slice(0, 10);
  const mins = Math.max(0, Math.round((now - then) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(then).toISOString().slice(0, 10);
}

export function HomeNews({ articles: nightly }: { articles: MarketHeadline[] }) {
  // The nightly's headlines, with anything published since on top.
  const articles = useLiveNews(nightly ?? []) as MarketHeadline[];
  if (!articles?.length) return null;

  // One clock for the whole list. Calling Date.now() per row would let two
  // rows published in the same minute disagree about how long ago that was.
  const now = Date.now();
  // Reporting first. The feed is mostly wire releases and law-firm notices,
  // and six of those at the top of the home page read as spam. They stay one
  // tap away on the news page; this is a filter by kind, not a ranking.
  const written = articles.filter((a) => !a.kind || a.kind === "analysis");
  const shown = (written.length >= 3 ? written : articles).slice(0, MAX);

  return (
    <section className="stack" style={{ gap: "var(--gap-md)" }}>
      <div className="ruled-head">
        <h2>In the news</h2>
        <Link href="/market/news" className="footnote"
              style={{ textDecoration: "underline", whiteSpace: "nowrap" }}>
          All headlines
        </Link>
      </div>

      <div className="ruled-list">
        {shown.map((article) => (
          <article key={article.url} className="news-row">
            <span className="mono caption dim">{ago(article.published_at, now)}</span>
            <div className="stack" style={{ gap: 4, minWidth: 0 }}>
              <a
                href={article.url}
                target="_blank"
                rel="noopener noreferrer nofollow"
                style={{ fontWeight: 500 }}
              >
                {article.title}
              </a>
              <div className="row wrap caption dim" style={{ gap: "var(--gap-xs)", alignItems: "baseline" }}>
                <span>{article.publisher}</span>
                {article.tickers.slice(0, 4).map((ticker) => (
                  <TickerLink key={ticker} symbol={ticker} className="badge badge--ticker">
                    {ticker}
                  </TickerLink>
                ))}
                {article.tickers.length > 4 && <span>+{article.tickers.length - 4}</span>}
              </div>
            </div>
          </article>
        ))}
      </div>

      <p className="caption dim" style={{ margin: 0 }}>
        Reporting only here; releases and legal notices are on the news page.
        Links go to the publisher. We do not host, summarise or rank these, and a
        headline appearing here is not a view about the company.{" "}
        <Link href="/legal" style={{ textDecoration: "underline" }}>Disclaimer</Link>.
      </p>
    </section>
  );
}
