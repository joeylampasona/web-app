"use client";

import { Locked } from "@/components/Locked";
import { OptionsVolumeBoard } from "@/components/OptionsVolumeBoard";
import { useGated } from "@/lib/useGated";
import type { OptionsVolume } from "@/lib/types";

type Board = { as_of: string; count: number; board_rows?: number; rows: OptionsVolume[] };

/**
 * The option volume board, free sample or the whole thing.
 *
 * As with the gamma board, a subscriber renders from the gated document
 * alone rather than from the public rows with the private ones appended: the
 * two are written by one run on a good night and by two on a bad one, and a
 * ranking stitched from both would be out of order with nothing to show it.
 */
export function GatedOptionsVolumeBoard({
  rows, total, read, gated, boardRows,
}: {
  rows: OptionsVolume[];
  total: number;
  read?: number;
  gated: boolean;
  /** How many rows the whole board carries, which is what is being withheld. */
  boardRows?: number;
}) {
  const full = useGated<Board>(gated ? "market/options_volume.json" : null);

  if (!gated) return <OptionsVolumeBoard rows={rows} total={total} read={read} />;

  if (full.state === "ready" && full.data?.rows?.length) {
    return (
      <OptionsVolumeBoard rows={full.data.rows}
                          total={Math.max(full.data.count ?? 0, total)} read={read} />
    );
  }

  const withheld = Math.max(boardRows ?? 0, rows.length);

  return (
    <>
      <OptionsVolumeBoard rows={rows} total={total} read={read} />
      {withheld > rows.length && (full.state === "loading" ? (
        <p className="caption dim" style={{ marginTop: "var(--gap-md)" }}>
          Checking your subscription…
        </p>
      ) : (
        <div style={{ marginTop: "var(--gap-md)" }}>
          <Locked
            what="The rest of the board, with each name's busiest contracts,"
            shown={rows.length}
            total={withheld}
          >
            {full.state === "error" && (
              <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
                The subscription check did not answer ({full.detail}). The rows
                above are the free sample either way.
              </p>
            )}
          </Locked>
        </div>
      ))}
    </>
  );
}
