"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { copy } from "@/lib/copy";
import { compactMoney, signed } from "@/lib/format";
import { Tooltip } from "./Tooltip";

interface Tile {
  slug: string; name: string; market_value: number; weight: number;
  rs_rating: number | null; rs_change_w1: number | null;
  rs_change_m1: number | null; rs_change_m3: number | null;
  fresh_breakouts: number; members: number; leaders: number;
}

const WINDOWS: { key: "w1" | "m1" | "m3"; label: string }[] = [
  { key: "w1", label: "1wk" },
  { key: "m1", label: "1mo" },
  { key: "m3", label: "3mo" },
];

/** Squarified-enough slice and dice: readable on a phone, no library. */
function layout(tiles: Tile[], width: number, height: number) {
  const total = tiles.reduce((sum, t) => sum + t.market_value, 0) || 1;
  const out: (Tile & { x: number; y: number; w: number; h: number })[] = [];
  let index = 0;
  let y = 0;
  let remaining = height;
  while (index < tiles.length) {
    const rowCount = Math.min(tiles.length - index, tiles.length <= 6 ? 2 : 3);
    const row = tiles.slice(index, index + rowCount);
    const rowValue = row.reduce((sum, t) => sum + t.market_value, 0);
    const rowHeight = Math.max(44, (rowValue / total) * height);
    const h = Math.min(rowHeight, remaining);
    let x = 0;
    for (const tile of row) {
      const w = (tile.market_value / (rowValue || 1)) * width;
      out.push({ ...tile, x, y, w, h });
      x += w;
    }
    y += h;
    remaining -= h;
    index += rowCount;
    if (remaining <= 0) break;
  }
  return out;
}

export function Treemap({ tiles }: { tiles: Tile[] }) {
  const [window_, setWindow] = useState<"w1" | "m1" | "m3">("m1");
  const top = useMemo(() => tiles.slice(0, 18), [tiles]);
  const placed = useMemo(() => layout(top, 100, 150), [top]);

  const colourFor = (tile: Tile) => {
    const delta = tile[`rs_change_${window_}`];
    if (delta === null) return "var(--surface-2)";
    if (delta > 0) return "var(--gain-muted)";
    if (delta < 0) return "var(--loss-muted)";
    return "var(--surface-2)";
  };

  return (
    <div className="stack">
      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        <span className="footnote muted grow row" style={{ gap: "var(--gap-xs)" }}>
          Coloured by RS change
          <Tooltip label="Colour" text={copy("treemap.colour")} />
          · sized by market value
          <Tooltip label="Size" text={copy("treemap.size")} />
        </span>
        <div className="row" style={{ gap: 0 }}>
          {WINDOWS.map((option, index) => (
            <button
              key={option.key}
              type="button"
              className="control footnote"
              aria-pressed={window_ === option.key}
              style={{
                borderRadius: index === 0
                  ? "var(--radius) 0 0 var(--radius)"
                  : index === WINDOWS.length - 1
                    ? "0 var(--radius) var(--radius) 0"
                    : 0,
                marginLeft: index ? -1 : 0,
              }}
              onClick={() => setWindow(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ position: "relative", width: "100%", aspectRatio: "2 / 3" }}>
        {placed.map((tile) => {
          const delta = tile[`rs_change_${window_}`];
          return (
            <Link
              key={tile.slug}
              href={`/industries/${tile.slug}`}
              style={{
                position: "absolute",
                left: `${tile.x}%`, top: `${(tile.y / 150) * 100}%`,
                width: `${tile.w}%`, height: `${(tile.h / 150) * 100}%`,
                padding: "var(--gap-xs)",
                border: "0.5px solid var(--border)",
                background: colourFor(tile),
                overflow: "hidden",
                display: "flex", flexDirection: "column", justifyContent: "space-between",
              }}
            >
              <span className="caption" style={{ lineHeight: 1.15 }}>{tile.name}</span>
              <span className="row caption" style={{ gap: "var(--gap-xs)" }}>
                <span className="num">{tile.rs_rating ?? "—"}</span>
                <span className="num dim">{signed(delta, 0, "")}</span>
                {tile.fresh_breakouts > 0 && (
                  <span className="num" style={{ color: "var(--gain)" }}>
                    +{tile.fresh_breakouts}
                  </span>
                )}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
