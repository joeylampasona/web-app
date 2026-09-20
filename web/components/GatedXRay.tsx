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
 * Gated whole, with no sample. The X-ray is a comparison between one company's
 * bases, so a version missing some of them is not a smaller reading — it is a
 * wrong one, and it would make the current base look more or less unusual than
 * it is.
 */
export function GatedXRay({
  symbol,
  bars,
  locked,
  bases,
}: {
  symbol: string;
  bars: Bar[];
  locked: boolean;
  /** Present only in a tree published before the X-ray moved behind the wall. */
  bases: unknown[];
}) {
  const fetched = useGated<unknown[]>(
    locked ? `stocks/xray/${symbol.toLowerCase()}.json` : null,
  );

  // An older tree still carries the bases. Asking for a gated copy would be
  // pointless, and hiding rows that are already in the page would be theatre.
  if (bases.length > 0) {
    return (
      <div className="card">
        <XRayChart bars={bars} bases={bases as never} />
      </div>
    );
  }

  if (!locked) {
    return (
      <p className="muted footnote">
        No completed base to compare this one with yet.
      </p>
    );
  }

  if (fetched.state === "ready" && fetched.data?.length) {
    return (
      <div className="card">
        <XRayChart bars={bars} bases={fetched.data as never} />
      </div>
    );
  }

  if (fetched.state === "loading") {
    return <p className="caption dim">Checking your subscription…</p>;
  }

  return (
    <Locked what={`Every base ${symbol} has built, on one chart,`}>
      {fetched.state === "error" && (
        <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
          The subscription check did not answer ({fetched.detail}).
        </p>
      )}
    </Locked>
  );
}
