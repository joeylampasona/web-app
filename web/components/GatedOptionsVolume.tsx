"use client";

import { Locked } from "@/components/Locked";
import { OptionsVolume } from "@/components/OptionsVolume";
import { useGated } from "@/lib/useGated";
import type { OptionsVolume as Volume } from "@/lib/types";

/**
 * One stock's option volume, free sample or fetched.
 *
 * Gated exactly as gamma is, for the same reason: the board is a ranking of
 * these cards, so leaving every card public would hand out the board a fetch
 * at a time. The few names at the top of the ranking are public in both
 * places and the rest are in neither.
 *
 * A name whose chain was not read has no card at all; the stock page decides
 * that before this is rendered, so nothing here offers a subscription over a
 * company with nothing behind the wall.
 */
export function GatedOptionsVolume({
  symbol,
  volume,
  locked,
}: {
  symbol: string;
  volume: Volume | null;
  locked: boolean;
}) {
  const fetched = useGated<Volume>(
    locked && !volume ? `stocks/options_volume/${symbol.toLowerCase()}.json` : null,
  );

  if (volume) return <OptionsVolume volume={volume} />;
  if (!locked) return null;

  if (fetched.state === "ready" && fetched.data) {
    return <OptionsVolume volume={fetched.data} />;
  }

  if (fetched.state === "loading") {
    return <p className="caption dim">Checking your subscription…</p>;
  }

  return (
    <Locked what={`${symbol}'s option trading for the session, with its busiest contracts,`}>
      {fetched.state === "error" && (
        <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
          The subscription check did not answer ({fetched.detail}).
        </p>
      )}
    </Locked>
  );
}
