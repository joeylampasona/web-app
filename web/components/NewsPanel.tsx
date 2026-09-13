import type { Headline } from "@/lib/types";

/**
 * Headlines, linked out, never reproduced.
 *
 * This is the only part of the site that is somebody else's editorial judgement
 * rather than a number we computed, and it is presented that way: what was
 * published, who published it, when — with no ranking, scoring or summary of
 * our own laid over the top. The headline is the link; the article belongs to
 * whoever wrote it.
 */
export function NewsPanel({ news }: { news: Headline[] }) {
  if (!news?.length) {
    return (
      <p className="muted footnote">
        No headlines for this company in the last couple of weeks.
      </p>
    );
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      {news.map((item) => (
        <a
          key={item.url}
          href={item.url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="card stack"
          style={{ gap: 2, padding: "var(--pad-md) var(--pad-lg)" }}
        >
          <span className="footnote">{item.title}</span>
          <span className="caption dim">
            {item.publisher} · {ago(item.published_at)}
          </span>
        </a>
      ))}
      <p className="caption dim" style={{ margin: 0 }}>
        Headlines link to the publisher. We do not host, summarise or rank them,
        and a headline appearing here is not a view about the company.
      </p>
    </div>
  );
}

/** "3 hours ago" reads better than a timestamp on something this recent. */
function ago(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return iso.slice(0, 10);
  const mins = Math.max(0, Math.round((Date.now() - then) / 60000));
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(then).toISOString().slice(0, 10);
}
