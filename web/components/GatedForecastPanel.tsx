"use client";

import { ForecastPanel } from "@/components/ForecastPanel";
import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { Forecast } from "@/lib/types";

/**
 * Analyst estimates, fetched or offered.
 *
 * The free half is the buy/hold/sell split. Not a price target, and not even
 * the consensus one — this panel's own argument is that a middle number
 * without its spread is a worse statement than no number, so showing exactly
 * that to everyone who has not paid would be publishing the thing the page
 * spends a paragraph warning against. The targets and the estimates arrive
 * together or not at all.
 *
 * A company nobody covers still says so, free. That is a fact about the
 * company rather than about what anyone has paid for, and answering it with an
 * offer would be selling an empty panel.
 */
export function GatedForecastPanel({
  symbol,
  forecast,
  locked,
}: {
  symbol: string;
  forecast: Forecast | null;
  locked: boolean;
}) {
  const fetched = useGated<Forecast>(
    locked ? `stocks/forecast/${symbol.toLowerCase()}.json` : null,
  );

  if (fetched.state === "ready" && fetched.data) {
    return <ForecastPanel forecast={fetched.data} />;
  }
  if (!locked) return <ForecastPanel forecast={forecast} />;

  return (
    <div className="stack" style={{ gap: "var(--gap-md)" }}>
      <ForecastPanel forecast={forecast} />
      {fetched.state === "loading" ? (
        <p className="caption dim" style={{ margin: 0 }}>
          Checking your subscription…
        </p>
      ) : (
        <Locked what={`The price targets and estimates for ${symbol}, with the spread,`}>
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
