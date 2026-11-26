import { price, shortDate } from "@/lib/format";
import type { AnchoredVwap, LevelsSummary, ReclaimDetails } from "@/lib/types";
import type { ChartLevel } from "./SetupChart";

/**
 * Three plain facts about where a stock's price sits, beside the three-touch
 * levels: last week's high and low, how far it moves on an ordinary day, and
 * the average price paid since a day that mattered.
 *
 * None of them is a level in the sense the panel above uses the word. Last
 * week's range is two prices everyone looking at a weekly chart can see. The
 * day's range is a yardstick for the others: "2% above support" means little
 * until you know the stock moves 4% on a quiet day. And an anchored VWAP says
 * whether the average buyer since the report is up or down.
 *
 * The VWAPs are worked out from daily bars, one typical price a session
 * weighted by that session's volume, and the page says so beside them. A
 * VWAP from every trade would differ a little.
 */

/** Last week's high and low as lines for the chart's levels layer. */
export function weekLines(summary: LevelsSummary | null | undefined): ChartLevel[] {
  const week = summary?.prior_week;
  if (!week) return [];
  return [
    { price: week.high, touches: 0, side: "other", label: "wk high" },
    { price: week.low, touches: 0, side: "other", label: "wk low" },
  ];
}

function away(level: number, close: number): string {
  const pct = (level / close - 1) * 100;
  return `${pct > 0 ? "+" : ""}${pct.toFixed(1)}%`;
}

function WeekSide({ label, level, close }: { label: string; level: number; close: number }) {
  // Which side of it the close is on is the whole reading, so it is said in
  // words: a reader should not have to compare two numbers to learn that the
  // stock is under last week's low.
  const where = close > level ? "the close is above it" : close < level
    ? "the close is below it" : "the close is on it";
  return (
    <div className="card" style={{ padding: "var(--pad-sm) var(--pad-md)" }}>
      <div className="caption muted">{label}</div>
      <div className="num" style={{ fontSize: "var(--size-h3)" }}>{price(level)}</div>
      <div className="caption dim">{away(level, close)} · {where}</div>
    </div>
  );
}

const SHORT: Record<AnchoredVwap["anchor"], string> = {
  earnings: "the last report", breakout: "the breakout", year: "the year began",
};

/** One sentence for a line that has just been crossed, or null. */
function crossing(row: AnchoredVwap): string | null {
  if (!row.crossed) return null;
  const name = row.anchor === "earnings" ? "its earnings VWAP"
    : row.anchor === "breakout" ? "its breakout VWAP" : "its year-to-date VWAP";
  return row.crossed === "up"
    ? `Closed back above ${name} today.` : `Closed back below ${name} today.`;
}

export function PriceMarkers({ summary, avwap }: {
  summary: LevelsSummary | null | undefined;
  avwap: AnchoredVwap[] | null | undefined;
}) {
  const week = summary?.prior_week ?? null;
  const normal = summary?.atr_pct ?? null;
  const rows = avwap ?? [];
  if (!week && normal === null && rows.length === 0) return null;
  const close = summary?.close ?? null;
  const notes = rows.map(crossing).filter((line): line is string => line !== null);

  return (
    <div className="stack" style={{ gap: "var(--gap-sm)" }}>
      {week && close !== null && (
        <div className="grid-2">
          <WeekSide label="Last week's low" level={week.low} close={close} />
          <WeekSide label="Last week's high" level={week.high} close={close} />
        </div>
      )}
      {normal !== null && (
        <p className="footnote" style={{ margin: 0 }}>
          A normal day for this stock is about{" "}
          <span className="num">{normal.toFixed(1)}%</span>, top to bottom.
          <span className="dim">
            {" "}The average true range of the last 14 sessions against the
            close. A level nearer than that is inside one ordinary day.
          </span>
        </p>
      )}
      {rows.length > 0 && (
        <div className="stack" style={{ gap: "var(--gap-xs)" }}>
          <div className="caption muted">The average price paid, from daily bars</div>
          <div>
            {rows.map((row) => (
              <div key={row.anchor} className="metric-row">
                <span className="label">
                  Since {SHORT[row.anchor] ?? row.label}
                  <span className="dim"> · {shortDate(row.from)}</span>
                </span>
                <span className="value">
                  {price(row.value)}{" "}
                  <span style={{ color: row.above ? "var(--gain)" : "var(--loss)",
                                 fontWeight: 400 }}>
                    {row.vs_pct > 0 ? "+" : ""}{row.vs_pct.toFixed(1)}%
                  </span>
                </span>
              </div>
            ))}
          </div>
          {notes.map((line) => (
            <p key={line} className="footnote" style={{ margin: 0, fontWeight: 600 }}>{line}</p>
          ))}
          <p className="caption dim" style={{ margin: 0 }}>
            Each is a volume-weighted average of every session since that day,
            and the percentage is the close against it: above, and the average
            buyer since then is in profit. Worked out from daily bars, one
            price a session, not from every trade, so on the first few
            sessions after the day it can differ from a true VWAP.
          </p>
        </div>
      )}
    </div>
  );
}

/** The dashed line's entry in the chart's key. */
export function VwapKey({ row }: { row: AnchoredVwap }) {
  return (
    <div className="row caption" style={{ gap: 6, color: "var(--text-secondary)",
                                         alignItems: "baseline", flexWrap: "wrap" }}>
      <span aria-hidden style={{
        width: 16, height: 0, flexShrink: 0, alignSelf: "center",
        borderTop: "2px dashed var(--chart-avwap, var(--text-secondary))",
      }} />
      <span>
        <span className="num" style={{ color: "var(--text-primary)" }}>
          Earnings VWAP {price(row.value)}
        </span>
        <span className="dim">
          {" "}· the average price paid since the report on {shortDate(row.from)},
          from daily bars
        </span>
      </span>
    </div>
  );
}

/** What the reclaim screen found, in the rows a shape screen uses. */
export function ReclaimReadout({ reclaim }: { reclaim: ReclaimDetails | null | undefined }) {
  if (!reclaim) return null;
  const back = reclaim.reclaim_date === null ? "not yet"
    : reclaim.sessions_to_reclaim === 0 ? `${shortDate(reclaim.reclaim_date)}, the same session`
      : reclaim.sessions_to_reclaim === 1 ? `${shortDate(reclaim.reclaim_date)}, the next session`
        : `${shortDate(reclaim.reclaim_date)}, ${reclaim.sessions_to_reclaim} sessions later`;
  return (
    <div>
      <div className="metric-row">
        <span className="label">Level<span className="dim"> · the low of the week of {shortDate(reclaim.week_of)}</span></span>
        <span className="value">{price(reclaim.level)}</span>
      </div>
      <div className="metric-row">
        <span className="label">Went under it<span className="dim"> · {shortDate(reclaim.undercut_date)}</span></span>
        <span className="value">{price(reclaim.low)} <span className="dim" style={{ fontWeight: 400 }}>−{reclaim.undercut_pct.toFixed(1)}%</span></span>
      </div>
      <div className="metric-row">
        <span className="label">Closed back above</span>
        <span className="value">{back}</span>
      </div>
      <div className="metric-row">
        <span className="label">Wrong below<span className="dim"> · a close under the level ends it</span></span>
        <span className="value">{price(reclaim.level)}</span>
      </div>
    </div>
  );
}
