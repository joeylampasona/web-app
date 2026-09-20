"use client";

import Link from "next/link";
import { useState } from "react";
import type { GammaBoardRow } from "@/lib/types";

const PREVIEW = 20;

/**
 * The names with the deepest option books, and where their gamma sits.
 *
 * Ranked by contracts outstanding rather than by the dollar gamma figure.
 * Dollar gamma scales with the square of the share price, so ranking on it
 * would sort the page by how expensive a stock is and put every high-priced
 * name on top whether or not anyone had traded its options. Open interest is
 * the thing that makes a book deep.
 *
 * The peak strike and its distance from spot are the reading. Everything else
 * is supporting detail, and the signed column is kept visually quieter than
 * the unsigned one for the reason set out in GammaPanel: one of them depends
 * on an assumption about who holds which side and the other does not.
 */
export function GammaBoard({ rows, total }: { rows: GammaBoardRow[]; total: number }) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? rows : rows.slice(0, PREVIEW);
  const hidden = rows.length - visible.length;
  const peak = Math.max(...rows.map((r) => r.peak_concentration), 1);

  return (
    <>
      <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
        {total.toLocaleString()} names carried usable open interest
        {total > rows.length && ` · showing the deepest ${rows.length}`}
      </p>

      <div className="scroll-x card" style={{ padding: 0, marginTop: "var(--gap-sm)" }}>
        <table className="data">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Contracts</th>
              <th>Peak strike</th>
              <th>vs spot</th>
              <th>Gamma there</th>
              <th>Net</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.symbol}>
                <td className="text">
                  <Link href={`/stocks/${row.symbol}`} className="mono">{row.symbol}</Link>
                  {row.stale && (
                    <span className="caption dim" title="Open interest is from the previous session">
                      {" "}·&nbsp;lagged
                    </span>
                  )}
                </td>
                <td className="num">{row.open_interest.toLocaleString()}</td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  {row.peak_strike.toFixed(2)}
                </td>
                <td className="num" style={{ whiteSpace: "nowrap" }}>
                  {row.peak_vs_spot_pct === null ? "—"
                    : `${row.peak_vs_spot_pct > 0 ? "+" : ""}${row.peak_vs_spot_pct.toFixed(1)}%`}
                </td>
                <td>
                  <span className="row" style={{ gap: "var(--gap-xs)", alignItems: "center",
                                                 justifyContent: "flex-end" }}>
                    <span
                      aria-hidden
                      style={{
                        width: 34, height: 4, borderRadius: "var(--radius-pill)",
                        background: "var(--border-stronger)", overflow: "hidden",
                        flexShrink: 0, display: "block",
                      }}
                    >
                      <span style={{
                        display: "block", height: "100%",
                        width: `${Math.max((row.peak_concentration / peak) * 100, 2)}%`,
                        background: "var(--screen-highs)", opacity: 0.85,
                      }} />
                    </span>
                    <span className="num caption">{compact(row.peak_concentration)}</span>
                  </span>
                </td>
                {/* Dimmer than the column beside it, on purpose: this one
                    rests on the dealer-positioning convention and that one
                    does not. */}
                <td className="num caption dim">{compact(row.total_net, true)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {hidden > 0 && (
        <button
          type="button"
          className="control footnote"
          onClick={() => setExpanded(true)}
          style={{ marginTop: "var(--gap-sm)" }}
        >
          Show {hidden} more
        </button>
      )}
    </>
  );
}

function compact(value: number, signed = false): string {
  const sign = signed && value > 0 ? "+" : value < 0 ? "−" : "";
  const n = Math.abs(value);
  if (n >= 1e9) return `${sign}$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `${sign}$${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${sign}$${(n / 1e3).toFixed(0)}K`;
  return `${sign}$${n.toFixed(0)}`;
}
