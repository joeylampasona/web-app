import type { IndexRow } from "@/lib/types";
import { PriceChange } from "./PriceChange";
import { price } from "@/lib/format";

/**
 * The broad-market strip.
 *
 * Deliberately short. It exists to answer "where is the market" in one glance,
 * and the useful half of that answer is not the closing price -- it is whether
 * the thing is above its 200-day line, which is the filter that decides whether
 * a breakout is worth taking at all.
 *
 * VIX is not here and cannot be. It is an index, and the pipeline reads the
 * stocks market; VIXY and VXX track VIX futures, which decay and are a
 * different number. Showing one under a "VIX" label would be a lie that looked
 * like a feature.
 *
 * An index with under 200 sessions shows its price and says the 200-day is not
 * available yet, rather than printing a dash that reads as zero.
 */
export function HomeIndexes({ rows }: { rows: IndexRow[] }) {
  if (rows.length === 0) return null;

  return (
    <section className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="eyebrow">The market</div>
      <div className="grid-auto">
        {rows.map((row) => (
          <div key={row.symbol} className="card stack" style={{ gap: "var(--gap-xs)" }}>
            <div className="between" style={{ alignItems: "baseline", gap: "var(--gap-sm)" }}>
              <span className="mono" style={{ fontWeight: 500 }}>{row.symbol}</span>
              <PriceChange value={row.change_pct} />
            </div>
            <div className="num" style={{ fontSize: "var(--size-h3)", lineHeight: 1.2 }}>
              {price(row.close)}
            </div>
            <div className="caption dim">
              {row.above_200 === null
                ? `${row.sessions} sessions of history — not enough for a 200-day line`
                : `${row.vs_200_pct === null ? "" : `${Math.abs(row.vs_200_pct).toFixed(1)}% `}` +
                  `${row.above_200 ? "above" : "below"} its 200-day line`}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
