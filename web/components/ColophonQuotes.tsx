"use client";

import { useQuotesMeta } from "@/lib/useQuotes";

/**
 * The colophon's row for the intraday prices.
 *
 * The one source the nightly cannot report on, because it is not part of the
 * nightly: a separate sweep through the session writes it, and its state is
 * whatever the last sweep left. So this row is read in the browser from the
 * same feed the pages use, and says when that sweep ran and how many names it
 * covered. Outside the session an idle feed is the ordinary state, not a
 * fault, and the row says "Idle" rather than borrowing a word that means
 * something went wrong.
 */
const NEW_YORK_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
});

const FEEDS: Record<string, string> = {
  "yahoo-delayed": "Yahoo",
  "cboe-delayed": "Cboe",
};

function feedName(source: string | null): string | null {
  if (!source || source === "none") return null;
  const names = source.split("+").map((part) => FEEDS[part] ?? part);
  return names.join(" and ");
}

export function ColophonQuotes({ asOf }: { asOf: string }) {
  const { fetchedAt, count, ready, source } = useQuotesMeta();

  let word = "Checking";
  let tone = "var(--border-strong)";
  let detail = "Asking the feed.";
  let covers = "—";

  if (ready) {
    const when = fetchedAt ? new Date(fetchedAt) : null;
    if (when && !Number.isNaN(when.getTime())) {
      const today = NEW_YORK_DAY.format(new Date());
      const day = NEW_YORK_DAY.format(when);
      const clock = when.toLocaleTimeString("en-US", {
        timeZone: "America/New_York", hour: "numeric", minute: "2-digit",
      });
      const feed = feedName(source);
      covers = when.toLocaleDateString("en-US", {
        timeZone: "America/New_York", month: "short", day: "numeric",
      });
      if (day === today) {
        word = "Fresh";
        tone = "var(--gain)";
      } else {
        word = "Idle";
      }
      detail = `Last sweep read ${count.toLocaleString("en-US")} names at ${clock} ET`
        + `${feed ? `, from ${feed}` : ""}. `
        + (day === today
          ? "Prices are delayed by fifteen to twenty minutes."
          : day >= asOf
            ? "No session has run since; the pages show the closing figures."
            : "");
    } else {
      word = "Idle";
      detail = "No sweep on file newer than the published close. "
        + "The pages show the closing figures.";
    }
  }

  return (
    <div className="colophon-row" role="row">
      <span role="cell" className="stack" style={{ gap: 2 }}>
        <span className="colophon-name">Intraday prices</span>
        <span className="caption dim">A delayed quote sweep, hourly through the session</span>
      </span>
      <span role="cell" className="colophon-status">
        <span className="colophon-swatch" aria-hidden style={{ background: tone }} />
        {word}
      </span>
      <span role="cell" className="footnote">{detail}</span>
      <span role="cell" className="num footnote" style={{ whiteSpace: "nowrap" }}>{covers}</span>
    </div>
  );
}
