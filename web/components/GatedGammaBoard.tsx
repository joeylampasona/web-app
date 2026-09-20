"use client";

import { GammaBoard } from "@/components/GammaBoard";
import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { GammaBoardRow } from "@/lib/types";

type Board = { as_of: string; count: number; rows: GammaBoardRow[] };

/**
 * The gamma board, free sample or the whole thing.
 *
 * A subscriber renders from the gated document alone rather than from the
 * public rows with the private ones appended. The two files are written by the
 * same run tonight and by different runs the moment one of the two publishing
 * steps fails, and a board stitched from a fresh head and a stale tail would
 * be sorted wrongly with nothing on the page to show it.
 */
export function GatedGammaBoard({
  rows,
  total,
  gated,
}: {
  rows: GammaBoardRow[];
  total: number;
  gated: boolean;
}) {
  // A tree published before gamma moved behind the paywall holds the whole
  // board in the public file. Asking for a gated copy of it would be pointless
  // and locking rows that are already in the page would be theatre.
  const full = useGated<Board>(gated ? "market/gamma.json" : null);

  if (!gated) return <GammaBoard rows={rows} total={total} />;

  if (full.state === "ready" && full.data?.rows?.length) {
    // The larger of the two counts, not the gated file's. Both are meant to be
    // every name that returned usable open interest, but a document written by
    // an older nightly carries the length of the board instead — and taking it
    // on trust would tell a subscriber that 60 names qualified where a free
    // reader is correctly told 129. The public file cannot overstate it.
    return (
      <GammaBoard rows={full.data.rows}
                  total={Math.max(full.data.count ?? 0, total)} />
    );
  }

  return (
    <>
      <GammaBoard rows={rows} total={total} />
      {full.state === "loading" ? (
        <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
          Checking your subscription…
        </p>
      ) : (
        <div style={{ marginTop: "var(--gap-md)" }}>
          <Locked
            what="The rest of the board, with every strike for each name,"
            shown={rows.length}
            total={total}
          >
            {full.state === "error" && (
              <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
                The subscription check did not answer ({full.detail}). The rows
                below are the free sample either way.
              </p>
            )}
          </Locked>
        </div>
      )}
    </>
  );
}
