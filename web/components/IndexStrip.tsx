"use client";

import { PriceChange } from "@/components/PriceChange";
import { price } from "@/lib/format";
import { useQuote, useQuotesMeta } from "@/lib/useQuotes";
import type { IndexRow } from "@/lib/types";

/**
 * SPY and QQQ, with the delayed intraday price when there is one.
 *
 * These two numbers are the first thing anybody looks at to decide whether
 * this site is live, and they were read straight from the nightly file — so
 * they showed Friday's close all through Monday and the whole site read as
 * frozen, however often the quote sweep ran. The sweep did not even ask about
 * them: it only covered names on a screen.
 *
 * The 200-day line is recomputed rather than carried over. The nightly gives
 * the close and its distance from the 200-day average, which is enough to
 * recover the average itself and measure the live price against it. Showing an
 * intraday price beside a percentage derived from the close would be two
 * different moments presented as one reading.
 */
function movingAverage(row: IndexRow): number | null {
  if (row.vs_200_pct === null || !row.close) return null;
  const ratio = 1 + row.vs_200_pct / 100;
  return ratio > 0 ? row.close / ratio : null;
}

function IndexCell({ row }: { row: IndexRow }) {
  const quote = useQuote(row.symbol);
  const live = quote && quote.last > 0;

  const shown = live ? quote.last : row.close;
  const change = live ? quote.change_pct : row.change_pct;

  const ma = movingAverage(row);
  const vs200 = live && ma ? (shown / ma - 1) * 100 : row.vs_200_pct;
  const above = live && ma ? shown >= ma : row.above_200;

  return (
    <div className="stack" style={{ gap: 2 }}>
      <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-xs)" }}>
        <span className="mono caption" style={{ color: "var(--text-secondary)" }}>
          {row.symbol}
        </span>
        <PriceChange value={change} className="caption" />
      </div>
      <div className="num" style={{ fontSize: "var(--size-lead)", lineHeight: 1.2 }}>
        {price(shown)}
      </div>
      <div className="caption" style={{ color: "var(--text-muted)" }}>
        {above === null
          ? "200-day not available yet"
          : `${vs200 === null ? "" : `${Math.abs(vs200).toFixed(1)}% `}`
            + `${above ? "above" : "below"} its 200-day`}
      </div>
    </div>
  );
}

export function IndexStrip({ rows }: { rows: IndexRow[] }) {
  const { liveAt, liveSymbols, ready } = useQuotesMeta();
  if (rows.length === 0) return null;

  // The live reading, not the sweep's. These two symbols are fetched at
  // request time; dating them by when the scheduled sweep ran would put hours
  // on a number that is a minute old.
  const covered = rows.every((row) => liveSymbols.includes(row.symbol));
  const stamp = ready && liveAt && covered
    ? new Date(liveAt).toLocaleTimeString(undefined,
        { hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <>
      <div className="hero-strip">
        {rows.map((row) => <IndexCell key={row.symbol} row={row} />)}
      </div>
      {/* Said plainly, or not at all. A price with no time on it invites the
          reader to assume it is current, and on this site it often is not. */}
      <p className="caption" style={{ margin: 0, color: "var(--text-muted)" }}>
        {stamp
          ? `Delayed, read at ${stamp}.`
          : "The last settled close."}
      </p>
    </>
  );
}
