"use client";

import { useState } from "react";
import { copy } from "@/lib/copy";
import { decimal, longDate, signed } from "@/lib/format";
import type { BreadthCard } from "@/lib/types";
import { Tooltip } from "./Tooltip";
import { PriceChange } from "./PriceChange";

export function BreadthGrid({ cards, universe }: { cards: BreadthCard[]; universe: number }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <>
      <div className="grid-2">
        {cards.map((card) => (
          <div key={card.key} className="card stack" style={{ gap: "var(--gap-sm)" }}>
            <div className="row" style={{ gap: "var(--gap-xs)" }}>
              <span className="footnote muted grow">{card.label}</span>
              <Tooltip label={card.label} text={copy(`breadth.${card.key}`) || card.note} />
            </div>
            <div className="num" style={{ fontSize: "var(--size-h2)" }}>
              {card.unit === "percent" ? `${decimal(card.value, 1)}%` : card.value}
            </div>
            <BreadthBar card={card} />
            <div className="caption dim">{supporting(card, universe)}</div>
            <div className="caption">
              <span className="dim">week over week </span>
              <PriceChange value={card.wow_delta} digits={card.unit === "percent" ? 1 : 0}
                           unit={card.unit === "percent" ? "pts" : ""} />
            </div>
            <button
              type="button"
              className="control footnote"
              style={{ minHeight: 36, alignSelf: "flex-start" }}
              onClick={() => setOpen(open === card.key ? null : card.key)}
              aria-expanded={open === card.key}
            >
              Day by day ›
            </button>
            {open === card.key && <Sparkline card={card} />}
          </div>
        ))}
      </div>
    </>
  );
}

/* Cards where a HIGH reading is the weak one.
 *
 * Everything else here counts something constructive — names near their highs,
 * names above the 50-day — so more is better and the obvious "green over 50%"
 * holds. "Near 52-week lows" counts the opposite, and colouring it by the same
 * rule would paint a market with 80% of its names at yearly lows bright green.
 * The bar has to know which way each card points. */
const INVERTED = new Set(["near_52w_lows"]);

/** A gauge under the headline figure.
 *
 * Only for percentages: the count cards ("broke out today") have no denominator
 * on this card, so a bar would need a maximum invented for it.
 */
function BreadthBar({ card }: { card: BreadthCard }) {
  if (card.unit !== "percent") return null;
  const pct = Math.min(Math.max(card.value, 0), 100);
  const constructive = INVERTED.has(card.key) ? pct < 50 : pct >= 50;
  return (
    <div
      role="img"
      aria-label={`${decimal(card.value, 1)} percent`}
      style={{
        height: 5, borderRadius: "var(--radius-pill)",
        background: "var(--border-stronger)", overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${pct}%`, height: "100%", borderRadius: "var(--radius-pill)",
          background: constructive ? "var(--gain)" : "var(--warn)",
          opacity: 0.85,
        }}
      />
    </div>
  );
}

function supporting(card: BreadthCard, universe: number): string {
  const counts = card.counts;
  if (card.key === "up_today") {
    return `${counts.up} up · ${counts.down} down · ${counts.universe ?? universe} names`;
  }
  if (card.unit === "count") {
    return `${counts.yesterday ?? 0} yesterday · ${counts.five_session_total ?? 0} over 5 sessions`;
  }
  return `${counts.count ?? 0} of ${counts.universe ?? universe} names`;
}

function Sparkline({ card }: { card: BreadthCard }) {
  const values = card.series.map((point) => point.value);
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <svg viewBox={`0 0 ${card.series.length * 8} 40`} height={40} width="100%"
           preserveAspectRatio="none" aria-hidden>
        {card.series.map((point, index) => {
          const height = ((point.value - min) / span) * 34 + 2;
          return (
            <rect
              key={point.date}
              x={index * 8}
              y={38 - height}
              width={6}
              height={height}
              fill="var(--text-muted)"
              rx={1}
            />
          );
        })}
      </svg>
      <table className="data">
        <tbody>
          {[...card.series].reverse().slice(0, 6).map((point) => (
            <tr key={point.date}>
              <td className="text caption dim">{longDate(point.date)}</td>
              <td>{card.unit === "percent" ? `${decimal(point.value, 1)}%` : point.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
