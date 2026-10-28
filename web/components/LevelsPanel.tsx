"use client";

import { useMemo } from "react";
import { type ChartLevel, SetupChart } from "./SetupChart";
import type { Bar, LevelsSummary, PriceLevel } from "@/lib/types";

/**
 * Support and resistance: prices this stock has turned at three or more times
 * in the last 120 sessions.
 *
 * Found from the chart alone -- pivot highs and lows clustered within about
 * three quarters of a percent, or half a day's average range -- by the same
 * method the Market Desk draws on its pick cards. It says where buyers and
 * sellers have shown up before. It does not say they will again, and it is
 * not an entry, a target or a stop.
 */
function money(v: number): string {
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function away(level: PriceLevel, close: number): string {
  const pct = (level.price / close - 1) * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function ago(n: number): string {
  if (n === 0) return "today";
  if (n === 1) return "yesterday";
  return `${n} sessions ago`;
}

function Side({ label, level, close, tone }: {
  label: string; level: PriceLevel | null; close: number; tone: string;
}) {
  return (
    <div className="card" style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
      <div className="caption muted">{label}</div>
      {level ? (
        <>
          <div className="num" style={{ fontSize: "var(--size-h3)", color: tone }}>
            {money(level.price)}
          </div>
          <div className="caption dim">
            {away(level, close)} · tested {level.touches}× · last {ago(level.sessions_ago)}
          </div>
        </>
      ) : (
        <div className="caption dim">None within the last 120 sessions</div>
      )}
    </div>
  );
}

export function LevelsPanel({ summary, bars, symbol }: {
  summary: LevelsSummary | null | undefined;
  bars: Bar[];
  symbol: string;
}) {
  const lines = useMemo<ChartLevel[]>(() => (summary?.levels ?? []).map((level) => ({
    price: level.price,
    touches: level.touches,
    side: level.price === summary?.support?.price ? "support"
      : level.price === summary?.resistance?.price ? "resistance" : "other",
  })), [summary]);

  if (!summary) return null;
  if (!summary.levels.length) {
    return (
      <p className="muted footnote" style={{ margin: 0 }}>
        No price has been tested three times in the last 120 sessions: it has
        not spent long enough in one range to form a level.
      </p>
    );
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="grid-2">
        <Side label="Support below" level={summary.support} close={summary.close}
              tone="var(--gain)" />
        <Side label="Resistance above" level={summary.resistance} close={summary.close}
              tone="var(--loss)" />
      </div>
      {bars.length > 0 && (
        <div className="card" style={{ padding: "var(--pad-md)" }}>
          <SetupChart bars={bars} pivot={null} contractions={[]} breakoutDate={null}
                      flags={[]} symbol={`${symbol}-levels`} height="responsive"
                      levels={lines} />
        </div>
      )}
      <p className="caption dim" style={{ margin: 0 }}>
        Prices this stock has turned at three or more times in the last
        120 sessions, with how many times. Where buyers and sellers showed up
        before, not a forecast, an entry or a stop.
      </p>
    </div>
  );
}
