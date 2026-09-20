"use client";

import { Locked } from "@/components/Locked";
import { XRayChart } from "@/components/XRayChart";
import { useGated } from "@/lib/useGated";
import type { Bar } from "@/lib/types";

/**
 * Every base this stock has built — for subscribers.
 *
 * This section used to be behind an account gate, and that gate was decorative:
 * the component correctly refused to render for a signed-out reader while the
 * bases themselves sat in the same public JSON file, one fetch away, for
 * months. The fix is not a better component. It is that `base_history` is no
 * longer in the public file at all, and this asks the server for it.
 *
 * The most recent completed base is free, and the chart says which of how many
 * it is. A partial X-ray would be a wrong reading if it pretended to be whole —
 * it would make the current base look more or less unusual than it is — so the
 * count is the part that has to be on the page, not the rows.
 */
export function GatedXRay({
  symbol,
  bars,
  locked,
  bases,
  total,
}: {
  symbol: string;
  bars: Bar[];
  locked: boolean;
  /** The free sample: the most recent completed base. A tree published before
   *  the X-ray moved behind the wall carries all of them here instead. */
  bases: unknown[];
  /** How many completed bases there are altogether. */
  total: number;
}) {
  const fetched = useGated<unknown[]>(
    locked ? `stocks/xray/${symbol.toLowerCase()}.json` : null,
  );

  if (fetched.state === "ready" && fetched.data?.length) {
    return (
      <div className="card">
        <XRayChart bars={bars} bases={fetched.data as never} />
      </div>
    );
  }

  if (bases.length === 0) {
    return (
      <p className="muted footnote">
        No completed base to compare this one with yet.
      </p>
    );
  }

  const chart = (
    <div className="card">
      <XRayChart bars={bars} bases={bases as never} />
    </div>
  );

  // An older tree carries every base in this field, so there is nothing to
  // offer and nothing to withhold — hiding rows already on the page would be
  // theatre.
  if (!locked) return chart;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      {chart}
      <p className="caption dim" style={{ margin: 0 }}>
        The most recent of {total} completed base{total === 1 ? "" : "s"}.
      </p>
      {fetched.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>
          Checking your subscription…
        </p>
      ) : (
        <Locked
          what={`Every base ${symbol} has built, on one chart,`}
          shown={bases.length}
          total={total}
        >
          {fetched.state === "error" && (
            <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
              The subscription check did not answer ({fetched.detail}).
            </p>
          )}
        </Locked>
      )}
    </div>
  );
}
