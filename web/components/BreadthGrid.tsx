"use client";

import { useState } from "react";
import { copy } from "@/lib/copy";
import { decimal, longDate } from "@/lib/format";
import type { BreadthCard } from "@/lib/types";
import { Tooltip } from "./Tooltip";
import { PriceChange } from "./PriceChange";

/**
 * The breadth figures, each with the line it sits on the end of.
 *
 * These were uniform cards: a number, a thin gauge, and a button that opened
 * the history. But a breadth reading means little without its direction, and
 * "36% in a confirmed uptrend" is a different fact on the way up from on the
 * way down. So the history is drawn on every figure, and the day-by-day table
 * is what the button opens.
 */
export function BreadthGrid({ cards, universe }: { cards: BreadthCard[]; universe: number }) {
  const [open, setOpen] = useState<string | null>(null);
  return (
    <div className="breadth-grid">
      {cards.map((card) => {
        const percent = card.unit === "percent";
        const delta = card.wow_delta ?? 0;
        const good = INVERTED.has(card.key) ? delta <= 0 : delta >= 0;
        return (
          <div key={card.key} className="breadth-cell">
            <div className="row" style={{ gap: "var(--gap-xs)" }}>
              <span className="label-caps grow" style={{ color: "var(--text-muted)" }}>{card.label}</span>
              <Tooltip label={card.label} text={copy(`breadth.${card.key}`) || card.note} />
            </div>
            <div className="between" style={{ alignItems: "flex-end", gap: "var(--gap-md)" }}>
              <div className="num breadth-figure">
                {percent ? <>{decimal(card.value, 1)}<span className="breadth-unit">%</span></> : card.value}
              </div>
              <div className="caption" style={{ textAlign: "right", paddingBottom: 4 }}>
                <PriceChange value={card.wow_delta} digits={percent ? 1 : 0} unit={percent ? "pts" : ""} />
                <div className="dim">on the week</div>
              </div>
            </div>
            <History card={card} tone={delta === 0 ? "flat" : good ? "gain" : "loss"} />
            <div className="between caption dim" style={{ gap: "var(--gap-sm)" }}>
              <span>{supporting(card, universe)}</span>
              <button type="button" className="breadth-days"
                      onClick={() => setOpen(open === card.key ? null : card.key)}
                      aria-expanded={open === card.key}>
                {open === card.key ? "Hide the days" : "Day by day"}
              </button>
            </div>
            {open === card.key && <Days card={card} />}
          </div>
        );
      })}
    </div>
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

/**
 * The published history as a line, the latest session marked.
 *
 * A percentage is drawn on its own range with the 50% line shown when the
 * range crosses it, since that is the level these readings are judged
 * against. The colour follows the week: green when the figure moved the
 * constructive way, which for the lows card means down.
 */
function History({ card, tone }: { card: BreadthCard; tone: "gain" | "loss" | "flat" }) {
  const values = card.series.map((point) => point.value);
  if (values.length < 2) return <div style={{ height: 56 }} />;
  const W = 300, H = 56, PADY = 6;
  const lo = Math.min(...values), hi = Math.max(...values);
  const span = hi - lo || 1;
  const x = (i: number) => (i / (values.length - 1)) * (W - 6) + 1;
  const y = (v: number) => H - PADY - ((v - lo) / span) * (H - PADY * 2);
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const colour = tone === "gain" ? "var(--gain)" : tone === "loss" ? "var(--loss)" : "var(--text-muted)";
  const last = values.length - 1;
  const first = card.series[0], latest = card.series[last];
  const show = (v: number) => (card.unit === "percent" ? `${decimal(v, 1)}%` : String(v));
  return (
    <div className="stack" style={{ gap: 2 }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" role="img"
           aria-label={`${card.label} from ${show(first.value)} on ${longDate(first.date)} to ${show(latest.value)} on ${longDate(latest.date)}; range ${show(lo)} to ${show(hi)}`}>
        {card.unit === "percent" && lo < 50 && hi > 50 && (
          <line x1="0" x2={W} y1={y(50)} y2={y(50)} stroke="var(--border-stronger)"
                strokeDasharray="3 3" vectorEffect="non-scaling-stroke" />
        )}
        <path d={`${line} L${x(last).toFixed(1)},${H} L${x(0).toFixed(1)},${H} Z`} fill={colour} opacity="0.1" />
        <path d={line} fill="none" stroke={colour} strokeWidth="1.75" vectorEffect="non-scaling-stroke"
              strokeLinejoin="round" />
        <rect x={x(last) - 2.5} y={y(values[last]) - 4} width="5" height="8" fill="var(--text-primary)" />
      </svg>
      <div className="between caption dim num">
        <span>{longDate(first.date)}</span>
        <span>range {show(lo)} to {show(hi)}</span>
      </div>
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

function Days({ card }: { card: BreadthCard }) {
  return (
    <table className="data">
      <tbody>
        {[...card.series].reverse().slice(0, 8).map((point) => (
          <tr key={point.date}>
            <td className="text caption dim">{longDate(point.date)}</td>
            <td>{card.unit === "percent" ? `${decimal(point.value, 1)}%` : point.value}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
