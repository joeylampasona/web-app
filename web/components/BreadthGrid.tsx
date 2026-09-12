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
