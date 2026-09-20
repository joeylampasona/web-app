"use client";

import { GammaPanel } from "@/components/GammaPanel";
import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { GammaProfile } from "@/lib/types";

/**
 * One stock's gamma, free sample or fetched.
 *
 * The same rule as the board, which is the point: the deepest few option books
 * are public in full and the rest are not, in both places gamma appears. A
 * version of this that left every stock page public while gating the board
 * would be no paywall at all — the board is a ranking of these pages, so a few
 * hundred fetches would rebuild it exactly.
 *
 * Three states, not two. A name with no options, a name whose gamma is behind
 * the wall, and a name whose gamma is on the page are different things to say,
 * and collapsing the first two would offer a subscription over companies that
 * have no option book to sell.
 */
export function GatedGammaPanel({
  symbol,
  gamma,
  locked,
}: {
  symbol: string;
  gamma: GammaProfile | null;
  locked: boolean;
}) {
  const fetched = useGated<GammaProfile>(
    locked ? `stocks/gamma/${symbol.toLowerCase()}.json` : null,
  );

  if (gamma) return <GammaPanel gamma={gamma} />;
  if (!locked) return <GammaPanel gamma={null} />;

  if (fetched.state === "ready" && fetched.data) {
    return <GammaPanel gamma={fetched.data} />;
  }

  if (fetched.state === "loading") {
    return <p className="caption dim">Checking your subscription…</p>;
  }

  return (
    <Locked what={`${symbol}'s option book, strike by strike,`}>
      {fetched.state === "error" && (
        <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
          The subscription check did not answer ({fetched.detail}).
        </p>
      )}
    </Locked>
  );
}
