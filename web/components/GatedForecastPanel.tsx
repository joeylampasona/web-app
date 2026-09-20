"use client";

import { ForecastPanel } from "@/components/ForecastPanel";
import { Locked } from "@/components/Locked";
import { useGated } from "@/lib/useGated";
import type { Forecast } from "@/lib/types";

/**
 * Analyst estimates, fetched or offered.
 *
 * No free sample here, unlike gamma and seasonals. There is no ranking to show
 * the top of — a forecast is a per-company fact, so any sample would be an
 * arbitrary list of companies whose page happens to be more useful than the
 * next one's, which is a worse thing to explain to a reader than "this section
 * is part of a subscription".
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

  if (forecast) return <ForecastPanel forecast={forecast} />;
  if (!locked) return <ForecastPanel forecast={null} />;

  if (fetched.state === "ready" && fetched.data) {
    return <ForecastPanel forecast={fetched.data} />;
  }

  if (fetched.state === "loading") {
    return <p className="caption dim">Checking your subscription…</p>;
  }

  return (
    <Locked what={`What analysts expect of ${symbol}, with the spread and the count,`}>
      {fetched.state === "error" && (
        <p className="caption" style={{ margin: 0, color: "var(--loss)" }}>
          The subscription check did not answer ({fetched.detail}).
        </p>
      )}
    </Locked>
  );
}
