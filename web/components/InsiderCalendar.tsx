"use client";

import Link from "next/link";
import { useState } from "react";
import { longDate } from "@/lib/format";
import type { InsiderDay } from "@/lib/types";

const PREVIEW = 8;

/**
 * Open-market insider decisions, day by day.
 *
 * Buys and sells are not given the same weight, and that is deliberate rather
 * than a bias. An officer has many reasons to sell — tax, a house, diversifying
 * a position that is most of their net worth — and only one obvious reason to
 * buy. The module that reads these filings already separates decisions from
 * vesting mechanics for the same reason; this is the next step of the same
 * distinction, and the copy says so rather than letting the colour imply it.
 */
export function InsiderCalendar({ days }: { days: InsiderDay[] }) {
  const [open, setOpen] = useState<string | null>(days[0]?.date ?? null);
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? days : days.slice(0, PREVIEW);
  const hidden = days.length - visible.length;
  const peak = Math.max(
    ...days.map((d) => Math.max(d.buy_value, d.sell_value)), 1);

  return (
    <>
      <div className="stack" style={{ gap: "var(--gap-xs)", marginTop: "var(--gap-md)" }}>
        {visible.map((day) => {
          const isOpen = open === day.date;
          return (
            <div key={day.date} className="card" style={{ padding: 0 }}>
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : day.date)}
                aria-expanded={isOpen}
                className="stack"
                style={{
                  width: "100%", background: "none", border: "none",
                  padding: "var(--pad-md) var(--pad-lg)", gap: "var(--gap-xs)",
                  textAlign: "left", cursor: "pointer",
                }}
              >
                <span className="between" style={{ gap: "var(--gap-sm)" }}>
                  <span className="footnote">{longDate(day.date)}</span>
                  <span className="caption dim num">
                    {day.buys + day.sells} filing{day.buys + day.sells === 1 ? "" : "s"}
                  </span>
                </span>
                <span className="row" style={{ gap: "var(--gap-sm)", alignItems: "center" }}>
                  <Bar label="bought" value={day.buy_value} peak={peak}
                       count={day.buys} colour="var(--gain)" />
                  <Bar label="sold" value={day.sell_value} peak={peak}
                       count={day.sells} colour="var(--text-muted)" />
                </span>
              </button>

              {isOpen && (
                <div className="scroll-x" style={{ borderTop: "1px solid var(--border)" }}>
                  <table className="data">
                    <thead>
                      <tr><th>Ticker</th><th>Who</th><th>Side</th><th>Value</th></tr>
                    </thead>
                    <tbody>
                      {day.rows.map((row, index) => (
                        <tr key={`${row.symbol}-${row.owner}-${index}`}>
                          <td className="text">
                            <Link href={`/stocks/${row.symbol}`} className="mono">
                              {row.symbol}
                            </Link>
                          </td>
                          <td className="text caption">
                            {row.owner}
                            <span className="dim"> · {row.role}</span>
                          </td>
                          <td className="text">
                            <span className={row.code === "P" ? "badge badge--gain" : "badge"}>
                              {row.code === "P" ? "Bought" : "Sold"}
                            </span>
                          </td>
                          <td className="num" style={{ whiteSpace: "nowrap" }}>
                            {money(row.value)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {hidden > 0 && (
        <button type="button" className="control footnote"
                onClick={() => setExpanded(true)} style={{ marginTop: "var(--gap-sm)" }}>
          Show {hidden} more day{hidden === 1 ? "" : "s"}
        </button>
      )}
    </>
  );
}

function Bar({ label, value, peak, count, colour }: {
  label: string; value: number; peak: number; count: number; colour: string;
}) {
  if (!count) return null;
  return (
    <span className="row caption dim" style={{ gap: "var(--gap-xs)", alignItems: "center" }}>
      <span aria-hidden style={{
        width: 44, height: 4, borderRadius: "var(--radius-pill)",
        background: "var(--border-stronger)", overflow: "hidden", display: "block",
      }}>
        <span style={{
          display: "block", height: "100%", background: colour,
          width: `${Math.max((value / peak) * 100, 3)}%`,
        }} />
      </span>
      <span className="num">{money(value)}</span>
      <span>{label}</span>
    </span>
  );
}

function money(value: number | null): string {
  if (value === null || value === undefined) return "—";
  const n = Math.abs(value);
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}
