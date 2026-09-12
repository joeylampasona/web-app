"use client";

import type { Bar, BaseStructure } from "@/lib/types";

/**
 * Every base the stock has ever built, on one chart. A closing line rather than
 * candles: at this zoom the candles are noise and the point is the shape of the
 * bases, drawn with the same semantics as everywhere else.
 */
export function XRayChart({
  bars, bases, height = 220,
}: {
  bars: Bar[];
  bases: BaseStructure[];
  height?: number;
}) {
  if (bars.length < 2) return null;
  const width = 640;
  const closes = bars.map((b) => b.close);
  const high = Math.max(...bars.map((b) => b.high));
  const low = Math.min(...bars.map((b) => b.low));
  const span = high - low || 1;
  const index = new Map(bars.map((bar, i) => [bar.time, i]));

  const x = (i: number) => (i / (bars.length - 1)) * width;
  const y = (price: number) => height - ((price - low) / span) * (height - 12) - 6;

  const path = closes.map((close, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(close).toFixed(1)}`)
    .join(" ");

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height}
         preserveAspectRatio="none" role="img" aria-label="Every base this stock has built">
      {bases.map((base, position) => {
        const from = index.get(base.start);
        const to = index.get(base.end);
        if (from === undefined || to === undefined) return null;
        const current = position === bases.length - 1;
        return (
          <g key={`${base.start}-${base.end}`}>
            <rect
              x={x(from)}
              y={y(base.pivot)}
              width={Math.max(2, x(to) - x(from))}
              height={Math.max(2, y(base.low) - y(base.pivot))}
              fill={current ? "var(--chart-base-fill)" : "none"}
              stroke={current ? "var(--chart-base-line)" : "var(--chart-prior-base)"}
              strokeDasharray={current ? undefined : "3 3"}
              strokeWidth={current ? 1 : 0.75}
            />
            <text x={x(from) + 3} y={y(base.pivot) - 3} fontSize="9"
                  fill={current ? "var(--chart-base-line)" : "var(--chart-prior-base)"}
                  fontFamily="var(--font-mono)">
              {base.weeks.toFixed(0)}w · {base.depth_pct.toFixed(0)}%
            </text>
          </g>
        );
      })}
      <path d={path} fill="none" stroke="var(--text-secondary)" strokeWidth="1" />
    </svg>
  );
}
