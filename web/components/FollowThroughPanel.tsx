"use client";

import { useMemo, useState } from "react";
import { ProvisionalBadge } from "./Badges";
import { PriceChange } from "./PriceChange";
import { TickerLink } from "./StockDrawer";
import { rsText } from "@/lib/format";
import type { BreakoutOutcome, FollowThroughFile, FollowThroughScreen } from "@/lib/types";

/** The same control the screens use, over the columns this page actually has.
 *  Default is worst-first: the list exists to be checked, and a page that opens
 *  on its best result is doing the opposite of what it claims to. */
type SortKey = "now_pct" | "peak_pct" | "worst_pct" | "breakout_date"
  | "sessions_since" | "symbol";

const SORTS: { key: SortKey; label: string }[] = [
  { key: "now_pct", label: "Return since" },
  { key: "peak_pct", label: "Best point" },
  // The drawdown is published and was not shown anywhere. On a page whose whole
  // job is to say whether it worked, the worst point is the more useful half.
  { key: "worst_pct", label: "Worst point" },
  { key: "breakout_date", label: "Breakout date" },
  { key: "sessions_since", label: "Sessions since" },
  { key: "symbol", label: "Ticker" },
];

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
  const [sort, setSort] = useState<SortKey>("now_pct");
  const [descending, setDescending] = useState(false);
  const shown = file.screens[active] ?? screens[0];

  const ordered = useMemo(() => {
    const rows: BreakoutOutcome[] = shown?.breakouts ?? [];
    const value = (b: BreakoutOutcome): number | string => {
      if (sort === "symbol") return b.symbol;
      if (sort === "breakout_date") return b.breakout_date;
      return (b[sort] as number | null) ?? -Infinity;
    };
    return [...rows].sort((a, b) => {
      const left = value(a);
      const right = value(b);
      const cmp = typeof left === "string"
        ? String(left).localeCompare(String(right))
        : Number(left) - Number(right);
      return descending ? -cmp : cmp;
    });
  }, [descending, shown, sort]);

  if (!shown) return null;

  return (
    <div className="stack" style={{ gap: "var(--pad-lg)" }}>
      <div className="stack" style={{ gap: "var(--gap-sm)" }}>
        <ProvisionalBadge />
        <p className="footnote muted" style={{ margin: 0 }}>
          Every breakout each screen would have shown in the last{" "}
          {Math.round(file.window_days / 30)} months, and what the stock did after.
          Detected from prices by the same rules that put a name on a screen, so
          these are the same events, not a second opinion.
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
        <div className="between wrap" style={{ gap: "var(--gap-sm)" }}>
          <div className="eyebrow">Every one of them</div>
          <div className="row" style={{ gap: "var(--gap-sm)" }}>
            <label className="row footnote dim" style={{ gap: "var(--gap-xs)" }}>
              <span className="visually-hidden">Sort by</span>
              <select
                className="control"
                value={sort}
                onChange={(event) => setSort(event.target.value as SortKey)}
                style={{ background: "var(--surface-2)", minHeight: "var(--h-control)" }}
              >
                {SORTS.map((option) => (
                  <option key={option.key} value={option.key}>{option.label}</option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="control"
              onClick={() => setDescending((v) => !v)}
              aria-label={descending ? "Sort ascending" : "Sort descending"}
            >
              {descending ? "↓" : "↑"}
            </button>
          </div>
        </div>
        {ordered.length === 0 && (
          <p className="muted footnote">
            No breakouts on this screen in the window. That is a reading, not a fault.
          </p>
        )}
        {ordered.map((b) => (
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
            <Range worst={b.worst_pct} peak={b.peak_pct} now={b.now_pct} />
            <div className="row wrap caption dim" style={{ gap: "var(--gap-sm)" }}>
              <span>broke out {b.breakout_date}</span>
              <span>· {b.sessions_since} sessions</span>
              <span>· RS then {rsText(b.rs_at_breakout ?? "not ranked yet")}</span>
              {b.failed_fast && (
                <span className="badge" style={{
                  color: "var(--warn)", borderColor: "var(--warn-border)",
                  background: "var(--warn-bg)",
                }}>
                  closed back under the pivot
                </span>
              )}
              {b.now_below_pivot && (
                <span className="badge badge--loss">below the pivot now</span>
              )}
            </div>
          </TickerLink>
        ))}
      </section>
    </div>
  );
}

/** Where the breakouts landed, as one bar rather than two opposed cells.
 *
 * "76 above" and "97 below" in separate boxes are two numbers to hold in your
 * head and compare. As one track they are a proportion you read in a glance,
 * which is the actual question — did more of them work than not.
 *
 * Muted deliberately. This page exists to be read by somebody who might not
 * like the answer, and a bright green half would be the page arguing with
 * them.
 */
function Distribution({ row }: { row: FollowThroughScreen }) {
  const total = row.settled || 1;
  const upShare = (row.up / total) * 100;
  return (
    <div className="stack" style={{ gap: "var(--gap-xs)" }}>
      <div className="between caption">
        <span style={{ color: "var(--gain)" }}>
          <span className="num">{row.up}</span> above where they broke out
          <span className="dim"> · {upShare.toFixed(0)}%</span>
        </span>
        <span style={{ color: "var(--loss)", textAlign: "right" }}>
          <span className="num">{row.down}</span> below
          <span className="dim"> · {(100 - upShare).toFixed(0)}%</span>
        </span>
      </div>
      <div
        role="img"
        aria-label={`${row.up} of ${row.settled} above where they broke out`}
        style={{
          display: "flex",
          // NOT className="row": that sets align-items:center, and an empty
          // span in a centred flex row has no content so it collapsed to zero
          // height. The widths were right the whole time — 159px and 198px of
          // a 358px track — and the bar rendered as a flat grey line.
          alignItems: "stretch",
          height: 8, borderRadius: "var(--radius-pill)", overflow: "hidden",
          background: "var(--border-stronger)", gap: 1,
        }}
      >
        <span style={{ width: `${upShare}%`, height: "100%",
                       background: "var(--gain)", opacity: 0.75 }} />
        <span style={{ flexGrow: 1, height: "100%",
                       background: "var(--loss)", opacity: 0.6 }} />
      </div>
    </div>
  );
}

/** Worst, peak, and where it sits now — on one line.
 *
 * The three numbers were three separate figures in a row of text, and reading
 * them meant doing the arithmetic yourself: was -12% near the bottom of its
 * range or near the top? The track answers that without the reader computing
 * anything. The numbers stay, because the picture is not precise enough to
 * replace them.
 */
function Range({ worst, peak, now }: { worst: number; peak: number; now: number }) {
  const lo = Math.min(worst, peak, now);
  const hi = Math.max(worst, peak, now);
  const span = hi - lo || 1;
  const at = (v: number) => ((v - lo) / span) * 100;
  // Zero is the line that matters: above it the trade was up, below it down.
  const zero = lo <= 0 && hi >= 0 ? at(0) : null;

  return (
    <div className="stack" style={{ gap: 2, marginTop: 4 }}>
      <div style={{ position: "relative", height: 12 }}>
        <div style={{
          position: "absolute", top: 5, left: 0, right: 0, height: 2,
          background: "var(--border-stronger)", borderRadius: "var(--radius-pill)",
        }} />
        {zero !== null && (
          <div title="flat" style={{
            position: "absolute", top: 1, left: `${zero}%`, width: 1, height: 10,
            background: "var(--text-muted)",
          }} />
        )}
        <div title={`worst ${worst}%`} style={{
          position: "absolute", top: 3, left: `${at(worst)}%`, width: 2, height: 6,
          background: "var(--loss)", transform: "translateX(-1px)",
        }} />
        <div title={`peak ${peak}%`} style={{
          position: "absolute", top: 3, left: `${at(peak)}%`, width: 2, height: 6,
          background: "var(--gain)", transform: "translateX(-1px)",
        }} />
        <div title={`now ${now}%`} style={{
          position: "absolute", top: 2, left: `${at(now)}%`, width: 8, height: 8,
          borderRadius: "50%", background: "var(--brand)",
          border: "1.5px solid var(--surface-1)", transform: "translateX(-4px)",
        }} />
      </div>
      <div className="between caption dim">
        <span className="num">{worst > 0 ? "+" : ""}{worst}% worst</span>
        <span className="num">{peak > 0 ? "+" : ""}{peak}% peak</span>
      </div>
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
      <Distribution row={row} />
      <div className="grid-2">
        <Cell label="Broke out" value={String(row.settled)}
              note={row.too_soon ? `${row.too_soon} more too recent to judge` : undefined} />
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
