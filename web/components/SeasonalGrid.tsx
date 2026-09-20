"use client";

import { useState } from "react";
import type { SeasonalSymbol } from "@/lib/types";

/**
 * Month by month, one row per year.
 *
 * The cell colour scales with the size of the move rather than only its sign,
 * so a +0.2% month and a +9% month are not the same green. The scale is per
 * symbol: a sector ETF's ordinary month is a different size from the
 * benchmark's, and a shared scale would wash one of them out.
 *
 * The summary row prints the average WITH the number of months behind it. With
 * three or four observations that count is not a footnote — it is most of what
 * the number means — so it sits in the cell rather than under the table.
 */
export function SeasonalGrid({ symbols }: { symbols: SeasonalSymbol[] }) {
  const [active, setActive] = useState(symbols[0]?.symbol ?? "");
  const grid = symbols.find((s) => s.symbol === active) ?? symbols[0];
  if (!grid) return null;

  const magnitudes = grid.years
    .flatMap((y) => y.months.map((m) => Math.abs(m.return_pct ?? 0)))
    .filter((v) => v > 0);
  const scale = magnitudes.length ? Math.max(...magnitudes) : 1;

  return (
    <>
      <div className="scroll-x" style={{ marginTop: "var(--gap-md)" }}>
        <div className="row" style={{ gap: "var(--gap-xs)", paddingBottom: 4 }}>
          {symbols.map((s) => (
            <button
              key={s.symbol}
              type="button"
              className="control caption mono"
              aria-pressed={s.symbol === active}
              onClick={() => setActive(s.symbol)}
              style={{ whiteSpace: "nowrap" }}
            >
              {s.symbol}
            </button>
          ))}
        </div>
      </div>

      <div className="scroll-x card" style={{ padding: 0, marginTop: "var(--gap-sm)" }}>
        <table className="data">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Year</th>
              {grid.months.map((label) => <th key={label}>{label}</th>)}
              <th>Year</th>
            </tr>
          </thead>
          <tbody>
            {grid.years.map((year) => (
              <tr key={year.year}>
                <td className="text num" style={{ whiteSpace: "nowrap" }}>
                  {year.year}
                  {year.partial && (
                    <span className="dim caption" title="History starts or ends inside this year">
                      {" "}part
                    </span>
                  )}
                </td>
                {year.months.map((cell) => (
                  <td key={cell.month} style={{
                    ...cellStyle(cell.return_pct, scale),
                    whiteSpace: "nowrap",
                  }}>
                    {cell.return_pct === null ? "—" : `${cell.return_pct.toFixed(1)}%`}
                  </td>
                ))}
                <td className="num" style={{
                  ...cellStyle(year.year_pct, scale * 3),
                  fontWeight: 500, whiteSpace: "nowrap",
                }}>
                  {year.year_pct === null ? "—" : `${year.year_pct.toFixed(1)}%`}
                </td>
              </tr>
            ))}
            <tr style={{ borderTop: "1px solid var(--border-stronger)" }}>
              <td className="text caption dim" style={{ whiteSpace: "nowrap" }}>
                Average
              </td>
              {grid.months.map((label, index) => {
                const t = grid.tally[String(index + 1)];
                return (
                  <td key={label} style={{ whiteSpace: "nowrap" }}>
                    <span className="stack" style={{ gap: 0, alignItems: "flex-end" }}>
                      <span className="num caption" style={{ color: toneOf(t?.avg_pct) }}>
                        {t?.avg_pct === null || t?.avg_pct === undefined
                          ? "—" : `${t.avg_pct.toFixed(1)}%`}
                      </span>
                      {/* The n, in the cell. An average of three Septembers and
                          an average of eighty look identical without it. */}
                      <span className="dim" style={{ fontSize: 10 }}>
                        {t?.up_rate === null || t?.up_rate === undefined
                          ? "" : `${t.up_rate.toFixed(0)}% up · n=${t.observations}`}
                      </span>
                    </span>
                  </td>
                );
              })}
              <td className="dim">—</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}

function toneOf(value: number | null | undefined): string {
  if (value === null || value === undefined) return "var(--text-muted)";
  return value >= 0 ? "var(--gain)" : "var(--loss)";
}

/** Alpha scales with the size of the move, capped so one outlier month does
 *  not flatten every other cell to nothing. */
function cellStyle(value: number | null | undefined, scale: number) {
  if (value === null || value === undefined) {
    return { color: "var(--text-muted)" };
  }
  const weight = Math.min(Math.abs(value) / (scale || 1), 1);
  const alpha = 0.08 + weight * 0.30;
  return {
    background: value >= 0
      ? `rgba(22, 163, 74, ${alpha.toFixed(3)})`
      : `rgba(220, 38, 38, ${alpha.toFixed(3)})`,
    color: "var(--text-primary)",
  };
}
