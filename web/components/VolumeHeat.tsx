"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { PriceChange } from "./PriceChange";
import type { VolumeRow } from "@/lib/types";

const PREVIEW = 40;

/** Bands come from the published file so the page and the pipeline cannot
 *  disagree about what "heavy" means. These are only the colours for them. */
const BAND_COLOUR: Record<string, string> = {
  extreme: "var(--screen-classic)",
  heavy: "var(--screen-comeback)",
  elevated: "var(--screen-highs)",
  above: "var(--screen-contraction)",
  normal: "var(--text-muted)",
};

export function VolumeHeat({
  rows, total, bands,
}: {
  rows: VolumeRow[];
  total: number;
  bands: { key: string; min: number; label: string }[];
}) {
  const [expanded, setExpanded] = useState(false);
  const [band, setBand] = useState<string | null>(null);

  const bandOf = useMemo(() => (rvol: number) => {
    for (const b of bands) if (rvol >= b.min) return b.key;
    return "normal";
  }, [bands]);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const row of rows) {
      const key = bandOf(row.rvol);
      out[key] = (out[key] ?? 0) + 1;
    }
    return out;
  }, [rows, bandOf]);

  const filtered = band ? rows.filter((r) => bandOf(r.rvol) === band) : rows;
  const visible = expanded || band ? filtered : filtered.slice(0, PREVIEW);
  const hidden = filtered.length - visible.length;

  return (
    <>
      <div className="scroll-x" style={{ marginTop: "var(--gap-md)" }}>
        <div className="row" style={{ gap: "var(--gap-xs)", paddingBottom: 4 }}>
          <button type="button" className="control caption" aria-pressed={band === null}
                  onClick={() => setBand(null)} style={{ whiteSpace: "nowrap" }}>
            All
          </button>
          {bands.filter((b) => counts[b.key]).map((b) => (
            <button
              key={b.key}
              type="button"
              className="control caption"
              aria-pressed={band === b.key}
              onClick={() => setBand(band === b.key ? null : b.key)}
              style={{ whiteSpace: "nowrap" }}
            >
              <span aria-hidden style={{
                display: "inline-block", width: 7, height: 7, borderRadius: 2,
                background: BAND_COLOUR[b.key], marginRight: 5,
              }} />
              {b.label} <span className="dim num">{counts[b.key]}</span>
            </button>
          ))}
        </div>
      </div>

      <p className="caption dim">
        {total.toLocaleString()} names measured · showing the {rows.length} most active
      </p>

      <div className="scroll-x card" style={{ padding: 0 }}>
        <table className="data">
          <thead>
            <tr>
              <th>Ticker</th><th>Volume</th><th>Close</th><th>Change</th><th>Industry</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const key = bandOf(row.rvol);
              return (
                <tr key={row.symbol}>
                  <td className="text">
                    <Link href={`/stocks/${row.symbol}`} className="mono">{row.symbol}</Link>
                  </td>
                  <td>
                    <span className="row" style={{ gap: "var(--gap-xs)",
                                                   justifyContent: "flex-end",
                                                   alignItems: "center" }}>
                      <span aria-hidden style={{
                        width: 7, height: 7, borderRadius: 2, flexShrink: 0,
                        background: BAND_COLOUR[key],
                      }} />
                      <span className="num" style={{ whiteSpace: "nowrap" }}>
                        {row.rvol.toFixed(1)}&#215;
                      </span>
                    </span>
                  </td>
                  <td className="num">{row.close.toFixed(2)}</td>
                  {/* The change is what separates a heavy up day from a heavy
                      down one. Without it the volume column alone would read
                      as bullish, which it is not. */}
                  <td><PriceChange value={row.change_pct} digits={1} badge /></td>
                  <td className="text caption dim">{row.industry}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {hidden > 0 && (
        <button type="button" className="control footnote"
                onClick={() => setExpanded(true)} style={{ marginTop: "var(--gap-sm)" }}>
          Show {hidden} more
        </button>
      )}
    </>
  );
}
