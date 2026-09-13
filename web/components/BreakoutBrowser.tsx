"use client";

import { useState } from "react";
import type { Bar, Setup } from "@/lib/types";
import { longDate } from "@/lib/format";
import { StockCard } from "./StockCard";

export function BreakoutBrowser({
  dates, initialDate, setups, bars,
}: {
  dates: string[];
  initialDate: string;
  setups: Setup[];
  bars: Record<string, Bar[]>;
}) {
  const [date, setDate] = useState(initialDate);
  const [rows, setRows] = useState(setups);
  const [barsByDate, setBars] = useState(bars);
  const [loading, setLoading] = useState(false);

  const pick = async (next: string) => {
    setDate(next);
    if (next === initialDate) {
      setRows(setups);
      setBars(bars);
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`/api/breakouts?date=${next}`);
      const payload = await response.json();
      setRows(payload.setups ?? []);
      setBars(payload.bars ?? {});
    } finally {
      setLoading(false);
    }
  };

  const sorted = [...rows].sort(
    (a, b) =>
      (b.breakout_metrics?.breakout_day_gain_pct ?? -Infinity) -
      (a.breakout_metrics?.breakout_day_gain_pct ?? -Infinity),
  );

  return (
    <>
      <label className="row footnote" style={{ gap: "var(--gap-sm)", marginBottom: "var(--gap-lg)" }}>
        <span className="dim">Session</span>
        <select
          className="control"
          value={date}
          onChange={(event) => pick(event.target.value)}
          style={{ background: "var(--surface-2)", minHeight: "var(--h-control)" }}
        >
          {dates.map((option) => (
            <option key={option} value={option}>{longDate(option)}</option>
          ))}
        </select>
        <span className="dim">sorted by breakout-day gain</span>
      </label>

      {loading && <p className="muted footnote">Loading…</p>}

      {!loading && sorted.length === 0 && (
        <div className="card muted footnote">
          Nothing cleared its pivot on this session. Quiet days are the common case.
        </div>
      )}

      <div className="grid-auto">
        {sorted.map((setup) => (
          <StockCard key={setup.symbol} setup={setup} bars={barsByDate[setup.symbol]}
                     variant="breakout" />
        ))}
      </div>
    </>
  );
}
