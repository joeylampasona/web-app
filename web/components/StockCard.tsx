"use client";

import { useCallback, useRef } from "react";
import type { Bar, Setup } from "@/lib/types";
import { copy } from "@/lib/copy";
import {
  change, decimal, longDate, price, ratio, rsText, shortDate, signed, tone, volume,
} from "@/lib/format";
import { EarningsBadge, FlagBadge, QuadrantBadge, StageBadge } from "./Badges";
import { MetricRow } from "./MetricRow";
import { PriceChange } from "./PriceChange";
import { SetupChart } from "./SetupChart";
import { ShareButton } from "./ShareButton";
import { TickerLink } from "./StockDrawer";
import { WatchStar } from "./WatchStar";

/**
 * Every surface on this site is a list of these. The metric rows swap on the
 * breakouts view; everything else is identical wherever the card appears.
 */
export function StockCard({
  setup, bars, variant = "setup",
}: {
  setup: Setup;
  bars?: Bar[];
  variant?: "setup" | "breakout";
}) {
  const ohlc = setup.ohlc;
  const rows = variant === "breakout" ? breakoutRows(setup) : setupRows(setup);

  // The chart hands its canvas up so Share can put the real thing in the image
  // rather than redrawing an approximation of it.
  const chartRef = useRef<(() => HTMLCanvasElement | null) | null>(null);
  const handleChartReady = useCallback(
    (screenshot: (() => HTMLCanvasElement | null) | null) => {
      chartRef.current = screenshot;
    }, []);

  return (
    <article className="card stack" style={{ gap: "var(--gap-md)" }}>
      <header className="between" style={{ alignItems: "flex-start" }}>
        <div className="grow">
          <div className="row">
            <TickerLink symbol={setup.symbol} style={{ fontWeight: 500 }}>
              {setup.name}
            </TickerLink>
            <WatchStar symbol={setup.symbol} />
          </div>
          <div className="num dim footnote">{setup.symbol}</div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div className="num" style={{ fontSize: "var(--size-lead)" }}>
            {price(setup.close)}
          </div>
          <PriceChange value={ohlc?.change_pct} />
        </div>
      </header>

      <div className="footnote num dim" style={{ lineHeight: 1.8 }}>
        {shortDate(ohlc?.date)}
        {"  "}O {decimal(ohlc?.open)}
        {"  "}H {decimal(ohlc?.high)}
        {"  "}L {decimal(ohlc?.low)}
        {"  "}C {decimal(ohlc?.close)}{" "}
        <PriceChange value={ohlc?.change_pct} />
        <br />
        Vol {volume(setup.volume)}
        {"   "}RS {rsText(setup.rs_rating)}
      </div>

      {bars && bars.length > 0 && (
        <SetupChart
          bars={bars}
          pivot={setup.pivot}
          contractions={setup.bases}
          breakoutDate={setup.breakout_date}
          flags={setup.flags}
          symbol={setup.symbol}
          onReady={handleChartReady}
        />
      )}

      <div>
        {rows.map((row) => (
          <MetricRow key={row.label} {...row} />
        ))}
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {setup.flags.map((flag) => (
          <FlagBadge key={flag} flag={flag} />
        ))}
        {setup.catalysts?.earnings_within_7d &&
          setup.catalysts.days_until_earnings !== null && (
            <EarningsBadge days={setup.catalysts.days_until_earnings} />
          )}
        <StageBadge stage={setup.stage} />
      </div>

      {setup.prior_breakout && (
        <div
          className="footnote"
          style={{
            border: "0.5px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "var(--pad-sm) var(--pad-md)",
            color: "var(--text-secondary)",
          }}
        >
          Previous breakout {setup.prior_breakout.reason}{" "}
          <span className={`num ${tone(setup.prior_breakout.outcome_pct)}`}>
            {change(setup.prior_breakout.outcome_pct)}
          </span>{" "}
          in {setup.prior_breakout.month}
        </div>
      )}

      <footer className="between">
        <ShareButton
          symbol={setup.symbol}
          name={setup.name}
          close={setup.close}
          changePct={ohlc?.change_pct ?? null}
          stage={setup.stage}
          rs={setup.rs_rating}
          rows={rows.map((row) => ({
            label: row.label, value: row.value, tone: row.tone,
          }))}
          getChart={() => chartRef.current?.() ?? null}
          text={`${setup.symbol} — ${setup.stage.replace("_", " ")}, pivot ${price(
            setup.pivot,
          )}, RS ${rsText(setup.rs_rating)}`}
        />
        <QuadrantBadge quadrant={setup.quadrant} />
      </footer>
    </article>
  );
}

function setupRows(setup: Setup) {
  return [
    { label: "RS rating", value: rsText(setup.rs_rating), help: copy("metric.rs_rating") },
    {
      label: "Now vs pivot (%)",
      value: signed(setup.now_vs_pivot_pct),
      help: copy("metric.now_vs_pivot"),
      tone: tone(setup.now_vs_pivot_pct),
    },
    {
      label: "Tightening (ATR ratio)",
      value: ratio(setup.tightening_atr_ratio),
      help: copy("metric.tightening"),
    },
    {
      label: "Volume dry-up",
      value: ratio(setup.volume_dryup_ratio),
      help: copy("metric.volume_dryup"),
    },
    {
      label: "Up/down volume, net",
      value: decimal(setup.up_down_volume_net),
      help: copy("metric.up_down_volume"),
      tone: tone(setup.up_down_volume_net),
    },
    {
      label: "From 52-week high",
      value: setup.from_52w_high_pct === null ? "—" : `${setup.from_52w_high_pct.toFixed(0)}%`,
      help: copy("metric.from_52w_high"),
    },
  ];
}

function breakoutRows(setup: Setup) {
  const m = setup.breakout_metrics ?? {};
  return [
    {
      label: "Breakout-day gain",
      value: signed(m.breakout_day_gain_pct ?? null),
      help: copy("metric.breakout_day_gain"),
      tone: tone(m.breakout_day_gain_pct ?? null),
    },
    {
      label: "1-day gain",
      value: signed(m.one_day_gain_pct ?? null),
      help: copy("metric.one_day_gain"),
      tone: tone(m.one_day_gain_pct ?? null),
    },
    {
      label: "Now vs pivot (%)",
      value: signed(setup.now_vs_pivot_pct),
      help: copy("metric.now_vs_pivot"),
      tone: tone(setup.now_vs_pivot_pct),
    },
    {
      label: "Breakout volume vs normal day",
      value: ratio(m.breakout_volume_multiple ?? null),
      help: copy("metric.breakout_volume"),
    },
    {
      label: "Breakout close in range",
      value: decimal(m.close_in_range ?? null),
      help: copy("metric.close_in_range"),
    },
    { label: "RS rating", value: rsText(setup.rs_rating), help: copy("metric.rs_rating") },
    {
      label: "Price vs 50-MA",
      value: signed(m.price_vs_50ma_pct ?? setup.price_vs_50ma_pct),
      help: copy("metric.price_vs_50ma"),
      tone: tone(m.price_vs_50ma_pct ?? setup.price_vs_50ma_pct),
    },
  ];
}
