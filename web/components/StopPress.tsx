"use client";

import Link from "next/link";
import { useQuotesMap, useQuotesMeta, type Quote } from "@/lib/useQuotes";
import { TickerLink } from "./StockDrawer";

/**
 * Stop press: names going through their pivot since the close.
 *
 * Everything else on the home page was set last night and is true as of the
 * close. This box is the one thing that was not: during the session it lists
 * the names on a screen whose delayed price is now above the pivot when the
 * published close was at or under it. That is the single question the nightly
 * cannot answer and the reason the quote sweep exists.
 *
 * It appears only when there is something to print. Outside the session, or
 * with quotes from an earlier day, or with nothing through its pivot, it
 * renders nothing: an empty box headed "Stop press" every evening would teach
 * a reader to skip it.
 *
 * Prices are delayed and the box says so, with the time they were read. A
 * cross here is a price above a level, on a delayed quote. It is not a close
 * above it and the nightly may not confirm it.
 */
export interface PivotCandidate {
  symbol: string;
  name: string;
  pivot: number;
  /** The published close, at or under the pivot. */
  close: number;
  screen: string;
  screenName: string;
}

const NEW_YORK_DAY = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit",
});
const SESSION_MINUTES = 390;      // 9:30 to 16:00 New York
const OPEN_MINUTE = 9 * 60 + 30;
const SHOWN = 8;

/**
 * Volume so far against where an ordinary day would be by now.
 *
 * `at` is New York wall time with no offset, so the clock is read straight
 * off the string rather than through a Date, which would apply the reader's
 * own timezone to it. Null in the first twenty minutes, when a share of the
 * session that small turns any opening print into a multiple of nothing.
 */
export function volumePace(quote: Quote): number | null {
  const { volume, avg_volume: average, at } = quote;
  if (!volume || !average || volume <= 0 || average <= 0 || !at) return null;
  const clock = /T(\d{2}):(\d{2})/.exec(at);
  if (!clock) return null;
  const minute = Number(clock[1]) * 60 + Number(clock[2]) - OPEN_MINUTE;
  const share = Math.min(1, minute / SESSION_MINUTES);
  if (!(share >= 20 / SESSION_MINUTES)) return null;
  return volume / average / share;
}

export function StopPress({ candidates }: { candidates: PivotCandidate[] }) {
  const quotes = useQuotesMap();
  const { fetchedAt, ready } = useQuotesMeta();
  if (!ready || !fetchedAt) return null;

  const swept = new Date(fetchedAt);
  if (Number.isNaN(swept.getTime())) return null;
  const today = NEW_YORK_DAY.format(new Date());
  // The sweep and each price must both belong to today's session. A file from
  // yesterday afternoon is yesterday's news, and a name that has not traded
  // today carries yesterday's last print under a fresh sweep time.
  if (NEW_YORK_DAY.format(swept) !== today) return null;

  const through = candidates
    .map((candidate) => {
      const quote = quotes[candidate.symbol];
      if (!quote || !quote.at || quote.at.slice(0, 10) !== today) return null;
      if (!(quote.last > candidate.pivot)) return null;
      return {
        ...candidate,
        last: quote.last,
        above: 100 * (quote.last / candidate.pivot - 1),
        pace: volumePace(quote),
      };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    // Heaviest trading first where the pace is known: a cross on twice the
    // usual volume is the reading, a cross on a quiet tape is a footnote.
    .sort((a, b) => (b.pace ?? 0) - (a.pace ?? 0) || b.above - a.above);

  if (through.length === 0) return null;

  const read = swept.toLocaleTimeString("en-US", {
    timeZone: "America/New_York", hour: "numeric", minute: "2-digit",
  });
  const shown = through.slice(0, SHOWN);

  return (
    <section className="stop-press" aria-label="Stop press">
      <div className="stop-press-head">
        <span className="stop-press-flag">Stop press</span>
        <span className="kicker">Delayed prices · read {read} ET</span>
      </div>
      <h2 className="stop-press-title">
        {through.length === 1
          ? "One name is through its pivot since the close"
          : `${through.length} names are through their pivots since the close`}
      </h2>
      <div className="stop-press-rows">
        {shown.map((row) => (
          <div key={row.symbol} className="stop-press-row">
            <span className="stop-press-name">
              <TickerLink symbol={row.symbol} className="mono stop-press-ticker">
                {row.symbol}
              </TickerLink>
              <span className="footnote stop-press-company">{row.name}</span>
            </span>
            <span className="num stop-press-figure" style={{ color: "var(--gain)" }}>
              ▲ +{row.above.toFixed(1)}%
              <span className="caption dim"> over {row.pivot.toFixed(2)}</span>
            </span>
            <span className="footnote stop-press-pace">
              {row.pace === null ? (
                <span className="dim">Volume pace not known</span>
              ) : (
                <>
                  <span className="num" style={{ fontWeight: 600 }}>{row.pace.toFixed(1)}×</span>{" "}
                  <span className="dim">the usual volume by now</span>
                </>
              )}
            </span>
            <Link href={`/screens/${row.screen}`} className="caption stop-press-screen">
              {row.screenName}
            </Link>
          </div>
        ))}
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        {through.length > shown.length && <>The {shown.length} trading heaviest are shown. </>}
        A price above a level on a quote fifteen to twenty minutes old. It is
        not a close above it; tonight&rsquo;s run decides that.{" "}
        <Link href="/market/breakouts" style={{ textDecoration: "underline" }}>
          Yesterday&rsquo;s confirmed breakouts
        </Link>
      </p>
    </section>
  );
}
