"use client";

import { useState } from "react";
import { ProvisionalBadge } from "./Badges";
import { PriceChange } from "./PriceChange";
import { TickerLink } from "./StockDrawer";
import { rsText } from "@/lib/format";
import type { FollowThroughFile, FollowThroughScreen } from "@/lib/types";

/**
 * The screens say what is setting up. This says whether it worked.
 *
 * Written to be read by someone who might not like the answer. The failure
 * count sits beside the success count at the same size, in the same weight,
 * and the median is a median rather than an average so that one name up 300%
 * cannot carry the row.
 */
export function FollowThroughPanel({ file }: { file: FollowThroughFile }) {
  const screens = Object.values(file.screens);
  const [active, setActive] = useState(screens[0]?.screen ?? "vcp");
  const shown = file.screens[active] ?? screens[0];
  if (!shown) return null;

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        <ProvisionalBadge />
        <p className="footnote muted" style={{ margin: 0 }}>
          Every breakout each screen would have shown in the last{" "}
          {Math.round(file.window_days / 30)} months, and what the stock did after.
          Detected from prices the same way the backtest detects them, so these are
          the same events, not a second opinion.
        </p>
        <p className="caption dim" style={{ margin: 0 }}>
          Our data provider&rsquo;s free tier carries no delisted companies, so the
          names that failed hardest are missing entirely. Every figure below is
          flattered by that, and we cannot tell you by how much.
        </p>
      </div>

      <div className="row wrap" style={{ gap: "var(--gap-sm)" }}>
        {screens.map((s) => (
          <button
            key={s.screen}
            type="button"
            className="control footnote"
            style={{ borderRadius: "var(--radius-pill)" }}
            aria-pressed={s.screen === active}
            onClick={() => setActive(s.screen)}
          >
            {s.name}
          </button>
        ))}
      </div>

      <Summary row={shown} />

      <section className="stack" style={{ gap: "var(--gap-sm)" }}>
        <div className="eyebrow">Every one of them</div>
        {shown.breakouts.length === 0 && (
          <p className="muted footnote">
            No breakouts on this screen in the window. That is a reading, not a fault.
          </p>
        )}
        {shown.breakouts.map((b) => (
          <TickerLink
            key={`${b.symbol}-${b.breakout_date}`}
            symbol={b.symbol}
            className="card"
            style={{ padding: "var(--pad-md) var(--pad-lg)", width: "100%" }}
          >
            <div className="between">
              <span className="grow">
                <span className="mono">{b.symbol}</span>{" "}
                <span className="footnote">{b.name}</span>
              </span>
              <PriceChange value={b.now_pct} />
            </div>
            <div className="row wrap caption dim" style={{ gap: "var(--gap-sm)" }}>
              <span>broke out {b.breakout_date}</span>
              <span>· {b.sessions_since} sessions</span>
              <span>· peak <span className="num">{b.peak_pct > 0 ? "+" : ""}{b.peak_pct}%</span></span>
              <span>· RS then {rsText(b.rs_at_breakout ?? "not ranked yet")}</span>
              {b.failed_fast && <span className="badge">closed back under the pivot</span>}
              {b.now_below_pivot && <span className="badge">below the pivot now</span>}
            </div>
          </TickerLink>
        ))}
      </section>
    </div>
  );
}

function Summary({ row }: { row: FollowThroughScreen }) {
  if (!row.settled) {
    return (
      <div className="card muted footnote">
        Nothing on this screen has had long enough to judge yet
        {row.too_soon > 0 && ` — ${row.too_soon} broke out in the last fortnight`}.
      </div>
    );
  }
  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      <div className="grid-2">
        <Cell label="Broke out" value={String(row.settled)}
              note={row.too_soon ? `${row.too_soon} more too recent to judge` : undefined} />
        <Cell label="Above where they broke out" value={`${row.up}`}
              note={`${row.share_up_pct}% of them`} />
        <Cell label="Below it" value={`${row.down}`}
              note={`${(100 - (row.share_up_pct ?? 0)).toFixed(1)}% of them`} />
        <Cell label="Closed back under the pivot" value={`${row.failed_fast}`}
              note={`${row.share_failed_pct}% within a fortnight`} />
      </div>
      <div className="grid-2">
        <Cell label="Median return since" value={`${row.median_now_pct}%`} />
        <Cell label="Median best point" value={`${row.median_peak_pct}%`}
              note="the most it was ever up" />
      </div>
      <p className="caption dim" style={{ margin: 0 }}>
        Medians, not averages — one name up three hundred per cent should not be
        able to carry the rest.
      </p>
    </div>
  );
}

function Cell({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="card">
      <div className="footnote muted">{label}</div>
      <div className="num" style={{ fontSize: "var(--size-h2)" }}>{value}</div>
      {note && <div className="caption dim">{note}</div>}
    </div>
  );
}
