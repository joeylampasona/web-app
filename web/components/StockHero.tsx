"use client";

import { price } from "@/lib/format";
import { useQuote } from "@/lib/useQuotes";
import type { Bar } from "@/lib/types";
import { PriceChange } from "./PriceChange";

/**
 * The price beside the name, and where it sits in its year's range.
 *
 * The price was only inside the chart card further down, so the top of a
 * stock's page named the company and never said what it cost. The delayed
 * quote is used during the session, as on the index strip, and the last
 * close otherwise; the caption says which.
 *
 * The range bar is the lowest low to the highest high of the last year, with
 * a mark at the price. A position, not a signal: near the top is where a
 * breakout happens and also where a stock is most extended.
 */
export function StockHero({ symbol, bars, range }: {
  symbol: string;
  bars: Bar[];
  range: { low: number; high: number; sessions: number } | null | undefined;
}) {
  const quote = useQuote(symbol);
  const last = bars.at(-1)?.close ?? null;
  const prior = bars.at(-2)?.close ?? null;
  const live = Boolean(quote && quote.last > 0);
  const shown = live ? quote!.last : last;
  const change = live ? quote!.change_pct
    : last != null && prior ? ((last / prior) - 1) * 100 : null;

  if (shown == null) return null;
  const span = range ? range.high - range.low : 0;
  const at = range && span > 0
    ? Math.min(100, Math.max(0, ((shown - range.low) / span) * 100)) : null;

  return (
    <div className="stock-hero">
      <div className="stack" style={{ gap: 0 }}>
        <div className="row" style={{ gap: "var(--gap-sm)", alignItems: "baseline" }}>
          <span className="num" style={{ fontSize: "var(--size-h2)", lineHeight: 1.1 }}>
            {price(shown)}
          </span>
          <PriceChange value={change} />
        </div>
        <span className="caption dim">{live ? "Delayed quote" : "Last close"}</span>
      </div>
      {range && at != null && (
        <div className="stack" style={{ gap: 4, minWidth: 0, flex: "1 1 200px", maxWidth: 320 }}>
          <div className="range-bar" role="img"
               aria-label={`${price(shown)}, ${Math.round(at)}% of the way from the ${range.sessions >= 250 ? "52-week" : `${range.sessions}-session`} low of ${price(range.low)} to the high of ${price(range.high)}`}>
            <span className="range-fill" style={{ width: `${at}%` }} />
            <span className="range-mark" style={{ left: `${at}%` }} />
          </div>
          <div className="between caption dim num">
            <span>{price(range.low)}</span>
            <span className="caption dim" style={{ fontFamily: "var(--font-sans)" }}>
              {range.sessions >= 250 ? "52-week range" : `${range.sessions}-session range`}
            </span>
            <span>{price(range.high)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
