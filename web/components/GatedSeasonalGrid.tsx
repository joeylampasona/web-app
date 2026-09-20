"use client";

import { Locked } from "@/components/Locked";
import { SeasonalGrid } from "@/components/SeasonalGrid";
import { useGated } from "@/lib/useGated";
import type { SeasonalSymbol } from "@/lib/types";

type File = { as_of: string; symbols: SeasonalSymbol[] };

/**
 * The seasonal grids: the benchmark, or all twelve.
 *
 * The benchmark's grid is the free one because it is the one everybody has
 * already seen somewhere — it shows what the page is without being what the
 * page is for. The reading here is the comparison between sectors, and that
 * needs the sectors.
 *
 * Whole grids on both sides of the line. This page's own footer argues that a
 * monthly return means little without the count of years behind it, so serving
 * a free tier a grid with the years trimmed would be publishing the thing it
 * spends a paragraph warning against.
 */
export function GatedSeasonalGrid({
  symbols,
  total,
  gated,
}: {
  symbols: SeasonalSymbol[];
  total: number;
  gated: boolean;
}) {
  const full = useGated<File>(gated ? "market/seasonals.json" : null);

  if (!gated) return <SeasonalGrid symbols={symbols} />;

  if (full.state === "ready" && full.data?.symbols?.length) {
    return <SeasonalGrid symbols={full.data.symbols} />;
  }

  return (
    <>
      <SeasonalGrid symbols={symbols} />
      {full.state === "loading" ? (
        <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
          Checking your subscription…
        </p>
      ) : (
        <div style={{ marginTop: "var(--gap-md)" }}>
          <Locked
            what="The sector grids, month by month and year by year,"
            shown={symbols.length}
            total={total}
          >
            {full.state === "error" && (
              <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
                The subscription check did not answer ({full.detail}).
              </p>
            )}
          </Locked>
        </div>
      )}
    </>
  );
}
